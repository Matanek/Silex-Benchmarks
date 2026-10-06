#!/usr/bin/env python3
"""Qualify torque-limited velocity hinges against pinned Jolt and analytical cases."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS = ('x', 'y', 'angle', 'speed', 'first_speed', 'second_speed', 'motor_torque',
          'anchor_error', 'axis_error', 'force_y')
CASES = {(case, step) for case in range(5) for step in range(15, 121, 15)}
TORQUES = (0.1, 1.0, 0.1, 0.4, 20.0)


def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        tokens = line.split()
        if len(tokens) != 13 or tokens[0] != 'motor':
            fail(f'invalid motor row: {line}')
        values = list(map(float, tokens[1:]))
        if not all(map(math.isfinite, values)):
            fail('non-finite motor evidence')
        identity = tuple(values[:2])
        if identity not in CASES or identity in rows:
            fail(f'unknown or duplicate motor row: {identity}')
        rows[tuple(map(int, identity))] = dict(zip(FIELDS, values[2:]))
    if set(rows) != CASES:
        fail('missing motor samples')
    return rows


def qualify(rows):
    for (case, step), row in rows.items():
        if not 0 <= row['anchor_error'] < 0.005 or not 0 <= row['axis_error'] < 0.002:
            fail(f'motor lost its anchor or axis: {case}, {step}')
        if abs(row['motor_torque']) > TORQUES[case] + 0.00001:
            fail(f'motor exceeded torque bound: {case}, {step}')
        if case < 4 and (abs(row['x']) > 0.001 or abs(row['y']) > 0.001):
            fail('central motor translated its center')
        if case == 0:
            if abs(row['speed'] - step / 60) > 0.0001 or abs(row['motor_torque'] - 0.1) > 0.00001:
                fail('torque/inertia acceleration differs')
        if case == 1:
            expected = 1 if step <= 60 else -1
            if abs(row['speed'] - expected) > 0.0001:
                fail('target, reversal or coasting differs')
            if step >= 105 and abs(row['motor_torque']) > 0.00001:
                fail('stopped motor still applies torque')
        if case == 2:
            expected = min(1, step / 48) if step <= 60 else max(-1, 1 - (step - 60) / 48)
            if abs(row['speed'] - expected) > 0.0001:
                fail('unequal inertia relative acceleration differs')
            if abs(0.1 * row['first_speed'] + 0.4 * row['second_speed']) > 0.00001:
                fail('motor violated action/reaction momentum')
        if case == 3:
            if not -0.203 <= row['angle'] <= 0.303:
                fail('powered hinge escaped hard stops')
            if step in (60, 120):
                limit = 0.3 if step == 60 else -0.2
                if abs(row['angle'] - limit) > 0.003 or abs(row['speed']) > 0.003:
                    fail('powered hinge failed to arrest at stop')
        if case == 4 and abs(row['speed'] - 1) > 0.08:
            fail('pendulum failed to reach target with sufficient torque')


def compare(actual, reference):
    errors = {name: 0.0 for name in FIELDS}
    for identity in sorted(CASES):
        case, step = identity
        bounds = {'x': 0.04 if case == 4 else 0.001, 'y': 0.04 if case == 4 else 0.001,
                  'angle': 0.04 if case == 4 else 0.034,
                  'speed': 0.08 if case == 4 else 0.003,
                  'first_speed': 0.003, 'second_speed': 0.08 if case == 4 else 0.003,
                  'motor_torque': 0.2 if case == 4 else 0.001,
                  'force_y': 0.8 if case == 4 else 0.05}
        for name in FIELDS:
            error = abs(actual[identity][name] - reference[identity][name])
            errors[name] = max(errors[name], error)
            if name not in bounds or error <= bounds[name]:
                continue
            phase = False
            if case == 3 and name in ('speed', 'second_speed') and step not in (60, 120):
                limit = 0.3 if step <= 60 else -0.2
                phase = all(abs(rows[identity]['angle'] - limit) <= 0.034 and
                            abs(rows[identity][name]) <= 2.001 for rows in (actual, reference))
            if not phase:
                fail(f'motor {identity} {name}: error {error}, bound {bounds[name]}')
    return errors


def self_test():
    rows = {}
    for case, step in CASES:
        speed = step / 60 if case == 0 else (1 if step <= 60 else -1) if case == 1 else (
            min(1, step / 48) if step <= 60 else max(-1, 1 - (step - 60) / 48)) if case == 2 else 0 if case == 3 else 1
        angle = (0.3 if step <= 60 else -0.2) if case == 3 else 0
        first = -0.8 * speed if case == 2 else 0
        second = 0.2 * speed if case == 2 else speed
        rows[(case, step)] = dict(zip(FIELDS, (0, 0, angle, speed, first, second, 0.1 if case == 0 else 0, 0, 0, 0)))
    output = '\n'.join('motor ' + ' '.join(map(str, (case, step, *(row[name] for name in FIELDS))))
                       for (case, step), row in sorted(rows.items()))
    qualify(parse_rows(output)); compare(rows, rows)
    corrupt = (output + '\n' + output.splitlines()[0], '\n'.join(output.splitlines()[1:]),
               output.replace('motor 0 15 0', 'motor 0 15 nan', 1), output.replace('motor 0 15', 'motor 7 15', 1))
    for evidence in corrupt:
        try:
            qualify(parse_rows(evidence))
        except ValueError:
            continue
        fail('motor guard accepted corrupt evidence')
    for key, field, value in (((0, 15), 'motor_torque', 0.2), ((2, 15), 'first_speed', 1),
                              ((3, 60), 'angle', 0.5), ((1, 120), 'motor_torque', 0.1)):
        altered = {key: row.copy() for key, row in rows.items()}
        altered[key][field] = value
        try:
            qualify(altered)
        except ValueError:
            continue
        fail('motor guard accepted physically invalid evidence')
    altered = {key: row.copy() for key, row in rows.items()}
    altered[(4, 120)]['x'] = 0.1
    try:
        compare(altered, rows)
    except ValueError:
        pass
    else:
        fail('motor comparator accepted perturbed trajectory')
    print('physics3d motor guard self-test: ok')


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
    record = {'schema': 1, 'fixture': 'hinge-velocity-motor-five-cases-120-steps-v1',
              'oracle_revision': REFERENCE, 'archive_sha256': digest,
              'host': platform.platform(), 'architecture': platform.machine(),
              'sources_sha256': {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                 for name in ('HingeMotorOracle.cpp', 'HingeMotor.sx', 'HingeMotorRun.py', 'Run.py')},
              'scope': 'one worker, 60 Hz, two seconds; velocity target, symmetric torque bound; no position servo, friction or soft stops',
              'iterations': {'jolt_velocity': 12, 'jolt_position': 8, 'silex_motor_preparation': 12, 'silex_contact_velocity': 12, 'silex_position': 4},
              'integration_convention': 'Silex applies external velocity, prepares joints when a powered motor is active, advances poses, then resolves contacts and joints with shared accumulated impulses. Stop-impact speed phase exception requires both angles near the same stop; both arrested at steps 60 and 120.',
              'modes': {}}
    for mode in (('Debug', 'Release') if options.mode == 'both' else (options.mode,)):
        oracle = build_oracle(source, mode, HERE / 'HingeMotorOracle.cpp', 'hinge-motor-oracle')
        silex = build_silex(mode, 'HingeMotor.sx', 'hinge-motor-silex', physics=True)
        outputs = {'jolt': checked([str(oracle)]), 'silex': checked([str(silex)])}
        for name, output in outputs.items():
            (BUILD / f'hinge-motor-{name}-{mode.lower()}.txt').write_text(output)
        reference = parse_rows(outputs['jolt']); actual = parse_rows(outputs['silex'])
        qualify(reference); qualify(actual)
        record['modes'][mode] = {'samples': 40, 'maximum_absolute_errors': compare(actual, reference)}
        print(f'physics3d motor {mode}: 40 samples qualified against Jolt and analytical cases')
    (BUILD / 'hinge-motor-qualification.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        print(f'physics3d motor: {error}', file=sys.stderr)
        sys.exit(1)
