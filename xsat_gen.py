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
import src.utils.z3_util as z3_util
import src.utils.verification as verification
from src.utils.sort import Sort
from src.parse import LinearityAnalyzer, ExpressionGenerator, CodeTemplate

DEBUG = False

class CodeGenerator:
    """Main orchestrator for code generation from Z3 expressions."""

    def __init__(self):
        self.linearity_analyzer = LinearityAnalyzer()
        self.expr_generator = ExpressionGenerator(self.linearity_analyzer)
        self.template = CodeTemplate()

    def generate(self, expr_z3):
        """Generate C code from Z3 expression."""
        # Reset state
        self.linearity_analyzer.reset()
        self.expr_generator.reset()
        # Generate code
        self.expr_generator.generate(expr_z3)
        # Print report
        # if len(self.expr_generator.symbolTable) > 0:
        #     self.linearity_analyzer.print_report()
        if len(self.expr_generator.symbolTable) == 0:
            return self.expr_generator.symbolTable, 'int main(){return 0;}'
        # Build variable declarations
        var_declarations = []
        parse_formats = []
        var_refs = []
        for var_name, var_type in self.expr_generator.symbolTable.items():
            if var_type == Sort.Float32:
                var_declarations.append(f"float {var_name};")
                parse_formats.append("f")
                var_refs.append(f"&{var_name}")
            elif var_type == Sort.Float64:
                var_declarations.append(f"double {var_name};")
                parse_formats.append("d")
                var_refs.append(f"&{var_name}")
            else:
                raise NotImplementedError("Unknown types in SMT")
        x_expr = verification.var_name(expr_z3)
        x_body = '\n  '.join(self.expr_generator.result)
        x_dim = len(self.expr_generator.symbolTable)
        code = self.template.get_template() % {
            "var_declarations": "\n  ".join(var_declarations),
            "parse_formats": "".join(parse_formats),
            "var_refs": ", ".join(var_refs),
            "x_expr": x_expr,
            "x_dim": x_dim,
            "x_body": x_body
        }
        return self.expr_generator.symbolTable, code

def print_xsat_info():
    """Print XSat banner information."""
    try:
        logo = open('logo.txt', "r").read().strip('\n')
        print(logo)
    except:
        pass
    print()
    print("*" * 50)
    print("XSat Version 04/04/2016 (OOP Refactored)")
    print("Contributors: Zhoulai Fu and Zhendong Su")
    print("*" * 50)

def get_parser():
    """Create and return argument parser."""
    parser = argparse.ArgumentParser(prog='XSat')
    parser.add_argument('smt2_file', help='specify the smt2 file to analyze.',
                        type=argparse.FileType('r'))
    parser.add_argument('-v', '--version', action='version', version='%(prog) version 12/18/2015')
    parser.add_argument('--niter', help='niter in basinhopping', action='store',
                        type=int, required=False, default=100)
    parser.add_argument('--nStartOver', help='startOver times', action='store',
                        type=int, required=False, default=2)
    parser.add_argument('--method', help='Local minimization procedure', default='powell',
                        choices=['powell', 'slsqp', 'cg', 'l-bfgs-b', 'cobyla', 'tnc',
                                 'bfgs', 'nelder-mead', 'noop_min'])
    parser.add_argument('--showTime', help='show the time-related info (default: false)',
                        action='store_true', default=False)
    parser.add_argument('--showResult', help='show the basinhopping output (default:false)',
                        action='store_true', default=False)
    parser.add_argument('--stepSize', help='parameter of basinhopping',
                        type=float, default=10.0)
    parser.add_argument('--stepSize_round2', help='parameter of basinhopping',
                        type=float, default=100.0)
    parser.add_argument('--verify', help='verify the model', action='store_true', default=False)
    parser.add_argument('--verify2', help='verify the model (method 2)',
                        action='store_true', default=False)
    parser.add_argument('--showModel', help='show the model as a var->value mapping',
                        action='store_true', default=False)
    parser.add_argument('--showSymbolTable', help='show the symbol table, var->type',
                        action='store_true', default=False)
    parser.add_argument('--showConstraint', help='show the constraint, using the Z3 frontend',
                        action='store_true', default=False)
    parser.add_argument('--showVariableNumber',
                        help='show variable number, using the Z3 frontend',
                        action='store_true', default=False)
    parser.add_argument('--command_compilation',
                        help='the command used to compile the generated foo.c to foo.so',
                        default='clang -O3 -fbracket-depth=2048 -fPIC')
    parser.add_argument('--startPoint', help='start point in a single dimension',
                        action='store', type=float, default=1.0)
    parser.add_argument("--multi", help="multi-processing (default: false)",
                        default=False, action='store_true')
    parser.add_argument("--multiMessage", help="multi-processing message",
                        default=False, action='store_true')
    parser.add_argument("--round2", help="activate round2 when unsat (default: false)",
                        default=False, action='store_true')
    parser.add_argument("--niter_round2", help="niter for round2", action='store',
                        type=int, required=False, default=100)
    parser.add_argument("--suppressWarning", help="Suppress warnings",
                        default=False, action='store_true')
    return parser

if __name__ == "__main__":
    parser = get_parser()
    if len(sys.argv[1:]) == 0:
        print_xsat_info()
        parser.print_help()
        parser.exit()
    args = parser.parse_args()
    if args.suppressWarning:
        warnings.filterwarnings("ignore")
    try:
        expr_z3_lis = z3.parse_smt2_string(args.smt2_file.read())
        expr_z3 = z3.And(expr_z3_lis)
        expr_z3 = z3.simplify(expr_z3, arith_lhs=False, hoist_cmul=False)
    except z3.Z3Exception as e:
        print(e)
        sys.stderr.write("[Xsat] The Z3 front-end crashes.\n")
        sys.exit(1)
    generator = CodeGenerator()
    symbolTable, foo_dot_c = generator.generate(expr_z3)
    args.smt2_file.close()
    os.makedirs("build", exist_ok=True)
    pickle.dump(symbolTable, open("build/foo.symbolTable", "wb"))
    print(foo_dot_c)