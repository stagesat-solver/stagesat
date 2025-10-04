from typing import Optional, Tuple
import z3
import collections
import numpy as np
import src.utils.z3_util as z3_util
import src.utils.verification as verification

DEBUG = False

class LinearConstraintExtractor:
    """Extracts linear equality constraints and builds matrix A and vector b."""

    def __init__(self, symbolTable: collections.OrderedDict):
        self.symbolTable = symbolTable
        self.var_to_index = {var: i for i, var in enumerate(symbolTable.keys())}
        self.n_vars = len(symbolTable)
        self.linear_eq_constraints = []
        self.other_constraints = []

    def extract_coefficient(self, expr_z3, var_name: str) -> float:
        """Extract the coefficient of a variable in a linear expression."""
        # If it's just the variable, coefficient is 1
        if z3_util.is_variable(expr_z3) and verification.rename_var(expr_z3.decl().name()) == var_name:
            return 1.0
        # If it's a constant, coefficient is 0
        if z3_util.is_value(expr_z3):
            return 0.0
        # Handle addition/subtraction
        if z3_util.is_fpAdd(expr_z3) and expr_z3.num_args() >= 3:
            lhs_coef = self.extract_coefficient(expr_z3.arg(1), var_name)
            rhs_coef = self.extract_coefficient(expr_z3.arg(2), var_name)
            return lhs_coef + rhs_coef
        if expr_z3.decl().kind() == z3.Z3_OP_FPA_SUB and expr_z3.num_args() >= 3:
            lhs_coef = self.extract_coefficient(expr_z3.arg(1), var_name)
            rhs_coef = self.extract_coefficient(expr_z3.arg(2), var_name)
            return lhs_coef - rhs_coef
        # Handle multiplication by constant
        if z3_util.is_fpMul(expr_z3) and expr_z3.num_args() >= 3:
            lhs = expr_z3.arg(1)
            rhs = expr_z3.arg(2)
            if z3_util.is_value(lhs):
                const_val = self.get_constant_value(lhs)
                return const_val * self.extract_coefficient(rhs, var_name)
            elif z3_util.is_value(rhs):
                const_val = self.get_constant_value(rhs)
                return const_val * self.extract_coefficient(lhs, var_name)
        # Handle division by constant (variable / constant)
        if z3_util.is_fpDiv(expr_z3) and expr_z3.num_args() >= 3:
            numerator = expr_z3.arg(1)
            denominator = expr_z3.arg(2)
            # Only linear if denominator is constant
            if z3_util.is_value(denominator):
                const_val = self.get_constant_value(denominator)
                if const_val != 0:  # Avoid division by zero
                    return self.extract_coefficient(numerator, var_name) / const_val
            # If numerator is constant and denominator has the variable, it's non-linear
            return 0.0
        # Handle negation
        if z3_util.is_fpNeg(expr_z3):
            return -self.extract_coefficient(expr_z3.arg(0), var_name)
        return 0.0

    def extract_constant_term(self, expr_z3) -> float:
        """Extract the constant term from a linear expression."""
        if z3_util.is_value(expr_z3):
            return self.get_constant_value(expr_z3)
        if z3_util.is_variable(expr_z3):
            return 0.0
        # Handle addition
        if z3_util.is_fpAdd(expr_z3) and expr_z3.num_args() >= 3:
            lhs_const = self.extract_constant_term(expr_z3.arg(1))
            rhs_const = self.extract_constant_term(expr_z3.arg(2))
            return lhs_const + rhs_const
        # Handle subtraction
        if expr_z3.decl().kind() == z3.Z3_OP_FPA_SUB and expr_z3.num_args() >= 3:
            lhs_const = self.extract_constant_term(expr_z3.arg(1))
            rhs_const = self.extract_constant_term(expr_z3.arg(2))
            return lhs_const - rhs_const
        # Handle multiplication
        if z3_util.is_fpMul(expr_z3) and expr_z3.num_args() >= 3:
            lhs = expr_z3.arg(1)
            rhs = expr_z3.arg(2)
            # Both constants
            if z3_util.is_value(lhs) and z3_util.is_value(rhs):
                return self.get_constant_value(lhs) * self.get_constant_value(rhs)
            # One constant, one expression with no variables
            elif z3_util.is_value(lhs):
                return self.get_constant_value(lhs) * self.extract_constant_term(rhs)
            elif z3_util.is_value(rhs):
                return self.get_constant_value(rhs) * self.extract_constant_term(lhs)
        # Handle division
        if z3_util.is_fpDiv(expr_z3) and expr_z3.num_args() >= 3:
            numerator = expr_z3.arg(1)
            denominator = expr_z3.arg(2)
            # Both constants
            if z3_util.is_value(numerator) and z3_util.is_value(denominator):
                denom_val = self.get_constant_value(denominator)
                if denom_val != 0:
                    return self.get_constant_value(numerator) / denom_val
            # Numerator is expression, denominator is constant
            elif z3_util.is_value(denominator):
                denom_val = self.get_constant_value(denominator)
                if denom_val != 0:
                    return self.extract_constant_term(numerator) / denom_val
        # Handle negation
        if z3_util.is_fpNeg(expr_z3):
            return -self.extract_constant_term(expr_z3.arg(0))
        return 0.0

    def get_constant_value(self, expr_z3) -> float:
        """Get numeric value from a Z3 constant expression."""
        import sympy
        if isinstance(expr_z3, z3.FPNumRef):
            if expr_z3.isNaN():
                return float('nan')
            elif expr_z3.isInf():
                return float('inf') if expr_z3.decl().kind() == z3.Z3_OP_FPA_PLUS_INF else float('-inf')
            else:
                try:
                    return float(str(sympy.Float(str(expr_z3), 17)))
                except:
                    # Handle special FP cases
                    is_float32 = expr_z3.sort() == z3.Float32()
                    offset = 127 if is_float32 else 1023
                    exponent_raw = expr_z3.exponent_as_long()
                    if exponent_raw == 0:
                        expr_z3_exponent = -126 if is_float32 else -1022
                    else:
                        expr_z3_exponent = exponent_raw - offset
                    significand = float(str(expr_z3.significand()))
                    value = ((-1) ** float(expr_z3.sign())) * significand * (2 ** expr_z3_exponent)
                    return value
        else:
            return float(str(expr_z3))

    def process_linear_equality(self, lhs_expr, rhs_expr) -> Optional[Tuple[np.ndarray, float]]:
        """
        Process a linear equality constraint lhs = rhs.
        Returns (coefficients, constant) where the constraint is: coefficients @ vars = constant
        """
        # For constraint lhs = rhs, rewrite as (lhs - rhs) = 0
        coefficients = np.zeros(self.n_vars)
        for var_name in self.symbolTable.keys():
            lhs_coef = self.extract_coefficient(lhs_expr, var_name)
            rhs_coef = self.extract_coefficient(rhs_expr, var_name)
            coefficients[self.var_to_index[var_name]] = lhs_coef - rhs_coef
        # Constant term: rhs_const - lhs_const
        lhs_const = self.extract_constant_term(lhs_expr)
        rhs_const = self.extract_constant_term(rhs_expr)
        constant = rhs_const - lhs_const
        return coefficients, constant

    def build_matrices(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Build matrix A and vector b from linear equality constraints.
        Returns (A, b) where A is m x n and b is m x 1
        """
        if not self.linear_eq_constraints:
            return None, None
        A_rows = []
        b_vals = []
        for lhs_expr, rhs_expr in self.linear_eq_constraints:
            result = self.process_linear_equality(lhs_expr, rhs_expr)
            if result:
                coefficients, constant = result
                A_rows.append(coefficients)
                b_vals.append(constant)
        if not A_rows:
            return None, None
        A = np.array(A_rows)
        b = np.array(b_vals).reshape(-1, 1)
        return A, b

    def generate_projection_c_code(self) -> Tuple[str, str]:
        """
        Generate C code for the projection-based objective function.
        Returns (matrix_functions_code, objective_computation_code)
        """
        A, b = self.build_matrices()
        if A is None:
            return "", ""
        m, n = A.shape
        # Generate C arrays for A and b
        A_init = self._matrix_to_c_init(A)
        b_init = self._vector_to_c_init(b.flatten())
        matrix_functions = f"""
// Projection-based objective for linear equality constraints
// Matrix A is {m}x{n}, vector b is {m}x1
static double compute_projection_objective({", ".join([f"double {var}" for var in self.symbolTable.keys()])}) {{
    static const double A[{m}][{n}] = {A_init};
    static const double b[{m}] = {b_init};

    double z[{n}] = {{{", ".join([var for var in self.symbolTable.keys()])}}};
    double residual[{m}];

    // Compute Az - b
    for (int i = 0; i < {m}; i++) {{
        residual[i] = -b[i];
        for (int j = 0; j < {n}; j++) {{
            residual[i] += A[i][j] * z[j];
        }}
    }}

    // Squared norm of residual
    double obj = 0.0;
    for (int i = 0; i < {m}; i++) {{
        obj += residual[i] * residual[i];
    }}

    return obj;
}}
"""

        objective_computation = f"""
  // Compute projection objective for linear equalities
  double obj_linear_eq = compute_projection_objective({", ".join(self.symbolTable.keys())});"""

        return matrix_functions, objective_computation

    def _matrix_to_c_init(self, matrix: np.ndarray) -> str:
        """Convert numpy matrix to C array initializer."""
        rows, cols = matrix.shape
        rows_str = []
        for i in range(rows):
            row_vals = ", ".join([f"{matrix[i, j]:.17e}" for j in range(cols)])
            rows_str.append(f"{{{row_vals}}}")
        return f"{{{', '.join(rows_str)}}}"

    def _vector_to_c_init(self, vector: np.ndarray) -> str:
        """Convert numpy vector to C array initializer."""
        vals_str = ", ".join([f"{val:.17e}" for val in vector])
        return f"{{{vals_str}}}"