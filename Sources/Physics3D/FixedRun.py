#!/usr/bin/env python3
"""Qualify fixed attachments against pinned Jolt and analytical invariants."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS = ('x', 'y', 'z', 'axis_x', 'axis_y', 'axis_z', 'anchor_error', 'angular_error',
          'force_y', 'torque_z', 'speed_x', 'speed_z', 'first_speed_x', 'first_speed_z')
SAMPLES = ((90,120,150,180,210,240,270,300), (150,180,210,240,270,300,330,360),
           (30,60,90,120,150,180,210,240), (90,120,390,1500,1530,1560,1590,1620),
           (900,930,960,990,1020,1050,1080,1110), (30,60,90,120,150,180,210,240))
CASES = {(case, step) for case, steps in enumerate(SAMPLES) for step in steps}
# Numerical bounds are unchanged from v1. Sampling times for v2 follow the
# observed slow Jolt position convergence at four position iterations.
BOUNDS = {name: 0.003 for name in FIELDS}
BOUNDS.update(force_y=0.5, torque_z=1.0, speed_x=0.02, speed_z=0.02)


def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        tokens = line.split()
        if len(tokens) != 17 or tokens[0] != 'fixed':
            fail(f'invalid fixed row: {line}')
        values = list(map(float, tokens[1:]))
        if not all(map(math.isfinite, values)):
            fail('non-finite fixed evidence')
        identity = tuple(values[:2])
        if identity not in CASES or identity in rows:
            fail(f'unknown or duplicate fixed row: {identity}')
        rows[tuple(map(int, identity))] = dict(zip(FIELDS, values[2:]))
    if set(rows) != CASES:
        fail('missing fixed samples')
    return rows


def qualify(rows):
    for (case, step), row in rows.items():
        free = case == 3 and step == 390
        if row['anchor_error'] < 0 or row['angular_error'] < 0:
            fail('negative fixed error norm')
        if not free and (row['anchor_error'] > 0.002 or row['angular_error'] > 0.002):
            fail(f'fixed lost frame alignment: {case}, {step}, {row}')
        if case in (0, 4) or (case == 3 and step >= 1500):
            force, torque = (98.1, 176.58) if case == 4 else (19.62, 39.24)
            if abs(row['force_y'] - force) > 0.5 or abs(row['torque_z'] - torque) > 1:
                fail(f'fixed load differs from force and lever moment: {case}, {step}, {row}')
        if free:
            if abs(row['force_y']) > 1e-5 or abs(row['torque_z']) > 1e-5 or row['y'] > -1:
                fail('disabled fixed attachment did not fall freely')
        if case == 2:
            if abs(2*row['first_speed_x'] + 8*row['speed_x'] - 2) > 1e-4:
                fail('fixed violated linear momentum')
            if abs(0.2*row['first_speed_z'] + 0.8*row['speed_z'] - 0.2) > 1e-4:
                fail('fixed violated angular momentum')
            if abs(row['x'] - 0.2*step/60) > 0.003 or abs(row['speed_z']-0.2) > 1e-4:
                fail('fixed free assembly differs from conserved motion')


def compare(actual, reference):
    errors = {name: 0.0 for name in FIELDS}
    for identity in sorted(CASES):
        case, step = identity
        for name in FIELDS:
            error = abs(actual[identity][name] - reference[identity][name])
            errors[name] = max(errors[name], error)
            if error > BOUNDS[name]:
                fail(f'fixed {identity} {name}: error {error}, bound {BOUNDS[name]}')
    return errors


def self_test():
    rows = {}
    for case, step in CASES:
        row = dict.fromkeys(FIELDS, 0.0); row['axis_x'] = 1
        if case in (0, 3, 4):
            row['force_y'], row['torque_z'] = (98.1, 176.58) if case == 4 else (19.62, 39.24)
        if case == 3 and step == 390:
            row.update(force_y=0, torque_z=0, y=-1.267, anchor_error=1.267)
        if case == 2:
            row.update(x=0.2*step/60, speed_x=0.2, first_speed_x=0.2, speed_z=0.2, first_speed_z=0.2)
        rows[(case, step)] = row
    output = '\n'.join('fixed ' + ' '.join(map(str, (case, step, *(row[name] for name in FIELDS))))
                       for (case, step), row in sorted(rows.items()))
    qualify(parse_rows(output)); compare(rows, rows)
    for corrupt in (output+'\n'+output.splitlines()[0], '\n'.join(output.splitlines()[1:]),
                    output.replace('fixed 0 90 0', 'fixed 0 90 nan', 1),
                    output.replace('fixed 0 90', 'fixed 7 30', 1)):
        try:
            parse_rows(corrupt)
        except ValueError:
            continue
        fail('fixed guard accepted corrupt evidence')
    for key, name, value in (((0, 90), 'force_y', 0), ((4, 900), 'torque_z', 0),
                             ((2, 60), 'first_speed_z', 1), ((3, 390), 'force_y', 1),
                             ((1, 240), 'angular_error', 0.1)):
        altered = {key: row.copy() for key, row in rows.items()}; altered[key][name] = value
        try:
            qualify(altered)
        except ValueError:
            continue
        fail('fixed guard accepted invalid physical evidence')
    altered = {key: row.copy() for key, row in rows.items()}; altered[(5, 240)]['x'] = 0.1
    try:
        compare(altered, rows)
    except ValueError:
        pass
    else:
        fail('fixed comparator accepted a perturbed trajectory')
    print('physics3d fixed guard self-test: ok')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--mode', choices=('Debug', 'Release', 'both'), default='both')
    parser.add_argument('--self-test', action='store_true')
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f'run from workspace or Spec group root: {GROUP}')
    self_test()
    if options.self_test:
        return
    source, digest = verified_source(options.archive)
    record = {'schema': 1, 'fixture': 'fixed-six-cases-settled-v2',
              'oracle_revision': REFERENCE, 'archive_sha256': digest,
              'host': platform.platform(), 'architecture': platform.machine(),
              'sources_sha256': {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                 for name in ('FixedOracle.cpp', 'Fixed.sx', 'FixedRun.py', 'Run.py')},
              'scope': '60 Hz, up to 27 seconds, static lever, rotated frames near pi, unequal free masses, disable/enable, loaded chain, translating and rotating kinematic support. Origin-local anchors equal COM-local anchors in these fixtures.',
              'bounds': BOUNDS, 'sampling_steps': SAMPLES, 'scope_limit': 'settled alignment and reactions, free and kinematic motion; no comparative claim about large-error correction trajectories or time-to-convergence',
              'iterations': {'jolt_velocity': 12, 'jolt_position': 4, 'silex_preparation': 12, 'silex_velocity': 12, 'silex_position': 4},
              'modes': {}}
    for mode in (('Debug', 'Release') if options.mode == 'both' else (options.mode,)):
        oracle = build_oracle(source, mode, HERE / 'FixedOracle.cpp', 'fixed-oracle')
        silex = build_silex(mode, 'Fixed.sx', 'fixed-silex', physics=True)
        outputs = {'jolt': checked([str(oracle)]), 'silex': checked([str(silex)])}
        for name, output in outputs.items():
            (BUILD / f'fixed-{name}-{mode.lower()}.txt').write_text(output)
        reference = parse_rows(outputs['jolt']); actual = parse_rows(outputs['silex'])
        qualify(reference); qualify(actual)
        record['modes'][mode] = {'samples': 48, 'maximum_absolute_errors': compare(actual, reference)}
        print(f'physics3d fixed {mode}: 48 samples qualified against Jolt and analytical invariants')
    (BUILD / 'fixed-qualification.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        print(f'physics3d fixed: {error}', file=sys.stderr)
        sys.exit(1)
