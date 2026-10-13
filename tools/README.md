# Supplemental dataset tools

These tools generate and validate ArithDiag-Supplement8-v1. Project-authored
files use the repository's CC BY 4.0 license; frozen generated arithmetic
libraries have separate provenance and are excluded from that grant.

| Tool | Purpose | Requirements |
|---|---|---|
| `supplement.py` | Generate all eight topologies and 144 observations | Python 3.10+ standard library |
| `check_generator.py` | Independent arithmetic formulas and healthy gate-library tests | Python standard library |
| `validate_supplement.py` | Check every observation and independently replay faulty components | Python and Icarus Verilog |
| `check_arithdiag.py` | Parse and check original integer witnesses, connection ordering, initialization and native LP input | A built ArithDiag checkout |
| `check_smt.py` | Check fixed generated witnesses in integer and bit-vector SMT encodings | SMT-Diag's Python environment with Z3 |

Run commands from the repository root. Generation never imports a solver project
or uses solver outcomes. Optional integration tests read solver projects without
modifying them. Reports contain metrics and hashes; transient witness values are
not retained.

```sh
python3 -B tools/check_generator.py
python3 -B tools/supplement.py --output /tmp/arithdiag-supplement-reproduction
python3 -B tools/validate_supplement.py \
  --dataset supplement_v1 --report /tmp/gate-validation.json
python3 -B tools/check_arithdiag.py \
  --arithdiag /path/to/ArithDiag --dataset supplement_v1 \
  --report /tmp/arithdiag-validation.json
/path/to/SMT-Diag/.venv/bin/python -B tools/check_smt.py \
  --smt-project /path/to/SMT-Diag --dataset supplement_v1 \
  --report /tmp/smt-validation.json
```

The original sampling implementation is not included or claimed to be recovered.
The new generator is fully provided and its precise acceptance conditions and
attempt counts are disclosed. The supplementary datasets contain 18 instances
per circuit (two fault levels), while the original contains 45 (five levels).

For resource-controlled execution, use serial single-thread processes and the
same safety limits as your experiment environment. The published validation used
one CPU, nice 10, a 2 GiB address-space cap, a 1.5 GiB process-group RSS cap and
host-memory guards. No benchmark performance is inferred from validation time.

`check_arithdiag.py` distinguishes valid data from native compatibility. Its
recorded 65-bit mesh input-audit failures are a known numeric-interface limitation,
not invalid observations. Check the explicit native-audit flags in the report.
