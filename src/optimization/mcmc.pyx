import os
import sys
import time
import struct
import importlib
import warnings
import random
import numpy as np
cimport numpy as cnp
import scipy.optimize as op
import multiprocessing as mp
import importlib.util
cimport cython
from libc.stdint cimport uint64_t, uint32_t, int64_t, int32_t
from libc.string cimport memcpy
# Type definitions
ctypedef cnp.float64_t DTYPE_t
ctypedef cnp.float32_t DTYPE32_t

warnings.filterwarnings('ignore', category=RuntimeWarning)

sys.path.insert(0, os.path.join(os.getcwd(), "build/R_ulp"))
import foo_ulp
importlib.reload(foo_ulp)
sys.path.insert(0, os.path.join(os.getcwd(), "build/R_square"))
import foo_square
importlib.reload(foo_square)
import foo_square_large
importlib.reload(foo_square_large)

class BasinHoppingCallback:
    """Callback class for basin hopping optimization."""
    def __init__(self, stop_event):
        self.stop_event = stop_event
    def __call__(self, x, f, accepted):
        if self.stop_event.is_set():
            return True  # Stop the optimization
        if f == 0:
            return True  # Also a stop condition
        return False

def tr_help(cnp.ndarray X):
    if X.ndim == 0:
        return np.array([X])
    else:
        return X

def noop_min(fun, x0, args, **options):
    return op.OptimizeResult(x=x0, fun=fun(x0), success=True, nfev=1)

cpdef cnp.ndarray scale(cnp.ndarray X, int i):
    return X ** (i + 1)

def R_quick(cnp.ndarray X, int i, f):
    return f(*scale(X, i))

def mcmc_bis(int i):
    print("*******value of i = ", i)

@cython.boundscheck(False)
@cython.wraparound(False)
cdef inline double nth_fp(long long n, double x) nogil:
    """
    Get the nth floating point number from x.
    """
    cdef uint64_t bits, sign_bit
    cdef int64_t m
    cdef double result
    if x < 0:
        return -nth_fp(-n, -x)
    memcpy(&bits, &x, sizeof(double))
    m = <int64_t> bits + n
    if m < 0:
        sign_bit = 0x8000000000000000ULL
        m = -m
    else:
        sign_bit = 0
    if m >= 0x7ff0000000000000LL:
        m = 0x7ff0000000000000LL
    bits = <uint64_t> m | sign_bit
    memcpy(&result, &bits, sizeof(double))
    return result

@cython.boundscheck(False)
@cython.wraparound(False)
cdef inline float nth_fp32(long n, float x) nogil:
    """
    Get the nth floating point number from x.
    """
    cdef uint32_t bits, sign_bit
    cdef int32_t m
    cdef float result
    if x < 0:
        return -nth_fp32(-n, -x)
    memcpy(&bits, &x, sizeof(float))
    m = <int32_t> bits + n
    if m < 0:
        sign_bit = 0x80000000U
        m = -m
    else:
        sign_bit = 0
    if m >= 0x7f800000:
        m = 0x7f800000
    bits = <uint32_t> m | sign_bit
    memcpy(&result, &bits, sizeof(float))
    return result

@cython.boundscheck(False)
@cython.wraparound(False)
@cython.cdivision(True)
cpdef cnp.ndarray transform_fp_separated(
        cnp.ndarray[cnp.float64_t, ndim=1] N,
        cnp.ndarray[cnp.float64_t, ndim=1] sp3,
        cnp.ndarray[cnp.int64_t, ndim=1] f32_positions,
        cnp.ndarray[cnp.int64_t, ndim=1] f64_positions):
    cdef Py_ssize_t i, idx
    cdef Py_ssize_t size = N.shape[0]
    cdef Py_ssize_t n_f32 = f32_positions.shape[0]
    cdef Py_ssize_t n_f64 = f64_positions.shape[0]
    cdef cnp.ndarray[cnp.float64_t, ndim=1] result = np.empty(size, dtype=np.float64)
    cdef long long n_val_i64
    cdef long n_val_i32
    for i in range(n_f32):
        idx = f32_positions[i]
        n_val_i32 = <long> N[idx]
        result[idx] = nth_fp32(n_val_i32, <float> sp3[idx])
    for i in range(n_f64):
        idx = f64_positions[i]
        n_val_i64 = <long long> N[idx]
        result[idx] = nth_fp(n_val_i64, sp3[idx])
    return result

def mcmc(args, int i, stop_event):
    cdef double start_time = time.process_time()
    # Load float32 mask to determine which variables are float32
    cdef cnp.ndarray f32_mask
    with open("build/f32_mask.npy", "rb") as f:
        f32_mask = np.load(f)
    cdef cnp.ndarray f32_positions = np.where(f32_mask)[0].astype(np.int64)
    cdef cnp.ndarray f64_positions = np.where(~f32_mask)[0].astype(np.int64)
    cdef cnp.ndarray best_X_star = np.zeros(foo_square.dim)
    cdef double best_R_star = float('inf')
    callback = BasinHoppingCallback(stop_event)
    cdef int round_num
    cdef cnp.ndarray sp, sp2, sp3, X_star
    cdef double R_star, rec
    cdef double noise_range
    cdef dict _minimizer_kwargs
    R_func = foo_square_large.R if args.use_large else foo_square.R
    # Main optimization loop
    for round_num in range(args.nStartOver):
        if stop_event.is_set():
            break
        np.random.seed()
        _minimizer_kwargs = dict(method=noop_min) if args.method == 'noop_min' else dict(method=args.method)
        noise_range = 0 if args.use_large else (0.5 if random.random() < 0.2 else 0)
        sp = np.zeros(foo_square.dim) + args.startPoint + np.random.uniform(-noise_range, noise_range, foo_square.dim)
        is_r1_bad = (round_num / args.nStartOver) >= args.round2_activate and best_R_star > args.round2_threshold
        # Round 1: Basin hopping with square objective
        res = op.basinhopping(
            lambda X: R_quick(X, i, R_func),
            sp,
            niter=args.niter,
            stepsize=1 if is_r1_bad else args.stepSize,
            minimizer_kwargs=_minimizer_kwargs,
            callback=callback
        )
        if args.showResult:
            print("result (round 1) with i = ", i, ":")
            print(f"{res.fun}")
            print()
        X_star = scale(res.x, i)
        # Skip if result is too poor
        if res.fun >= args.round1_threshold:
            continue
        ########################################################################
        # Optional Round 2: ULP-based refinement when round 1 is not good enough
        ########################################################################
        if is_r1_bad:
            if args.showTime:
                print("[stagesat] round2_move!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
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
        ########################################################################
        # Round 3: Floating point neighborhood search
        ########################################################################
        if args.showTime:
            print("[stagesat] round3_move!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        if stop_event.is_set():
            break
        sp3 = np.array([X_star + 0]) if X_star.ndim == 0 else X_star
        def obj_near3(N):
            X3_moved = transform_fp_separated(N, sp3, f32_positions, f64_positions)
            return foo_ulp.R(*X3_moved)
        res_round3 = op.basinhopping(
            obj_near3,
            np.zeros(foo_ulp.dim),
            niter=args.round3_niter,
            stepsize=args.round3_stepsize,
            minimizer_kwargs=_minimizer_kwargs,
            callback=callback
        )
        R_star = res_round3.fun
        X_star = transform_fp_separated(res_round3.x, sp3, f32_positions, f64_positions)
        if R_star < best_R_star:
            best_R_star = R_star
            best_X_star = X_star
            if args.showResult:
                print(f"//////////////////////////////R3 found a best_R_star: {best_R_star} + R1: {res.fun}")
        if best_R_star == 0:
            break
    cdef double elapsed_time = time.process_time() - start_time
    return best_X_star, best_R_star, elapsed_time