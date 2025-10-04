import z3
import argparse
import sys, os
import warnings
import pickle
import src.utils.verification as verification
from src.utils.sort import Sort
from src.parse import LinearConstraintExtractor, ExpressionGenerator, CodeTemplate, LinearityAnalyzer

DEBUG = False

class CodeGenerator:
    """Main orchestrator for code generation from Z3 expressions."""

    def __init__(self):
        self.linearity_analyzer = LinearityAnalyzer()
        self.expr_generator = ExpressionGenerator(self.linearity_analyzer)
        self.template = CodeTemplate()

    def generate(self, expr_z3):
        """Generate C code from Z3 expression."""
        # Reset state
        self.linearity_analyzer.reset()
        self.expr_generator.reset()
        # Generate code
        main_expr = self.expr_generator.generate(expr_z3)
        symbolTable = self.expr_generator.symbolTable
        if len(self.expr_generator.symbolTable) == 0:
            return self.expr_generator.symbolTable, 'int main(){return 0;}'
        extractor = LinearConstraintExtractor(symbolTable)
        linear_eq_constraints = []
        other_constraint_vars = []
        for constraint_id, lhs_expr, rhs_expr in self.expr_generator.linear_eq_constraints:
            # Check if both sides are linear
            lhs_linear = self.linearity_analyzer.is_linear(lhs_expr, symbolTable, self.expr_generator.cache)
            rhs_linear = self.linearity_analyzer.is_linear(rhs_expr, symbolTable, self.expr_generator.cache)
            if lhs_linear and rhs_linear:
                linear_eq_constraints.append((lhs_expr, rhs_expr))
            else:
                other_constraint_vars.append(verification.var_name_from_id(constraint_id))
        for constraint_id, var_name in self.expr_generator.other_constraints:
            other_constraint_vars.append(var_name)
        matrix_code = ""
        objective_computation = ""
        return_expr = main_expr
        if linear_eq_constraints:
            extractor.linear_eq_constraints = linear_eq_constraints
            A, b = extractor.build_matrices()
            if A is not None:
                matrix_code = self._generate_matrix_code(A, b, symbolTable)
                # Generate combined objective
                if other_constraint_vars:
                    # Combine both objectives
                    other_obj = " + ".join(other_constraint_vars) if other_constraint_vars else "0.0"
                    # TODO check the last variable, based on BAND and BOR generate the code, need to change
                    #  ExpressionGenerator!!!!!!!!!!!!!!!
                    objective_computation = f"""
// Compute projection objective for linear equalities
double obj_linear_eq = compute_projection_objective({", ".join(symbolTable.keys())});
// Compute squared distance objective for other constraints
double obj_others = {other_obj};
// Combined objective
double final_objective = obj_linear_eq + obj_others;"""
                    return_expr = "final_objective"
                else:
                    # Only projection objective
                    objective_computation = f"""
// Compute projection objective for linear equalities only
double final_objective = compute_projection_objective({", ".join(symbolTable.keys())});"""
                    return_expr = "final_objective"
            # Build variable declarations
        var_declarations = []
        parse_formats = []
        var_refs = []
        for var_name, var_type in symbolTable.items():
            if var_type == Sort.Float32:
                var_declarations.append(f"float {var_name};")
                parse_formats.append("f")
                var_refs.append(f"&{var_name}")
            elif var_type == Sort.Float64:
                var_declarations.append(f"double {var_name};")
                parse_formats.append("d")
                var_refs.append(f"&{var_name}")
            else:
                raise NotImplementedError("Unknown types in SMT")
        x_body = '\n  '.join(self.expr_generator.result)
        x_dim = len(symbolTable)
        x_expr = "final_objective"
        code = self.template.get_template() % {
            "matrix_functions": matrix_code,
            "var_declarations": "\n  ".join(var_declarations),
            "parse_formats": "".join(parse_formats),
            "var_refs": ", ".join(var_refs),
            "x_body": x_body,
            "objective_computation": objective_computation,
            "return_expr": return_expr,
            "x_dim": x_dim,
            "x_expr": x_expr,
        }
        return symbolTable, code

    def _generate_matrix_code(self, A, b, symbolTable):
        """Generate C code for matrix operations."""
        m, n = A.shape

        # Convert matrices to C arrays
        A_init = self._matrix_to_c_init(A)
        b_init = self._vector_to_c_init(b.flatten())

        code = f"""
// Matrix operations for projection-based objective
// A is {m}x{n}, b is {m}x1

static double compute_projection_objective({", ".join([f"double {var}" for var in symbolTable.keys()])}) {{
    // Matrix A
    static const double A[{m}][{n}] = {A_init};

    // Vector b
    static const double b[{m}] = {b_init};

    // Input vector z
    double z[{n}] = {{{", ".join([var for var in symbolTable.keys()])}}};

    // Compute Az - b
    double residual[{m}];
    for (int i = 0; i < {m}; i++) {{
        residual[i] = -b[i];
        for (int j = 0; j < {n}; j++) {{
            residual[i] += A[i][j] * z[j];
        }}
    }}

    // For now, use squared norm of residual
    // This is equivalent to the full projection formula when A has full row rank
    double obj = 0.0;
    for (int i = 0; i < {m}; i++) {{
        obj += residual[i] * residual[i];
    }}

    return obj;
}}
"""
        return code

    def _matrix_to_c_init(self, matrix):
        """Convert numpy matrix to C array initializer."""
        rows, cols = matrix.shape
        rows_str = []
        for i in range(rows):
            row_vals = ", ".join([f"{matrix[i, j]:.17e}" for j in range(cols)])
            rows_str.append(f"{{{row_vals}}}")
        return f"{{{', '.join(rows_str)}}}"

    def _vector_to_c_init(self, vector):
        """Convert numpy vector to C array initializer."""
        vals_str = ", ".join([f"{val:.17e}" for val in vector])
        return f"{{{vals_str}}}"

def print_xsat_info():
    """Print XSat banner information."""
    try:
        logo = open('logo.txt', "r").read().strip('\n')
        print(logo)
    except:
        pass
    print()
    print("*" * 50)
    print("XSat Version 04/04/2016 (OOP Refactored)")
    print("Contributors: Zhoulai Fu and Zhendong Su")
    print("*" * 50)

def get_parser():
    """Create and return argument parser."""
    parser = argparse.ArgumentParser(prog='XSat')
    parser.add_argument('smt2_file', help='specify the smt2 file to analyze.',
                        type=argparse.FileType('r'))
    parser.add_argument('-v', '--version', action='version', version='%(prog) version 12/18/2015')
    parser.add_argument('--niter', help='niter in basinhopping', action='store',
                        type=int, required=False, default=100)
    parser.add_argument('--nStartOver', help='startOver times', action='store',
                        type=int, required=False, default=2)
    parser.add_argument('--method', help='Local minimization procedure', default='powell',
                        choices=['powell', 'slsqp', 'cg', 'l-bfgs-b', 'cobyla', 'tnc',
                                 'bfgs', 'nelder-mead', 'noop_min'])
    parser.add_argument('--showTime', help='show the time-related info (default: false)',
                        action='store_true', default=False)
    parser.add_argument('--showResult', help='show the basinhopping output (default:false)',
                        action='store_true', default=False)
    parser.add_argument('--stepSize', help='parameter of basinhopping',
                        type=float, default=10.0)
    parser.add_argument('--stepSize_round2', help='parameter of basinhopping',
                        type=float, default=100.0)
    parser.add_argument('--verify', help='verify the model', action='store_true', default=False)
    parser.add_argument('--verify2', help='verify the model (method 2)',
                        action='store_true', default=False)
    parser.add_argument('--showModel', help='show the model as a var->value mapping',
                        action='store_true', default=False)
    parser.add_argument('--showSymbolTable', help='show the symbol table, var->type',
                        action='store_true', default=False)
    parser.add_argument('--showConstraint', help='show the constraint, using the Z3 frontend',
                        action='store_true', default=False)
    parser.add_argument('--showVariableNumber',
                        help='show variable number, using the Z3 frontend',
                        action='store_true', default=False)
    parser.add_argument('--command_compilation',
                        help='the command used to compile the generated foo.c to foo.so',
                        default='clang -O3 -fbracket-depth=2048 -fPIC')
    parser.add_argument('--startPoint', help='start point in a single dimension',
                        action='store', type=float, default=1.0)
    parser.add_argument("--multi", help="multi-processing (default: false)",
                        default=False, action='store_true')
    parser.add_argument("--multiMessage", help="multi-processing message",
                        default=False, action='store_true')
    parser.add_argument("--round2", help="activate round2 when unsat (default: false)",
                        default=False, action='store_true')
    parser.add_argument("--niter_round2", help="niter for round2", action='store',
                        type=int, required=False, default=100)
    parser.add_argument("--suppressWarning", help="Suppress warnings",
                        default=False, action='store_true')
    return parser

if __name__ == "__main__":
    parser = get_parser()
    if len(sys.argv[1:]) == 0:
        print_xsat_info()
        parser.print_help()
        parser.exit()
    args = parser.parse_args()
    if args.suppressWarning:
        warnings.filterwarnings("ignore")
    try:
        expr_z3_lis = z3.parse_smt2_string(args.smt2_file.read())
        expr_z3 = z3.And(expr_z3_lis)
        expr_z3 = z3.simplify(expr_z3, arith_lhs=False, hoist_cmul=False)
    except z3.Z3Exception as e:
        print(e)
        sys.stderr.write("[Xsat] The Z3 front-end crashes.\n")
        sys.exit(1)
    generator = CodeGenerator()
    symbolTable, foo_dot_c = generator.generate(expr_z3)
    args.smt2_file.close()
    os.makedirs("build", exist_ok=True)
    pickle.dump(symbolTable, open("build/foo.symbolTable", "wb"))
    print(foo_dot_c)