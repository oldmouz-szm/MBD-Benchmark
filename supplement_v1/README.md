# ArithDiag-Supplement8-v1

**8 circuits, 48 permanent physical fault configurations, 144 independent
single-observation diagnosis instances.** This supplement is added to the
original 10 circuits and 450 observations; it does not replace or renumber them.
Dataset version 1.0.0, generated on 2026-10-13. Cite the repository commit or
release together with this dataset identifier.

## Fixed design

| Circuit | Components | Boolean operations in components | Injected component levels | Observations |
|---|---:|---:|---|---:|
| nl_ring256_u16 | 512 | 1,527,040 | 16, 32 | 18 |
| nl_ring512_u16 | 1,024 | 3,054,080 | 32, 64 | 18 |
| nl_ring256_u8 | 512 | 369,920 | 16, 32 | 18 |
| nl_mesh24x24_u8 | 2,304 | 1,733,760 | 72, 144 | 18 |
| nl_mesh32x32_u8 | 4,096 | 3,082,240 | 128, 256 | 18 |
| nl_mesh24x24_u16 | 2,304 | 7,009,920 | 72, 144 | 18 |
| nl_cascade256_u8 | 768 | 482,560 | 24, 48 | 18 |
| nl_nonlocal_square128_u8 | 1,280 | 986,240 | 40, 80 | 18 |

Component counts and Boolean-operation counts have different meanings. The
latter sum AND/OR/XOR/NOT operations in instantiated modules, not mapped cells.
The design was fixed before solving. No observation is selected or rejected
using diagnosis cardinality, runtime, a reference answer, or relative performance.
These structures are intended to probe nonlinear search; actual difficulty is
an experimental outcome, not an acceptance criterion.

### Controlled comparisons

- Ring size at 16 bits: original 128 nodes, new 256 and 512 nodes.
- Ring width at 256 nodes: 8 and 16 bits.
- Mesh size at 8 bits: original 16x16, new 24x24 and 32x32.
- Mesh width at 24x24: 8 and 16 bits.

New fault densities are 1/32 and 1/16 of whole components. Only matched density
levels may be used when including old anchors. The old 16x16 mesh has its 1/32
level (32 components), but no 1/16 level (64 components); do not invent or
regenerate that missing anchor. Different sizes are not paired physical faults.

### Topologies and widths

All circuits are unsigned, combinational and have top-level input/output
observations only. Packed input lanes have width indicated by `u8` or `u16`.
Index wrap describes spatial sharing, not clocked feedback. Every full top-level
adder/multiplier instance has its own diagnostic health variable.

- Ring: `t[i]=a[i]+b[i]`, `y[i]=t[i]*t[(i+1) mod n]`.
  Pre-addition preserves its carry; zero extension feeds a multiplier with twice
  the base input width. Outputs have 32 or 64 bits.
- Periodic mesh: `t[r,c]=a[r,c]+b[r,c]`,
  `y[r,c]=t[r,c]*t[r,c+1]+t[r,c]*t[r+1,c]`.
  Outputs preserve both full products and the final carry: 33 or **65 bits**.
- Cascade: `p[i]=a[i]*b[i]`, `q[i]=p[i]*p[i+1]`,
  `y[i]=q[i]+q[i+1]`, with indices modulo 256. This has two successive
  multiplication layers, 512 multipliers and 256 adders. Widths are
  8-bit inputs, 16-bit first products, 32-bit second products and 33-bit outputs.
- Nonlocal square: `t[i]=a[i]+b[i]`, `s[i]=t[i]*t[i]`,
  `p[i,k]=t[i]*t[(i+k) mod 128]`, `y[i,k]=s[i]+p[i,k]`, where
  `k` is ordered as `{1,7,31,63}`. There are 128 pre-adders, 128 square
  multipliers, 512 cross-product multipliers and 512 output adders. A factor
  has eight distinct cross-product neighbors, in addition to its square term.
  Nine-bit pre-additions are zero extended to 16-bit multiplier ports;
  full products are 32 bits and outputs are 33 bits.

Complete component output domains are retained even when their healthy values
occupy fewer bits. In particular, a faulty multiplier may produce any value
within its full output width. No internal observation or hidden narrowing is
introduced to make the diagnosis problem easier.

## Fault and observation generation

For each circuit: **2 fault levels x 3 recipes x 3 inputs = 18 observations**.
The first nine observations use the lower level, the next nine the higher level.
Within a level, observations 1-3 use SA0, 4-6 SA1, and 7-9 mixed faults.

Recipes are unchanged from the original dataset:

1. One permanent stuck-at-0 gate output per selected component.
2. One permanent stuck-at-1 gate output per selected component.
3. Two or three distinct gate outputs per selected component, with randomly
   sampled permanent polarities.

Whole components are sampled across strata of instance order, covering both
arithmetic operations. Gate outputs are real internal Boolean operations in
the frozen library. Gate sets are sampled conditional on a changed component
output on the anchor input, using the actual inputs propagated through the
faulty upstream circuit. All component outputs are fully used in these
topologies. Each of the three distinct input vectors must produce an externally
detectable output change. Later vectors need not activate every selected
component. The physical gate locations and polarities stay fixed across the
three observations.

The new standalone generator preserves the original fault semantics and recipes,
but is not claimed to reconstruct the unavailable original sampling program.
Master seed: **20261013**. Stable group seeds are SHA-256 derived from the
master seed, circuit, fault level and recipe. Headers retain group seeds and
sampling-attempt counts; `generation_report.json` summarizes all 48 groups.
There are **5,467 injected gate sites** across these groups, counted once per
physical configuration, not once per input. Injected counts are not optimum
diagnosis labels.

All observations have exactly two lines: a `# ` JSON metadata header, then a
JSON object containing only top-level `inputs` and `outputs`. Diagnosis software
must skip the header. Integer and bit files encode the same task. Use
`instances.json` for paths and group IDs. Group statistical resampling by
`(circuit, fault_pattern_id)` and retain all three observations.

## Generation and validation

The seven required arithmetic modules are byte-identical copies of the original
release's ArithsGen-generated library, pinned to commit
`2b5cc8f783b778043fdfca3d3f7e50a35cb69eaf`. No new arithmetic implementation is
substituted. The new topologies are project compositions, not upstream benchmark
circuits or industrial RTL. See `dataset_config.json` for component hashes and
the root `THIRD_PARTY_NOTICES.md` for provenance and licensing boundaries.

From the repository root, using Python 3.10 or later:

```sh
python3 -B tools/check_generator.py
python3 -B tools/supplement.py --output /path/to/new-private-directory
```

Generation uses only Python's standard library. It refuses to overwrite a file
with different contents and refuses the original dataset root as a target.
Use a new directory for regeneration. Observations are deterministically
reproducible; validation timing and external solver hashes are not generation
inputs.

With Icarus Verilog available:

```sh
python3 -B tools/validate_supplement.py \
  --dataset supplement_v1 --report /tmp/supplement-validation.json
```

Validation covers all 144 observations, both formats, legal widths, physical
gate sites and polarities, fixed fault groups, anchor activation and external
detectability. Independent Icarus Verilog replay passed **12,704 vectors**:
10,800 faulted component evaluations at their actual propagated input values,
plus 1,904 healthy component corner/random vectors. This is compositional gate
replay; it is not a claim that Icarus flattened all multi-million-gate top levels.
An additional 96 small circuit vectors check topology formulas with the complete
Boolean-library evaluator. Reports contain counts and hashes, no internal
witness assignments.

The optional `tools/check_arithdiag.py` checks all 144 witnesses against the
separately parsed original integer model, including ordered input connections,
and audits selected native inputs before/after preprocessing. Run it against an
ArithDiag checkout with its native binary built:

```sh
python3 -B tools/check_arithdiag.py --arithdiag /path/to/ArithDiag \
  --dataset supplement_v1 --report /tmp/model-validation.json
```

`tools/check_smt.py`, using SMT-Diag's interpreter and dependencies, validates a
fixed generated witness for one observation per circuit in both integer and
bit-vector encodings. This is a semantic compatibility check; it does not run
optimization and its witness constraints must never enter a comparison experiment.

### Recorded ArithDiag numeric limitation

All 144 original integer models and initial candidates validate exactly. Of
120 native input audits, 84 pass; the 36 failures are both preprocessing modes
for all 18 observations of `nl_mesh24x24_u16`. The tested native build has a
64-bit significand and cannot equivalently read some Big-M coefficients arising
from the full 65-bit output. Its existing input audit correctly rejects these
inputs. See `model_validation.json` for per-input flags and tested source/binary
hashes. Fix and validate the solver interface before including those ArithDiag
runs in formal timing comparisons. Do not truncate or replace valid benchmark
data to hide the limitation. Other solver budgets and memory limits may also
produce failures; this release supplies no optimality or runtime labels.

The original 450 instances remain frozen. Supplemental files use the same
whole-component weak-fault diagnosis semantics and project CC BY 4.0 license;
generated component libraries remain excluded from that grant.
