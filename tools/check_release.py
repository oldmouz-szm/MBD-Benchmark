#!/usr/bin/env python3
"""Check distributed hashes, dataset registries and generation/report provenance."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
checked=0
for base in (ROOT,ROOT/'supplement_v1'):
    seen=set()
    for row in (base/'SHA256SUMS').read_text().splitlines():
        expected,name=row.split('  ',1)
        path=(base/name).resolve()
        assert path.is_relative_to(base.resolve()) and name not in seen
        assert sha(path)==expected,name
        seen.add(name);checked+=1
    if base!=ROOT:
        actual={p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
        assert actual==seen
registry=json.loads((ROOT/'datasets.json').read_text())
combined=json.loads((ROOT/'all_instances.json').read_text())
assert len(combined)==registry['observations']==594
assert len({r['instance_id'] for r in combined})==594
for row in combined:
    assert sha(ROOT/row['observation'])==row['sha256']
    assert (ROOT/row['netlist']).is_file() and (ROOT/row['library_dir']).is_dir()
    assert (ROOT/row['bit_observation']).is_file()
for filename,source,field in [('validation.json','validate_supplement.py','validator_sha256'),
                              ('model_validation.json','check_arithdiag.py','auditor_sha256'),
                              ('smt_validation.json','check_smt.py','auditor_sha256')]:
    report=json.loads((ROOT/'supplement_v1'/filename).read_text())
    assert report[field]==sha(ROOT/'tools'/source),(filename,source)
gate=json.loads((ROOT/'supplement_v1/validation.json').read_text())
assert gate['generator_sha256']==sha(ROOT/'tools/supplement.py')
assert gate['passed'] and gate['observations']==144
model=json.loads((ROOT/'supplement_v1/model_validation.json').read_text())
assert model['data_checks_passed'] and model['exact_original_models']==144
bad=[r for r in model['native_audits'] if not r['equivalent']]
assert len(bad)==36 and all(r['instance_id'].startswith('nl_mesh24x24_u16/') for r in bad)
print(json.dumps(dict(passed=True,checksum_entries=checked,combined_observations=594,
                      supplemental_observations=144,known_native_input_audit_failures=len(bad))))
