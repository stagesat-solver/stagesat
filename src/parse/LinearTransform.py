import z3
import sympy
from math import gcd
from decimal import Decimal
from functools import reduce
from fractions import Fraction
from z3 import FPRef, is_fp_value, is_const, simplify
import src.utils.z3_util as z3_util

class LinearTransform:
    def __init__(self):
        self.has_float = False
        self.had_double = False

    @staticmethod
    def _mat_transpose(A):
        return [list(row) for row in zip(*A)]

    @staticmethod
    def _mat_eye(n):
        return [[Fraction(int(i == j)) for j in range(n)] for i in range(n)]

    @staticmethod
    def _mat_mul(A, B):
        m, n, p = len(A), len(A[0]), len(B[0])
        out = [[Fraction(0) for _ in range(p)] for _ in range(m)]
        for i in range(m):
            Ai = A[i]
            for k in range(n):
                aik = Ai[k]
                if aik == 0: continue
                Bk = B[k]
                for j in range(p):
                    out[i][j] += aik * Bk[j]
        return out

    @staticmethod
    def _mat_inv(A):
        n = len(A)
        M = [row[:] + eye[:] for row, eye in zip(A, LinearTransform._mat_eye(n))]
        for col in range(n):
            piv = next((r for r in range(col, n) if M[r][col] != 0), None)
            if piv is None:
                raise ValueError("Singular matrix in constraints (AA^T not invertible).")
            if piv != col: M[col], M[piv] = M[piv], M[col]
            f = M[col][col]
            M[col] = [v / f for v in M[col]]
            for r in range(n):
                if r == col: continue
                factor = M[r][col]
                if factor != 0:
                    M[r] = [vr - factor * vc for vr, vc in zip(M[r], M[col])]
        return [row[n:] for row in M]

    @staticmethod
    def _mat_add(A, B, sign=1):
        return [[a + sign * b for a, b in zip(ra, rb)] for ra, rb in zip(A, B)]

    @staticmethod
    def _mat_vec(A, x):
        return [sum(aij * xj for aij, xj in zip(row, x)) for row in A]

    @staticmethod
    def _lcm(a, b):
        return abs(a * b) // gcd(a, b) if a and b else abs(a or b)

    @staticmethod
    def linear_expr_to_str(row, const, var_order):
        den = reduce(LinearTransform._lcm, [x.denominator for x in row + [const]], 1)
        ints = [int(x * den) for x in row]
        c0 = int(const * den)
        terms = []
        for coef, v in zip(ints, var_order):
            if coef == 0: continue
            sgn = '-' if coef < 0 else '+'
            mag = abs(coef)
            terms.append(f"{sgn} {v}" if mag == 1 else f"{sgn} {mag}*{v}")
        if c0 != 0:
            sgn = '-' if c0 < 0 else '+'
            terms.append(f"{sgn} {abs(c0)}")
        num = ' '.join(terms).lstrip('+ ').replace('+ -', '- ')
        if not num: num = "0"
        try:
            if den == 1:
                if not any(v in num for v in var_order):
                    ret = float(eval(num))
                else:
                    ret = num
            else:
                ret = float(eval(num)) / den
        except:
            ret = num if den == 1 else f"({num})/{den}"
        return ret

    def _is_variable(self, expr):
        """Check if expression is a variable (constant symbol, not a value)"""
        return is_const(expr) and not is_fp_value(expr)

    def _extract_constant(self, expr_z3):
        """Extract numeric value from Z3 expression as Fraction"""
        if z3.is_fp(expr_z3) or z3.is_real(expr_z3):
            if isinstance(expr_z3, z3.FPNumRef):
                if expr_z3.isNaN():
                    raise NotImplementedError
                elif expr_z3.isInf() and expr_z3.decl().kind() == z3.Z3_OP_FPA_PLUS_INF:
                    raise NotImplementedError
                elif expr_z3.isInf() and expr_z3.decl().kind() == z3.Z3_OP_FPA_MINUS_INF:
                    raise NotImplementedError
                else:
                    try:
                        ret = sympy.Float(str(expr_z3), 17)
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
                        ret = sympy.Float(value, 17)
            else:
                ret = sympy.Float(str(expr_z3), 17)
        elif z3.is_int(expr_z3):
            ret = sympy.Integer(str(expr_z3))
        else:
            raise NotImplementedError("[XSat] type not considered")
        return ret

    def _parse_z3_linear_expr(self, expr):
        """
        Parse Z3 FPRef linear expression into coefficients.
        Returns: (var_coefs: dict[str, Fraction], constant: Fraction)
        """
        expr = simplify(expr)  # Simplify first
        var_coefs = {}
        constant = Fraction(0)
        def traverse(e, sign):
            nonlocal var_coefs, constant
            if is_fp_value(e):
                constant += sign * Fraction(Decimal(str(self._extract_constant(e))))
                return
            if self._is_variable(e):
                if e.sort() == z3.FPSort(8, 24):
                    self.has_float = True
                if e.sort() == z3.FPSort(11, 53):
                    self.has_double = True
                var_name = str(e)
                var_coefs[var_name] = var_coefs.get(var_name, Fraction(0)) + sign
                return
            decl = e.decl()
            op_name = decl.name()
            children = [c for c in e.children() if not z3_util.is_RNE(c)]
            if op_name in ['fp.add', '+']:
                # Addition: traverse all operands
                for child in children:
                    traverse(child, sign)
            elif op_name in ['fp.sub', '-'] and len(children) == 2:
                # Binary subtraction: a - b
                traverse(children[0], sign)
                traverse(children[1], -sign)
            elif op_name in ['fp.neg', '-'] and len(children) == 1:
                # Unary negation
                traverse(children[0], -sign)
            elif op_name in ['fp.mul', '*']:
                # Try to evaluate as constant * variable
                assert len(children) == 2
                left, right = children
                # constant * variable_expression
                try:
                    coef_val = self._extract_constant(left)
                    coef = Fraction(Decimal(str(coef_val)))
                    traverse(right, sign * coef)
                except:
                    raise ValueError(f"Cannot parse multiplication: {e}")
            elif e.decl().kind() == z3.Z3_OP_FPA_TO_FP:
                traverse(e.arg(1), sign)
            else:
                raise ValueError(f"Unsupported operation '{op_name}' in linear expression: {e}")
        traverse(expr, Fraction(1))
        return var_coefs, constant

