import z3
import sys

def is_fpNeg(a):
    return a.decl().kind() == z3.Z3_OP_FPA_NEG

def is_fpDiv(a):
    return a.decl().kind() == z3.Z3_OP_FPA_DIV

def is_fpMul(a):
    return a.decl().kind() == z3.Z3_OP_FPA_MUL

def is_RNE(a):
    return a.decl().kind() == z3.Z3_OP_FPA_RM_NEAREST_TIES_TO_EVEN

def get_rounding_mode_c_constant(a):
    """Return the C <fenv.h> rounding constant for a Z3 rounding mode expression.
    Exits if RNA (roundNearestTiesToAway) is encountered — no standard C equivalent."""
    kind = a.decl().kind()
    if kind == z3.Z3_OP_FPA_RM_NEAREST_TIES_TO_AWAY:
        raise SystemExit(
            "[stagesat] ERROR: Rounding mode RNA (roundNearestTiesToAway) "
            "has no C equivalent and is not supported.")
    mapping = {
        z3.Z3_OP_FPA_RM_NEAREST_TIES_TO_EVEN: "FE_TONEAREST",
        z3.Z3_OP_FPA_RM_TOWARD_POSITIVE:       "FE_UPWARD",
        z3.Z3_OP_FPA_RM_TOWARD_NEGATIVE:       "FE_DOWNWARD",
        z3.Z3_OP_FPA_RM_TOWARD_ZERO:           "FE_TOWARDZERO",
    }
    return mapping.get(kind, None)

def is_rounding_mode(a):
    """Check if expression is a floating-point rounding mode."""
    kind = a.decl().kind()
    if kind in [
        z3.Z3_OP_FPA_RM_NEAREST_TIES_TO_EVEN,
        z3.Z3_OP_FPA_RM_NEAREST_TIES_TO_AWAY,
        z3.Z3_OP_FPA_RM_TOWARD_POSITIVE,
        z3.Z3_OP_FPA_RM_TOWARD_NEGATIVE,
        z3.Z3_OP_FPA_RM_TOWARD_ZERO
    ]:
        return True
    # Uninterpreted RoundingMode variable — not supported
    if str(a.sort()) == 'RoundingMode':
        print(
            f"[stagesat] Unsupported: '{a.decl().name()}' is an uninterpreted "
            "RoundingMode variable. StageSAT cannot optimize over RoundingMode. "
            "Exiting.",
            file=sys.stderr
        )
        sys.exit(1)
    return False

def is_fpAdd(a):
    return a.decl().kind() == z3.Z3_OP_FPA_ADD

def is_lt(a):
    return a.decl().kind() == z3.Z3_OP_LT or a.decl().kind() == z3.Z3_OP_FPA_LT

def is_le(a):
    return a.decl().kind() == z3.Z3_OP_LE or a.decl().kind() == z3.Z3_OP_FPA_LE

def is_ge(a):
    return a.decl().kind() == z3.Z3_OP_GE or a.decl().kind() == z3.Z3_OP_FPA_GE

def is_eq(a):
    return a.decl().kind() == z3.Z3_OP_EQ or a.decl().kind() == z3.Z3_OP_FPA_EQ

def is_distinct(a):
    return a.decl().kind()==z3.Z3_OP_DISTINCT # no FPA_DISTINCT

def is_gt(a):
    return a.decl().kind()==z3.Z3_OP_GT or a.decl().kind()==z3.Z3_OP_FPA_GT

def is_true(a):
    return a.decl().kind()==z3.Z3_OP_TRUE

def is_false(a):
    return a.decl().kind()==z3.Z3_OP_FALSE

def is_fpFP(a):
    return a.decl().kind() == z3.Z3_OP_FPA_TO_FP

def is_variable(a):
    return z3.is_const(a) and a.decl().kind() == z3.Z3_OP_UNINTERPRETED

def is_value(a):
    return z3.is_const(a) and a.decl().kind() != z3.Z3_OP_UNINTERPRETED