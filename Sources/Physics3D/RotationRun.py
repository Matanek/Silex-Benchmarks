#!/usr/bin/env python3
"""Qualify the rotational limit of linear CCD against pinned Jolt."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from Run import (BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex,
                 checked, fail, verified_source)

FIELDS = ('translating', 'subdivisions', 'contacts', 'x', 'z', 'axis_y')
CASES = {(moving, count) for moving in (0, 1) for count in (1, 36)}


def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        tokens = line.split()
        if len(tokens) != 7 or tokens[0] != 'rotation':
            fail(f'invalid rotation row: {line}')
        row = {}
        for token in tokens[1:]:
            key, separator, value = token.partition('=')
            if separator != '=' or key not in FIELDS or key in row:
                fail(f'invalid or duplicate field: {token}')
            if key == 'translating' and value in ('false', 'true'):
                value = '1' if value == 'true' else '0'
            number = float(value)
            if not math.isfinite(number):
                fail(f'non-finite field: {key}')
            row[key] = number
        identity = (row['translating'], row['subdivisions'])
        if identity not in CASES or identity in rows:
            fail(f'unknown or duplicate rotation case: {identity}')
        if row['contacts'] < 0 or row['contacts'] != int(row['contacts']):
            fail('contact count must be a nonnegative integer')
        rows[identity] = row
    if set(rows) != CASES:
        fail('missing rotation cases')
    return rows


def qualify(rows):
    for (translating, count), row in rows.items():
        if count == 1:
            if row['contacts'] != 0 or abs(row['x'] + 0.4) > 0.00001 or abs(row['axis_y'] + 1) > 0.00001:
                fail(f'coarse step no longer exposes the expected missed contact: {row}')
            if abs(row['z'] - 2 * translating) > 0.00001:
                fail(f'coarse translation changed: {row}')
        elif row['contacts'] < 1 or not -1.5 < row['x'] < -0.4:
            fail(f'subdivided step did not resolve contact: {row}')


def self_test():
    baseline = '\n'.join(f'rotation translating={moving} subdivisions={count} contacts={int(count > 1)} x={-0.4 if count == 1 else -1.1} z={moving * 2} axis_y={-1 if count == 1 else 0.4}'
                         for moving, count in sorted(CASES))
    qualify(parse_rows(baseline))
    invalid = (baseline + '\n' + baseline.splitlines()[0],
               '\n'.join(baseline.splitlines()[1:]), baseline.replace('contacts=0', 'contacts=nan', 1),
               baseline.replace('x=-0.4', 'x=0.4', 1), baseline.replace('contacts=1', 'contacts=0', 1),
               baseline.replace('subdivisions=36', 'subdivisions=35', 1), baseline.replace('contacts=1', 'contacts=1.5', 1))
    for output in invalid:
        try:
            qualify(parse_rows(output))
        except ValueError:
            continue
        fail('rotation qualifier accepted altered evidence')
    print('physics3d rotation guard self-test: ok')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--mode', choices=('Debug', 'Release', 'both'), default='both')
    parser.add_argument('--self-test', action='store_true')
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f'run from the workspace or Spec worktree group: {GROUP}')
    self_test()
    if options.self_test:
        return
    source, digest = verified_source(options.archive)
    record = {'schema': 1, 'fixture': 'rotating-blade-linear-ccd-v1', 'oracle_revision': REFERENCE,
              'archive_sha256': digest, 'host': platform.platform(), 'architecture': platform.machine(),
              'sources_sha256': {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                 for name in ('RotationOracle.cpp', 'RotationLimit.sx', 'RotationRun.py', 'Run.py')},
              'scope': 'coarse missed contact and contact with 36 subdivisions; no post-impact trajectory equivalence',
              'modes': {}}
    for mode in (('Debug', 'Release') if options.mode == 'both' else (options.mode,)):
        oracle = build_oracle(source, mode, HERE / 'RotationOracle.cpp', 'rotation-oracle')
        candidate = build_silex(mode, 'RotationLimit.sx', 'rotation-silex', physics=True)
        configuration = checked([str(oracle), '--configuration']).strip()
        if not configuration.startswith('Single precision '):
            fail('incompatible Jolt precision')
        observations = {}
        for name, binary in (('jolt', oracle), ('silex', candidate)):
            output = checked([str(binary)])
            (BUILD / f'rotation-{name}-{mode.lower()}.txt').write_text(output, encoding='utf-8')
            rows = parse_rows(output); qualify(rows)
            observations[name] = list(rows.values())
        record['modes'][mode] = {'jolt_configuration': configuration, **observations}
        print(f'physics3d rotation {mode}: pure/parallel motion miss in one step and contact in 36 substeps')
    (BUILD / 'rotation-qualification.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        print(f'physics3d rotation qualification failed: {error}', file=sys.stderr)
        raise SystemExit(1)
