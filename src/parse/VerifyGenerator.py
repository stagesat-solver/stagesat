import sympy
import z3
import collections
import warnings
import src.utils.z3_util as z3_util
import src.utils.verification as verification
from src.utils.sort import Sort

DEBUG=False

class VerifyGenerator():
    def __init__(self):
        return
    def _get_template(self):
        template = """#include <Python.h>
    #include "xsat.h"
    #include <math.h>
    static PyObject* R(PyObject* self, PyObject *args){
    
      %(var_declarations)s
      if (!PyArg_ParseTuple(args,"%(parse_formats)s", %(var_refs)s))
        return NULL;
      %(x_body)s
      return Py_BuildValue("d",%(x_expr)s);
    }
    
    static PyMethodDef methods[] = {
      {"R", R, METH_VARARGS, NULL},
      {NULL, NULL, 0, NULL}
    };
    
    static struct PyModuleDef moduledef = {
      PyModuleDef_HEAD_INIT,
      #ifdef MODULE_NAME
        MODULE_NAME,
      #else
        "foo",
      #endif
      NULL,            /* m_doc */
      -1,              /* m_size */
      methods,         /* m_methods */
      NULL,            /* m_reload */
      NULL,            /* m_traverse */
      NULL,            /* m_clear */
      NULL,            /* m_free */
    };
    
    PyMODINIT_FUNC
    PyInit_foo(void)
    {
      PyObject* module = PyModule_Create(&moduledef);
      if (module == NULL)
        return NULL;
    
      PyModule_AddIntConstant(module, "dim", %(x_dim)s);
      return module;
    }
    """
        return template

    def _get_operand_type(self, expr, symbolTable, cache):
        """Determine if an operand is float32 or float64"""
        if z3_util.is_variable(expr):
            var_name = verification.rename_var(expr.decl().name())
            if var_name in symbolTable:
                return symbolTable[var_name]
        elif z3_util.is_value(expr):
            if expr.sort() == z3.Float32():
                return Sort.Float32
            elif expr.sort() == z3.Float64():
                return Sort.Float64
        elif expr.get_id() in cache:
            # Check the type of intermediate result
            if expr.sort() == z3.Float32():
                return Sort.Float32
            elif expr.sort() == z3.Float64():
                return Sort.Float64
        return Sort.Float64  # Default to float64

    def _get_comparison_function(self, base_func, lhs_type, rhs_type):
        """Get the appropriate comparison function based on operand types"""
        if lhs_type == Sort.Float32 and rhs_type == Sort.Float32:
            return f"{base_func}_f32"
        elif lhs_type == Sort.Float32 and rhs_type == Sort.Float64:
            return f"{base_func}_mixed_fd"
        elif lhs_type == Sort.Float64 and rhs_type == Sort.Float32:
            return f"{base_func}_mixed_df"
        else:
            return base_func  # Both float64 or default

    def _gen(self, expr_z3, symbolTable, cache, result):
        ###Leaf: var
        if z3_util.is_variable(expr_z3):
            if DEBUG:
                print("-- Branch _is_variable with ", expr_z3)
            symVar = expr_z3.decl().name()
            symVar = verification.rename_var(symVar)
            if z3.is_int(expr_z3):
                symType = Sort.Int
            elif z3.is_fp(expr_z3):
                if expr_z3.sort() == z3.Float64():
                    symType = Sort.Float64
                elif expr_z3.sort() == z3.Float32():
                    symType = Sort.Float32
                else:
                    raise NotImplementedError("Unexpected sort.", expr_z3.sort())
            elif z3.is_real(expr_z3):
                symType = Sort.Float
                warnings.warn("****WARNING****: Real variable '%s' treated as floating point" % symVar)
            else:
                raise NotImplementedError("Unexpected type")
            if (symVar in symbolTable.keys()):
                assert symType == symbolTable[symVar]
            else:
                symbolTable[symVar] = symType
            return symVar
        ###Leaf: val
        if z3_util.is_value(expr_z3):
            if DEBUG:
                print("-- Branch _is_value")
            if z3.is_fp(expr_z3) or z3.is_real(expr_z3):
                if DEBUG:
                    print("---- Sub-Branch FP or Real")
                if isinstance(expr_z3, z3.FPNumRef):
                    if DEBUG:
                        print("------- Sub-Sub-Branch _is_FPNumRef")
                    # Check for special values first
                    if expr_z3.isNaN():
                        str_ret = "NAN"
                    elif expr_z3.isInf() and expr_z3.decl().kind() == z3.Z3_OP_FPA_PLUS_INF:
                        str_ret = "INFINITY"
                    elif expr_z3.isInf() and expr_z3.decl().kind() == z3.Z3_OP_FPA_MINUS_INF:
                        str_ret = "- INFINITY"
                    else:
                        # Handle normal values
                        try:
                            str_ret = str(sympy.Float(str(expr_z3), 17))
                        except ValueError:
                            # Handle other edge cases
                            is_float32 = expr_z3.sort() == z3.Float32()
                            offset = 127 if is_float32 else 1023
                            exponent_raw = expr_z3.exponent_as_long()
                            if exponent_raw == 0:
                                expr_z3_exponent = -126 if is_float32 else -1022
                            else:
                                expr_z3_exponent = exponent_raw - offset
                            significand = float(str(expr_z3.significand()))
                            value = ((-1) ** float(expr_z3.sign())) * significand * (2 ** expr_z3_exponent)
                            str_ret = str(sympy.Float(value, 17))
                else:
                    if DEBUG:
                        print("------- Sub-Sub-Branch other than FPNumRef, probably FPRef")
                    str_ret = str(sympy.Float(str((expr_z3)), 17))
            elif z3.is_int(expr_z3):
                if DEBUG:
                    print("---- Sub-Branch Integer")
                str_ret = str(sympy.Integer(str(expr_z3)))
            elif z3_util.is_true(expr_z3):
                str_ret = "0"
            elif z3_util.is_false(expr_z3):
                str_ret = "1"
            else:
                raise NotImplementedError("[XSat: Coral Benchmarking] type not considered ")
            if expr_z3.sort() == z3.Float32():
                str_ret = str_ret + "f"
            return str_ret

        if (expr_z3.get_id() in cache): return verification.var_name(expr_z3)
        cache.add(expr_z3.get_id())
        sort_z3 = expr_z3.decl().kind()

        expr_type = 'double'
        if expr_z3.sort() == z3.FPSort(8, 24): expr_type = 'float'
        ###
        if sort_z3 == z3.Z3_OP_FPA_LE:
            if DEBUG:
                print("-- Branch _is_le")
            lhs = self._gen(expr_z3.arg(0), symbolTable, cache, result)
            rhs = self._gen(expr_z3.arg(1), symbolTable, cache, result)
            lhs_type = self._get_operand_type(expr_z3.arg(0), symbolTable, cache)
            rhs_type = self._get_operand_type(expr_z3.arg(1), symbolTable, cache)
            func_name = self._get_comparison_function("DLE", lhs_type, rhs_type)
            toAppend = "double %s = %s(%s,%s);" % (
                verification.var_name(expr_z3), func_name, lhs, rhs)
            result.append(toAppend)
            return verification.var_name(expr_z3)

        #########!!!!!!!!!!!! need to do something
        if sort_z3 == z3.Z3_OP_FPA_TO_FP:
            if DEBUG:
                print("-- Branch _is_fpFP")
            assert expr_z3.num_args() == 2
            if not (z3_util.is_RNE(expr_z3.arg(0))):
                warnings.warn(f"WARNING!!! I expect the first argument of fpFP is RNE, but it is {expr_z3.arg(0)}")
            x = self._gen(expr_z3.arg(1), symbolTable, cache, result)
            if expr_z3.sort() == z3.FPSort(8, 24):
                toAppend = "float %s = (float)(%s);" % (verification.var_name(expr_z3), x)
            else:
                toAppend = "double %s = (double)(%s);" % (verification.var_name(expr_z3), x)
            result.append(toAppend)
            return verification.var_name(expr_z3)

        if sort_z3 == z3.Z3_OP_FPA_LT:
            if DEBUG:
                print("-- Branch _is_lt")
            lhs = self._gen(expr_z3.arg(0), symbolTable, cache, result)
            rhs = self._gen(expr_z3.arg(1), symbolTable, cache, result)
            lhs_type = self._get_operand_type(expr_z3.arg(0), symbolTable, cache)
            rhs_type = self._get_operand_type(expr_z3.arg(1), symbolTable, cache)
            func_name = self._get_comparison_function("DLT", lhs_type, rhs_type)
            toAppend = "double %s = %s(%s,%s);" % (
                verification.var_name(expr_z3), func_name, lhs, rhs)
            result.append(toAppend)
            return verification.var_name(expr_z3)

        if z3_util.is_eq(expr_z3):
            if DEBUG:
                print("-- Branch _is_eq")
            lhs = self._gen(expr_z3.arg(0), symbolTable, cache, result)
            rhs = self._gen(expr_z3.arg(1), symbolTable, cache, result)
            lhs_type = self._get_operand_type(expr_z3.arg(0), symbolTable, cache)
            rhs_type = self._get_operand_type(expr_z3.arg(1), symbolTable, cache)
            func_name = self._get_comparison_function("DEQ", lhs_type, rhs_type)
            toAppend = "double %s = %s(%s,%s);" % (
                verification.var_name(expr_z3), func_name, lhs, rhs)
            result.append(toAppend)
            return verification.var_name(expr_z3)

        if z3_util.is_fpMul(expr_z3):
            if DEBUG:
                print("-- Branch _is_fpMul")
            if not z3_util.is_RNE(expr_z3.arg(0)):
                warnings.warn(f"WARNING!!! arg(0) is not RNE but is treated as RNE. arg(0) = {expr_z3.arg(0)}")
            assert expr_z3.num_args() == 3
            lhs = self._gen(expr_z3.arg(1), symbolTable, cache, result)
            rhs = self._gen(expr_z3.arg(2), symbolTable, cache, result)
            if expr_type == 'float':
                toAppend = "float %s = (float)(%s) * (float)(%s);" % (verification.var_name(expr_z3), lhs, rhs)
            else:
                toAppend = "double %s = %s * %s;" % (verification.var_name(expr_z3), lhs, rhs)
            result.append(toAppend)
            return verification.var_name(expr_z3)

        if z3_util.is_fpDiv(expr_z3):
            if DEBUG:
                print("-- Branch _is_fpDiv")
            if not z3_util.is_RNE(expr_z3.arg(0)):
                warnings.warn(f"WARNING!!! arg(0) is not RNE but is treated as RNE. arg(0) = {expr_z3.arg(0)}")
            assert expr_z3.num_args() == 3
            lhs = self._gen(expr_z3.arg(1), symbolTable, cache, result)
            rhs = self._gen(expr_z3.arg(2), symbolTable, cache, result)
            if expr_type == 'float':
                toAppend = "float %s = (float)(%s) / (float)(%s);" % (verification.var_name(expr_z3), lhs, rhs)
            else:
                toAppend = "double %s = %s / %s;" % (verification.var_name(expr_z3), lhs, rhs)
            result.append(toAppend)
            return verification.var_name(expr_z3)

        if z3_util.is_fpAdd(expr_z3):
            if DEBUG:
                print("-- Branch _is_fpAdd")
            if not z3_util.is_RNE(expr_z3.arg(0)):
                warnings.warn(f"WARNING!!! arg(0) is not RNE but is treated as RNE. arg(0) = {expr_z3.arg(0)}")
            assert expr_z3.num_args() == 3
            lhs = self._gen(expr_z3.arg(1), symbolTable, cache, result)
            rhs = self._gen(expr_z3.arg(2), symbolTable, cache, result)
            if expr_type == 'float':
                toAppend = "float %s = (float)(%s) + (float)(%s);" % (verification.var_name(expr_z3), lhs, rhs)
            else:
                toAppend = "double %s = %s + %s;" % (verification.var_name(expr_z3), lhs, rhs)
            result.append(toAppend)
            return verification.var_name(expr_z3)

        if z3.is_and(expr_z3):
            if DEBUG: print("-- Branch _is_and")
            ##TODO Not sure if symbolTable will be treated in a multi-threaded way
            toAppendExpr = self._gen(expr_z3.arg(0), symbolTable, cache, result)
            for i in range(1, expr_z3.num_args()):
                toAppendExpr = 'BAND( %s,%s )' % (toAppendExpr, self._gen(expr_z3.arg(i), symbolTable, cache, result))
            toAppend = "double %s = %s; " \
                       % (verification.var_name(expr_z3), \
                          toAppendExpr, \
                          )
            result.append(toAppend)
            return verification.var_name(expr_z3)

        if z3.is_or(expr_z3):
            if DEBUG: print("-- Branch _is_or")
            # Handle OR by combining all arguments with BOR (boolean OR)
            toAppendExpr = self._gen(expr_z3.arg(0), symbolTable, cache, result)
            for i in range(1, expr_z3.num_args()):
                toAppendExpr = 'BOR( %s,%s )' % (toAppendExpr, self._gen(expr_z3.arg(i), symbolTable, cache, result))
            toAppend = "double %s = %s; " \
                       % (verification.var_name(expr_z3), \
                          toAppendExpr, \
                          )
            result.append(toAppend)
            return verification.var_name(expr_z3)

        if z3.is_not(expr_z3):
            if DEBUG:
                print("-- Branch _is_not")
            assert expr_z3.num_args() == 1
            if not (expr_z3.arg(0).num_args() == 2):
                warnings.warn(f"WARNING!!! arg(0) is not RNE but is treated as RNE. arg(0) = {expr_z3.arg(0)}")
            op1 = self._gen(expr_z3.arg(0).arg(0), symbolTable, cache, result)
            op2 = self._gen(expr_z3.arg(0).arg(1), symbolTable, cache, result)
            lhs_type = self._get_operand_type(expr_z3.arg(0).arg(0), symbolTable, cache)
            rhs_type = self._get_operand_type(expr_z3.arg(0).arg(1), symbolTable, cache)
            if z3_util.is_ge(expr_z3.arg(0)):
                func = self._get_comparison_function("DLT", lhs_type, rhs_type)
            elif z3_util.is_gt(expr_z3.arg(0)):
                func = self._get_comparison_function("DLE", lhs_type, rhs_type)
            elif z3_util.is_le(expr_z3.arg(0)):
                func = self._get_comparison_function("DGT", lhs_type, rhs_type)
            elif z3_util.is_lt(expr_z3.arg(0)):
                func = self._get_comparison_function("DGE", lhs_type, rhs_type)
            elif z3_util.is_eq(expr_z3.arg(0)):
                func = self._get_comparison_function("DNE", lhs_type, rhs_type)
            elif z3_util.is_distinct(expr_z3.arg(0)):
                func = self._get_comparison_function("DEQ", lhs_type, rhs_type)
            else:
                raise NotImplementedError("Not implemented case")
            a = "%s(%s,%s)" % (func, op1, op2)
            toAppend = "double %s = %s;" % (verification.var_name(expr_z3), a)
            result.append(toAppend)
            return verification.var_name(expr_z3)

        if z3_util.is_fpNeg(expr_z3):
            if DEBUG:
                print("-- Branch _is_fpNeg")
            assert expr_z3.num_args() == 1
            op1 = self._gen(expr_z3.arg(0), symbolTable, cache, result)
            toAppend = "%s %s =  - %s ;" \
                       % (expr_type, verification.var_name(expr_z3), \
                          op1, \
                          )
            result.append(toAppend)
            return verification.var_name(expr_z3)

        raise NotImplementedError(
            "Not implemented case 002 for expr_z3  =  %s, kind(%s)" % (expr_z3, expr_z3.decl().kind()))

    def gen(self, expr_z3):
        symbolTable = collections.OrderedDict()
        cache = set()
        result = []
        self._gen(expr_z3, symbolTable, cache, result)   #########STOHERE
        if len(symbolTable)==0:
            return symbolTable,'int main(){return 0;}'
        # Build variable declarations with correct types
        var_declarations = []
        parse_formats = []
        var_refs = []
        for var_name, var_type in symbolTable.items():
            if var_type == Sort.Float32:
                var_declarations.append(f"float {var_name};")
                parse_formats.append("f")  # 'f' for float in PyArg_ParseTuple
                var_refs.append(f"&{var_name}")
            elif var_type == Sort.Float64:
                var_declarations.append(f"double {var_name};")
                parse_formats.append("d")  # 'd' for double
                var_refs.append(f"&{var_name}")
            else:
                raise NotImplementedError("Unknown types in smt")
        x_expr = verification.var_name(expr_z3)   #the last var
        x_body = '\n  '.join(result)
        x_dim = len(symbolTable)
        return symbolTable, self._get_template() % {
            "var_declarations": "\n  ".join(var_declarations),
            "parse_formats": "".join(parse_formats),
            "var_refs": ", ".join(var_refs),
            "x_expr": x_expr,
            "x_dim": x_dim,
            "x_body": x_body
        }
