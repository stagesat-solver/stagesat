import os
import sys
import struct
import importlib
import warnings
import random
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

class BasinHoppingCallback:
    def __init__(self, stop_event):
        self.stop_event = stop_event

    def __call__(self, x, f, accepted):
        if self.stop_event.is_set():
            return True  # Stop the optimization
        if f == 0:
            return True  # Also a stop condition
        return False

def tr_help(X):
    if X.ndim == 0:
        return np.array([X])
    else:
        return X

def noop_min(fun, x0, args, **options):
    return op.OptimizeResult(x=x0, fun=fun(x0), success=True, nfev=1)

def scale(X, i):
    return X ** (i + 1)

def R_quick(X, i, f):
    return f(*scale(X, i))

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
    if m < 0:
        sign_bit = 0x8000000000000000
        m = -m
    else:
        sign_bit = 0
    if m >= 0x7ff0000000000000:
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
        m = 0x7f800000
    bit_pattern = struct.pack('I', m | sign_bit)
    return struct.unpack('f', bit_pattern)[0]

def mcmc(args, i, stop_event):
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
    callback = BasinHoppingCallback(stop_event)
    for round_num in range(args.nStartOver):
        if stop_event.is_set():
            break
        np.random.seed()
        _minimizer_kwargs = dict(method=noop_min) if args.method == 'noop_min' else dict(method=args.method)
        noise_range = 0.5 if random.random() < 0.2 else 5e-50
        sp = np.zeros(foo_square.dim) + args.startPoint + np.random.uniform(-noise_range, noise_range, foo_square.dim)
        res = op.basinhopping(lambda X: R_quick(X, i, foo_square.R), sp, niter=args.niter, stepsize=args.stepSize,
                              minimizer_kwargs=_minimizer_kwargs, callback=callback)
        if args.showResult:
            print("result (round 1) with i = ", i, ":")
            print(f"{res.fun}")
            print()
        X_star = scale(res.x, i)
        # R_star = res.fun
        if res.fun >= args.round1_threshold:
            # bad results, retry
            continue
        ########################################################################################
        # optional round 2, do it when r1 round is bad
        if round_num > args.round2_activate and best_R_star > args.round2_threshold:
            if args.showTime:
                print("[Xsat] round2_move!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            if stop_event.is_set():
                break
            rec = foo_ulp.R(*X_star)
            sp2 = np.array([X_star + 0]) if X_star.ndim == 0 else X_star
            res_round2 = op.basinhopping(
                lambda X: foo_ulp.R(*scale(X, i)),
                sp2,
                niter=args.round2_niter,
                stepsize=args.round2_stepsize,
                minimizer_kwargs=_minimizer_kwargs,
                callback=callback
            )
            if stop_event.is_set():
                break
            if res_round2.fun < rec:
                R_star = res_round2.fun
                X_star = scale(tr_help(res_round2.x), i)
            else:
                R_star = rec
            if R_star < best_R_star:
                best_R_star = R_star
                best_X_star = X_star
                if args.showResult:
                    print(f"//////////////////////////////R2 found a best_R_star: {best_R_star} + R1: {res.fun}")
            if best_R_star == 0:
                break
        ########################################################################################
        if args.showTime:
            print("[Xsat] round3_move!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        if stop_event.is_set():
            break
        sp3 = np.array([X_star + 0]) if X_star.ndim == 0 else X_star
        def obj_near3(N):
            X3_moved = np.array([
                nth_fp_dispatchers[j](n_val, x_base_val)
                for j, (n_val, x_base_val) in enumerate(zip(N, sp3))
            ])
            return foo_ulp.R(*X3_moved)
        res_round3 = op.basinhopping(obj_near3, np.zeros(foo_ulp.dim), niter=args.round3_niter,
                                     stepsize=args.round3_stepsize, minimizer_kwargs=_minimizer_kwargs,
                                     callback=callback)
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