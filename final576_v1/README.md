# ArithDiag-Final576-v1

Frozen on **2026-10-21**: **36 circuits, 192 physical fault configurations,
576 independent single-observation diagnosis tasks**. Each task has integer and
bit formats: 1,152 observation files, not 1,152 independent tasks.

This is the designated final evaluation input snapshot. Freezing the inputs
does not imply that a uniform final solver experiment has already been run.

## Composition

| Source pool | Original tasks | Retained | Excluded |
|---|---:|---:|---:|
| CAIQ-Arith10-v1 (`final_v1`) | 450 | 180 | 270 |
| ArithDiag-Supplement8-v1 | 144 | 72 | 72 |
| ArithDiag-Medium9-v1 | 162 | 162 | 0 |
| ArithDiag-Stress9-v1 | 162 | 162 | 0 |
| Total | 918 | 576 | 342 |

All 36 circuit types and all injected-component count levels within each
circuit remain represented. An entire physical fault group and its three
observations are kept or excluded together. All three fault recipes remain:
one stuck-at-0 gate per component, one stuck-at-1 gate per component, and
two or three mixed-polarity gates per component. Original instance IDs,
observation numbers, faults, inputs, outputs, netlists and component libraries
are preserved byte for byte; retained observation numbers may have gaps.

## Selection and interpretation

**The reduction is performance-informed. This is not an unseen test set.**
The original and first-supplement pools were reduced using previously observed
AD-LS and BE-RC2 complete-process wall times. Among combinations satisfying
the fixed per-circuit quotas and coverage constraints, selection maximizes
the sum of the slower method's wall time, followed by the sum of absolute
wall-time differences, with SHA256 order breaking remaining ties.
This is symmetric in method identity; the method winner, diagnosis cardinality,
optimum label and proof status are not selection inputs. The 324 medium/stress
tasks are retained in full. Nevertheless, timing-informed selection changes
the evaluation population and must be disclosed in performance claims.

Original circuits retain six physical groups each: all five fault-count levels,
with each recipe represented twice. First-supplement circuits retain three
groups each: both count levels, with each recipe represented once. Every
medium and stress circuit retains all six original groups.

`selection_manifest.json` records the policy and historical timing-source hash;
`selection_groups.json` records all 306 group decisions, and
`excluded_instances.json` records the 342 excluded tasks. Actual historical
timings, solver results and optimum labels are not included. These decision
lists reproduce the frozen membership without rerunning a timing experiment.
`provenance/` preserves source generation conditions and third-party notices.
The source data generators did not filter by runtime; this later reduction did.

## Diagnosis semantics

Each complete top-level adder or multiplier is one unit-cost diagnosable
component. A healthy component must satisfy its unsigned full arithmetic
function. An abnormal component's output is unrestricted within its declared
width, subject to all wiring, slice, extension and observation constraints.
Only top-level inputs and outputs are observed. Gate stuck-at locations are
generation truth, not constraints or initialization information for diagnosis.
The injected component count is not a minimum diagnosis label.

Each of the three observations in a physical group is solved separately.
For statistical analysis retain the `(circuit, fault_pattern_id)` cluster.
No reference optima or expected solver outcomes are supplied.
Ring/mesh indices describe spatial connections in layered combinational DAGs,
not temporal feedback. Width in the table below is the base operand width;
intermediate and output buses can be wider, including 65-bit outputs.

## Usage and verification

Pass **this directory** as the dataset root and use its `instances.json`.
The root repository's legacy `instances.json` and `all_instances.json` still
describe the old 450 and 594 tasks, respectively; they are not this release's
recommended evaluation list. Do not concatenate overlapping historical and
final datasets.

```bash
python tools/verify_final576.py --dataset-root final576_v1
```

The verifier uses only the Python standard library. It checks file hashes,
instance layout, integer/bit correspondence, complete physical groups and
coverage. This integrity check is not a solver benchmark, a new gate-fault
replay, or a formal optimality proof. `SHA256SUMS` covers every file in this
directory except itself. The repository-level checksums are refreshed for this release; historical checksums remain available at v1.x tags.

## Circuits

| Circuit | Source | Components | Base width | Observations |
|---|---|---:|---:|---:|
| `dot128_u8` | `final_v1` | 255 | 8 | 18 |
| `fir32x32_u8` | `final_v1` | 2016 | 8 | 18 |
| `mac_bank16_u4` | `final_v1` | 32 | 4 | 18 |
| `matvec16x16_u8` | `final_v1` | 496 | 8 | 18 |
| `matvec64x64_u8` | `final_v1` | 8128 | 8 | 18 |
| `nl_cascade256_u8` | `supplement_v1` | None | 8 | 9 |
| `nl_chord_ring1024_u16` | `stress_v1` | None | 16 | 18 |
| `nl_chord_ring1024_u8` | `stress_v1` | None | 8 | 18 |
| `nl_chord_ring2048_u16` | `stress_v1` | None | 16 | 18 |
| `nl_chord_ring256_u16` | `medium_v1` | None | 16 | 18 |
| `nl_chord_ring256_u8` | `medium_v1` | None | 8 | 18 |
| `nl_chord_ring512_u8` | `medium_v1` | None | 8 | 18 |
| `nl_mesh16x16_u8` | `final_v1` | 1024 | 8 | 18 |
| `nl_mesh24x24_u16` | `supplement_v1` | None | 16 | 9 |
| `nl_mesh24x24_u8` | `supplement_v1` | None | 8 | 9 |
| `nl_mesh28x28_u16` | `medium_v1` | None | 16 | 18 |
| `nl_mesh32x32_u16` | `stress_v1` | None | 16 | 18 |
| `nl_mesh32x32_u8` | `supplement_v1` | None | 8 | 9 |
| `nl_mesh36x36_u8` | `medium_v1` | None | 8 | 18 |
| `nl_mesh40x40_u8` | `medium_v1` | None | 8 | 18 |
| `nl_mesh48x48_u8` | `stress_v1` | None | 8 | 18 |
| `nl_mesh64x64_u8` | `stress_v1` | None | 8 | 18 |
| `nl_nonlocal_square128_u8` | `supplement_v1` | None | 8 | 9 |
| `nl_ring128_u16` | `final_v1` | 256 | 16 | 18 |
| `nl_ring16_u8` | `final_v1` | 32 | 8 | 18 |
| `nl_ring256_u16` | `supplement_v1` | None | 16 | 9 |
| `nl_ring256_u8` | `supplement_v1` | None | 8 | 9 |
| `nl_ring512_u16` | `supplement_v1` | None | 16 | 9 |
| `nl_shared_product1024_u8` | `stress_v1` | None | 8 | 18 |
| `nl_shared_product128_u16` | `medium_v1` | None | 16 | 18 |
| `nl_shared_product128_u8` | `medium_v1` | None | 8 | 18 |
| `nl_shared_product256_u8` | `medium_v1` | None | 8 | 18 |
| `nl_shared_product512_u16` | `stress_v1` | None | 16 | 18 |
| `nl_shared_product512_u8` | `stress_v1` | None | 8 | 18 |
| `sliding_pair128_u8` | `final_v1` | 255 | 8 | 18 |
| `sumprod16x64_u8` | `final_v1` | 4080 | 8 | 18 |

## License and provenance

Project-owned data and top-level compositions are CC BY 4.0. The eight
generated ArithsGen component files are excluded from this license grant;
the pinned upstream revision has no explicit license file. See
`THIRD_PARTY_NOTICES.md`, `dataset_config.json` and source notices in
`provenance/`. No new license is assigned to third-party generated libraries.
