from fractions import Fraction
from decimal import Decimal

def F(x):
    if isinstance(x, Fraction): return x
    return Fraction(Decimal(str(x)))

class DSU:
    """
    val(v) = alpha[v]*val(parent[v]) + beta[v]
    Root may carry an anchor (val(root) = const).
    """
    def __init__(self, vars_list):
        self.vars = list(vars_list)
        self.idx  = {v:i for i,v in enumerate(self.vars)}
        n = len(self.vars)
        self.parent = list(range(n))
        self.rank   = [0]*n
        self.alpha  = [F(1)]*n
        self.beta   = [F(0)]*n
        self.has_anchor = [False]*n
        self.anchor     = [F(0)]*n

    def _compose(self, a1, b1, a2, b2):
        # (a1*x + b1) ∘ (a2*x + b2) = a1*(a2*x + b2) + b1
        return (a1*a2, a1*b2 + b1)

    def _find_raw(self, i):
        if self.parent[i] == i:
            return (i, F(1), F(0))
        (r, Ap, Bp) = self._find_raw(self.parent[i])
        Ai, Bi = self.alpha[i], self.beta[i]
        Anew, Bnew = self._compose(Ai, Bi, Ap, Bp)
        self.parent[i] = r
        self.alpha[i], self.beta[i] = Anew, Bnew
        return (r, Anew, Bnew)

    def find(self, v):
        i = self.idx[v]
        return self._find_raw(i)

    def _attach(self, ry, rx, A, B):
        self.parent[ry] = rx
        self.alpha[ry]  = A
        self.beta[ry]   = B
        if self.rank[ry] == self.rank[rx]:
            self.rank[rx] += 1

    def _set_anchor(self, r, c):
        if not self.has_anchor[r]:
            self.has_anchor[r] = True
            self.anchor[r] = c
        else:
            if self.anchor[r] != c:
                raise ValueError("UNSAT: conflicting anchors")

    def union_constraint(self, x, a, b, y, c, d):
        """
        a*x + b = c*y + d.
        """
        # both sides constant?
        if x is None and y is None:
            if b != d: raise ValueError("UNSAT: constant != constant")
            return

        # single var side -> direct anchor
        if x is not None and y is None:
            rx, Ax, Bx = self.find(x)
            val_root = (d - b) / a
            self._set_anchor(rx, val_root)
            return

        if x is None and y is not None:
            ry, Ay, By = self.find(y)
            val_root = (b - d) / c
            self._set_anchor(ry, val_root)
            return

        # two variables: normalize to x = A*y + B
        A = c / a
        B = (d - b) / a

        rx, Ax, Bx = self.find(x)
        ry, Ay, By = self.find(y)

        if rx != ry:
            # Ax*rx + Bx = A*(Ay*ry + By) + B
            # => ry = (Ax/(A*Ay))*rx + (Bx - A*By - B)/(A*Ay)
            U = Ax / (A * Ay)
            V = (Bx - A*By - B) / (A * Ay)
            self._attach(ry, rx, U, V)

            # propagate anchors
            if self.has_anchor[ry]:
                if U == 0:
                    if self.anchor[ry] != V:
                        raise ValueError("UNSAT: anchor conflict via zero U")
                else:
                    c_rx = (self.anchor[ry] - V) / U
                    self._set_anchor(rx, c_rx)
            # if rx anchored already, nothing else to do

        else:
            # close cycle at root rx
            # Ax*root + Bx = A*(Ay*root + By) + B
            L = Ax - A*Ay
            R = A*By + B - Bx
            if L == 0:
                if R != 0: raise ValueError("UNSAT: inconsistent cycle")
            else:
                self._set_anchor(rx, R / L)