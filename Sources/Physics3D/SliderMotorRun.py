#!/usr/bin/env python3
"""Qualify a force-bounded velocity slider motor against pinned Jolt and mechanics."""
import argparse, hashlib, json, math, platform, sys
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
FIELDS = ('position', 'speed', 'first_velocity_x', 'second_velocity_x', 'x', 'y',
          'first_angular_speed', 'second_angular_speed', 'anchor_error', 'angular_error',
          'force_x', 'force_y', 'limit_force', 'motor_force', 'torque_z')
CASES = {(case, step) for case in range(6) for step in range(10, 241, 10)}
# Bounds declared before the first execution; never widened after comparison.
BOUNDS = dict(position=0.003, speed=0.003, first_velocity_x=0.003,
              second_velocity_x=0.003, x=0.003, y=0.003,
              first_angular_speed=0.003, second_angular_speed=0.003,
              anchor_error=0.001, angular_error=0.001, force_x=0.1,
              force_y=0.1, limit_force=0.05, motor_force=0.05, torque_z=0.1)

def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        tokens = line.split()
        if len(tokens) != 18 or tokens[0] != 'slider-motor':
            fail(f'invalid slider-motor row: {line}')
        values = list(map(float, tokens[1:]))
        key = tuple(values[:2])
        if not all(map(math.isfinite, values)) or key not in CASES or key in rows:
            fail('non-finite, duplicate or unknown slider-motor sample')
        rows[tuple(map(int, key))] = dict(zip(FIELDS, values[2:]))
    if set(rows) != CASES:
        fail('missing slider-motor samples')
    return rows

def recurrence(case, step):
    speed = position = force = 0.0
    acceleration = 2.0 if case == 1 else 1.0
    mass = 1.6 if case == 1 else 2.0
    for index in range(1, step + 1):
        target = 0.6 if index <= 80 else (-0.6 if index <= 160 else 0.0)
        previous = speed
        speed += max(-acceleration / 120, min(acceleration / 120, target - speed))
        force = mass * (speed - previous) * 120
        position += speed / 120
    return position, speed, force

def qualify(rows):
    for (case, step), r in rows.items():
        capacity = 3.2 if case == 1 else 2.0
        if not 0 <= r['anchor_error'] < 0.001 or not 0 <= r['angular_error'] < 0.001:
            fail('slider motor lost transverse or angular alignment')
        if abs(r['motor_force']) > capacity + 0.0001:
            fail('slider motor exceeded its force budget')
        if case in (0, 1, 2):
            position, speed, force = recurrence(case, step)
            if abs(r['position'] - position) > 0.0003 or abs(r['speed'] - speed) > 0.0003:
                fail('independent slider motor trajectory differs')
            if abs(r['motor_force'] - force) > 0.02 or abs(r['force_x'] - force) > 0.02 or abs(r['limit_force']) > 0.001:
                fail('slider motor acceleration reaction differs')
            if case == 1:
                if abs(2 * r['first_velocity_x'] + 8 * r['second_velocity_x']) > 0.0001 or abs(r['x'] - 0.2 * position) > 0.0003:
                    fail('slider motor failed to conserve momentum for unequal masses')
            if case in (0, 2) and abs(r['force_y'] - 19.62) > 0.05:
                fail('slider motor lost transverse support')
            if case == 2 and abs(r['torque_z'] - 0.5 * force) > 0.02:
                fail('offset slider motor lost its compensating free couple')
        if case == 3:
            if abs(r['first_angular_speed'] - 0.2) > 0.0001 or abs(r['second_angular_speed'] - 0.2) > 0.0001:
                fail('slider motor does not follow the rotating rail')
            angle = 0.2 * step / 120
            if abs(r['x'] - r['position'] * math.cos(angle)) > 0.0003 or abs(r['y'] - r['position'] * math.sin(angle)) > 0.0003:
                fail('slider motor departed from the rotating rail geometry')
            target = 0.6
            if abs(r['motor_force']) < 1.99 and abs(r['speed'] - target) > 0.002:
                fail('unsaturated rotating slider motor failed to track its relative speed')
            if abs(r['position'] - (1.0 + 0.6 * step / 120)) > 0.003 or abs(r['motor_force'] + 0.08 * r['position']) > 0.005:
                fail('rotating slider motor differs from constant relative speed and centrifugal reaction')
        if case == 4:
            position, force = (0.5, 2.0) if step <= 120 else (-0.5, -2.0)
            if abs(r['position'] - position) > 0.001 or abs(r['speed']) > 0.001:
                fail('slider motor passed a static rigid stop')
            if abs(r['motor_force'] - force) > 0.01 or abs(r['limit_force'] + force) > 0.01 or abs(r['force_x']) > 0.01:
                fail('slider motor and limit reactions do not balance')
        if case == 5:
            if abs(r['speed'] + step / 120) > 0.0003 or abs(r['position'] + step * (step + 1) / (2 * 120 * 120)) > 0.0003 or abs(r['motor_force'] - 2.0) > 0.01:
                fail('underpowered slider motor invented acceleration')

def compare(actual, reference):
    errors = dict.fromkeys(FIELDS, 0.0)
    for key in sorted(CASES):
        for name in FIELDS:
            error = abs(actual[key][name] - reference[key][name])
            errors[name] = max(errors[name], error)
            if error > BOUNDS[name]:
                fail(f'slider-motor {key} {name}: error {error}, bound {BOUNDS[name]}')
    return errors

def self_test():
    rows = {key: dict.fromkeys(FIELDS, 0.0) for key in CASES}
    output = '\n'.join(('slider-motor ' + ' '.join(map(str, (case, step, *(r[n] for n in FIELDS)))) for (case, step), r in sorted(rows.items())))
    compare(parse_rows(output), rows)
    for corrupt in (output + '\n' + output.splitlines()[0], '\n'.join(output.splitlines()[1:]), output.replace('slider-motor 0 10 0.0', 'slider-motor 0 10 nan', 1), output.replace('slider-motor 0 10', 'slider-motor 6 10', 1)):
        try:
            parse_rows(corrupt)
        except ValueError:
            continue
        fail('slider-motor guard accepted corrupt evidence')
    altered = {key: r.copy() for key, r in rows.items()}
    altered[0, 10]['position'] = 0.1
    try:
        compare(altered, rows)
    except ValueError:
        pass
    else:
        fail('slider-motor comparator accepted a perturbed position')
    try:
        qualify(rows)
    except ValueError:
        pass
    else:
        fail('slider-motor independent guard accepted motionless or unloaded fixtures')
    print('physics3d slider-motor guard self-test: ok')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path)
    p.add_argument('--mode', choices=('Debug', 'Release', 'both'), default='both')
    p.add_argument('--self-test', action='store_true')
    o = p.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f'run from workspace or Spec group root: {GROUP}')
    self_test()
    if o.self_test:
        return
    source, digest = verified_source(o.archive)
    record = dict(
        schema=1,
        fixture='slider-motor-six-cases-240-steps',
        oracle_revision=REFERENCE,
        archive_sha256=digest,
        host=platform.platform(),
        architecture=platform.machine(),
        bounds=BOUNDS,
        sources_sha256={n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in ('SliderMotor.sx', 'SliderMotorOracle.cpp', 'SliderMotorRun.py', 'Run.py')},
        scope='120 Hz, two seconds; bounded acceleration, signed speed inversion and zero-speed braking, two free unequal masses, offset anchor and compensating couple, steady constant-speed rotating kinematic rail, opposing rigid stops with explicit pose reset, capacity below axial load; no impact or general-chain parity claim',
        iterations=dict(jolt_velocity=24, jolt_position=8, silex_preparation=12, silex_velocity=12, silex_position=4),
        modes={},
    )
    for mode in ('Debug', 'Release') if o.mode == 'both' else (o.mode,):
        oracle = build_oracle(source, mode, HERE / 'SliderMotorOracle.cpp', 'slider-motor-oracle')
        silex = build_silex(mode, 'SliderMotor.sx', 'slider-motor-silex', physics=True)
        outputs = dict(jolt=checked([str(oracle)]), silex=checked([str(silex)]))
        for name, out in outputs.items():
            (BUILD / f'slider-motor-{name}-{mode.lower()}.txt').write_text(out)
        reference, actual = (parse_rows(outputs['jolt']), parse_rows(outputs['silex']))
        qualify(reference)
        qualify(actual)
        record['modes'][mode] = dict(samples=144, maximum_absolute_errors=compare(actual, reference))
        print(f'physics3d slider-motor {mode}: 144 samples qualified against Jolt and independent mechanics')
    (BUILD / 'slider-motor-qualification.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as e:
        print(f'physics3d slider-motor: {e}', file=sys.stderr)
        sys.exit(1)
