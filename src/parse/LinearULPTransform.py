from collections import defaultdict
from fractions import Fraction
from decimal import Decimal
from typing import List
from z3 import FPRef

from src.parse.LinearTransform import LinearTransform
from src.utils.DSU import DSU

def F(x):
    if isinstance(x, Fraction): return x
    return Fraction(Decimal(str(x)))

def fmt(q: Fraction) -> str:
    return str(float(q))

def simplify_affine_var(A: Fraction, B: Fraction, var: str) -> str:
    if A == 0:   return fmt(B)
    if B == 0:
        if A == 1:  return var
        if A == -1: return f"-{var}"
        return f"{fmt(A)}*{var}"
    if A == 1:  return f"{var} + {fmt(B)}"
    if A == -1: return f"-{var} + {fmt(B)}"
    return f"{fmt(A)}*{var} + {fmt(B)}"

class LinearULPTransform(LinearTransform):
    def __init__(self):
        super().__init__()
        self.var = set()
        self.var_32 = set()
        self.mix_constraints = []

    def get_var(self):
        return sorted(self.var)

    def get_var_32(self):
        return sorted(self.var_32)

    def _parse_constraint(self, lhs: FPRef, rhs: FPRef):
        """
        Move RHS to LHS; ensure <= 2 distinct variables overall.
        Return canonical (x, a, b, y, ccoef, d) for  a*x + b = c*y + d.
        (x or y can be None when only one variable appears.)
        """
        self.has_float = False
        self.has_double = False
        lhs_c, lhs_k = self._parse_z3_linear_expr(lhs)
        rhs_c, rhs_k = self._parse_z3_linear_expr(rhs)
        if self.has_float and self.has_double:
            return None
        # LHS - RHS:  sum_v (lc[v]-rc[v]) * v + (lk - rk) = 0
        coef = defaultdict(Fraction)
        for v in set(lhs_c) | set(rhs_c):
            coef[v] = lhs_c.get(v, F(0)) - rhs_c.get(v, F(0))
        k = lhs_k - rhs_k
        vars_list = [v for v, c0 in coef.items() if c0 != 0]
        if len(vars_list) > 2:
            return None
        if len(vars_list) == 0:
            if k != 0:
                raise ValueError(f"UNSAT constant equality")
            # dummy no-op: 0 = 0
            if self.has_float:
                return (None, F(1), F(0), None, F(1), F(0)), "f32"
            else:
                return (None, F(1), F(0), None, F(1), F(0)), "f64"
        if len(vars_list) == 1:
            v1 = vars_list[0]
            a1 = coef[v1]
            # a1*v1 + k = 0   ->  v1 = (-k/a1)  (anchor)
            if self.has_float:
                return (v1, a1, k, None, F(1), F(0)), "f32"
            else:
                return (v1, a1, k, None, F(1), F(0)), "f64"
        # two variables: a1*v1 + a2*v2 + k = 0  ->  a1*v1 + k = (-a2)*v2 + 0
        v1, v2 = vars_list
        a1, a2 = coef[v1], coef[v2]
        if self.has_float:
            return (v1, a1, k, v2, -a2, F(0)), "f32"
        else:
            return (v1, a1, k, v2, -a2, F(0)), "f64"

    def build_objective(self, constraints: List[FPRef]):
        vars_list, vars_f32_list = [], []
        parsed_f64, parsed_f32 = [], []
        parts, parts_f32 = [], []
        for c in constraints:
            _, lhs_expr, rhs_expr, _ = c
            res = self._parse_constraint(lhs_expr, rhs_expr)
            if not res:
                self.mix_constraints.append(c)
                continue
            (x, a, b, y, c2, d), ty = res
            if ty == "f64":
                for v in (x, y):
                    if v and v not in self.var:
                        self.var.add(v)
                        vars_list.append(v)
                parsed_f64.append((x, a, b, y, c2, d))
            else:
                for v in (x, y):
                    if v and v not in self.var_32:
                        self.var_32.add(v)
                        vars_f32_list.append(v)
                parsed_f32.append((x, a, b, y, c2, d))
        # generate coded
        # handle double first
        if vars_list:
            dsu = DSU(vars_list)
            # feed constraints
            for (x, a, b, y, c, d) in parsed_f64:
                dsu.union_constraint(x, a, b, y, c, d)
            # group by root
            comps = defaultdict(list)
            for v in vars_list:
                r, A, B = dsu.find(v)
                comps[r].append((v, A, B))
            for r, items in comps.items():
                rep = min(v for (v, _, _) in items)
                if dsu.has_anchor[r]:
                    c = dsu.anchor[r]
                    for (v, A_v, B_v) in items:
                        target = A_v * c + B_v
                        parts.append(f"ulp({v}, {fmt(target)})")
                else:
                    # express each v as α*rep + β
                    A_rep = next(A for (vv, A, _) in items if vv == rep)
                    B_rep = next(B for (vv, _, B) in items if vv == rep)
                    for (v, A_v, B_v) in items:
                        if v == rep: continue
                        A_vr = A_v / A_rep
                        B_vr = B_v - (A_v * B_rep) / A_rep
                        rhs = simplify_affine_var(A_vr, B_vr, rep)
                        parts.append(f"ulp({v}, {rhs})")
        if vars_f32_list:
            dsu_f32 = DSU(vars_f32_list)
            for (x, a, b, y, c, d) in parsed_f32:
                dsu_f32.union_constraint(x, a, b, y, c, d)
            comps = defaultdict(list)
            for v in vars_f32_list:
                r, A, B = dsu_f32.find(v)
                comps[r].append((v, A, B))
            for r, items in comps.items():
                rep = min(v for (v, _, _) in items)
                if dsu_f32.has_anchor[r]:
                    c = dsu_f32.anchor[r]
                    for (v, A_v, B_v) in items:
                        target = A_v * c + B_v
                        parts_f32.append(f"ulp_f32({v}, {fmt(target)})")
                else:
                    # express each v as α*rep + β
                    A_rep = next(A for (vv, A, _) in items if vv == rep)
                    B_rep = next(B for (vv, _, B) in items if vv == rep)
                    for (v, A_v, B_v) in items:
                        if v == rep: continue
                        A_vr = A_v / A_rep
                        B_vr = B_v - (A_v * B_rep) / A_rep
                        rhs = simplify_affine_var(A_vr, B_vr, rep)
                        parts_f32.append(f"ulp_f32({v}, {rhs})")

        d_code = " + ".join(parts) if parts else ""
        c_code = " + ".join(parts_f32) if parts_f32 else ""
        return self._gen_code(d_code), self._gen_code_f32(c_code)

    def _gen_code(self, d_code):
        # Only add objective calculation if d_code is not empty
        obj_additions = f"\tobj += {d_code};" if d_code else ""
        code = f"""
    static double compute_projection_objective_ulp({", ".join([f"double {var}" for var in self.get_var()])}) {{
        double obj = 0.0;
    {obj_additions}
        return obj;
    }}
        """
        return code

    def _gen_code_f32(self, c_code):
        # Only add objective calculation if d_code is not empty
        obj_additions = f"\tobj += {c_code};" if c_code else ""
        code = f"""
    static double compute_projection_objective_ulp_f32({", ".join([f"float {var}" for var in self.get_var_32()])}) {{
        double obj = 0.0;
    {obj_additions}
        return obj;
    }}
        """
        return code


