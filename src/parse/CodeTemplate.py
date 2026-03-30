class CodeTemplate:
    """Manages C code templates with hybrid objective support."""

    @staticmethod
    def get_template():
        return """#include <Python.h>
    #include "stagesat.h"
    #include <math.h>

    %(matrix_functions)s

    static PyObject* R(PyObject* self, PyObject *args){

      %(var_declarations)s
      if (!PyArg_ParseTuple(args,"%(parse_formats)s", %(var_refs)s))
        return NULL;
      %(x_body)s

      %(objective_computation)s

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
      NULL,
      -1,
      methods,
      NULL,
      NULL,
      NULL,
      NULL,
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

    @staticmethod
    def get_template_ulp():
        """Return the C code template for Python C extension module."""
        return """#include <Python.h>
    #include "stagesat.h"
    #include <math.h>
    %(ulp_projection)s
    %(ulp_f32_projection)s
    static PyObject* R(PyObject* self, PyObject *args){

      %(var_declarations)s
      if (!PyArg_ParseTuple(args,"%(parse_formats)s", %(var_refs)s))
        return NULL;
      %(x_body)s

      %(objective_computation)s

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

    @staticmethod
    def get_empty_template():
        template = """#include <Python.h>
    #include "stagesat.h"
    #include <math.h>

    static PyObject* R(PyObject* self, PyObject *args){
      return PyFloat_FromDouble(0.0);  // Fixed: Must return PyObject*, not double
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

      PyModule_AddIntConstant(module, "dim", 0);  // Fixed: Use actual value instead of placeholder
      return module;
    }
    """
        return template