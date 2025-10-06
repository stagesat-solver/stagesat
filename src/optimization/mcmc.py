import os
import sys
import struct
import importlib
import warnings
import numpy as np
import scipy.optimize as op
import multiprocessing as mp
import importlib.util

warnings.filterwarnings('ignore', category=RuntimeWarning)

sys.path.insert(0, os.path.join(os.getcwd(), "build/R_ulp"))
import foo_ulp
importlib.reload(foo_ulp)
sys.path.insert(0, os.path.join(os.getcwd(), "build/R_square"))
import foo_square
importlib.reload(foo_square)

foundit = mp.Event()
def _callback_global(x, f, accepted):
    if f == 0 or foundit.is_set():
        foundit.set()
        return True

#to handle an issue due to 'powell': it returns a zero-dimensional array even if the starting point is of one dimension.
def tr_help(X):
        if X.ndim == 0: return np.array([X])
        else: return X

def scales():
    return [(lambda x: x ** 11, lambda x: np.sign(x) * np.abs(x) ** (1.0/11)),
            (lambda x: x ** 17, lambda x: np.sign(x) * np.abs(x) ** (1.0/17)),
            (lambda x: x ** 25, lambda x: np.sign(x) * np.abs(x) ** (1.0/25))]

def noop_min(fun, x0, args, **options):
    return op.OptimizeResult(x=x0, fun=fun(x0), success=True, nfev=1)

def scale(X, i):
    return X ** (i + 1)

def R_quick(X,i,f):
    return f(* scale(X,i))

def mcmc_bis(i):
    print("*******value of i = ", i)

# little-endian
@np.vectorize
def nth_fp_vectorized(n, x):
    if x < 0: return -nth_fp_vectorized(-n, -x)
    n = int(n)
    s = struct.pack('<d', x)
    i = struct.unpack('<Q', s)[0]
    m = i + n
    # m = n + struct.unpack('!i',struct.pack('!f',x))[0]
    if m < 0:
        sign_bit = 0x8000000000000000
        m = -m
    else:
        sign_bit = 0
    if m >= 0x7ff0000000000000:
        warnings.warn("Value out of range, with n= %g,x=%g,m=%g, process=%g" % (n, x, m, mp.current_process.name))
        m = 0x7ff0000000000000
    bit_pattern = struct.pack('Q', m | sign_bit)
    return struct.unpack('d', bit_pattern)[0]

@np.vectorize
def nth_fp32_vectorized(n, x):
    if x < 0: return -nth_fp32_vectorized(-n, -x)
    n = int(n)
    x_f32 = np.float32(x)
    s = struct.pack('<f', x_f32)
    i = struct.unpack('<I', s)[0]
    m = i + n
    if m < 0:
        sign_bit = 0x80000000
        m = -m
    else:
        sign_bit = 0
    if m >= 0x7f800000:  # Float32 infinity
        # warnings.warn(f"Float32 value out of range, n={n}, x={x}")
        m = 0x7f800000
    bit_pattern = struct.pack('I', m | sign_bit)
    return struct.unpack('f', bit_pattern)[0]

def mcmc(args, i):
    with open("build/f32_mask.npy", "rb") as f:
        f32_mask = np.load(f)
    f32_indices = np.where(f32_mask)[0]
    f64_indices = np.where(~f32_mask)[0]
    nth_fp_dispatchers = [
        nth_fp32_vectorized if j in f32_indices else nth_fp_vectorized
        for j in range(foo_square.dim)
    ]
    best_X_star = np.zeros(foo_square.dim)
    best_R_star = float('inf')
    for round_num in range(args.nStartOver):
        np.random.seed()
        _minimizer_kwargs = dict(method=noop_min) if args.method == 'noop_min' else dict(method=args.method)
        sp = np.zeros(foo_square.dim) + args.startPoint + (i % 4) + np.random.uniform(-0.05, 0.05, foo_square.dim)
        # sp = np.zeros(foo_square.dim) + np.random.uniform(-0.05, 0.05, foo_square.dim)
        res = op.basinhopping(lambda X: R_quick(X, i, foo_square.R), sp, niter=args.niter, stepsize=args.stepSize,
                              minimizer_kwargs=_minimizer_kwargs)
        if args.showResult:
            print("result (round 1) with i = ", i, ":")
            # print(f"{res.fun} + {scale(res.x, i)}")
            print(f"{res.fun}")
            print()
        X_star = scale(res.x, i)
        R_star = res.fun
        if res.fun >= args.round2_threshold:
            continue
        ########################################################################################
        # if args.showTime:
        #     print("[Xsat] round2_move!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        # sp2 = np.array([X_star + 0]) if X_star.ndim == 0 else X_star
        # res_round2 = op.basinhopping(
        #     lambda X: foo_ulp.R(*scale(X, i)),
        #     sp2,
        #     niter=args.round2_niter,
        #     stepsize=args.round2_stepsize,
        #     minimizer_kwargs=_minimizer_kwargs,
        #     callback=_callback_global
        # )
        # R_star = res_round2.fun
        # X_star = scale(tr_help(res_round2.x), i)
        # if R_star < best_R_star:
        #     best_R_star = R_star
        #     best_X_star = X_star
        #     print(f"//////////////////////////////R2 found a best_R_star: {best_R_star} + R1: {res.fun}")
        # if best_R_star == 0:
        #     break
        # if res_round2.fun >= args.round3_threshold:
        #     continue
        ########################################################################################
        if args.showTime:
            print("[Xsat] round3_move!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        sp3 = np.array([X_star + 0]) if X_star.ndim == 0 else X_star
        def obj_near3(N):
            X3_moved = np.array([
                nth_fp_dispatchers[j](n_val, x_base_val)
                for j, (n_val, x_base_val) in enumerate(zip(N, sp3))
            ])
            return foo_ulp.R(*X3_moved)
        res_round3 = op.basinhopping(obj_near3, np.zeros(foo_ulp.dim), niter=args.round3_niter,
                                     stepsize=args.round3_stepsize, minimizer_kwargs=_minimizer_kwargs,
                                     callback=_callback_global)
        R_star = res_round3.fun
        X_star = np.array([
            nth_fp_dispatchers[j](n_val, x_base_val)
            for j, (n_val, x_base_val) in enumerate(zip(res_round3.x, sp3))])
        if R_star < best_R_star:
            best_R_star = R_star
            best_X_star = X_star
            if args.showResult:
                print(f"//////////////////////////////R3 found a best_R_star: {best_R_star} + R1: {res.fun}")
        if best_R_star == 0:
            break
    return best_X_star, best_R_star


import math
SIGN_BIT_MASK = 1 << 63
def ordered_bits_py(d: float) -> int:
    u, = struct.unpack('Q', struct.pack('d', d))
    if u & SIGN_BIT_MASK:
        return ~u
    else:
        return u ^ SIGN_BIT_MASK

def ulp_py(x: float, y: float) -> float:
    if not math.isfinite(x) or not math.isfinite(y):
        return float('inf')
    a = ordered_bits_py(x)
    b = ordered_bits_py(y)
    distance = abs(a - b)
    return float(distance)


def double_to_parts(d):
    # Get the 64-bit representation
    bits = struct.unpack('>Q', struct.pack('>d', d))[0]
    sign = (bits >> 63) & 1
    # Exponent: bits 62-52 (11 bits)
    exponent = (bits >> 52) & 0x7FF
    # Mantissa: bits 51-0 (52 bits)
    mantissa = bits & 0xFFFFFFFFFFFFF
    # Convert to hex string (13 hex digits for 52 bits)
    mantissa_hex = format(mantissa, '013x')
    return sign, exponent, mantissa_hex

def smt_fp_to_double(sign: int, exponent_str: str, mantissa_hex_str: str) -> float:
    exponent = int(exponent_str, 2)
    mantissa = int(mantissa_hex_str, 16)
    as_uint64 = (sign << 63) | (exponent << 52) | mantissa
    packed = struct.pack('Q', as_uint64)
    return struct.unpack('d', packed)[0]

def smt_fp_to_float(sign: int, exponent_str: str, mantissa_hex_str: str) -> float:
    exponent = int(exponent_str, 2)  # 8-bit exponent
    mantissa = int(mantissa_hex_str, 16)  # 23-bit mantissa
    as_uint32 = (sign << 31) | (exponent << 23) | mantissa
    packed = struct.pack('I', as_uint32)  # 'I' = unsigned int (32-bit)
    return struct.unpack('f', packed)[0]  # 'f' = float (32-bit)

smt_vars = {
        'b1509': (0, 0x5d, 0b01001000100011011111111),
        'b2090': (0, 0x3b, 0b10010010001110100111101),
        'b1487': (1, 0b01110111011, 0x923a0e0000000),
        'b1506': (1, 0b01110111011, 0x923a0e0000000),
        'b1699': (0, 0x5d, 0b01001000100011011111111),
        'b2172': (0, 0x3b, 0b10010010001110100111101),
        'b1775': (0, 0x5d, 0b01001000100011011111111),
        'b212': (1, 0x3b, 0b01011110011110110101111),
        'b1482': (1, 0b01110111011, 0x923a0e0000000),
        'b1490': (0, 0x5d, 0b01001000100011011111111),
        'b1838': (0, 0x3b, 0b10010010001110100111101),
        'b1642': (0, 0x5d, 0b01001000100011011111111),
        'b1772': (1, 0b01110111011, 0x923a0e0000000),
        'b1547': (0, 0x5d, 0b01001000100011011111111),
        'b1718': (0, 0x5d, 0b01001000100011011111111),
        'b207': (1, 0x70, 0b00110111110100011100011),
        'b832': (1, 0x5f, 0b10110101011111111111000),
        'b221': (1, 0b10000010001, 0xe5ebb7622b70f),
        'b1756': (0, 0x5d, 0b01001000100011011111111),
        'b210': (0, 0b01110111011, 0x923a3a0000000),
        'b1585': (0, 0x5d, 0b01001000100011011111111),
        'b1563': (1, 0b01110111011, 0x923a0e0000000),
        'b1737': (0, 0x5d, 0b01001000100011011111111),
        'b1677': (1, 0b01110111011, 0x923a0e0000000),
        'b1566': (0, 0x5d, 0b01001000100011011111111),
        'b2153': (0, 0x3b, 0b10010010001110100111101),
        'b1623': (0, 0x5d, 0b01001000100011011111111),
        'b1544': (1, 0b01110111011, 0x923a0e0000000),
        'b1620': (1, 0b01110111011, 0x923a0e0000000),
        'b1680': (0, 0x5d, 0b01001000100011011111111),
        'b1639': (1, 0b01110111011, 0x923a0e0000000),
        'b2181': (0, 0x3b, 0b10010010001110100000111),
        'b2132': (0, 0x3b, 0b10010010001110100111101),
        'b1791': (1, 0b01110111011, 0x923a0e0000000),
        'b1901': (0, 0x3b, 0b10010010001110100111101),
        'b1601': (1, 0b01110111011, 0x923a0e0000000),
        'b1922': (0, 0x3b, 0b10010010001110100111101),
        'b1582': (1, 0b01110111011, 0x923a0e0000000),
        'b1816': (0, 0x3b, 0b10010010001110100111101),
        'b1661': (0, 0x5d, 0b01001000100011011111111),
        'b1964': (0, 0x3b, 0b10010010001110100111101),
        'b818': (0, 0b00000000000, 0x923a0e0000002),
        'b1696': (1, 0b01110111011, 0x923a0e0000000),
        'b1715': (1, 0b01110111011, 0x923a0e0000000),
        'b205': (0, 0x37, 0b00110111001000011100111),
        'b1753': (1, 0b01110111011, 0x923a0e0000000),
        'b1794': (0, 0x5d, 0b01001000100011011111111),
        'b2048': (0, 0x3b, 0b10010010001110100111101),
        'b1477': (0, 0x3b, 0b10010010001110100000111),
        'b1880': (0, 0x3b, 0b10010010001110100111101),
        'b2069': (0, 0x3b, 0b10010010001110100111101),
        'b1734': (1, 0b01110111011, 0x923a0e0000000),
        'b1985': (0, 0x3b, 0b10010010001110100111101),
        'b1474': (1, 0b01110111011, 0x923a0e0000000),
        'b1943': (0, 0x3b, 0b10010010001110100111101),
        'b1528': (0, 0x5d, 0b01001000100011011111111),
        'b2006': (0, 0x3b, 0b10010010001110100111101),
        'b2027': (0, 0x3b, 0b10010010001110100111101),
        'b1604': (0, 0x5d, 0b01001000100011011111111),
        'b1859': (0, 0x3b, 0b10010010001110100111101),
        'b2111': (0, 0x3b, 0b10010010001110100111101),
        'b1525': (1, 0b01110111011, 0x923a0e0000000),
        'b1658': (1, 0b01110111011, 0x923a0e0000000),
}
from collections import OrderedDict
# Type information
type_dict = OrderedDict({
        'b205': 'float32', 'b207': 'float32', 'b221': 'float64', 'b2181': 'float32',
        'b2172': 'float32', 'b1490': 'float32', 'b2153': 'float32', 'b1509': 'float32',
        'b2132': 'float32', 'b1528': 'float32', 'b2111': 'float32', 'b1547': 'float32',
        'b2090': 'float32', 'b1566': 'float32', 'b2069': 'float32', 'b1585': 'float32',
        'b2048': 'float32', 'b1604': 'float32', 'b2027': 'float32', 'b1623': 'float32',
        'b2006': 'float32', 'b1642': 'float32', 'b1985': 'float32', 'b1661': 'float32',
        'b1964': 'float32', 'b1680': 'float32', 'b1943': 'float32', 'b1699': 'float32',
        'b1922': 'float32', 'b1718': 'float32', 'b1901': 'float32', 'b1737': 'float32',
        'b1880': 'float32', 'b1756': 'float32', 'b1859': 'float32', 'b1775': 'float32',
        'b1838': 'float32', 'b1794': 'float32', 'b1816': 'float32', 'b1474': 'float64',
        'b818': 'float64', 'b1791': 'float64', 'b1772': 'float64', 'b1753': 'float64',
        'b1734': 'float64', 'b1715': 'float64', 'b1696': 'float64', 'b1677': 'float64',
        'b1658': 'float64', 'b1639': 'float64', 'b1620': 'float64', 'b1601': 'float64',
        'b1582': 'float64', 'b1563': 'float64', 'b1544': 'float64', 'b1525': 'float64',
        'b1506': 'float64', 'b1487': 'float64', 'b1482': 'float64', 'b1477': 'float32',
        'b212': 'float32', 'b832': 'float32', 'b210': 'float64'
})

# Convert according to type
result_array = []
for var_name, var_type in type_dict.items():
    sign, exp, mant = smt_vars[var_name]
    if var_type == 'float32':
        # Convert to binary/hex strings for float32
        exp_str = format(exp, '08b') if isinstance(exp, int) else bin(exp)[2:].zfill(8)
        mant_str = format(mant, '06x') if isinstance(mant, int) else hex(mant)[2:].zfill(6)
        value = smt_fp_to_float(sign, exp_str, mant_str)
    else:  # float64
        exp_str = format(exp, '011b') if isinstance(exp, int) else bin(exp)[2:].zfill(11)
        mant_str = format(mant, '013x') if isinstance(mant, int) else hex(mant)[2:].zfill(13)
        value = smt_fp_to_double(sign, exp_str, mant_str)
    result_array.append(value)

# Convert to numpy array
result_array = np.array(result_array)
