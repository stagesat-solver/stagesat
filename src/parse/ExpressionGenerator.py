import sympy
import z3
import collections
import warnings
import src.utils.z3_util as z3_util
import src.utils.verification as verification
from src.utils.sort import Sort

DEBUG = False


class ExpressionGenerator:
    def __init__(self):
        self.symbolTable = collections.OrderedDict()
        self.cache = set()
        self.result = []
        # Hybrid approach attributes
        self.linear_eq_constraints = []  # List of (id, lhs_expr, rhs_expr, c_var_name)
        self.linear_neq_constraints = []
        self.other_constraints = []  # List of (id, c_var_name)
        self.inside_or = False
        # Linearity analysis
        self.linearity_info = {}  # Maps expr_id -> (is_linear, expr_str)

    def reset(self):
        """Reset the generator state."""
        self.symbolTable = collections.OrderedDict()
        self.cache = set()
        self.result = []
        self.linear_eq_constraints = []
        self.linear_neq_constraints = []
        self.other_constraints = []
        self.inside_or = False
        self.linearity_info = {}

    def is_linear(self, expr_z3, symbolTable=None, cache=None):
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
        if symbolTable is None:
            symbolTable = self.symbolTable
        if cache is None:
            cache = self.cache
        expr_id = expr_z3.get_id()
        if expr_id == 376:
            a = 1
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
        if sort_z3 == z3.Z3_OP_FPA_TO_FP:
            is_linear = self.is_linear(expr_z3.arg(1), symbolTable, cache)
            self.linearity_info[expr_id] = (is_linear, "FPA_TO_FP")
            return is_linear
        # Default: non-linear
        self.linearity_info[expr_id] = (False, f"UNKNOWN(kind={sort_z3})")
        return False

    def print_linearity_report(self):
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

    @staticmethod
    def get_operand_type(expr, symbolTable, cache):
        """Determine if an operand is float32 or float64."""
        if z3_util.is_variable(expr):
            var_name = verification.rename_var(expr.decl().name())
            if var_name in symbolTable:
                return symbolTable[var_name]
        elif z3_util.is_value(expr):
            if expr.sort() == z3.Float32():
                return Sort.Float32
            elif expr.sort() == z3.Float64():
                return Sort.Float64
        elif expr.get_id() in cache:
            if expr.sort() == z3.Float32():
                return Sort.Float32
            elif expr.sort() == z3.Float64():
                return Sort.Float64
        return Sort.Float64

    @staticmethod
    def get_comparison_function(base_func, lhs_type, rhs_type):
        """Get the appropriate comparison function based on operand types."""
        if lhs_type == Sort.Float32 and rhs_type == Sort.Float32:
            return f"{base_func}_f32"
        else:
            return base_func

    def generate(self, expr_z3):
        """Generate C code from Z3 expression tree."""
        return self._gen_recursive(expr_z3)

    def _gen_recursive(self, expr_z3):
        """Recursively generate C code for expressions."""
        if z3_util.is_variable(expr_z3):
            return self.handle_variable(expr_z3)
        if z3_util.is_value(expr_z3):
            return self.handle_value(expr_z3)
        if expr_z3.get_id() in self.cache:
            return verification.var_name(expr_z3)
        self.cache.add(expr_z3.get_id())
        sort_z3 = expr_z3.decl().kind()
        # Handle different operation types
        handlers = {
            z3.Z3_OP_FPA_LE: self.handle_comparison,
            z3.Z3_OP_FPA_LT: self.handle_comparison,
            z3.Z3_OP_FPA_GE: self.handle_comparison,
            z3.Z3_OP_FPA_GT: self.handle_comparison,
            z3.Z3_OP_FPA_TO_FP: self.handle_cast,
            z3.Z3_OP_FPA_SUB: self.handle_arithmetic,
        }
        if sort_z3 in handlers:
            return handlers[sort_z3](expr_z3)
        if z3_util.is_eq(expr_z3):
            return self.handle_equality(expr_z3)
        if z3_util.is_fpMul(expr_z3):
            return self.handle_arithmetic(expr_z3)
        if z3_util.is_fpDiv(expr_z3):
            return self.handle_arithmetic(expr_z3)
        if z3_util.is_fpAdd(expr_z3):
            return self.handle_arithmetic(expr_z3)
        if z3.is_and(expr_z3):
            return self.handle_and(expr_z3)
        if z3.is_not(expr_z3):
            return self.handle_not(expr_z3)
        if z3_util.is_fpNeg(expr_z3):
            return self.handle_negation(expr_z3)
        if z3.is_or(expr_z3):
            return self.handle_or(expr_z3)
        raise NotImplementedError(
            f"Not implemented case for expr_z3 = {expr_z3}, kind({expr_z3.decl().kind()})")

    def handle_variable(self, expr_z3):
        """Handle variable expressions."""
        if DEBUG:
            print("-- Branch _is_variable with ", expr_z3)
        symVar = verification.rename_var(expr_z3.decl().name())
        if z3.is_int(expr_z3):
            symType = Sort.Int
        elif z3.is_fp(expr_z3):
            if expr_z3.sort() == z3.Float64():
                symType = Sort.Float64
            elif expr_z3.sort() == z3.Float32():
                symType = Sort.Float32
            else:
                raise NotImplementedError("Unexpected sort.", expr_z3.sort())
        elif z3.is_real(expr_z3):
            symType = Sort.Float
            warnings.warn(f"****WARNING****: Real variable '{symVar}' treated as floating point")
        else:
            raise NotImplementedError("Unexpected type")
        if symVar in self.symbolTable:
            assert symType == self.symbolTable[symVar]
        else:
            self.symbolTable[symVar] = symType
        return symVar

    def handle_value(self, expr_z3):
        """Handle constant value expressions."""
        if DEBUG:
            print("-- Branch _is_value")
        if z3.is_fp(expr_z3) or z3.is_real(expr_z3):
            if isinstance(expr_z3, z3.FPNumRef):
                if expr_z3.isNaN():
                    str_ret = "NAN"
                elif expr_z3.isInf() and expr_z3.decl().kind() == z3.Z3_OP_FPA_PLUS_INF:
                    str_ret = "INFINITY"
                elif expr_z3.isInf() and expr_z3.decl().kind() == z3.Z3_OP_FPA_MINUS_INF:
                    str_ret = "- INFINITY"
                else:
                    try:
                        str_ret = str(sympy.Float(str(expr_z3), 17))
                    except ValueError:
                        is_float32 = expr_z3.sort() == z3.Float32()
                        offset = 127 if is_float32 else 1023
                        exponent_raw = expr_z3.exponent_as_long()
                        if exponent_raw == 0:
                            expr_z3_exponent = -126 if is_float32 else -1022
                        else:
                            expr_z3_exponent = exponent_raw - offset
                        significand = float(str(expr_z3.significand()))
                        value = ((-1) ** float(expr_z3.sign())) * significand * (2 ** expr_z3_exponent)
                        str_ret = str(sympy.Float(value, 17))
            else:
                str_ret = str(sympy.Float(str(expr_z3), 17))
        elif z3.is_int(expr_z3):
            str_ret = str(sympy.Integer(str(expr_z3)))
        elif z3_util.is_true(expr_z3):
            str_ret = "0"
        elif z3_util.is_false(expr_z3):
            str_ret = "1"
        else:
            raise NotImplementedError("[stagesat] type not considered")
        if expr_z3.sort() == z3.Float32():
            str_ret = str_ret + "f"
        return str_ret

    def handle_comparison(self, expr_z3):
        """Handle comparison operations (LE, LT, GE, GT)."""
        lhs_expr = expr_z3.arg(0)
        rhs_expr = expr_z3.arg(1)
        sort_z3 = expr_z3.decl().kind()
        op_map = {
            z3.Z3_OP_FPA_LE: "DLE",
            z3.Z3_OP_FPA_LT: "DLT",
            z3.Z3_OP_FPA_GE: "DGE",
            z3.Z3_OP_FPA_GT: "DGT"
        }
        base_func = op_map[sort_z3]
        constraint_name = base_func[1:]  # Remove 'D' prefix
        lhs = self._gen_recursive(expr_z3.arg(0))
        rhs = self._gen_recursive(expr_z3.arg(1))
        lhs_type = self.get_operand_type(expr_z3.arg(0), self.symbolTable, self.cache)
        rhs_type = self.get_operand_type(expr_z3.arg(1), self.symbolTable, self.cache)
        lhs_linear = self.is_linear(expr_z3.arg(0), self.symbolTable, self.cache)
        rhs_linear = self.is_linear(expr_z3.arg(1), self.symbolTable, self.cache)
        is_linear = lhs_linear and rhs_linear
        expr_id = expr_z3.get_id()
        self.linearity_info[expr_id] = (
            is_linear, f"CONSTRAINT_{constraint_name}(lhs={lhs_linear},rhs={rhs_linear})")
        if is_linear and not self.inside_or:
            self.linear_neq_constraints.append((expr_id, lhs_expr, rhs_expr, verification.var_name(expr_z3)))
        func_name = self.get_comparison_function(base_func, lhs_type, rhs_type)
        comment = f" // {'LINEAR' if is_linear else 'NON-LINEAR'}"
        toAppend = f"double {verification.var_name(expr_z3)} = {func_name}({lhs},{rhs});{comment}"
        self.result.append(toAppend)
        # Track as other constraint (not linear equality)
        if not self.inside_or:
            self.other_constraints.append((expr_id, verification.var_name(expr_z3)))
        return verification.var_name(expr_z3)

    def handle_equality(self, expr_z3):
        """Handle equality operations."""
        lhs_expr = expr_z3.arg(0)
        rhs_expr = expr_z3.arg(1)
        lhs = self._gen_recursive(lhs_expr)
        rhs = self._gen_recursive(rhs_expr)
        lhs_type = self.get_operand_type(lhs_expr, self.symbolTable, self.cache)
        rhs_type = self.get_operand_type(rhs_expr, self.symbolTable, self.cache)
        lhs_linear = self.is_linear(lhs_expr, self.symbolTable, self.cache)
        rhs_linear = self.is_linear(rhs_expr, self.symbolTable, self.cache)
        is_linear = lhs_linear and rhs_linear
        expr_id = expr_z3.get_id()
        self.linearity_info[expr_id] = (
            is_linear, f"CONSTRAINT_EQ(lhs={lhs_linear},rhs={rhs_linear})")
        if is_linear and not self.inside_or:
            self.linear_eq_constraints.append((expr_id, lhs_expr, rhs_expr, verification.var_name(expr_z3)))
            comment = " // LINEAR EQ - for projection objective"
        else:
            if self.inside_or:
                comment = f" // {'LINEAR' if is_linear else 'NON-LINEAR'} EQ - inside OR (treated as other constraint)"
            else:
                self.other_constraints.append((expr_id, verification.var_name(expr_z3)))
                comment = f" // {'LINEAR' if is_linear else 'NON-LINEAR'}"
        func_name = self.get_comparison_function("DEQ", lhs_type, rhs_type)
        toAppend = f"double {verification.var_name(expr_z3)} = {func_name}({lhs},{rhs});{comment}"
        self.result.append(toAppend)
        return verification.var_name(expr_z3)

    def handle_arithmetic(self, expr_z3):
        """Handle arithmetic operations (add, sub, mul, div)."""
        sort_z3 = expr_z3.decl().kind()
        expr_type = 'float' if expr_z3.sort() == z3.FPSort(8, 24) else 'double'
        if not z3_util.is_RNE(expr_z3.arg(0)):
            warnings.warn(f"WARNING!!! arg(0) is not RNE but treated as RNE. arg(0) = {expr_z3.arg(0)}")
        assert expr_z3.num_args() == 3
        lhs = self._gen_recursive(expr_z3.arg(1))
        rhs = self._gen_recursive(expr_z3.arg(2))
        op_map = {
            z3.Z3_OP_FPA_ADD: '+',
            z3.Z3_OP_FPA_SUB: '-',
            z3.Z3_OP_FPA_MUL: '*',
            z3.Z3_OP_FPA_DIV: '/'
        }
        # Handle fpMul, fpDiv, fpAdd specifically
        if z3_util.is_fpMul(expr_z3):
            op = '*'
        elif z3_util.is_fpDiv(expr_z3):
            op = '/'
        elif z3_util.is_fpAdd(expr_z3):
            op = '+'
        elif sort_z3 == z3.Z3_OP_FPA_SUB:
            op = '-'
        else:
            raise NotImplementedError("bugs in _handle_arithmetic")
        if expr_type == 'float':
            toAppend = f"float {verification.var_name(expr_z3)} = (float)({lhs}) {op} (float)({rhs});"
        else:
            toAppend = f"double {verification.var_name(expr_z3)} = {lhs} {op} {rhs};"
        self.result.append(toAppend)
        return verification.var_name(expr_z3)

    def handle_cast(self, expr_z3):
        """Handle type casting operations."""
        assert expr_z3.num_args() == 2
        if not z3_util.is_RNE(expr_z3.arg(0)):
            warnings.warn(f"WARNING!!! First argument of fpFP is not RNE: {expr_z3.arg(0)}")
        x = self._gen_recursive(expr_z3.arg(1))
        if expr_z3.sort() == z3.FPSort(8, 24):
            toAppend = f"float {verification.var_name(expr_z3)} = (float)({x});"
        else:
            toAppend = f"double {verification.var_name(expr_z3)} = (double)({x});"
        self.result.append(toAppend)
        return verification.var_name(expr_z3)

    def handle_and(self, expr_z3):
        """Handle AND operations."""
        if DEBUG:
            print("-- Branch _is_and")
        toAppendExpr = self._gen_recursive(expr_z3.arg(0))
        for i in range(1, expr_z3.num_args()):
            toAppendExpr = f'BAND( {toAppendExpr},{self._gen_recursive(expr_z3.arg(i))} )'
        toAppend = f"double {verification.var_name(expr_z3)} = {toAppendExpr};"
        self.result.append(toAppend)
        return verification.var_name(expr_z3)

    def handle_or(self, expr_z3):
        """Handle OR operations."""
        if DEBUG:
            print("-- Branch _is_or")
        old_inside_or = self.inside_or
        self.inside_or = True
        toAppendExpr = self._gen_recursive(expr_z3.arg(0))
        for i in range(1, expr_z3.num_args()):
            toAppendExpr = f'BOR( {toAppendExpr},{self._gen_recursive(expr_z3.arg(i))} )'
        self.inside_or = old_inside_or
        # add total BOR results as one other_constraints
        self.other_constraints.append((expr_z3.get_id(), verification.var_name(expr_z3)))
        toAppend = f"double {verification.var_name(expr_z3)} = {toAppendExpr};"
        self.result.append(toAppend)
        return verification.var_name(expr_z3)

    def handle_not(self, expr_z3):
        """Handle NOT operations."""
        assert expr_z3.num_args() == 1
        if expr_z3.arg(0).num_args() != 2:
            warnings.warn(f"WARNING!!! arg(0) num_args != 2: {expr_z3.arg(0)}")
        op1 = self._gen_recursive(expr_z3.arg(0).arg(0))
        op2 = self._gen_recursive(expr_z3.arg(0).arg(1))
        lhs_type = self.get_operand_type(expr_z3.arg(0).arg(0), self.symbolTable, self.cache)
        rhs_type = self.get_operand_type(expr_z3.arg(0).arg(1), self.symbolTable, self.cache)
        lhs_linear = self.is_linear(expr_z3.arg(0).arg(0), self.symbolTable, self.cache)
        rhs_linear = self.is_linear(expr_z3.arg(0).arg(1), self.symbolTable, self.cache)
        is_linear = lhs_linear and rhs_linear
        expr_id = expr_z3.get_id()
        # Determine which negated comparison this is
        comparison_map = {
            'is_ge': ('DLT', 'CONSTRAINT_NOT_GE'),
            'is_gt': ('DLE', 'CONSTRAINT_NOT_GT'),
            'is_le': ('DGT', 'CONSTRAINT_NOT_LE'),
            'is_lt': ('DGE', 'CONSTRAINT_NOT_LT'),
            'is_eq': ('DNE', 'CONSTRAINT_NOT_EQ'),
            'is_distinct': ('DEQ', 'CONSTRAINT_NOT_DISTINCT')
        }
        for check_name, (func_base, constraint_type) in comparison_map.items():
            check_func = getattr(z3_util, check_name)
            if check_func(expr_z3.arg(0)):
                func = self.get_comparison_function(func_base, lhs_type, rhs_type)
                self.linearity_info[expr_id] = (
                    is_linear, f"{constraint_type}(lhs={lhs_linear},rhs={rhs_linear})")
                break
        else:
            raise NotImplementedError("Not implemented case in NOT handler")
        if not self.inside_or:
            self.other_constraints.append((expr_id, verification.var_name(expr_z3)))
        comment = f" // {'LINEAR' if is_linear else 'NON-LINEAR'}"
        toAppend = f"double {verification.var_name(expr_z3)} = {func}({op1},{op2});{comment}"
        self.result.append(toAppend)
        return verification.var_name(expr_z3)

    def handle_negation(self, expr_z3):
        """Handle negation operations."""
        assert expr_z3.num_args() == 1
        op1 = self._gen_recursive(expr_z3.arg(0))
        expr_type = 'float' if expr_z3.sort() == z3.FPSort(8, 24) else 'double'
        toAppend = f"{expr_type} {verification.var_name(expr_z3)} = - {op1} ;"
        self.result.append(toAppend)
        return verification.var_name(expr_z3)