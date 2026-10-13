#!/usr/bin/env python3
"""Validate all supplementary observations and replay component faults in Icarus.

Faulted components are replayed with the actual propagated input values from
each observation. This is compositional gate replay, not a claim that every
large top-level circuit was flattened by Icarus. Temporary internal values are
deleted; only validation counts, versions and source hashes are reported.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import re
import subprocess
import tempfile
from supplement import CONFIGS, Circuit, DATASET, ROOT, RECIPES, digest, dump, load_libraries

def read(path):
    lines=path.read_text().splitlines()
    assert len(lines)==2 and lines[0].startswith('# ')
    return json.loads(lines[0][2:]),json.loads(lines[1])

def check(data):
    lib=load_libraries(data/'library')
    pinned={v['module']:v['sha256'] for v in json.loads((ROOT/'dataset_config.json').read_text())['library']}
    assert all(digest(g.path)==pinned[name] for name,g in lib.items())
    instances=json.loads((data/'instances.json').read_text())
    assert len(instances)==144 and len({r['instance_id'] for r in instances})==144
    circuits={conf[0]:Circuit(conf,lib) for conf in CONFIGS}
    for name,c in circuits.items():
        assert (data/'cases'/name/'netlist.v').read_text()==c.netlist()
    groups=defaultdict(list);vectors=defaultdict(list);active_total=0
    for row in instances:
        c=circuits[row['circuit']];path=data/row['observation']
        assert digest(path)==row['sha256']
        h,obs=read(path);bh,bits=read(data/row['bit_observation'])
        assert h==bh and set(obs)=={'inputs','outputs'} and set(bits)=={'inputs','outputs'}
        assert h['dataset']==DATASET and h['circuit']==c.name
        assert row['instance_id']==c.name+'/'+path.stem
        assert h['fault_pattern_id']==row['fault_pattern_id'] and h['observation_id']==row['observation_id']
        assert set(obs['inputs'])=={'a','b'} and set(obs['outputs'])=={'y'}
        for kind in ('inputs','outputs'):
            expected={f'{port}[{i}]':(int(value,16)>>i)&1 for port,value in obs[kind].items() for i in range(c.port_widths[port])}
            assert bits[kind]==expected
            assert all(0<=int(value,16)<1<<c.port_widths[port] for port,value in obs[kind].items())
        fault_groups=defaultdict(list)
        for f in h['faults']:
            co=c.component_map[f['component']];g=lib[co.module]
            assert f['module']==co.module and f['library']=='library/'+co.module+'.v'
            gate=g.gates[g.gate_index[f['gate']]]
            assert (f['line'],f['gate_type'])==(gate.line,gate.gate_type) and f['stuck_at'] in (0,1)
            fault_groups[co.name].append(f)
        assert len(fault_groups)==h['faulty_component_count']==row['injected_component_count']
        assert len(h['faults'])==h['injected_gate_count']==row['injected_gate_count']
        for fs in fault_groups.values():
            assert len({f['gate'] for f in fs})==len(fs)
            if h['fault_recipe']==RECIPES[2]:assert len(fs) in (2,3)
            else:assert len(fs)==1 and fs[0]['stuck_at']==(0 if h['fault_recipe']==RECIPES[0] else 1)
        inputs={k:int(v,16) for k,v in obs['inputs'].items()}
        transient=[]
        observed,_,active=c.simulate(inputs,h['faults'],trace=transient)
        healthy,_,_=c.simulate(inputs)
        assert observed=={k:int(v,16) for k,v in obs['outputs'].items()}
        assert observed!=healthy and active==h['locally_active_component_count']
        if h['observation_id']==1:assert active==len(fault_groups)
        active_total+=active
        for vector in transient:vectors[vector['module']].append(vector)
        groups[(c.name,h['fault_pattern_id'])].append((h,obs['inputs']))
    for rows in groups.values():
        assert len(rows)==3 and {r[0]['observation_id'] for r in rows}=={1,2,3}
        assert len({dump(r[1]) for r in rows})==3
        assert len({dump(r[0]['faults']) for r in rows})==1
        assert len({r[0]['pattern_seed'] for r in rows})==1
    assert len(groups)==48
    # Independent simulator additionally exercises zeros, maximum words,
    # carry propagation and pseudo-random healthy operands for every library.
    rng=random.Random(984612)
    healthy_count=0
    for name,g in lib.items():
        w=g.widths['a'];hi=(1<<w)-1
        pairs=[(a,b) for a in (0,1,hi,hi//2) for b in (0,1,hi,hi//2)]
        pairs += [(rng.getrandbits(w),rng.getrandbits(w)) for _ in range(256)]
        for a,b in pairs:
            value=g.arithmetic(a,b)
            assert g.evaluate(a,b)[0]==value
            vectors[name].append(dict(module=name,a=a,b=b,forced={},value=value))
            healthy_count+=1
    report=dict(dataset=DATASET,passed=True,circuits=8,observations=144,physical_fault_configurations=48,
                integer_bit_format_pairs=144,gate_fault_observation_replays=144,
                locally_active_component_observations=active_total,
                healthy_library_vectors=healthy_count,faulted_component_vectors=sum(len(v) for v in vectors.values())-healthy_count)
    return lib,vectors,report

def replay(lib,vectors,iverilog,vvp,ivl_dir,work):
    counts={}
    for module,vs in sorted(vectors.items()):
        g=lib[module];w=g.widths['a'];ow=g.widths[module+'_out']
        # Compile each module with bounded batches to bound elaboration memory.
        for batch_id,start in enumerate(range(0,len(vs),300)):
            batch=vs[start:start+300]
            lines=['module test;',f'reg [{w-1}:0] a,b;',f'wire [{ow-1}:0] y;',
                   f'{module} dut(.a(a),.b(b),.{module}_out(y));','initial begin']
            for i,v in enumerate(batch):
                lines.append(f"a={w}'h{v['a']:x}; b={w}'h{v['b']:x};")
                for index,stuck in v['forced'].items():
                    lines.append(f"force dut.{g.gates[index].name}=1'b{stuck};")
                lines += ['#1;',f"if(y !== {ow}'h{v['value']:x}) $fatal(1, \"mismatch {module} {start+i}\");"]
                for index in v['forced']:
                    lines.append('release dut.'+g.gates[index].name+';')
                lines.append('#1;')
            lines += [f'$display("PASS {len(batch)}");','$finish;','end','endmodule','']
            tb=work/'test.v';binary=work/'test.vvp';tb.write_text('\n'.join(lines))
            command=[iverilog]
            if ivl_dir:command+=['-B',ivl_dir]
            command+=['-g2012','-s','test','-o',str(binary),str(g.path),str(tb)]
            built=subprocess.run(command,capture_output=True,text=True,timeout=90)
            if built.returncode:raise RuntimeError('Icarus compilation failed: '+built.stderr[-3000:])
            result=subprocess.run([vvp,str(binary)],capture_output=True,text=True,timeout=90)
            if result.returncode or f'PASS {len(batch)}' not in result.stdout:
                raise RuntimeError('Independent gate replay failed: '+result.stdout[-2000:]+result.stderr[-1000:])
        counts[module]=len(vs)
        print(dump(dict(icarus_module=module,passed_vectors=len(vs))),flush=True)
    return counts

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dataset',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--iverilog',default='iverilog');ap.add_argument('--vvp',default='vvp')
    ap.add_argument('--ivl-dir');ap.add_argument('--work-dir',type=Path)
    args=ap.parse_args()
    lib,vectors,report=check(args.dataset.resolve())
    with tempfile.TemporaryDirectory(prefix='mbd-replay-',dir=args.work_dir) as temp:
        counts=replay(lib,vectors,args.iverilog,args.vvp,args.ivl_dir,Path(temp))
    report['independent_replay']=dict(method='Icarus Verilog compositional gate replay at actual propagated component inputs',
                                      module_vectors=counts,total_vectors=sum(counts.values()),passed=True)
    command=[args.iverilog]+(['-B',args.ivl_dir] if args.ivl_dir else [])+['-V']
    version=subprocess.run(command,capture_output=True,text=True,timeout=10)
    report['independent_replay']['version']=version.stdout.splitlines()[0]
    report['validator_sha256']=digest(Path(__file__))
    report['generator_sha256']=digest(Path(__file__).with_name('supplement.py'))
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(dump(report),flush=True)

if __name__=='__main__':main()
