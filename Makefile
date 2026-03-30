SHELL := /bin/bash
# Set dynamic library flag
UNAMES=$(shell uname -s)
ifeq ($(UNAMES),Linux)
	DLIBFLAG=-shared
	PYTHONINC := $(shell python3-config --includes)
	PYTHONLIB := $(shell python3-config --ldflags)
endif
ifeq ($(UNAMES),Darwin)
	DLIBFLAG=-dynamiclib
	PYTHONINC := $(shell python3-config --includes)
	PYTHONLIB := $(shell python3-config --ldflags)
endif


STAGESAT_ := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
OUT_=$(STAGESAT_)/out
R_SQUARE_=$(OUT_)/R_square
R_ULP_=$(OUT_)/R_ulp
R_VERIFY_=$(OUT_)/R_verify

STAGESAT_GEN=$(STAGESAT_)/stagesat_gen.py
CYTHON_DIR=src/optimization

ifdef IN
   $(shell echo $(IN) > STAGESAT_IN.txt)
endif


IN:= $(shell cat STAGESAT_IN.txt)

PYTHON_H:=

define STAGESAT_echo
	@echo "[stagesat] $1 "
endef


all: clean compile

gen:  build/foo.c stagesat_gen.py
build/foo.c: $(IN)  STAGESAT_IN.txt
	@echo "[stagesat] .smt2 -> .c"
	@mkdir -p build
	python stagesat_gen.py $<  > $@

compile_square: build/R_square/foo_square.so build/R_square/foo_square_large.so
build/foo_square.c: $(IN)
	@echo "[stagesat] .smt2 -> build/foo_square.c (square mode)"
	@mkdir -p build
	@python stagesat_gen.py $(IN) --square > build/foo_square.c
build/R_square/foo_square.so: include/R_square/stagesat.h build/foo_square.c
	@echo [stagesat]Compiling foo_square.so with stagesat.h
	@mkdir -p build/R_square
	@clang -O3 -fPIC build/foo_square.c $(DLIBFLAG) -o $@ $(PYTHONINC) -I include/R_square $(PYTHONLIB) \
		-DPyInit_foo=PyInit_foo_square \
		-DMODULE_NAME=\"foo_square\" \
		-fbracket-depth=3000
build/R_square/foo_square_large.so: include/R_square/stagesat_large.h build/foo_square.c
	@echo [stagesat]Compiling foo_square_large.so with stagesat_large.h
	@mkdir -p build/R_square
	@sed 's/#include "stagesat\.h"/#include "stagesat_large.h"/' build/foo_square.c > build/foo_square_large_tmp.c
	@clang -O3 -fPIC build/foo_square_large_tmp.c $(DLIBFLAG) -o $@ $(PYTHONINC) -I include/R_square $(PYTHONLIB) \
		-DPyInit_foo=PyInit_foo_square_large \
		-DMODULE_NAME=\"foo_square_large\" \
		-fbracket-depth=3000
	@rm -f build/foo_square_large_tmp.c

compile_ulp: build/R_ulp/foo_ulp.so
build/R_ulp/foo_ulp.so: include/R_ulp/stagesat.h $(IN)
	@echo "[stagesat] .smt2 -> build/foo_ulp.c (ulp mode)"
	@mkdir -p build
	@python stagesat_gen.py $(IN) --ulp > build/foo_ulp.c
	@echo [stagesat]Compiling the representing function as $@
	@mkdir -p build/R_ulp
	@clang -O3 -fPIC build/foo_ulp.c $(DLIBFLAG) -o $@ $(PYTHONINC) -I include/R_ulp $(PYTHONLIB) \
		-DPyInit_foo=PyInit_foo_ulp \
		-DMODULE_NAME=\"foo_ulp\" \
		-fbracket-depth=3000

compile_verify: build/R_verify/foo_verify.so
build/R_verify/foo_verify.so: include/R_verify/stagesat.h $(IN)
	@echo "[stagesat] .smt2 -> build/foo_verify.c (verify mode)"
	@mkdir -p build
	@python stagesat_gen.py $(IN) --verify > build/foo_verify.c
	@echo [stagesat]Compiling the representing function as $@
	@mkdir -p build/R_verify
	@clang -O3 -fPIC build/foo_verify.c $(DLIBFLAG) -o $@ $(PYTHONINC) -I include/R_verify $(PYTHONLIB) \
		-DPyInit_foo=PyInit_foo_verify \
		-DMODULE_NAME=\"foo_verify\" \
		-fbracket-depth=3000

compile: compile_square compile_ulp compile_verify

solve: compile
	@echo [stagesat] Executing the solver.
	@python stagesat.py

test: test_benchmarks.py
	python $

helloworld: Benchmarks/div3.c.50.smt2
	make IN=$>
	python stagesat.py

clean:
	$(STAGESAT_echo) Cleaning build/ and Results/
	@rm -vf build/*.c build/foo.symbolTable
	@rm -vfr build/R_square build/R_ulp build/R_verify
	@rm -vf Results/*

cython:
	@echo "[StageSAT] Building Cython extensions in $(CYTHON_DIR)..."
	@cd $(CYTHON_DIR) && python3 setup.py build_ext --inplace
	@echo "[StageSAT] Cython build complete"

clean_cython:
	@echo "[StageSAT] Cleaning Cython files"
	@find $(CYTHON_DIR) -name "*.so" -delete
	@find $(CYTHON_DIR) -name "*.c" -not -name "setup.py" -delete
	@find $(CYTHON_DIR) -name "*.html" -delete
	@find $(CYTHON_DIR) -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@rm -rf $(CYTHON_DIR)/build

.PHONY: copy gen clean compile compile_square compile_ulp test