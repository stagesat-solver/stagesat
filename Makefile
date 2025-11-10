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


XSAT_ := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
OUT_=$(XSAT_)/out
R_SQUARE_=$(OUT_)/R_square
R_ULP_=$(OUT_)/R_ulp
R_VERIFY_=$(OUT_)/R_verify

XSAT_GEN=$(XSAT_)/xsat_gen.py
CYTHON_DIR=src/optimization

ifdef IN
   $(shell echo $(IN) > XSAT_IN.txt)
endif


IN:= $(shell cat XSAT_IN.txt)

PYTHON_H:=

define XSAT_echo
	@echo "[XSat] $1 "
endef


all: clean compile

gen:  build/foo.c xsat_gen.py
build/foo.c: $(IN)  XSAT_IN.txt
	@echo "[XSAT] .smt2 -> .c"
	@mkdir -p build
	python xsat_gen.py $<  > $@

compile_square: build/R_square/foo_square.so
build/R_square/foo_square.so: include/R_square/xsat.h $(IN)
	@echo "[XSAT] .smt2 -> build/foo_square.c (square mode)"
	@mkdir -p build
	@python xsat_gen.py $(IN) --square > build/foo_square.c
	@echo [XSAT]Compiling the representing function as $@
	@mkdir -p build/R_square
	@clang -O3 -fPIC build/foo_square.c $(DLIBFLAG) -o $@ $(PYTHONINC) -I include/R_square $(PYTHONLIB) \
		-DPyInit_foo=PyInit_foo_square \
		-DMODULE_NAME=\"foo_square\" \
		-fbracket-depth=3000

compile_ulp: build/R_ulp/foo_ulp.so
build/R_ulp/foo_ulp.so: include/R_ulp/xsat.h $(IN)
	@echo "[XSAT] .smt2 -> build/foo_ulp.c (ulp mode)"
	@mkdir -p build
	@python xsat_gen.py $(IN) --ulp > build/foo_ulp.c
	@echo [XSAT]Compiling the representing function as $@
	@mkdir -p build/R_ulp
	@clang -O3 -fPIC build/foo_ulp.c $(DLIBFLAG) -o $@ $(PYTHONINC) -I include/R_ulp $(PYTHONLIB) \
		-DPyInit_foo=PyInit_foo_ulp \
		-DMODULE_NAME=\"foo_ulp\" \
		-fbracket-depth=3000

compile_verify: build/R_verify/foo_verify.so
build/R_verify/foo_verify.so: include/R_verify/xsat.h $(IN)
	@echo "[XSAT] .smt2 -> build/foo_verify.c (verify mode)"
	@mkdir -p build
	@python xsat_gen.py $(IN) --verify > build/foo_verify.c
	@echo [XSAT]Compiling the representing function as $@
	@mkdir -p build/R_verify
	@clang -O3 -fPIC build/foo_verify.c $(DLIBFLAG) -o $@ $(PYTHONINC) -I include/R_verify $(PYTHONLIB) \
		-DPyInit_foo=PyInit_foo_verify \
		-DMODULE_NAME=\"foo_verify\" \
		-fbracket-depth=3000

compile: compile_square compile_ulp compile_verify

solve: compile
	@echo [XSAT] Executing the solver.
	@python xsat.py

test: test_benchmarks.py
	python $

helloworld: Benchmarks/div3.c.50.smt2
	make IN=$>
	python xsat.py

clean:
	$(XSAT_echo) Cleaning build/ and Results/
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