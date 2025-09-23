#include <Python.h>
#include "xsat.h"

static PyObject* R(PyObject* self, PyObject *args){

  float b108;
  double b127;
  float b641;
  double b149;
  float b636;
  double b165;
  float b631;
  double b182;
  float b626;
  double b199;
  float b621;
  double b216;
  float b616;
  double b233;
  float b611;
  double b250;
  float b606;
  double b267;
  float b601;
  double b283;
  float b596;
  float b545;
  float b587;
  float b582;
  float b577;
  float b572;
  float b567;
  float b562;
  float b557;
  float b552;
  float b547;
  float b540;
  float b110;
  double b140;
  float b117;
  float b376;
  float b373;
  if (!PyArg_ParseTuple(args,"fdfdfdfdfdfdfdfdfdfdfffffffffffffdfff", &b108, &b127, &b641, &b149, &b636, &b165, &b631, &b182, &b626, &b199, &b621, &b216, &b616, &b233, &b611, &b250, &b606, &b267, &b601, &b283, &b596, &b545, &b587, &b582, &b577, &b572, &b567, &b562, &b557, &b552, &b547, &b540, &b110, &b140, &b117, &b376, &b373))
    return NULL;
  float _t_7 = (float)(b108) * (float)(b108);
  float _t_8 =  - _t_7 ;
  float _t_9 = (float)(b108) * (float)(_t_8);
  double _t_10 = (double)(_t_9);
  double _t_12 = _t_10 / b127;
  float _t_13 = (float)(_t_12);
  double _t_16 = DNE_f32(_t_13,b641);
  float _t_17 = (float)(_t_8) * (float)(_t_13);
  double _t_18 = (double)(_t_17);
  double _t_20 = _t_18 / b149;
  float _t_21 = (float)(_t_20);
  double _t_24 = DNE_f32(_t_21,b636);
  float _t_25 = (float)(_t_8) * (float)(_t_21);
  double _t_26 = (double)(_t_25);
  double _t_28 = _t_26 / b165;
  float _t_29 = (float)(_t_28);
  double _t_32 = DNE_f32(_t_29,b631);
  float _t_33 = (float)(_t_8) * (float)(_t_29);
  double _t_34 = (double)(_t_33);
  double _t_36 = _t_34 / b182;
  float _t_37 = (float)(_t_36);
  double _t_40 = DNE_f32(_t_37,b626);
  float _t_41 = (float)(_t_8) * (float)(_t_37);
  double _t_42 = (double)(_t_41);
  double _t_44 = _t_42 / b199;
  float _t_45 = (float)(_t_44);
  double _t_48 = DNE_f32(_t_45,b621);
  float _t_49 = (float)(_t_8) * (float)(_t_45);
  double _t_50 = (double)(_t_49);
  double _t_52 = _t_50 / b216;
  float _t_53 = (float)(_t_52);
  double _t_56 = DNE_f32(_t_53,b616);
  float _t_57 = (float)(_t_8) * (float)(_t_53);
  double _t_58 = (double)(_t_57);
  double _t_60 = _t_58 / b233;
  float _t_61 = (float)(_t_60);
  double _t_64 = DNE_f32(_t_61,b611);
  float _t_65 = (float)(_t_8) * (float)(_t_61);
  double _t_66 = (double)(_t_65);
  double _t_68 = _t_66 / b250;
  float _t_69 = (float)(_t_68);
  double _t_72 = DNE_f32(_t_69,b606);
  float _t_73 = (float)(_t_8) * (float)(_t_69);
  double _t_74 = (double)(_t_73);
  double _t_76 = _t_74 / b267;
  float _t_77 = (float)(_t_76);
  double _t_80 = DNE_f32(_t_77,b601);
  float _t_81 = (float)(_t_8) * (float)(_t_77);
  double _t_82 = (double)(_t_81);
  double _t_84 = _t_82 / b283;
  float _t_85 = (float)(_t_84);
  double _t_88 = DNE_f32(_t_85,b596);
  double _t_92 = DNE_f32(b545,b587);
  double _t_95 = DNE_f32(b587,b582);
  double _t_98 = DNE_f32(b582,b577);
  double _t_101 = DNE_f32(b577,b572);
  double _t_104 = DNE_f32(b572,b567);
  double _t_107 = DNE_f32(b567,b562);
  double _t_110 = DNE_f32(b562,b557);
  double _t_113 = DNE_f32(b557,b552);
  float _t_114 = (float)(b108) + (float)(_t_13);
  float _t_115 = (float)(_t_21) + (float)(_t_114);
  float _t_116 = (float)(_t_29) + (float)(_t_115);
  float _t_117 = (float)(_t_37) + (float)(_t_116);
  float _t_118 = (float)(_t_45) + (float)(_t_117);
  float _t_119 = (float)(_t_53) + (float)(_t_118);
  float _t_120 = (float)(_t_61) + (float)(_t_119);
  float _t_121 = (float)(_t_69) + (float)(_t_120);
  float _t_122 = (float)(_t_77) + (float)(_t_121);
  float _t_123 = (float)(_t_85) + (float)(_t_122);
  double _t_125 = DNE_f32(b552,_t_123);
  double _t_128 = DNE_f32(b545,b547);
  double _t_131 = DNE_f32(b108,b540);
  double _t_134 = DGT_f32(b110,b108);
  float _t_135 =  - b108 ;
  double _t_136 = DEQ_f32(b540,_t_135);
  double _t_140 = DGT_f32(b110,b545);
  float _t_142 =  - b545 ;
  double _t_143 = DEQ_f32(b547,_t_142);
  double _t_146 = (double)(b601);
  double _t_149 = DGT(b140,_t_146);
  double _t_151 = DEQ_f32(b552,_t_122);
  double _t_155 = DGT_f32(b547,b117);
  double _t_158 = DLE_f32(b540,b376);
  double _t_161 = DLE_f32(b373,b108);
  double _t_163 = DLE_f32(b108,b376);
  double _t_166 = (double)(b606);
  double _t_168 = DGT(b140,_t_166);
  double _t_170 = DEQ_f32(b557,_t_121);
  double _t_173 = (double)(b611);
  double _t_175 = DGT(b140,_t_173);
  double _t_177 = DEQ_f32(b562,_t_120);
  double _t_180 = (double)(b616);
  double _t_182 = DGT(b140,_t_180);
  double _t_184 = DEQ_f32(b567,_t_119);
  double _t_187 = (double)(b621);
  double _t_189 = DGT(b140,_t_187);
  double _t_191 = DEQ_f32(b572,_t_118);
  double _t_194 = (double)(b626);
  double _t_196 = DGT(b140,_t_194);
  double _t_198 = DEQ_f32(b577,_t_117);
  double _t_201 = (double)(b631);
  double _t_203 = DGT(b140,_t_201);
  double _t_205 = DEQ_f32(b582,_t_116);
  double _t_208 = (double)(b636);
  double _t_210 = DGT(b140,_t_208);
  double _t_212 = DEQ_f32(b587,_t_115);
  double _t_215 = (double)(b641);
  double _t_217 = DGT(b140,_t_215);
  double _t_219 = DEQ_f32(b545,_t_114);
  double _t_223 = DGT_f32(b110,_t_85);
  float _t_225 =  - _t_85 ;
  double _t_226 = DEQ_f32(b596,_t_225);
  double _t_230 = DGT_f32(b110,_t_77);
  float _t_232 =  - _t_77 ;
  double _t_233 = DEQ_f32(b601,_t_232);
  double _t_237 = DGT_f32(b110,_t_69);
  float _t_239 =  - _t_69 ;
  double _t_240 = DEQ_f32(b606,_t_239);
  double _t_244 = DGT_f32(b110,_t_61);
  float _t_246 =  - _t_61 ;
  double _t_247 = DEQ_f32(b611,_t_246);
  double _t_251 = DGT_f32(b110,_t_53);
  float _t_253 =  - _t_53 ;
  double _t_254 = DEQ_f32(b616,_t_253);
  double _t_258 = DGT_f32(b110,_t_45);
  float _t_260 =  - _t_45 ;
  double _t_261 = DEQ_f32(b621,_t_260);
  double _t_265 = DGT_f32(b110,_t_37);
  float _t_267 =  - _t_37 ;
  double _t_268 = DEQ_f32(b626,_t_267);
  double _t_272 = DGT_f32(b110,_t_29);
  float _t_274 =  - _t_29 ;
  double _t_275 = DEQ_f32(b631,_t_274);
  double _t_279 = DGT_f32(b110,_t_21);
  float _t_281 =  - _t_21 ;
  double _t_282 = DEQ_f32(b636,_t_281);
  double _t_286 = DGT_f32(b110,_t_13);
  float _t_288 =  - _t_13 ;
  double _t_289 = DEQ_f32(b641,_t_288);
  double _t_291 = (double)(b596);
  double _t_293 = DGT(b140,_t_291);
  double _t_362 = BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( BAND( _t_16,_t_24 ),_t_32 ),_t_40 ),_t_48 ),_t_56 ),_t_64 ),_t_72 ),_t_80 ),_t_88 ),_t_92 ),_t_95 ),_t_98 ),_t_101 ),_t_104 ),_t_107 ),_t_110 ),_t_113 ),_t_125 ),_t_128 ),_t_131 ),_t_134 ),_t_136 ),_t_140 ),_t_143 ),_t_149 ),_t_151 ),_t_155 ),_t_158 ),_t_161 ),_t_163 ),_t_168 ),_t_170 ),_t_175 ),_t_177 ),_t_182 ),_t_184 ),_t_189 ),_t_191 ),_t_196 ),_t_198 ),_t_203 ),_t_205 ),_t_210 ),_t_212 ),_t_217 ),_t_219 ),_t_223 ),_t_226 ),_t_230 ),_t_233 ),_t_237 ),_t_240 ),_t_244 ),_t_247 ),_t_251 ),_t_254 ),_t_258 ),_t_261 ),_t_265 ),_t_268 ),_t_272 ),_t_275 ),_t_279 ),_t_282 ),_t_286 ),_t_289 ),_t_293 ); 
  return Py_BuildValue("d",_t_362);
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

  PyModule_AddIntConstant(module, "dim", 37);
  return module;
}

