#!/usr/bin/env python3
"""Verify Final576 integrity and observation/group structure, without solving."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def resolve(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Missing or escaping file: ' + relative)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_observation(path):
    lines = path.read_text(encoding='utf-8').splitlines()
    if len(lines) != 2 or not lines[0].startswith('#'):
        raise ValueError('Observation must have one metadata line and one payload: ' + str(path))
    metadata, payload = json.loads(lines[0][1:]), json.loads(lines[1])
    if set(payload) != {'inputs', 'outputs'}:
        raise ValueError('Only top-level inputs and outputs are permitted')
    return metadata, payload


def verify(root):
    root = root.resolve()
    seen = set()
    for line in (root / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        expected, relative = line.split('  ', 1)
        if relative in seen or sha(resolve(root, relative)) != expected:
            raise ValueError('Duplicate or mismatched checksum: ' + relative)
        seen.add(relative)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*')
              if p.is_file() and p != root / 'SHA256SUMS'}
    if actual != seen:
        raise ValueError('Checksum inventory does not match distributed files')
    rows = read(root / 'instances.json')
    if len(rows) != 576 or len({r['instance_id'] for r in rows}) != 576:
        raise ValueError('Expected exactly 576 unique tasks')
    if collections.Counter(r['source_dataset'] for r in rows) != {
            'final_v1': 180, 'supplement_v1': 72, 'medium_v1': 162, 'stress_v1': 162}:
        raise ValueError('Source counts do not match freeze')
    groups = collections.defaultdict(list)
    widths = {}
    for row in rows:
        circuit = row['circuit']
        if not re.fullmatch(r'[A-Za-z0-9_]+/observations_[0-9]+', row['instance_id']):
            raise ValueError('Invalid instance ID')
        if row['instance_id'] != circuit + '/' + Path(row['observation']).stem:
            raise ValueError('Misleading instance paths')
        integer = resolve(root, row['observation'])
        bits = resolve(root, row['bit_observation'])
        netlist = resolve(root, row['netlist'])
        expected_parent = root / 'cases' / circuit
        if integer.parent != expected_parent or bits.parent != expected_parent or netlist != expected_parent / 'netlist.v':
            raise ValueError('Unexpected input layout')
        if sha(integer) != row['sha256'] or sha(bits) != row['bit_sha256']:
            raise ValueError('Index hash mismatch')
        a_meta, a = load_observation(integer)
        b_meta, b = load_observation(bits)
        for meta in (a_meta, b_meta):
            if meta['circuit'] != circuit or meta['fault_pattern_id'] != row['fault_pattern_id']:
                raise ValueError('Metadata identity mismatch')
            if meta['observation_id'] != row['observation_id']:
                raise ValueError('Observation identity mismatch')
        if a_meta['faults'] != b_meta['faults']:
            raise ValueError('Integer/bit fault truth differs')
        if circuit not in widths:
            ports = re.findall(r'\b(input|output)\s+\[(\d+):0\]\s+(\w+)', netlist.read_text(encoding='utf-8'))
            widths[circuit] = {kind: {name: int(msb) + 1 for k, msb, name in ports if k == kind}
                               for kind in ('input', 'output')}
        for kind, direction in (('input', 'inputs'), ('output', 'outputs')):
            if set(a[direction]) != set(widths[circuit][kind]):
                raise ValueError('Top-level port mismatch')
            expected_bits = {}
            for port, value in a[direction].items():
                value = int(value, 0) if isinstance(value, str) else value
                width = widths[circuit][kind][port]
                if type(value) is not int or not 0 <= value < (1 << width):
                    raise ValueError('Unsigned signal exceeds declared width')
                # Linear conversion also handles very wide flattened buses.
                little_endian_bits = bin(value)[2:].zfill(width)[::-1]
                expected_bits.update({f'{port}[{i}]': int(bit)
                                      for i, bit in enumerate(little_endian_bits)})
            if b[direction] != expected_bits:
                raise ValueError('Integer/bit observation mismatch')
        groups[(row['source_dataset'], circuit, row['fault_pattern_id'])].append((row, a_meta))
    if len(groups) != 192 or len(widths) != 36:
        raise ValueError('Expected 192 physical groups and 36 circuits')
    profiles = collections.defaultdict(list)
    for (source, circuit, pattern), values in groups.items():
        if len(values) != 3 or len({meta['observation_id'] for _, meta in values}) != 3:
            raise ValueError('Physical group lost observations')
        if len({json.dumps(meta['faults'], sort_keys=True) for _, meta in values}) != 1:
            raise ValueError('Permanent fault configuration changed within a group')
        levels = {row['injected_component_count'] for row, _ in values}
        recipes = {meta['fault_recipe'] for _, meta in values}
        if len(levels) != 1 or len(recipes) != 1:
            raise ValueError('Inconsistent fault-group descriptors')
        profiles[(source, circuit)].append((next(iter(levels)), next(iter(recipes))))
    for (source, circuit), profile in profiles.items():
        original = next(c for c in read(root / 'provenance' / source / 'original_circuits.json')
                        if c['name'] == circuit)
        if {level for level, _ in profile} != set(original['fault_levels']):
            raise ValueError('Fault-level coverage lost')
        expected = 1 if source == 'supplement_v1' else 2
        recipes = collections.Counter(recipe for _, recipe in profile)
        if len(recipes) != 3 or set(recipes.values()) != {expected}:
            raise ValueError('Fault-recipe coverage is not balanced')
    excluded = read(root / 'excluded_instances.json')
    excluded_ids = {row['instance_id'] for row in excluded}
    if len(excluded) != 342 or len(excluded_ids) != 342 or excluded_ids & {r['instance_id'] for r in rows}:
        raise ValueError('Excluded membership mismatch')
    decisions = read(root / 'selection_groups.json')
    decision_keys = {(g['dataset'], g['circuit'], g['fault_pattern_id']) for g in decisions if g['selected']}
    if len(decisions) != 306 or decision_keys != set(groups):
        raise ValueError('Group decision manifest mismatch')
    return dict(passed=True, checksum_files=len(seen), circuits=36, physical_fault_groups=192,
                observations=576, observation_files=1152, excluded=342,
                integer_bit_equivalence=True, unsigned_port_widths=True,
                complete_groups=True, fault_level_coverage=True, balanced_recipes=True,
                solver_invocations=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-root', type=Path, default=Path(__file__).resolve().parents[1] / 'final576_v1')
    args = parser.parse_args()
    print(json.dumps(verify(args.dataset_root), sort_keys=True))
