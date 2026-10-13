"""Optional ArithDiag integration audit; stores validation counts, never witnesses.

Uses fault metadata only to check data-generation witnesses. This is a data
validation tool, not a diagnosis experiment or a source of optimum labels.
"""
import argparse,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--arithdiag',type=Path,required=True)
ap.add_argument('--dataset',type=Path,default=REPO/'supplement_v1')
ap.add_argument('--report',type=Path,required=True)
args=ap.parse_args()
DATA=args.dataset.resolve()
ARITH=args.arithdiag.resolve()
sys.path.insert(0,str(REPO/'tools'))
import supplement as gen
sys.path.insert(0,str(ARITH/'src'))
from model_io import load_builder,validate,render,audit
from preprocess import transform,initial,projected_initial,restore
from worker import encode
builder=load_builder()
lib=gen.load_libraries(DATA/'library')
circuits={c[0]:gen.Circuit(c,lib) for c in gen.CONFIGS}
rows=json.loads((DATA/'instances.json').read_text())
report=dict(exact_original_models=0,bit_format_models=0,native_audits=[],initialisations=0,data_checks_passed=True)
begun=time.monotonic()
with tempfile.TemporaryDirectory(prefix='model-audit-',dir=None) as tmp:
    for row in rows:
        name=row['circuit'];c=circuits[name]
        hraw,oraw=(DATA/row['observation']).read_text().splitlines()
        h=json.loads(hraw[2:]);obs=json.loads(oraw)
        model=builder.build_diagnostic_model(DATA/row['netlist'],DATA/row['observation'],DATA/'library')
        assert builder._observation_values(DATA/row['bit_observation'],model)==model['observed_ports']
        report['bit_format_models']+=1
        values={};c.simulate({p:int(v,16) for p,v in obs['inputs'].items()},h['faults'],values_out=values)
        def expression(e):
            result=0
            for part in e['parts']:
                ref=part['ref']
                value=0 if ref is None else (values[ref['signal']]>>ref['low'])&((1<<(ref['high']-ref['low']+1))-1)
                result=(result<<part['width'])+value
            return result
        for co in model['components']:
            generated=c.component_map[co['name']]
            # Check input ordering even on faulty components: gate faults need
            # not be symmetric when the healthy arithmetic is commutative.
            assert expression(co['a'])==generated.a.read(values)
            assert expression(co['b'])==generated.b.read(values)
        faulty={f['component'] for f in h['faults']}
        witness={}
        for v in model['variables']:
            if v['role']=='abnormal':witness[v['name']]=int(v['signal'] in faulty)
            else:
                high,low=v['bits'];witness[v['name']]=(values[v['signal']]>>low)&((1<<(high-low+1))-1)
        check=validate(model,witness)
        assert check['valid'],(row['instance_id'],len(check.get('errors',[])))
        report['exact_original_models']+=1
        init=initial(model);assert validate(model,init)['valid'];report['initialisations']+=1
        if row['observation_id']==1 or name=='nl_mesh24x24_u16':
            for structural in (False,True):
                pre=transform(model,structural,structural)
                restore(pre,projected_initial(pre,init))
                group=dict(variables=sorted(pre['specs']),components=[v['signal'] for v in pre['specs'].values() if v['role']=='abnormal'],
                           constraints=[constraint for g in pre['groups'] for constraint in g['constraints']])
                specs,encoded,names=encode(pre,group)
                lp=Path(tmp)/'audit.lp';lp.write_text(render(specs,encoded))
                p=subprocess.run([str(ARITH/'native/ls-iqcqp/build/LS-IQCQP'),'--audit',str(lp)],capture_output=True,text=True,timeout=30)
                if p.returncode:raise RuntimeError('native parser failed '+str(p.returncode))
                checked=audit(specs,encoded,json.loads(p.stdout))
                entry=dict(instance_id=row['instance_id'],structural=structural,
                           equivalent=checked['mathematically_equivalent_input'],numbers_exact=checked['parsed_numbers_exact'],
                           mantissa_bits=checked['native_float_mantissa_bits'],
                           safe_bigm_roundings=checked['safe_redundant_bigm_rounding_count'],
                           numeric_mismatch_count=checked['numeric_mismatch_count'],
                           mismatch_fields=sorted({v['field'] for v in checked['numeric_mismatches']}))
                report['native_audits'].append(entry)
        if row['observation_id']==3:
            print(json.dumps(dict(circuit=name,models_checked=report['exact_original_models'])),flush=True)
report['all_tested_native_inputs_equivalent']=all(a['equivalent'] for a in report['native_audits'])
report['native_input_audits_passed']=sum(a['equivalent'] for a in report['native_audits'])
report['native_input_audits_failed']=sum(not a['equivalent'] for a in report['native_audits'])
report['elapsed_s']=round(time.monotonic()-begun,3)
report['auditor_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
report['source_hashes']={str(p.relative_to(ARITH)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ARITH/'vendor/iqcqp_model.py',ARITH/'vendor/exact_verify.py',ARITH/'src/preprocess.py',ARITH/'src/model_io.py',ARITH/'native/ls-iqcqp/build/LS-IQCQP']}
args.report.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('native_audits','source_hashes')}),flush=True)
