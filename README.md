# MBD-Benchmark: CAIQ-Arith10-v1

A frozen benchmark for model-based diagnosis of arithmetic circuits at the
**whole-component level**.

**10 circuits · 150 fixed physical fault configurations · 450 single-observation
diagnosis instances.** Each circuit has 45 instances:
**5 injected-component levels × 3 fault configurations × 3 distinct input vectors**.
Each instance has equivalent integer and bit observation formats, giving 900
observation files. These formats are mirrors, not additional instances.

## Circuits

| Circuit | Arithmetic components | Boolean gates | Injected component levels | Structure |
|---|---:|---:|---|---|
| mac_bank16_u4 | 32 | 1,952 | 1/2/4/6/8 | Small MAC bank; Dadda multipliers |
| dot128_u8 | 255 | 60,899 | 1/2/4/8/16 | Single-output linearizable control |
| sliding_pair128_u8 | 255 | 50,739 | 1/2/4/8/16 | Shared products; overlapping outputs |
| matvec16x16_u8 | 496 | 119,600 | 1/2/4/8/16 | Medium matrix-vector array |
| fir32x32_u8 | 2,016 | 483,424 | 1/4/8/16/32 | 32-tap FIR; 32 output samples |
| matvec64x64_u8 | 8,128 | 1,943,744 | 1/8/16/32/64 | Large matrix-vector array |
| sumprod16x64_u8 | 4,080 | 1,837,104 | 1/8/16/32/64 | Pre-addition feeding unknown-factor products |
| nl_ring16_u8 | 32 | 23,120 | 1/2/4/6/8 | Small nonlinear shared ring |
| nl_ring128_u16 | 256 | 763,520 | 1/2/4/8/16 | Wide nonlinear shared ring |
| nl_mesh16x16_u8 | 1,024 | 770,560 | 1/4/8/16/32 | Shared nonlinear mesh; reconvergence |

Boolean-gate counts sum AND, OR, XOR and NOT operations inside instantiated
arithmetic components, excluding aliases and top-level wiring. Gate, component,
integer-variable and CNF-variable counts are different.

Small controls, large arithmetic networks and unobserved internal multiplication
factors are included. Size and nonlinear terms do not guarantee solver difficulty.
Instances were not selected by solver runtime, diagnosis cardinality or method wins.

## Diagnosis semantics

- One complete top-level adder or multiplier instance is one diagnosable component.
- AB(c)=0: the component obeys its unsigned arithmetic function.
- AB(c)=1: its output is unrestricted within its legal output width, subject to
  circuit wiring and the observed top-level inputs and outputs.
- Minimum-cardinality diagnosis minimizes the number of abnormal components.

This is a weak component fault model. Gate-level stuck-at faults generate the
observations; they do not define the diagnostic granularity. A faulty component
must not retain healthy internal gate-function constraints. Fault metadata are
for replay and evaluation, never known faults or constraints for diagnosis.

The injected component count is **not** the minimum diagnosis cardinality.
Masking and alternative explanations are possible. No optimality labels are supplied.

The three observations of a fault configuration use exactly the same permanent
fault sites and polarities. Diagnose them **independently**, rather than jointly.
Group statistical analyses by circuit and fault_pattern_id to account for
correlated observations.

## Files

~~~text
library/                         # eight generated arithmetic modules
cases/<circuit>/
    netlist.v                    # complete hierarchical healthy circuit
    files.f                      # top-level and relative library compilation list
    observations_001.jsonl ... observations_045.jsonl
    gate_observations_001.jsonl ... gate_observations_045.jsonl
circuits.json                    # circuit sizes and instance counts
dataset_config.json              # design, generation conditions and provenance
instances.json                   # 450 entries, relative paths and group IDs
SHA256SUMS                       # checksums for all other distributed files
LICENSE
THIRD_PARTY_NOTICES.md
~~~

The top-level netlist and its modules in library/ form the complete circuit.
These are healthy models; permanent gate faults are specified in observation
headers. Merged copies of the same circuit and separate copies of fault truth
are unnecessary.

Numbering is continuous within each circuit: 001–009, 010–018, 019–027,
028–036 and 037–045 are its five increasing fault levels. Within each level,
the first three observations use stuck-at-0, the next three stuck-at-1, and the
last three mixed-polarity multiple-gate faults. observation_id is 1–3 within a
physical fault configuration. Stable fault-pattern IDs may have gaps.

Use instances.json for batch experiments. Entries provide the circuit, netlist,
library directory, equivalent observation paths, fault group, injected component
and gate counts, and the integer-observation SHA256.

## Observation format

Every observation file has exactly two lines:

1. A line beginning with # followed by JSON metadata: physical fault group,
   input-generation seeds and gate sites. Each site specifies component instance,
   module, library file, one-based source line, gate signal, type and stuck value.
2. A JSON object with **only inputs and outputs** of top-level ports.

Example integer-format data from the first MAC instance:

~~~json
{
  "inputs": {
    "a": "0x660f1d7ca3000370",
    "b": "0x506953f7f0ae7aa2",
    "acc": "0x4a436fcd117ad3713415f89ff3a027f4"
  },
  "outputs": {
    "y": "0x3410cdf540b28678c565055f09f79af8caf4"
  }
}
~~~

Integer values are unsigned hexadecimal strings. Equivalent bit files use keys
such as a[0], where bit zero is the least significant bit, and values 0 or 1.
No internal signals are observed.

Read line two for diagnosis; use line one only for fault replay and evaluation.
Standard JSONL readers must explicitly skip the # metadata line.

## Fault generation

Each component-count level has three fixed configurations:

1. One stuck-at-0 gate per selected component.
2. One stuck-at-1 gate per selected component.
3. Two or three distinct gates per selected component, with randomly sampled
   stuck values.

Distinct whole components are selected by stratified random sampling across
instance order. Both adders and multipliers are covered when both types are
present and at least two components are selected. Gate sites are actual internal
Boolean operation outputs selected randomly inside those components.

Sampling is conditional on activation: the first input changes at least one
used output-boundary bit of every selected component; all three inputs produce
externally detectable output changes. Some faults can be masked on other inputs.
This is not unconditional uniform gate sampling.

There are 2,427 injected gate sites across 150 configurations; one configuration
has at most 173 sites. Replaying a configuration under three inputs does not
create three independent physical fault configurations. Seeds remain in the
headers. The frozen observations are the canonical experimental inputs.

## Arithmetic provenance and wiring

All eight arithmetic modules were generated directly using
[ArithsGen](https://github.com/ehw-fit/ariths-gen), pinned to commit
[2b5cc8f783b778043fdfca3d3f7e50a35cb69eaf](https://github.com/ehw-fit/ariths-gen/tree/2b5cc8f783b778043fdfca3d3f7e50a35cb69eaf).
Generator classes, widths and module hashes are in dataset_config.json.

Top-level networks were composed by this project. They are not an upstream
standard ArithsGen benchmark suite.

All signals are unsigned. Module outputs retain their full width; explicit
Verilog slices and zero extensions define wiring, including fault-state truncation.

- Dot, matrix-vector and FIR reductions retain 33-bit adder outputs with
  low-32-bit connections. Healthy inputs do not overflow the retained result.
- Sum-product pre-additions preserve 9 bits, extend to 16-bit multiplier inputs,
  and feed a 64-bit reduction tree with explicit low-64-bit connections.
- Ring pre-additions preserve 9 or 17 bits and feed 16- or 32-bit multipliers.
- The mesh has periodic boundaries. Each pre-addition output is multiplied
  by its right and lower neighbors; the two products form one output.
  Intermediate signals are not observed.

## Checking and using the release

From the repository root, on a system with sha256sum:

~~~sh
sha256sum -c SHA256SUMS
~~~

Compile a healthy circuit with Icarus Verilog:

~~~sh
cd cases/mac_bank16_u4
iverilog -g2012 -s bench_mac_bank16_u4 -o /tmp/mac_bank16_u4.vvp -f files.f
~~~

Compilation checks the complete healthy source hierarchy. To replay a fault,
force the listed internal gate signals in the listed instances to fixed values.

All 450 instances were checked before publication for widths, wiring,
healthy-component arithmetic, top-level observations, fault replay and format
equivalence. Independent Icarus Verilog gate replay passed 4,898 test vectors.
These checks establish data consistency, not a formal proof for arbitrary
Verilog or optimal diagnoses.

For comparisons, use the same manifest, complete-component fault boundaries,
observations and diagnostic objective. Report failed and timed-out runs as well
as successes. Include preprocessing and model construction in complete-process time.

## Citation and license

Please cite this repository, release version **1.0.0**, and the commit used
in your experiments. Acknowledge ArithsGen for the generated components.

Repository: https://github.com/oldmouz-szm/MBD-Benchmark

Project-authored observations, metadata, documentation and top-level circuit
compositions use **CC BY 4.0**; see [LICENSE](LICENSE).
Generated component libraries are excluded from that license grant. Their
origin and the absence of an upstream license file at the pinned revision are
documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
