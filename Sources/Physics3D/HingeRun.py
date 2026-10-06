#!/usr/bin/env python3
"""Compare a free hinge, weight support, mutated stops and a pendulum with pinned Jolt."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from Run import (BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex,
                 checked, fail, verified_source)

FIELDS = ('x', 'y', 'angle', 'angular_speed', 'anchor_error', 'axis_error', 'force_y')
CASES = {(case, step) for case in range(4) for step in range(15, 121, 15)}


def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        tokens = line.split()
        if len(tokens) != 10 or tokens[0] != 'hinge':
            fail(f'invalid hinge row: {line}')
        values = list(map(float, tokens[1:]))
        if not all(map(math.isfinite, values)):
            fail('hinge row contains a non-finite value')
        identity = tuple(values[:2])
        if identity not in CASES or identity in rows:
            fail(f'unknown or duplicate hinge row: {identity}')
        rows[identity] = dict(zip(FIELDS, values[2:]))
    if set(rows) != CASES:
        fail('missing hinge samples')
    return rows


def qualify(rows):
    for (case, step), row in rows.items():
        if not 0 <= row['anchor_error'] < 0.003 or not 0 <= row['axis_error'] < 0.001:
            fail(f'hinge lost its anchor or axis: {case}, {step}, {row}')
        if case == 0 and (abs(row['angle'] - step / 60) > 0.002 or
                          abs(row['angular_speed'] - 1) > 0.0001):
            fail('free hinge rotation or off-axis rejection changed')
        if case == 1 and (abs(row['y'] + 1) > 0.002 or abs(row['force_y'] - 9.81) > 0.05):
            fail('hinge weight support changed')
        if case == 2:
            minimum, maximum = (-0.3, 0.4) if step <= 60 else (-0.2, 0.2)
            if not minimum - 0.003 <= row['angle'] <= maximum + 0.003:
                fail('hinge escaped its active stops')
            if step == 60 and abs(row['angle'] - 0.4) > 0.003:
                fail('upper stop was not reached')
            if step == 120 and (abs(row['angle'] + 0.2) > 0.003 or abs(row['angular_speed']) > 0.002):
                fail('mutated lower stop was not reached')
        if case == 3 and (abs(row['angle']) > 0.61 or abs(row['x']) > 1.15):
            fail('pendulum escaped its initial amplitude')


def compare(actual, reference):
    errors = {name: 0.0 for name in FIELDS}
    for identity in sorted(CASES):
        pendulum = identity[0] == 3
        bounds = {'x': 0.06 if pendulum else 0.001, 'y': 0.06 if pendulum else 0.001,
                  'angle': 0.03 if pendulum else 0.034 if identity[0] == 2 and identity[1] > 60 else 0.002,
                  'angular_speed': 0.08 if pendulum else 0.002,
                  'force_y': 0.5 if pendulum else 0.05}
        for name in FIELDS:
            errors[name] = max(errors[name], abs(actual[identity][name] - reference[identity][name]))
        for name, bound in bounds.items():
            error = abs(actual[identity][name] - reference[identity][name])
            boundary_speed = False
            if identity[0] == 2 and identity[1] > 60 and name == 'angular_speed':
                boundary_speed = (abs(actual[identity]['angle'] + 0.2) <= 0.034 and
                                  abs(reference[identity]['angle'] + 0.2) <= 0.034 and
                                  abs(actual[identity][name]) <= 2.001 and abs(reference[identity][name]) <= 2.001)
            if error > bound and not boundary_speed:
                fail(f'hinge {identity} {name} differs by {error}, bound {bound}')
    return errors


def self_test():
    rows = {}
    for case, step in CASES:
        angle = step / 60 if case == 0 else (0.4 if step <= 60 else -0.2) if case == 2 else 0
        rows[(case, step)] = dict(zip(FIELDS, (0, -1 if case == 1 else 0, angle,
                                             1 if case == 0 else 0, 0, 0, 9.81 if case == 1 else 0)))
    output = '\n'.join('hinge ' + ' '.join(map(str, (case, step, *(row[name] for name in FIELDS))))
                       for (case, step), row in sorted(rows.items()))
    qualify(parse_rows(output))
    invalid = [output + '\n' + output.splitlines()[0], '\n'.join(output.splitlines()[1:]),
               output.replace('hinge 0 15 0', 'hinge 0 15 nan', 1)]
    for evidence in invalid:
        try:
            qualify(parse_rows(evidence))
        except ValueError:
            continue
        fail('hinge parser accepted corrupt evidence')
    altered = {key: row.copy() for key, row in rows.items()}
    altered[(3, 120)]['angle'] = 0.5
    try:
        compare(altered, rows)
    except ValueError:
        pass
    else:
        fail('hinge comparator accepted a perturbed angle')
    print('physics3d hinge guard self-test: ok')


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
    record = {'schema': 1, 'fixture': 'hinge-four-cases-120-steps-v1', 'oracle_revision': REFERENCE,
              'archive_sha256': digest, 'host': platform.platform(), 'architecture': platform.machine(),
              'sources_sha256': {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                 for name in ('HingeOracle.cpp', 'Hinge.sx', 'HingeRun.py', 'Run.py')},
              'scope': 'one worker, 60 Hz, two seconds, local frames, hard stops; no motors or soft stops',
              'boundary_comparison': 'After limit mutation, angle allows one 2 rad/s step (0.034 rad). Speed near the lower stop may differ at the impact sample; both must stop by 120.',
              'modes': {}}
    for mode in (('Debug', 'Release') if options.mode == 'both' else (options.mode,)):
        oracle = build_oracle(source, mode, HERE / 'HingeOracle.cpp', 'hinge-oracle')
        silex = build_silex(mode, 'Hinge.sx', 'hinge-silex', physics=True)
        oracle_output = checked([str(oracle)])
        silex_output = checked([str(silex)])
        (BUILD / f'hinge-jolt-{mode.lower()}.txt').write_text(oracle_output)
        (BUILD / f'hinge-silex-{mode.lower()}.txt').write_text(silex_output)
        oracle_rows = parse_rows(oracle_output); silex_rows = parse_rows(silex_output)
        qualify(oracle_rows); qualify(silex_rows)
        record['modes'][mode] = {'samples': 32, 'maximum_absolute_errors': compare(silex_rows, oracle_rows)}
        print(f'physics3d hinge {mode}: 32 samples qualified against Jolt')
    (BUILD / 'hinge-qualification.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        print(f'physics3d hinge: {error}', file=sys.stderr)
        sys.exit(1)
