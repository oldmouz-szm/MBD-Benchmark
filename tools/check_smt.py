#!/usr/bin/env python3
"""Optional SMT encoding check for generated witnesses, not a search experiment.

Run with SMT-Diag's interpreter. Gate-fault metadata are used only to construct
known witnesses for validation. No optimization, benchmark timing, diagnoses or
signal assignments are exported.
"""
import argparse,hashlib,json,sys
from pathlib import Path
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--smt-project',type=Path,required=True)
ap.add_argument('--dataset',type=Path,required=True)
ap.add_argument('--report',type=Path,required=True)
args=ap.parse_args()
sys.path.insert(0,str(Path(__file__).resolve().parent))
import supplement as gen
sys.path.insert(0,str(args.smt_project.resolve()/'src'))
import z3
from circuit import load
from encoding import Encoding
data=args.dataset.resolve();lib=gen.load_libraries(data/'library')
rows=json.loads((data/'instances.json').read_text())
report=dict(kind='fixed_generated_witness_validation',not_a_performance_experiment=True,
            z3_version=z3.get_version_string(),checks=[],passed=True)
for conf in gen.CONFIGS:
    c=gen.Circuit(conf,lib)
    row=next(r for r in rows if r['circuit']==c.name)
    lines=(data/row['observation']).read_text().splitlines()
    h=json.loads(lines[0][2:]);obs=json.loads(lines[1]);values={}
    c.simulate({k:int(v,16) for k,v in obs['inputs'].items()},h['faults'],values_out=values)
    faulty={f['component'] for f in h['faults']}
    for mode in ('int','bv'):
        circuit=load(data,row['instance_id']);enc=Encoding(circuit,mode)
        for variable in circuit.model['variables']:
            if variable['role']=='abnormal':continue
            high,low=variable['bits'];value=(values[variable['signal']]>>low)&((1<<(high-low+1))-1)
            enc.solver.add(enc.terms[variable['name']]==value)
        for name,term in enc.ab.items():enc.solver.add(term==(name in faulty))
        enc.solver.set(timeout=30000)
        status=enc.solver.check()
        assert status==z3.sat,(row['instance_id'],mode,str(status))
        assignment,diagnosis=enc.decode(enc.solver.model())
        assert circuit.verify(assignment,diagnosis)==len(faulty)
        report['checks'].append(dict(instance_id=row['instance_id'],encoding=mode,verified=True))
        print(json.dumps(report['checks'][-1]),flush=True)
        del enc,circuit,assignment,diagnosis
report['auditor_sha256']=gen.digest(Path(__file__))
report['source_hashes']={str(p.relative_to(args.smt_project)):gen.digest(p) for p in [args.smt_project/'src/encoding.py',args.smt_project/'src/circuit.py']}
args.report.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,checks=len(report['checks']))),flush=True)
