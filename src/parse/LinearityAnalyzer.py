import z3
import src.utils.z3_util as z3_util

class LinearityAnalyzer:
    """Analyzes Z3 expressions to determine if they are linear with respect to variables."""

    def __init__(self):
        self.linearity_info = {}  # Maps expr_id -> (is_linear, expr_str)

    def reset(self):
        """Reset the analyzer state."""
        self.linearity_info = {}

    def is_linear(self, expr_z3, symbolTable, cache):
        """
        Determine if an expression is linear with respect to input variables.

        Linear expressions:
        - Variables (input variables)
        - Constants
        - Addition/subtraction of linear expressions
        - Multiplication/division by constants

        Non-linear expressions:
        - Multiplication of two non-constant expressions
        - Division by a non-constant expression
        """
        expr_id = expr_z3.get_id()
        if expr_id in self.linearity_info:
            return self.linearity_info[expr_id][0]
        # Variables are linear
        if z3_util.is_variable(expr_z3):
            self.linearity_info[expr_id] = (True, "VAR")
            return True
        # Constants are linear
        if z3_util.is_value(expr_z3):
            self.linearity_info[expr_id] = (True, "CONST")
            return True
        sort_z3 = expr_z3.decl().kind()
        # Addition/Subtraction
        if z3_util.is_fpAdd(expr_z3) and expr_z3.num_args() >= 3:
            lhs_linear = self.is_linear(expr_z3.arg(1), symbolTable, cache)
            rhs_linear = self.is_linear(expr_z3.arg(2), symbolTable, cache)
            is_linear = lhs_linear and rhs_linear
            self.linearity_info[expr_id] = (is_linear, "ADD")
            return is_linear
        if sort_z3 == z3.Z3_OP_FPA_SUB and expr_z3.num_args() >= 3:
            lhs_linear = self.is_linear(expr_z3.arg(1), symbolTable, cache)
            rhs_linear = self.is_linear(expr_z3.arg(2), symbolTable, cache)
            is_linear = lhs_linear and rhs_linear
            self.linearity_info[expr_id] = (is_linear, "SUB")
            return is_linear
        # Multiplication
        if z3_util.is_fpMul(expr_z3) and expr_z3.num_args() >= 3:
            lhs = expr_z3.arg(1)
            rhs = expr_z3.arg(2)
            lhs_is_const = z3_util.is_value(lhs)
            rhs_is_const = z3_util.is_value(rhs)
            lhs_linear = self.is_linear(lhs, symbolTable, cache)
            rhs_linear = self.is_linear(rhs, symbolTable, cache)
            is_linear = (lhs_is_const and rhs_linear) or (rhs_is_const and lhs_linear)
            self.linearity_info[expr_id] = (is_linear, f"MUL(const={lhs_is_const or rhs_is_const})")
            return is_linear
        # Division
        if z3_util.is_fpDiv(expr_z3) and expr_z3.num_args() >= 3:
            lhs = expr_z3.arg(1)
            rhs = expr_z3.arg(2)
            rhs_is_const = z3_util.is_value(rhs)
            lhs_linear = self.is_linear(lhs, symbolTable, cache)
            is_linear = rhs_is_const and lhs_linear
            self.linearity_info[expr_id] = (is_linear, f"DIV(divisor_const={rhs_is_const})")
            return is_linear
        # Comparisons
        if sort_z3 in [z3.Z3_OP_FPA_LE, z3.Z3_OP_FPA_LT, z3.Z3_OP_FPA_GE, z3.Z3_OP_FPA_GT]:
            lhs_linear = self.is_linear(expr_z3.arg(0), symbolTable, cache)
            rhs_linear = self.is_linear(expr_z3.arg(1), symbolTable, cache)
            is_constraint_linear = lhs_linear and rhs_linear
            self.linearity_info[expr_id] = (is_constraint_linear,
                                            f"CMP_LE/LT/GE/GT(lhs={lhs_linear},rhs={rhs_linear})")
            return is_constraint_linear
        if z3_util.is_eq(expr_z3):
            lhs_linear = self.is_linear(expr_z3.arg(0), symbolTable, cache)
            rhs_linear = self.is_linear(expr_z3.arg(1), symbolTable, cache)
            is_constraint_linear = lhs_linear and rhs_linear
            self.linearity_info[expr_id] = (is_constraint_linear,
                                            f"EQ(lhs={lhs_linear},rhs={rhs_linear})")
            return is_constraint_linear
        # AND/OR operations
        if z3.is_and(expr_z3) or z3.is_or(expr_z3):
            all_linear = True
            for i in range(expr_z3.num_args()):
                arg_linear = self.is_linear(expr_z3.arg(i), symbolTable, cache)
                all_linear = all_linear and arg_linear
            op_name = "AND" if z3.is_and(expr_z3) else "OR"
            self.linearity_info[expr_id] = (all_linear, f"{op_name}(all_linear={all_linear})")
            return all_linear
        # NOT operations
        if z3.is_not(expr_z3) and expr_z3.num_args() >= 1:
            is_linear = self.is_linear(expr_z3.arg(0), symbolTable, cache)
            self.linearity_info[expr_id] = (is_linear, "NOT")
            return is_linear
        if z3_util.is_fpNeg(expr_z3):
            is_linear = self.is_linear(expr_z3.arg(0), symbolTable, cache)
            self.linearity_info[expr_id] = (is_linear, "fpNeg")
            return is_linear
        # Default: non-linear
        self.linearity_info[expr_id] = (False, f"UNKNOWN(kind={sort_z3})")
        return False

    def print_report(self):
        """Print a summary report of linearity analysis."""
        print("\n" + "=" * 70)
        print("LINEARITY ANALYSIS REPORT")
        print("=" * 70)

        linear_constraints = []
        nonlinear_constraints = []
        operations = []

        for expr_id, (is_linear, expr_type) in self.linearity_info.items():
            if expr_type.startswith("CONSTRAINT_"):
                if is_linear:
                    linear_constraints.append((expr_id, expr_type))
                else:
                    nonlinear_constraints.append((expr_id, expr_type))
            else:
                operations.append((expr_id, is_linear, expr_type))

        print(f"\nTotal constraints analyzed: {len(linear_constraints) + len(nonlinear_constraints)}")
        print(f"  - Linear constraints: {len(linear_constraints)}")
        print(f"  - Non-linear constraints: {len(nonlinear_constraints)}")

        if linear_constraints:
            print(f"\nLinear Constraints (easier to solve):")
            for expr_id, expr_type in linear_constraints:
                print(f"  ✓ Expression ID {expr_id}: {expr_type}")

        if nonlinear_constraints:
            print(f"\nNon-Linear Constraints (harder to solve):")
            for expr_id, expr_type in nonlinear_constraints:
                print(f"  ✗ Expression ID {expr_id}: {expr_type}")

        linear_ops = [op for op in operations if op[1]]
        nonlinear_ops = [op for op in operations if not op[1]]

        if operations:
            print(f"\nIntermediate Operations:")
            print(f"  - Linear operations: {len(linear_ops)}")
            print(f"  - Non-linear operations: {len(nonlinear_ops)}")

        print("=" * 70 + "\n")