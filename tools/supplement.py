#!/usr/bin/env python3
"""Reproducible supplementary circuits and permanent gate-fault observations.

Python standard library only. Existing output files must match byte-for-byte.
The frozen root dataset is never a generation target. Component RTL is reused
unchanged from the root library with hashes recorded in dataset_config.json.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
DATASET = "ArithDiag-Supplement8-v1"
SEED = 20261013
UPSTREAM = "2b5cc8f783b778043fdfca3d3f7e50a35cb69eaf"
CONFIGS = [
    ("nl_ring256_u16", "ring", 256, 16, 512),
    ("nl_ring512_u16", "ring", 512, 16, 1024),
    ("nl_ring256_u8", "ring", 256, 8, 512),
    ("nl_mesh24x24_u8", "mesh", 24, 8, 2304),
    ("nl_mesh32x32_u8", "mesh", 32, 8, 4096),
    ("nl_mesh24x24_u16", "mesh", 24, 16, 2304),
    ("nl_cascade256_u8", "cascade", 256, 8, 768),
    ("nl_nonlocal_square128_u8", "nonlocal_square", 128, 8, 1280),
]
RECIPES = ("sa0_single", "sa1_single", "mixed_multi_2_to_3")
OFFSETS = (1, 7, 31, 63)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def seed_for(*parts):
    return int.from_bytes(hashlib.sha256("|".join(map(str, (SEED, *parts))).encode()).digest()[:8], "big")

def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def write(path, text):
    path = Path(path)
    data = text.encode()
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Refusing to replace different existing file: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

def json_file(path, value):
    write(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")

@dataclass(frozen=True)
class Gate:
    name: str
    line: int
    gate_type: str

class GateLibrary:
    """Compile only validated scalar Boolean RTL; support simultaneous faults."""
    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.stem
        text = self.path.read_text()
        ports = re.findall(r"(input|output)\s+\[(\d+):0\]\s+(\w+)", text.split(";", 1)[0])
        self.widths = {name: int(high)+1 for _, high, name in ports}
        assert set(self.widths) == {"a", "b", self.name+"_out"}
        self.operation = "multiply" if "mul" in self.name else "add"
        self.gates = []
        known = {"a", "b"}
        lines = ["def evaluate(a,b,forced=None,capture=False):", "    forced = {} if forced is None else forced", "    result=0"]
        outputs = set()
        for number, raw in enumerate(text.splitlines(), 1):
            raw = raw.split("//", 1)[0].strip()
            if not raw.startswith("assign "):
                continue
            m = re.fullmatch(r"assign\s+(.+?)\s*=\s*(.+?)\s*;", raw)
            if not m:
                raise ValueError((self.name, number, raw))
            target, source = m.groups()
            tree = ast.parse(source, mode="eval")
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Expression, ast.BinOp, ast.BitAnd, ast.BitOr, ast.BitXor,
                                         ast.UnaryOp, ast.Invert, ast.Name, ast.Load, ast.Subscript, ast.Constant)):
                    raise ValueError((self.name, "unsupported gate expression", source))
                if isinstance(node, ast.Name) and node.id not in known:
                    raise ValueError((self.name, "undefined signal", node.id))
                if isinstance(node, ast.Subscript):
                    if not isinstance(node.value, ast.Name) or node.value.id not in ("a", "b") or not isinstance(node.slice, ast.Constant):
                        raise ValueError(source)
                    if type(node.slice.value) is not int or not 0 <= node.slice.value < self.widths[node.value.id]:
                        raise ValueError(source)
            expr = re.sub(r"\b([ab])\[(\d+)\]", r"((\1 >> \2) & 1)", source)
            bit = re.fullmatch(re.escape(self.name+"_out")+r"\[(\d+)\]", target)
            if bit:
                index = int(bit[1])
                if index in outputs:
                    raise ValueError("duplicate output bit")
                outputs.add(index)
                lines.append(f"    result |= (({expr}) & 1) << {index}")
            else:
                if not re.fullmatch(r"[A-Za-z_]\w*", target) or target in known:
                    raise ValueError(target)
                kind = {ast.BitAnd:"AND", ast.BitOr:"OR", ast.BitXor:"XOR"}.get(type(getattr(tree.body, "op", None)))
                if isinstance(tree.body, ast.UnaryOp):
                    kind = "NOT"
                if kind:
                    idx = len(self.gates)
                    self.gates.append(Gate(target, number, kind))
                    lines.append(f"    {target}=forced.get({idx}, ({expr}) & 1)")
                else:
                    lines.append(f"    {target}=({expr}) & 1")
                known.add(target)
        assert outputs == set(range(self.widths[self.name+"_out"]))
        trace = ",".join(g.name for g in self.gates)
        lines.append(f"    return result, ({trace},) if capture else None")
        namespace = {}
        exec(compile("\n".join(lines), self.name, "exec"), {"__builtins__": {}}, namespace)
        self.evaluate = namespace["evaluate"]
        self.gate_index = {g.name:i for i,g in enumerate(self.gates)}

    def arithmetic(self, a, b):
        return a*b if self.operation == "multiply" else a+b

@dataclass(frozen=True)
class Ref:
    signal: str
    low: int
    width: int
    def verilog(self):
        return f"{self.signal}[{self.low+self.width-1}:{self.low}]"
    def read(self, values):
        return (values[self.signal] >> self.low) & ((1 << self.width)-1)

@dataclass(frozen=True)
class Component:
    name: str
    module: str
    a: Ref
    b: Ref
    output: str
    width: int

class Circuit:
    def __init__(self, config, library):
        self.name, self.family, self.size, self.width, expected = config
        self.library = library
        n = self.size**2 if self.family == "mesh" else self.size
        count = n*4 if self.family == "nonlocal_square" else n
        ow = 4*self.width if self.family == "ring" else 4*self.width+1 if self.family == "mesh" else 33
        self.port_widths = {"a":n*self.width, "b":n*self.width, "y":count*ow}
        self.components = []
        self.outputs = []
        self.counts = Counter()
        def part(port, i):
            return Ref(port, i*self.width, self.width)
        def comp(module, a, b):
            op = "M" if "mul" in module else "A"
            i = self.counts[op]; self.counts[op] += 1
            name = op+str(i); signal = ("p" if op == "M" else "t")+str(i)
            width = library[module].widths[module+"_out"]
            self.components.append(Component(name, module, a, b, signal, width))
            return Ref(signal, 0, width)
        if self.family in ("ring", "mesh", "nonlocal_square"):
            ts = [comp(f"u_rca{self.width}", part("a", i), part("b", i)) for i in range(n)]
        if self.family == "ring":
            self.outputs = [comp(f"u_arrmul{2*self.width}", ts[i], ts[(i+1)%n]) for i in range(n)]
        elif self.family == "mesh":
            for i in range(n):
                r,c = divmod(i, self.size)
                right = r*self.size+(c+1)%self.size
                lower = ((r+1)%self.size)*self.size+c
                p = comp(f"u_arrmul{2*self.width}", ts[i], ts[right])
                q = comp(f"u_arrmul{2*self.width}", ts[i], ts[lower])
                self.outputs.append(comp(f"u_rca{4*self.width}", p, q))
        elif self.family == "cascade":
            ps = [comp("u_arrmul8", part("a", i), part("b", i)) for i in range(n)]
            qs = [comp("u_arrmul16", ps[i], ps[(i+1)%n]) for i in range(n)]
            self.outputs = [comp("u_rca32", qs[i], qs[(i+1)%n]) for i in range(n)]
        elif self.family == "nonlocal_square":
            ss = [comp("u_arrmul16", t, t) for t in ts]
            for i in range(n):
                for k in OFFSETS:
                    p = comp("u_arrmul16", ts[i], ts[(i+k)%n])
                    self.outputs.append(comp("u_rca32", ss[i], p))
        else:
            raise ValueError(self.family)
        assert len(self.components) == expected
        assert all(ref.width == ow for ref in self.outputs)
        self.output_width = ow
        self.component_map = {c.name:c for c in self.components}

    def netlist(self):
        lines = ["// ArithDiag supplementary benchmark; project-composed topology.",
                 f"// Unmodified ArithsGen components from commit {UPSTREAM}.",
                 "// Full unsigned component outputs; each M/A instance is faultable.",
                 "// Packed top-level observations only; all index wraps are spatial, not feedback.",
                 f"// family={self.family}; size={self.size}; input_width={self.width}",
                 f"module bench_{self.name} (", f"  input [{self.port_widths['a']-1}:0] a,",
                 f"  input [{self.port_widths['b']-1}:0] b,", f"  output [{self.port_widths['y']-1}:0] y", ");"]
        for c in self.components:
            def padded(ref):
                w = self.library[c.module].widths['a']
                assert ref.width <= w
                return ref.verilog() if ref.width == w else "{"+str(w-ref.width)+"'b0, "+ref.verilog()+"}"
            lines += [f"  wire [{c.width-1}:0] {c.output};",
                      f"  {c.module} {c.name} (.a({padded(c.a)}), .b({padded(c.b)}), .{c.module}_out({c.output}));"]
        for i, ref in enumerate(self.outputs):
            lines.append(f"  assign y[{(i+1)*self.output_width-1}:{i*self.output_width}] = {ref.verilog()};")
        return "\n".join([*lines, "endmodule", ""])

    def simulate(self, inputs, faults=(), choose=None, rng=None, recipe=None, stats=None, trace=None, all_gates=False, values_out=None):
        values = dict(inputs)
        by_component = defaultdict(list)
        for f in faults:
            by_component[f['component']].append(f)
        generated = []; active = 0
        for c in self.components:
            a,b = c.a.read(values),c.b.read(values)
            lib = self.library[c.module]
            nominal = lib.arithmetic(a,b)
            forced = {lib.gate_index[f['gate']]:f['stuck_at'] for f in by_component[c.name]}
            if choose is not None and c.name in choose:
                healthy, gate_values = lib.evaluate(a,b,capture=True)
                assert healthy == nominal
                success = False
                for trial in range(10000):
                    stats['gate_set_attempts'] += 1
                    count = rng.choice((2,3)) if recipe == RECIPES[2] else 1
                    indices = rng.sample(range(len(lib.gates)), count)
                    polarity = [rng.randrange(2) for _ in indices] if count > 1 else [0 if recipe == RECIPES[0] else 1]
                    forced = dict(zip(indices, polarity))
                    # No changed internal value means no output change is possible.
                    if all(gate_values[i] == v for i,v in forced.items()):
                        continue
                    value,_ = lib.evaluate(a,b,forced)
                    if value != nominal:
                        success = True
                        break
                if not success:
                    raise ValueError('No locally active gate set within fixed generation budget')
                for index, stuck in forced.items():
                    g = lib.gates[index]
                    generated.append(dict(component=c.name, module=c.module, library=f'library/{c.module}.v',
                                          line=g.line, gate=g.name, gate_type=g.gate_type, stuck_at=stuck))
            elif forced or all_gates:
                value,_ = lib.evaluate(a,b,forced)
            else:
                value = nominal
            if forced:
                active += value != nominal
                if trace is not None:
                    trace.append(dict(module=c.module, a=a, b=b, forced=forced, value=value))
            assert 0 <= value < 1 << c.width
            values[c.output] = value
        values['y'] = sum(ref.read(values) << (i*self.output_width) for i,ref in enumerate(self.outputs))
        if values_out is not None:
            values_out.update(values)
        return {'y':values['y']}, generated, active

def stratified(circuit, count, rng):
    cs = circuit.components
    indices = [rng.randrange(i*len(cs)//count, (i+1)*len(cs)//count) for i in range(count)]
    selected = {cs[i].name for i in indices}
    assert len(selected) == count
    if len({name[0] for name in selected}) < 2:
        missing = 'A' if next(iter(selected)).startswith('M') else 'M'
        alternatives = [c.name for c in cs if c.name.startswith(missing) and c.name not in selected]
        selected.remove(sorted(selected)[rng.randrange(len(selected))])
        selected.add(rng.choice(alternatives))
    return selected

def generate(circuit, out):
    case = out/'cases'/circuit.name
    write(case/'netlist.v', circuit.netlist())
    modules = sorted({c.module for c in circuit.components})
    write(case/'files.f', '\n'.join(['netlist.v', *['../../library/'+m+'.v' for m in modules]])+'\n')
    records=[]; group_reports=[]; number=0
    for level in (len(circuit.components)//32, len(circuit.components)//16):
        for recipe in RECIPES:
            pid = f'F{len(group_reports)+1:03d}'
            seed = seed_for(circuit.name, level, recipe)
            rng = random.Random(seed)
            selected = stratified(circuit, level, rng)
            stats = dict(anchor_input_attempts=0, gate_set_attempts=0, extra_input_attempts=0)
            for attempt in range(1000):
                stats['anchor_input_attempts'] += 1
                inputs = {p:rng.getrandbits(circuit.port_widths[p]) for p in ('a','b')}
                try:
                    observed,faults,active = circuit.simulate(inputs, choose=selected, rng=rng, recipe=recipe, stats=stats)
                except ValueError:
                    continue
                healthy,_,_ = circuit.simulate(inputs)
                if observed != healthy and active == level:
                    break
            else:
                raise RuntimeError((circuit.name, level, recipe, 'anchor generation exhausted'))
            samples = [(inputs,observed,active)]
            while len(samples) < 3:
                stats['extra_input_attempts'] += 1
                if stats['extra_input_attempts'] > 10000:
                    raise RuntimeError('external detectability sampling exhausted')
                inputs = {p:rng.getrandbits(circuit.port_widths[p]) for p in ('a','b')}
                if any(inputs == old[0] for old in samples):
                    continue
                observed,_,active = circuit.simulate(inputs, faults)
                healthy,_,_ = circuit.simulate(inputs)
                if observed != healthy:
                    samples.append((inputs,observed,active))
            for oid,(inputs,observed,active) in enumerate(samples,1):
                number += 1
                header = dict(dataset=DATASET,circuit=circuit.name,fault_model='gate_output_stuck_at',
                              fault_pattern_id=pid,fault_recipe=recipe,faults=faults,faulty_component_count=level,
                              injected_gate_count=len(faults),locally_active_component_count=active,
                              observation_id=oid,pattern_seed=seed,observation_seed=None,
                              input_generation='pattern_rng_stream',generation_statistics=stats)
                row = dict(inputs={k:hex(v) for k,v in inputs.items()},outputs={k:hex(v) for k,v in observed.items()})
                obs = case/f'observations_{number:03d}.jsonl'
                write(obs, '# '+dump(header)+'\n'+dump(row)+'\n')
                bits = {kind:{f'{p}[{i}]':(int(v,16)>>i)&1 for p,v in row[kind].items() for i in range(circuit.port_widths[p])}
                        for kind in ('inputs','outputs')}
                bitobs = case/f'gate_observations_{number:03d}.jsonl'
                write(bitobs, '# '+dump(header)+'\n'+dump(bits)+'\n')
                records.append(dict(instance_id=f'{circuit.name}/{obs.stem}',circuit=circuit.name,
                                    netlist=str((case/'netlist.v').relative_to(out)),library_dir='library',
                                    observation=str(obs.relative_to(out)),bit_observation=str(bitobs.relative_to(out)),
                                    fault_pattern_id=pid,observation_id=oid,injected_component_count=level,
                                    injected_gate_count=len(faults),externally_detectable=True,sha256=digest(obs),
                                    split='supplement',independent_single_observation=True))
            group_reports.append(dict(circuit=circuit.name,fault_pattern_id=pid,fault_recipe=recipe,
                                      injected_component_count=level,injected_gate_count=len(faults),**stats))
            print(dump(dict(circuit=circuit.name,group=pid,observations=number,**stats)),flush=True)
    return records,group_reports

def load_libraries(path):
    return {p.stem:GateLibrary(p) for p in sorted(Path(path).glob('*.v')) if p.stem != 'u_dadda_cla4'}

def metadata(circuit):
    return dict(name=circuit.name,family=circuit.family,size=circuit.size,width=circuit.width,
                arithmetic_components=len(circuit.components),adders=circuit.counts['A'],multipliers=circuit.counts['M'],
                boolean_gates=sum(len(circuit.library[c.module].gates) for c in circuit.components),
                fault_levels=[len(circuit.components)//32,len(circuit.components)//16],observations=18,
                fixed_fault_configurations=6,ports=circuit.port_widths,output_lane_width=circuit.output_width,
                multiplication_depth=2 if circuit.family == 'cascade' else 1,
                square_components=circuit.size if circuit.family == 'nonlocal_square' else 0,
                offsets=list(OFFSETS) if circuit.family == 'nonlocal_square' else [])

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--library', type=Path, default=ROOT/'library')
    args=ap.parse_args()
    out=args.output.resolve()
    if out == ROOT or out == args.library.resolve() or (out/'dataset_config.json').exists() and json.loads((out/'dataset_config.json').read_text()).get('dataset') != DATASET:
        raise ValueError('Not a supplementary generation target')
    out.mkdir(parents=True,exist_ok=True)
    lib=load_libraries(args.library)
    pinned={v['module']:v['sha256'] for v in json.loads((ROOT/'dataset_config.json').read_text())['library']}
    for name,g in lib.items():
        if digest(g.path) != pinned[name]:
            raise ValueError('Component differs from frozen library: '+name)
    for module in lib:
        target=out/'library'/(module+'.v')
        write(target,lib[module].path.read_text())
    records=[];groups=[];circuits=[]
    for config in CONFIGS:
        circuit=Circuit(config,lib)
        rows,reports=generate(circuit,out)
        records+=rows;groups+=reports;circuits.append(metadata(circuit))
    json_file(out/'instances.json',records)
    json_file(out/'circuits.json',circuits)
    json_file(out/'generation_report.json',dict(dataset=DATASET,seed=SEED,physical_fault_configurations=48,
                                               gate_sites=sum(g['injected_gate_count'] for g in groups),groups=groups))
    json_file(out/'dataset_config.json',dict(dataset=DATASET,version='1.0.0',release_date='2026-10-13',seed=SEED,
        circuits=circuits,logical_instances=144,fixed_fault_configurations=48,physical_observation_files=288,
        fault_patterns_per_level=3,observations_per_pattern=3,fault_recipes=list(RECIPES),
        fault_density_denominators=[32,16],observation_numbering='001-018 per circuit',
        observation_mode='independent single-observation weak component diagnosis',
        injection='permanent internal Boolean gate-output stuck-at faults in distinct whole components',
        selection='predeclared topology, size and width; no solver result or performance filtering',
        acceptance='all selected components locally active on anchor input under propagated faulty inputs; all three observations externally detectable',
        generation='new standalone generator; same fault semantics and recipes as original set; not an exact recreation of the old sampling implementation',
        arithmetic_generator=dict(repository='https://github.com/ehw-fit/ariths-gen',commit=UPSTREAM,version='1.1.4'),
        topology_origin='project-composed; not an upstream benchmark or external industrial RTL',
        library=[dict(module=m,sha256=digest(g.path),commit=UPSTREAM,origin='unmodified frozen v1.0.0 component') for m,g in lib.items()],
        dataset_license='CC-BY-4.0',generated_library_license='not specified by pinned upstream'))
    print(dump(dict(completed=True,circuits=len(circuits),observations=len(records),fault_configurations=len(groups))),flush=True)

if __name__ == '__main__':
    main()
