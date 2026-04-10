# StageSAT

A floating-point constraint solver via staged optimization.

## Dependencies

Install the required dependencies:
```bash
pip install -r requirements.txt
apt install clang
```

## Usage

First, compile the Cython extensions:
```bash
make cython
```

**Run a benchmark**

Consider a benchmark located at `Benchmarks/griggio-benchmarks/small/sin2.c.5.smt2`. The first command below compiles the benchmark into a C shared object, and the second command invokes an optimization backend to solve it:

```
make IN=Benchmarks/griggio-benchmarks/small/sin2.c.5.smt2
python stagesat.py --bench --time
```

To view debug information, run the following command instead:
```
python stagesat.py
```

**Run a benchmark suite**

To run an entire benchmark suite (for example, `Benchmarks/griggio-benchmarks/large/`), use the following command:
```
python stagesat-test.py experiment/large.csv Benchmarks/griggio-benchmarks/large
```

Results will be stored in `experiment/large.csv`.

## Benchmarks

`Benchmarks` folder contains all five suites used in StageSAT paper.

`Benchmarks/griggio-benchmarks` folder contains the MathSAT-small/middle/large benchmarks used in the paper.

`Benchmarks/grater-benchmarks` folder contains the JFS/Grater benchmarks used in the paper.

## Baselines

|                      Solver                      |                     Version / SHA Commit                     |
| :----------------------------------------------: | :----------------------------------------------------------: |
|    [XSat](https://github.com/zhoulaifu/xsat)     | [f757a7a](https://github.com/zhoulaifu/xsat/tree/f757a7af36953b8b9100c06dc59d342bf46ebb63) |
|    [goSAT](https://github.com/abenkhadra/gosat)     | [dd4bd30](https://github.com/abenkhadra/gosat/tree/dd4bd306119f2411dbda05514985ff94535f18ff) |
|    [Grater](https://github.com/grater-exp/grater-experiment)     | [e405648](https://github.com/grater-exp/grater-experiment/tree/e4056488f8b5664e433e66b301f98573f48ae61a) |
|    [JFS](https://github.com/mc-imperial/jfs)     | [c45b12c](https://github.com/mc-imperial/jfs/tree/c45b12c5383e0242099b645cac4376fb0216a60d) |
|       [cvc5](https://github.com/cvc5/cvc5)       | [v1.3.1](https://github.com/cvc5/cvc5/releases/tag/cvc5-1.3.1) |
| [Bitwuzla](https://github.com/bitwuzla/bitwuzla) | [v0.8.2](https://github.com/bitwuzla/bitwuzla/releases/tag/0.8.2) |
|       [Z3](https://github.com/Z3Prover/z3)       | [v4.8.12](https://github.com/Z3Prover/z3/releases/tag/z3-4.8.12) |
|       [MathSAT](https://mathsat.fbk.eu/)       | [v5.6.12](https://mathsat.fbk.eu/downloadall.html) |