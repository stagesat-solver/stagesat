from fractions import Fraction
from typing import List
from z3 import FPRef
from src.parse.LinearTransform import LinearTransform


class LinearSquareTransform(LinearTransform):
    def __init__(self):
        super().__init__()
        self.var = set()
        self.lhs_ck = []
        self.rhs_ck = []

    def get_var(self):
        return sorted(self.var)

    def handle_constraint(self, lhs: FPRef, rhs: FPRef):
        lhs_c, lhs_k = self._parse_z3_linear_expr(lhs)
        rhs_c, rhs_k = self._parse_z3_linear_expr(rhs)
        # get variables from lhs_c and rhs_c
        for k in lhs_c.keys():
            self.var.add(k)
        for k in rhs_c.keys():
            self.var.add(k)
        self.lhs_ck.append((lhs_c, lhs_k))
        self.rhs_ck.append((rhs_c, rhs_k))
        return True

    def build_A_b(self, constraints: List[FPRef]):
        for constraint in constraints:
            _, lhs_expr, rhs_expr, _ = constraint
            self.handle_constraint(lhs_expr, rhs_expr)
        A, b = [], []
        for i in range(len(self.lhs_ck)):
            lhs_c, lhs_k = self.lhs_ck[i]
            rhs_c, rhs_k = self.rhs_ck[i]
            row = []
            for v in self.get_var():
                row.append(lhs_c.get(v, Fraction(0)) - rhs_c.get(v, Fraction(0)))
            A.append(row)
            b.append(rhs_k - lhs_k)
        return A, b

    # def square_projection_objective(self, constraints: List[FPRef]):
    #     A, b = self.build_A_b(constraints)
    #     if not A:
    #         return ""
    #     try:
    #         AT = LinearTransform._mat_transpose(A)
    #         AAT = LinearTransform._mat_mul(A, AT)
    #         AAT_inv = LinearTransform._mat_inv(AAT)
    #         P = LinearTransform._mat_mul(AT, AAT_inv)
    #         PA = LinearTransform._mat_mul(P, A)
    #         I = LinearTransform._mat_eye(len(self.var))
    #         M = LinearTransform._mat_add(I, PA, sign=-1)
    #         c = LinearTransform._mat_vec(P, b)
    #         return self._gen_matrix_code(M, c)
    #     except ValueError as e:
    #         # Matrix is singular (redundant or over-determined constraints)
    #         # Fall back to direct constraint evaluation without projection
    #         import warnings
    #         warnings.warn(f"Singular matrix detected: {e}. Using direct constraint evaluation instead of projection.")
    #         return ""

    def square_projection_objective(self, constraints: List[FPRef]):
        A, b = self.build_A_b(constraints)
        if not A:
            return ""
        AT = LinearTransform._mat_transpose(A)
        AAT = LinearTransform._mat_mul(A, AT)
        try:
            AAT_inv = LinearTransform._mat_inv(AAT)
        except ValueError:
            import warnings
            warnings.warn(
                "Singular matrix detected in AA^T. Using Moore-Penrose pseudoinverse "
                "as described in Section 2 of the paper."
            )
            AAT_inv = LinearTransform._mat_pinv(AAT)
        P = LinearTransform._mat_mul(AT, AAT_inv)
        PA = LinearTransform._mat_mul(P, A)
        I = LinearTransform._mat_eye(len(self.var))
        M = LinearTransform._mat_add(I, PA, sign=-1)
        c = LinearTransform._mat_vec(P, b)
        return self._gen_matrix_code(M, c)

    def _gen_matrix_code(self, M, c):
        var_lis = sorted(self.var)
        parts = []
        for i, v in enumerate(var_lis):
            parts.append(f"ulp({v}, {LinearTransform.linear_expr_to_str(M[i], c[i], var_lis)})")
        obj_additions = "\n\t\t".join([f"obj += {part};" for part in parts]) if parts else ""
        code = f"""
    static double compute_projection_objective_square({", ".join([f"double {var}" for var in var_lis])}) {{
        double obj = 0.0;
        {obj_additions}
        return obj;
    }}
        """
        return code