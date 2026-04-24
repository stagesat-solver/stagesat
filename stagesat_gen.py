import z3
import argparse
import sys, os
import warnings
import pickle
import src.utils.verification as verification
from src.utils.sort import Sort
from src.parse import ExpressionGenerator, CodeTemplate, LinearULPTransform, LinearSquareTransform, VerifyGenerator

DEBUG = False


class CodeGenerator:
    """Main orchestrator for code generation from Z3 expressions."""

    def __init__(self):
        self.expr_generator = ExpressionGenerator()
        self.template = CodeTemplate()
        self.ulp_transform = LinearULPTransform()
        self.verify = VerifyGenerator()

    def generate_square(self, expr_z3):
        """Generate C code from Z3 expression with static matrix generation."""
        self.expr_generator.reset()
        self.square_transform = LinearSquareTransform()
        main_expr = self.expr_generator.generate(expr_z3)
        symbolTable = self.expr_generator.symbolTable
        if len(self.expr_generator.symbolTable) == 0:
            return self.expr_generator.symbolTable, self.template.get_empty_template()
        # Separate linear equality constraints from other constraints
        linear_eq_constraints = []
        other_constraint_vars = []
        for constraint_id, lhs_expr, rhs_expr, var_name in self.expr_generator.linear_eq_constraints:
            # Check if both sides are linear
            lhs_linear = self.expr_generator.is_linear(lhs_expr, symbolTable, self.expr_generator.cache)
            rhs_linear = self.expr_generator.is_linear(rhs_expr, symbolTable, self.expr_generator.cache)
            if lhs_linear and rhs_linear:
                linear_eq_constraints.append((constraint_id, lhs_expr, rhs_expr, var_name))
            else:
                other_constraint_vars.append(var_name)
        for constraint_id, var_name in self.expr_generator.other_constraints:
            other_constraint_vars.append(var_name)
        square_code = self.square_transform.square_projection_objective(linear_eq_constraints)
        objective_computation = ""
        # Only use projection if we successfully generated the matrix code (non-singular)
        if linear_eq_constraints and square_code:
            # Combine both objectives
            other_obj = " + ".join(other_constraint_vars) if other_constraint_vars else "0.0"
            # Only pass variables that appear in linear constraints
            objective_computation = f"""
    // Compute projection objective for linear equalities (squared distance)
    double obj_linear_eq = compute_projection_objective_square({", ".join(self.square_transform.get_var())});
    // Compute squared distance objective for other constraints
    double obj_others = {other_obj};
    // Combined objective
    double final_objective = obj_linear_eq + obj_others;"""
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
        rm_preamble = self.expr_generator.get_rounding_mode_preamble()
        rm_restore = self.expr_generator.get_rounding_mode_restore()
        if rm_preamble:
            x_body = rm_preamble + '\n  ' + x_body
        x_dim = len(symbolTable)
        x_expr = "final_objective" if (linear_eq_constraints and square_code) else verification.var_name(expr_z3)
        code = self.template.get_template() % {
            "matrix_functions": square_code,
            "var_declarations": "\n  ".join(var_declarations),
            "parse_formats": "".join(parse_formats),
            "var_refs": ", ".join(var_refs),
            "x_body": x_body,
            "objective_computation": objective_computation,
            "return_expr": x_expr,
            "x_dim": x_dim,
            "x_expr": x_expr,
            "rm_restore": rm_restore
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
            return self.expr_generator.symbolTable, self.template.get_empty_template()
        linear_eq_constraints = []
        other_constraint_vars = []
        d_code, f_code = self.ulp_transform.build_objective(self.expr_generator.linear_eq_constraints)
        for constraint in self.expr_generator.linear_eq_constraints:
            constraint_id, lhs_expr, rhs_expr, var_name = constraint
            # Check if both sides are linear
            lhs_linear = self.expr_generator.is_linear(lhs_expr, symbolTable, self.expr_generator.cache)
            rhs_linear = self.expr_generator.is_linear(rhs_expr, symbolTable, self.expr_generator.cache)
            if lhs_linear and rhs_linear and constraint not in self.ulp_transform.mix_constraints:
                linear_eq_constraints.append((lhs_expr, rhs_expr))
            else:
                other_constraint_vars.append(var_name)
        for constraint_id, var_name in self.expr_generator.other_constraints:
            other_constraint_vars.append(var_name)
        objective_computation = ""
        return_expr = main_expr
        if linear_eq_constraints:
            other_obj = " + ".join(other_constraint_vars) if other_constraint_vars else "0.0"
            obj_components = []
            objective_lines = ["    // Compute projection objective for linear equalities"]
            if self.ulp_transform.get_var():
                objective_lines.append(
                    f'    double obj_linear_eq = compute_projection_objective_ulp({", ".join(self.ulp_transform.get_var())});')
                obj_components.append("obj_linear_eq")
            if self.ulp_transform.get_var_32():
                objective_lines.append(
                    f'    double obj_linear_eq_f32 = compute_projection_objective_ulp_f32({", ".join(self.ulp_transform.get_var_32())});')
                obj_components.append("obj_linear_eq_f32")
            objective_lines.append(f'    // Compute squared distance objective for other constraints')
            objective_lines.append(f'    double obj_others = {other_obj};')
            obj_components.append("obj_others")
            combined = " + ".join(obj_components)
            objective_lines.append(f'    // Combined objective')
            objective_lines.append(f'    double final_objective = {combined};')
            objective_computation = "\n".join(objective_lines)
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
        rm_preamble = self.expr_generator.get_rounding_mode_preamble()
        rm_restore = self.expr_generator.get_rounding_mode_restore()
        if rm_preamble:
            x_body = rm_preamble + '\n  ' + x_body
        x_dim = len(symbolTable)
        x_expr = "final_objective" if linear_eq_constraints else verification.var_name(expr_z3)
        code = self.template.get_template_ulp() % {
            "ulp_projection": d_code,
            "ulp_f32_projection": f_code,
            "var_declarations": "\n  ".join(var_declarations),
            "parse_formats": "".join(parse_formats),
            "var_refs": ", ".join(var_refs),
            "x_body": x_body,
            "objective_computation": objective_computation,
            "return_expr": return_expr,
            "x_dim": x_dim,
            "x_expr": x_expr,
            "rm_restore": rm_restore
        }
        return symbolTable, code

def print_stagesat_info():
    """Print stagesat banner information."""
    try:
        logo = open('logo.txt', "r").read().strip('\n')
        print(logo)
    except:
        pass
    print()
    print("*" * 50)
    print("stagesat Version 03/30/2026 (OOP Refactored)")
    print("Contributors: Yuanzhuo Zhang and Zhoulai Fu")
    print("*" * 50)

def get_parser():
    """Create and return argument parser."""
    parser = argparse.ArgumentParser(prog='stagesat', allow_abbrev=False)
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
    parser.add_argument('--verify', action='store_true')
    return parser

if __name__ == "__main__":
    parser = get_parser()
    if len(sys.argv[1:]) == 0:
        print_stagesat_info()
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
        sys.stderr.write("[stagesat] The Z3 front-end crashes.\n")
        sys.exit(1)
    generator = CodeGenerator()
    if args.square:
        symbolTable, foo_dot_c = generator.generate_square(expr_z3)
    elif args.ulp:
        symbolTable, foo_dot_c = generator.generate_ulp(expr_z3)
    elif args.verify:
        symbolTable, foo_dot_c = generator.verify.gen(expr_z3)
    else:
        print("Error: Must specify either --square or --ulp or --verify", file=sys.stderr)
        sys.exit(1)
    args.smt2_file.close()
    os.makedirs("build", exist_ok=True)
    pickle.dump(symbolTable, open("build/foo.symbolTable", "wb"))
    print(foo_dot_c)