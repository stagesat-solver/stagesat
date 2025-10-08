from fractions import Fraction
from typing import List
from z3 import FPRef
from src.parse.LinearTransform import LinearTransform

class LinearULPTransform(LinearTransform):
    def __init__(self):
        super().__init__()
        self.var = set()
        self.var_32 = set()
        self.lhs_ck = []
        self.rhs_ck = []
        self.lhs_ck_32 = []
        self.rhs_ck_32 = []
        self.mix_constraints = []

    def get_var(self):
        return sorted(self.var)

    def get_var_32(self):
        return sorted(self.var_32)

    def handle_constraint(self, lhs: FPRef, rhs: FPRef):
        self.has_float = False
        self.has_double = False
        lhs_c, lhs_k = self._parse_z3_linear_expr(lhs)
        rhs_c, rhs_k= self._parse_z3_linear_expr(rhs)
        if self.has_float and self.has_double:
            return False
        # get variables from lhs_c and rhs_c
        if self.has_float:
            for k in lhs_c.keys():
                self.var_32.add(k)
            for k in rhs_c.keys():
                self.var_32.add(k)
            self.lhs_ck_32.append((lhs_c, lhs_k))
            self.rhs_ck_32.append((rhs_c, rhs_k))
        else:
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
            if not self.handle_constraint(lhs_expr, rhs_expr):
                self.mix_constraints.append(constraint)
        # handle double constraints
        var_lis = sorted(self.var)
        A, b = [], []
        for i in range(len(self.lhs_ck)):
            lhs_c, lhs_k = self.lhs_ck[i]
            rhs_c, rhs_k = self.rhs_ck[i]
            row = []
            for v in var_lis:
                row.append(lhs_c.get(v, Fraction(0)) - rhs_c.get(v, Fraction(0)))
            A.append(row)
            b.append(rhs_k - lhs_k)
        # handle float constraints
        var_lis_32 = sorted(self.var_32)
        A_32, b_32 = [], []
        for i in range(len(self.lhs_ck_32)):
            lhs_c, lhs_k = self.lhs_ck_32[i]
            rhs_c, rhs_k = self.rhs_ck_32[i]
            row = []
            for v in var_lis_32:
                row.append(lhs_c.get(v, Fraction(0)) - rhs_c.get(v, Fraction(0)))
            A_32.append(row)
            b_32.append(rhs_k - lhs_k)
        return A, b, A_32, b_32

    def ulp_projection_objective(self, constraints: List[FPRef]):
        A, b, A_32, b_32 = self.build_A_b(constraints)
        d_code = ""
        f_code = ""
        # handle double first
        if A:
            AT = LinearTransform._mat_transpose(A)
            AAT = LinearTransform._mat_mul(A, AT)
            AAT_inv = LinearTransform._mat_inv(AAT)
            P = LinearTransform._mat_mul(AT, AAT_inv)
            PA = LinearTransform._mat_mul(P, A)
            I = LinearTransform._mat_eye(len(self.var))
            M = LinearTransform._mat_add(I, PA, sign=-1)
            c = LinearTransform._mat_vec(P, b)
            d_code = self._gen_matrix_code(M, c)
        if A_32:
            AT_32 = LinearTransform._mat_transpose(A_32)
            AAT_32 = LinearTransform._mat_mul(A_32, AT_32)
            AAT_inv_32 = LinearTransform._mat_inv(AAT_32)
            P_32 = LinearTransform._mat_mul(AT_32, AAT_inv_32)
            PA_32 = LinearTransform._mat_mul(P_32, A_32)
            I_32 = LinearTransform._mat_eye(len(self.var_32))
            M_32 = LinearTransform._mat_add(I_32, PA_32, sign=-1)
            c_32 = LinearTransform._mat_vec(P_32, b_32)
            f_code = self._gen_matrix_code_32(M_32, c_32)
        return d_code, f_code

    def _gen_matrix_code(self, M, c):
        var_lis = sorted(self.var)
        parts = []
        for i, v in enumerate(var_lis):
            parts.append(f"ulp({v}, {LinearTransform.linear_expr_to_str(M[i], c[i], var_lis)})")
        obj_additions = "\n\t\t".join([f"obj += {part};" for part in parts]) if parts else ""
        code = f"""
    static double compute_projection_objective_ulp({", ".join([f"double {var}" for var in var_lis])}) {{
        double obj = 0.0;
        {obj_additions}
        return obj;
    }}
        """
        return code

    def _gen_matrix_code_32(self, M, c):
        var_lis = sorted(self.var_32)
        parts = []
        for i, v in enumerate(var_lis):
            parts.append(f"ulp_f32({v}, {LinearTransform.linear_expr_to_str(M[i], c[i], var_lis)})")
        obj_additions = "\n\t\t".join([f"obj += {part};" for part in parts]) if parts else ""
        code = f"""
    static double compute_projection_objective_ulp_f32({", ".join([f"float {var}" for var in var_lis])}) {{
        double obj = 0.0;
        {obj_additions}
        return obj;
    }}
        """
        return code

