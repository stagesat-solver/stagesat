import z3
import argparse
import sys, os
import warnings
import pickle
import src.utils.verification as verification
from src.utils.sort import Sort
from src.parse import LinearConstraintExtractor, ExpressionGenerator, CodeTemplate, LinearULPTransform

DEBUG = False


class CodeGenerator:
    """Main orchestrator for code generation from Z3 expressions."""

    def __init__(self):
        self.expr_generator = ExpressionGenerator()
        self.template = CodeTemplate()
        self.ulp_transform = LinearULPTransform()

    def generate_square(self, expr_z3):
        """Generate C code from Z3 expression."""
        # Reset state
        self.expr_generator.reset()
        # Generate code
        main_expr = self.expr_generator.generate(expr_z3)
        symbolTable = self.expr_generator.symbolTable
        if len(self.expr_generator.symbolTable) == 0:
            return self.expr_generator.symbolTable, 'int main(){return 0;}'
        extractor = LinearConstraintExtractor(symbolTable)
        linear_eq_constraints = []
        other_constraint_vars = []
        for constraint_id, lhs_expr, rhs_expr, var_name in self.expr_generator.linear_eq_constraints:
            # Check if both sides are linear
            lhs_linear = self.expr_generator.is_linear(lhs_expr, symbolTable, self.expr_generator.cache)
            rhs_linear = self.expr_generator.is_linear(rhs_expr, symbolTable, self.expr_generator.cache)
            if lhs_linear and rhs_linear:
                linear_eq_constraints.append((lhs_expr, rhs_expr))
            else:
                other_constraint_vars.append(var_name)
        for constraint_id, var_name in self.expr_generator.other_constraints:
            other_constraint_vars.append(var_name)
        matrix_code = ""
        objective_computation = ""
        return_expr = main_expr
        if linear_eq_constraints:
            extractor.linear_eq_constraints = linear_eq_constraints
            A, b = extractor.build_matrices()
            if A is not None:
                # Pass extractor.linear_vars instead of symbolTable
                matrix_code = self._generate_matrix_code(A, b, extractor.linear_vars)
                # Generate combined objective
                # Combine both objectives
                other_obj = " + ".join(other_constraint_vars) if other_constraint_vars else "0.0"
                # Only pass linear_vars to projection function
                objective_computation = f"""
    // Compute projection objective for linear equalities
    double obj_linear_eq = compute_projection_objective({", ".join(extractor.linear_vars.keys())});
    // Compute squared distance objective for other constraints
    double obj_others = {other_obj};
    // Combined objective
    double final_objective = obj_linear_eq + obj_others;"""
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
        x_expr = "final_objective" if linear_eq_constraints else verification.var_name(expr_z3)
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

    def generate_ulp(self, expr_z3):
        """Generate C code from Z3 expression."""
        # Reset state
        self.expr_generator.reset()
        # Generate code
        main_expr = self.expr_generator.generate(expr_z3)
        symbolTable = self.expr_generator.symbolTable
        if len(self.expr_generator.symbolTable) == 0:
            return self.expr_generator.symbolTable, 'int main(){return 0;}'
        extractor = LinearConstraintExtractor(symbolTable)
        linear_eq_constraints = []
        other_constraint_vars = []
        ulp_code = self.ulp_transform.ulp_projection_objective(self.expr_generator.linear_eq_constraints)
        for constraint in self.expr_generator.linear_eq_constraints:
            constraint_id, lhs_expr, rhs_expr, var_name = constraint
            # Check if both sides are linear
            lhs_linear = self.expr_generator.is_linear(lhs_expr, symbolTable, self.expr_generator.cache)
            rhs_linear = self.expr_generator.is_linear(rhs_expr, symbolTable, self.expr_generator.cache)
            if lhs_linear and rhs_linear and constraint in self.ulp_transform.fp64_constraints:
                linear_eq_constraints.append((lhs_expr, rhs_expr))
            else:
                other_constraint_vars.append(var_name)
        for constraint_id, var_name in self.expr_generator.other_constraints:
            other_constraint_vars.append(var_name)
        objective_computation = ""
        return_expr = main_expr
        if linear_eq_constraints:
            other_obj = " + ".join(other_constraint_vars) if other_constraint_vars else "0.0"
            # Only pass linear_vars to projection function
            objective_computation = f"""
    // Compute projection objective for linear equalities
    double obj_linear_eq = compute_projection_objective_ulp({", ".join(self.ulp_transform.get_var())});
    // Compute squared distance objective for other constraints
    double obj_others = {other_obj};
    // Combined objective
    double final_objective = obj_linear_eq + obj_others;"""
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
        x_expr = "final_objective" if linear_eq_constraints else verification.var_name(expr_z3)
        code = self.template.get_template_ulp() % {
            "ulp_projection": ulp_code,
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

    # def generate_ulp(self, expr_z3):
    #     """Generate C code from Z3 expression."""
    #     # Reset state
    #     self.expr_generator.reset()
    #     # Generate code
    #     self.expr_generator.generate(expr_z3)
    #     if len(self.expr_generator.symbolTable) == 0:
    #         return self.expr_generator.symbolTable, 'int main(){return 0;}'
    #     # Build variable declarations
    #     var_declarations = []
    #     parse_formats = []
    #     var_refs = []
    #     for var_name, var_type in self.expr_generator.symbolTable.items():
    #         if var_type == Sort.Float32:
    #             var_declarations.append(f"float {var_name};")
    #             parse_formats.append("f")
    #             var_refs.append(f"&{var_name}")
    #         elif var_type == Sort.Float64:
    #             var_declarations.append(f"double {var_name};")
    #             parse_formats.append("d")
    #             var_refs.append(f"&{var_name}")
    #         else:
    #             raise NotImplementedError("Unknown types in SMT")
    #     x_expr = verification.var_name(expr_z3)
    #     x_body = '\n  '.join(self.expr_generator.result)
    #     x_dim = len(self.expr_generator.symbolTable)
    #     code = self.template.get_template_ulp() % {
    #         "var_declarations": "\n  ".join(var_declarations),
    #         "parse_formats": "".join(parse_formats),
    #         "var_refs": ", ".join(var_refs),
    #         "x_expr": x_expr,
    #         "x_dim": x_dim,
    #         "x_body": x_body
    #     }
    #     return self.expr_generator.symbolTable, code

    def _generate_matrix_code(self, A, b, linear_vars):
        """Generate C++ code for matrix operations using Eigen library.

        Args:
            A: Coefficient matrix (m x n)
            b: Constant vector (m x 1)
            linear_vars: OrderedDict of variables that appear in linear constraints
        """
        import numpy as np
        m, n = A.shape
        # Convert matrices to C++ Eigen initializers
        A_init = self._matrix_to_eigen_init(A)
        b_init = self._vector_to_eigen_init(b.flatten())
        code = f"""
    #include <Eigen/Dense>
    using namespace Eigen;

    // Projection-based objective for linear equality constraints
    // Formula: g(z) = ||A^T(AA^T)^(-1)(Az - b)||^2
    // A is {m}x{n}, b is {m}x1
    // Uses Eigen for numerically stable computation

    static double compute_projection_objective({", ".join([f"double {var}" for var in linear_vars.keys()])}) {{
        // Initialize constraint matrix A ({m} x {n})
        MatrixXd A_matrix({m}, {n});
        A_matrix << {A_init};
        // Initialize constraint vector b ({m} x 1)
        VectorXd b_matrix({m});
        b_matrix << {b_init};
        // Input vector z (only variables in linear constraints)
        VectorXd z_matrix({n});
        z_matrix << {", ".join([var for var in linear_vars.keys()])};
        // Step 1: Compute residual r = Az - b
        VectorXd residual = A_matrix * z_matrix - b_matrix;
        // Step 2: Solve (AA^T)x = residual for x using numerically stable solver
        // This is equivalent to x = (AA^T)^(-1) * residual
        MatrixXd AAT = A_matrix * A_matrix.transpose();
        VectorXd x_matrix = AAT.ldlt().solve(residual);
        // Step 3: Compute projection vector = A^T * x
        VectorXd proj_vec = A_matrix.transpose() * x_matrix;
        // Step 4: Return squared norm (distance-to-feasible-set objective)
        return proj_vec.squaredNorm();
    }}
    """
        return code

    def _matrix_to_eigen_init(self, matrix):
        """Convert numpy matrix to Eigen comma initializer format."""
        rows, cols = matrix.shape
        all_vals = []
        for i in range(rows):
            for j in range(cols):
                all_vals.append(f"{matrix[i, j]:.16e}")
        return ",\n        ".join(all_vals)

    def _vector_to_eigen_init(self, vector):
        """Convert numpy vector to Eigen comma initializer format."""
        vals_str = ",\n        ".join([f"{val:.16e}" for val in vector])
        return vals_str

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
    parser = argparse.ArgumentParser(prog='XSat', allow_abbrev=False)
    parser.add_argument('smt2_file', help='specify the smt2 file to analyze.',
                        type=argparse.FileType('r'))
    parser.add_argument('-v', '--version', action='version', version='%(prog) version 12/18/2015')
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
    parser.add_argument("--multi", help="multi-processing (default: false)",
                        default=False, action='store_true')
    parser.add_argument("--multiMessage", help="multi-processing message",
                        default=False, action='store_true')
    parser.add_argument("--suppressWarning", help="Suppress warnings",
                        default=False, action='store_true')
    parser.add_argument('--square', action='store_true')
    parser.add_argument('--ulp', action='store_true')
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
    if args.square:
        symbolTable, foo_dot_c = generator.generate_square(expr_z3)
    elif args.ulp:
        symbolTable, foo_dot_c = generator.generate_ulp(expr_z3)
    else:
        print("Error: Must specify either --square or --ulp", file=sys.stderr)
        sys.exit(1)
    args.smt2_file.close()
    os.makedirs("build", exist_ok=True)
    pickle.dump(symbolTable, open("build/foo.symbolTable", "wb"))
    print(foo_dot_c)