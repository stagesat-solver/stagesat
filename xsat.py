import sympy
import z3
import numpy as np
import scipy.optimize as op
import argparse
import sys, os
import time
import collections
import subprocess
import multiprocessing as mp
import warnings
import struct
import pickle
import importlib
import threading

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.utils.sort import Sort
import src.optimization.mcmc_cython as op_mcmc
import src.utils.verification as verification
np.set_printoptions(precision=2000, suppress=True)

def str2bool(v: str) -> bool:
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def create_typed_input(X, symbolTable):
    """Convert numpy array to correct types based on symbolTable"""
    typed_X = []
    for idx, (var, var_type) in enumerate(symbolTable.items()):
        if var_type == Sort.Float32:
            typed_X.append(np.float32(X[idx]))
        else:  # Float64 or other types
            typed_X.append(np.float64(X[idx]))
    return typed_X

def worker_process(args, worker_id, queue, stop_event):
    """The function that each worker process will execute."""
    result = op_mcmc.mcmc(args, worker_id, stop_event)
    queue.put(result)

def get_parser():
    parser = argparse.ArgumentParser(prog='Xsat')
    parser.add_argument('-v', '--version', action='version', version='%(prog) version 2.0.0')
    parser.add_argument('--niter', help='niter in basinhopping', action='store', type=int, required=False, default=30)
    parser.add_argument('--nStartOver', help='startOver times', action='store', type=int, required=False, default=20)
    parser.add_argument('--method', help='Local minimization procedure', default='powell',
                        choices=['powell', 'slsqp', 'cg', 'l-bfgs-b', 'cobyla', 'tnc', 'bfgs', 'nelder-mead',
                                 'noop_min']
                        )
    parser.add_argument('--showTime', help='show the time-related info (default: false)', action='store_true',
                        default=False)
    parser.add_argument('--showResult', help='show the basinhopping output (default:false)', action='store_true',
                        default=False)
    parser.add_argument('--stepSize', help='parameter of basinhopping', type=float, default=1e-3)
    parser.add_argument('--round2_stepsize', help='parameter of basinhopping', type=float, default=1e-3)
    parser.add_argument('--verify', help='verify the model', action='store_true', default=False)
    parser.add_argument('--verify2', help='verify the model (method 2)', action='store_true', default=True)
    parser.add_argument('--showModel', help='show the model as a var->value mapping', action='store_true',
                        default=False)
    parser.add_argument('--showSymbolTable', help='show the symbol table, var->type', action='store_true',
                        default=False)
    parser.add_argument('--showConstraint', help='show the constraint, using the Z3 frontend', action='store_true',
                        default=False)
    parser.add_argument('--showVariableNumber', help='show variable number, using the Z3 frontend', action='store_true',
                        default=False)

    # TODO: previously hardcode compile command, need to check it out
    parser.add_argument('--command_compilation', help='the command used to compile the generated foo.c to foo.so',
                        default='gcc -O3 -fbracket-depth=2048 -fPIC -I /usr/local/Cellar/python/2.7.9/Frameworks/Python.framework/Versions/2.7/include/python2.7/ %(file)s.c -dynamiclib -o %(file)s.so -L /usr/local/Cellar/python/2.7.9/Frameworks/Python.framework/Versions/Current/lib/ -lpython2.7')

    parser.add_argument('--startPoint', help='start point in a single dimension', action='store', type=float,
                        default=1.0)
    parser.add_argument('--round1_threshold', help='threshold  for round1', action='store', type=float, default=1e-11)
    parser.add_argument('--round2_threshold', help='threshold  for round2', action='store', type=float, default=1e10)
    parser.add_argument('--round2_activate', help='threshold  for round2', action='store', type=float, default=10)
    parser.add_argument("--multi", help="multi-processing (default: true)", default=True, action='store', type=str2bool)
    # parser.add_argument("--single", help="single processor  (default: true)",default=True,action='store')
    # parser.add_argument("--round2", help="activate round2 when unsat (default: false)",default=False,action='store_true')
    parser.add_argument("--round2_niter", help="niter for round2", action='store', type=int, required=False, default=10)
    parser.add_argument("--round3_niter", help="niter for round3", action='store', type=int, required=False, default=10)
    parser.add_argument("--round3_stepsize", help="stepsize for round3", action='store', type=float, required=False,
                        default=10.0)
    parser.add_argument("--suppressWarning", help="Suppress warnings", default=False, action='store_true')
    parser.add_argument("--debug", help="debug mode (with verify and showresults, etc.)", default=True,
                        action='store_true')
    parser.add_argument("--printModel", help="print the model", default=False, action='store_true')
    parser.add_argument("--bench", help="benchmarking mode", default=False, action='store_true')
    parser.add_argument("--genOnly", help="generate code only, without deciding satisfiability", default=False,
                        action='store_true')
    return parser

def configure(args):
    if args.bench:
        args.debug = False
        args.verify = False
        args.verify2 = False
        args.showResult = False
        args.showTime = False
        args.suppressWarning = True
        args.multi = True
    if args.debug:
        args.verify = True
        args.verify2 = True
        args.showResult = True
        args.showTime = True
        args.suppressWarning = False
    return

def main():
    parser = get_parser()
    args = parser.parse_args()
    configure(args)
    if args.suppressWarning:
        warnings.filterwarnings("ignore")
    t_start = time.time()
    # use z3 frontend
    with open("XSAT_IN.txt") as f:
        try:
            expr_z3_lis = z3.parse_smt2_file(f.read().rstrip())
            expr_z3 = z3.And(expr_z3_lis)
            expr_z3 = z3.simplify(expr_z3)
        except z3.Z3Exception as e:
            print(e)
            sys.stderr.write("[Xsat] The Z3 front-end fails when verifying the model.\n")
    with open("build/foo.symbolTable", "rb") as f:
        symbolTable = pickle.load(f)
    if len(symbolTable) == 0:
        print("sat")
        sys.exit(0)
    try:
        names = list(symbolTable.keys())
        types = list(symbolTable.values())
        f32_mask = np.array([t == Sort.Float32 for t in types], dtype=bool)
        os.makedirs("build", exist_ok=True)
        with open("build/f32_mask.npy", "wb") as _f:
            np.save(_f, f32_mask)
    except Exception as _e:
        print("[Xsat] Warning: failed to persist f32 mask:", _e)
    if args.showTime:
        print("[Xsat] ENTERING: main_multi")
    results_queue = mp.Queue()
    stop_event = mp.Event()
    processes = [mp.Process(target=worker_process, args=(args, i, results_queue, stop_event))
                 for i in range(mp.cpu_count())]
    for p in processes:
        p.start()
    X_star = None
    R_star = float('inf')
    num_workers_finished = 0
    worker_times = []
    try:
        while num_workers_finished < len(processes):
            X, R, cpu_time = results_queue.get()
            worker_times.append(cpu_time)
            num_workers_finished += 1
            if R <= R_star:
                R_star = R
                X_star = X
            if R_star == 0:
                if args.showTime:
                    print("[Xsat Host] Optimal solution found. Terminating workers.")
                stop_event.set()
                break
    finally:
        for p in processes:
            if p.is_alive():
                p.terminate()
            p.join()
    if X_star.ndim == 0: X_star = np.array([X_star[()]])
    if R_star == 0:
        print('sat')
    else:
        print('unsat')
    has_float32 = any(t == Sort.Float32 for t in symbolTable.values())
    if has_float32:
        X_star = np.array(create_typed_input(X_star, symbolTable))
    if args.showResult:
        print(f"X_star (final) {X_star}")
        print(f"R_star (final) {R_star}")
    t_mcmc = time.time()
    if args.verify:
        if args.showTime:
            print("[Xsat] verify X_star with z3 front-end")
        verified = verification.verify_solution(expr_z3, X_star, symbolTable, printModel=args.printModel)
        if verified and R_star != 0:
            sys.stderr.write("WARNING!!!!!!!!!!!!!!!! Actually sat.\n")
        elif not verified and R_star == 0:
            sys.stderr.write("WARNING!!!!!!!!!!!!!!!  Wrong model !\n")
        else:
            pass
    if args.verify2:
        if args.showTime:
            print("[Xsat] verify X_star with build/R_verify")
        sys.path.insert(0, os.path.join(os.getcwd(), "build/R_verify"))
        import foo_verify
        importlib.reload(foo_verify)
        verify_res = foo_verify.R(*X_star) if foo_verify.dim == 1 else foo_verify.R(*(X_star))
        if verify_res == 0 and R_star != 0:
            sys.stderr.write("WARNING from verify2 (using include/R_verify/xsat.h) !!!!!!!!!!!!!!!! Actually sat.\n")
        elif verify_res != 0 and R_star == 0:
            sys.stderr.write("WARNING from verify2  (using include/R_verify/xsat.h) !!!!!!!!!!!!!!!  Wrong model ! \n")
        else:
            pass
    t_verify = time.time()
    if args.showSymbolTable:
        print(symbolTable)
    if args.showConstraint:
        print(expr_z3)
    if args.showVariableNumber:
        print("nVar = ", len(symbolTable))
    if args.showTime:
        print("[Xsat] Time elapsed:")
        print("  solve (all) cpu time : %g seconds" % (max(worker_times)))
        print("  verify : %g seconds" % (t_verify - t_mcmc))
        print("\n  Total        : %g seconds" % (t_verify - t_start))


if __name__ == "__main__":
    main()