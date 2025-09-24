import os
import sys
import struct
import importlib
import warnings
import numpy as np
import scipy.optimize as op
import multiprocessing as mp
import importlib.util

import warnings
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
    return X ** ((i + 1) % 4)

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
    #        raise ValueError('out of range')
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


def get_sp(X_star, f32_indices):
    import random
    for ind in range(len(X_star)):
        rand = random.randint(-1, 1)
        if ind in f32_indices:
            X_star[ind] = nth_fp32_vectorized(rand, X_star[ind])
        else:
            X_star[ind] = nth_fp_vectorized(rand, X_star[ind])
    return X_star

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
        sp = np.zeros(foo_square.dim) + args.startPoint + i + np.random.uniform(-0.05, 0.05, foo_square.dim)
        res = op.basinhopping(lambda X: R_quick(X, i, foo_square.R), sp, niter=args.niter, stepsize=args.stepSize,
                              minimizer_kwargs=_minimizer_kwargs)
        # if args.showResult:
        #     print("result (round 1) with i = ", i, ":")
        #     # print(f"{res.fun} + {scale(res.x, i)}")
        #     print(f"{res.fun}")
        #     print()
        X_star = scale(res.x, i)
        R_star = res.fun
        if res.fun >= args.round2_threshold:
            continue
        ########################################################################################
        # if args.showTime:
        #     print("[Xsat] round2_move!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        sp2 = np.array([X_star + 0]) if X_star.ndim == 0 else X_star
        def obj_near2(N):
            X2_moved = np.array([
                nth_fp_dispatchers[j](n_val, x_base_val)
                for j, (n_val, x_base_val) in enumerate(zip(N, sp2))
            ])
            return foo_ulp.R(*X2_moved)
        res_round2 = op.basinhopping(obj_near2, np.zeros(foo_ulp.dim), niter=args.round2_niter,
                                     stepsize=args.round2_stepsize, minimizer_kwargs=_minimizer_kwargs,
                                     callback=_callback_global)
        R_star = res_round2.fun
        X_star = np.array([
                    nth_fp_dispatchers[j](n_val, x_base_val)
                    for j, (n_val, x_base_val) in enumerate(zip(res_round2.x, sp2))])
        if R_star < best_R_star:
            best_R_star = R_star
            best_X_star = X_star
            print(f"//////////////////////////////R2 found a best_R_star: {best_R_star} + R1: {res.fun}")
        if best_R_star == 0:
            break
        # if res_round2.fun >= args.round3_threshold:
        #     continue
        ########################################################################################
        # X = [-4.842073917388916, -1.217218041419983,
        #      -20390302.151690435, 20.666431427001953,
        #      20.666433334350586, 3.9779841899871826,
        #      20.666433334350586, 3.9779841899871826,
        #      20.666433334350586, 3.9779841899871826,
        #      20.666433334350586, 3.9779841899871826,
        #      20.666433334350586, 3.9779841899871826,
        #      20.666433334350586, 3.9779841899871826,
        #      20.666433334350586, 3.9779841899871826,
        #      20.666433334350586, 3.9779841899871826,
        #      20.666433334350586, -14.671028035174352,
        #      14.671028137207031, -11.44757080078125,
        #      20.666431705660145, -457.0663146972656]
        # if
        ########################################################################################
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