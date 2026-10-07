#!/usr/bin/env python3
"""Qualify a passive slider friction against pinned Jolt and mechanics."""
import argparse, hashlib, json, math, platform, sys
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
FIELDS = ('position', 'speed', 'first_velocity_x', 'second_velocity_x', 'x', 'y',
          'first_angular_speed', 'second_angular_speed', 'anchor_error', 'angular_error',
          'force_x', 'force_y', 'limit_force', 'motor_force', 'friction_force', 'torque_z')
CASES = {(case, step) for case in range(8) for step in range(15, 361, 15)}
# Bounds declared before the first execution; never widened after comparison.
BOUNDS = dict(position=0.003, speed=0.003, first_velocity_x=0.003,
              second_velocity_x=0.003, x=0.003, y=0.003,
              first_angular_speed=0.003, second_angular_speed=0.003,
              anchor_error=0.001, angular_error=0.001, force_x=0.1,
              force_y=0.1, limit_force=0.05, motor_force=0.05, friction_force=0.05, torque_z=0.1)

def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        tokens = line.split()
        if len(tokens) != 19 or tokens[0] != 'slider-friction':
            fail(f'invalid slider-friction row: {line}')
        values = list(map(float, tokens[1:]))
        key = tuple(values[:2])
        if not all(map(math.isfinite, values)) or key not in CASES or key in rows:
            fail('non-finite, duplicate or unknown slider-friction sample')
        rows[tuple(map(int, key))] = dict(zip(FIELDS, values[2:]))
    if set(rows) != CASES:
        fail('missing slider-friction samples')
    return rows

def capacities(case, step):
    friction = (2.0, 2.0, 2.0, 0.8, 0.5, 4.0, 2.0, 1.0)[case]
    motor = None
    if case == 4: friction = 0.5 if step <= 60 else (2.0 if step <= 180 else (0.0 if step <= 240 else 1.0))
    if case == 5: motor = 2.0 if step <= 120 else (10.0 if step <= 300 else None)
    if case == 6: motor = None if 120 < step <= 180 else 0.0
    if case == 7 and step > 180: friction = 0.2
    return (friction if motor is None else 0.0), (0.0 if motor is None else motor)

def recurrence(case, step):
    speed = -1.0 if case == 1 else (0.0 if case == 7 else 1.0)
    position = friction_force = motor_force = 0.0
    mass = 1.6 if case == 3 else 2.0
    gravity = 0.3 if case == 7 else 0.0
    dt = 1 / 60
    for index in range(1, step + 1):
        if case in (4, 6) and index == 181: speed = -1.0
        friction, motor = capacities(case, index)
        free_speed = speed + gravity * dt
        desired = 0.0
        if case == 5 and index <= 120: desired = 0.5
        if case == 5 and 120 < index <= 300:
            desired = (mass * speed + dt * 8 * (-0.4 - position)) / (mass + dt * 8 + dt * dt * 8)
        bound = motor if (case == 5 and index <= 300) or (case == 6 and not 120 < index <= 180) else friction
        force = max(-bound, min(bound, mass * (desired - free_speed) / dt))
        speed = free_speed + force * dt / mass
        position += speed * dt
        friction_force = force if friction > 0 else 0.0
        motor_force = force if motor > 0 else 0.0
    return position, speed, friction_force, motor_force

def qualify(rows):
    for (case, step), r in rows.items():
        friction, motor = capacities(case, step)
        if not 0 <= r['anchor_error'] < 0.001 or not 0 <= r['angular_error'] < 0.001:
            fail('slider friction lost transverse or angular alignment')
        if abs(r['friction_force']) > friction + 0.0001 or abs(r['motor_force']) > motor + 0.0001:
            fail('slider friction exceeded capacity or violated motor precedence')
        position, speed, friction_force, motor_force = recurrence(case, step)
        if abs(r['position'] - position) > 0.0003 or abs(r['speed'] - speed) > 0.0003:
            fail(f'independent slider friction trajectory differs at {(case, step)}: {r["position"]}, {position}; {r["speed"]}, {speed}')
        total = friction_force + motor_force
        if abs(r['friction_force'] - friction_force) > 0.02 or abs(r['motor_force'] - motor_force) > 0.02 or abs(r['force_x'] - total) > 0.02 or abs(r['limit_force']) > 0.001:
            fail(f'slider friction reaction differs at {(case, step)}')
        if case == 3:
            if abs(2 * r['first_velocity_x'] + 8 * r['second_velocity_x'] - 8.0) > 0.0001 or abs(r['x'] - (0.8 * step / 60 + 0.2 * position)) > 0.0003:
                fail('slider friction failed to conserve momentum for unequal masses')
        elif abs(r['force_y'] - 19.62) > 0.05:
            fail('slider friction lost transverse support')
        if case == 2 and abs(r['torque_z'] - 0.5 * total) > 0.02:
            fail('offset slider friction lost its compensating free couple')
    if abs(rows[0, 360]['speed']) > 0.0001 or abs(rows[1, 360]['speed']) > 0.0001 or abs(rows[3, 360]['speed']) > 0.0001:
        fail('slider friction failed to stop without reversal')
    if abs(rows[7, 180]['position']) > 0.0001 or rows[7, 360]['position'] < 0.8:
        fail('slider static friction failed to hold or release the axial load')

def compare(actual, reference):
    errors = dict.fromkeys(FIELDS, 0.0)
    for key in sorted(CASES):
        for name in FIELDS:
            error = abs(actual[key][name] - reference[key][name])
            errors[name] = max(errors[name], error)
            if error > BOUNDS[name]:
                fail(f'slider-friction {key} {name}: error {error}, bound {BOUNDS[name]}')
    return errors

def self_test():
    rows = {key: dict.fromkeys(FIELDS, 0.0) for key in CASES}
    output = '\n'.join(('slider-friction ' + ' '.join(map(str, (case, step, *(r[n] for n in FIELDS)))) for (case, step), r in sorted(rows.items())))
    compare(parse_rows(output), rows)
    for corrupt in (output + '\n' + output.splitlines()[0], '\n'.join(output.splitlines()[1:]), output.replace('slider-friction 0 15 0.0', 'slider-friction 0 15 nan', 1), output.replace('slider-friction 0 15', 'slider-friction 8 15', 1)):
        try:
            parse_rows(corrupt)
        except ValueError:
            continue
        fail('slider-friction guard accepted corrupt evidence')
    altered = {key: r.copy() for key, r in rows.items()}
    altered[0, 15]['position'] = 0.1
    try:
        compare(altered, rows)
    except ValueError:
        pass
    else:
        fail('slider-friction comparator accepted a perturbed position')
    try:
        qualify(rows)
    except ValueError:
        pass
    else:
        fail('slider-friction independent guard accepted motionless or unloaded fixtures')
    print('physics3d slider-friction guard self-test: ok')

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
        fixture='slider-friction-eight-cases-360-steps',
        oracle_revision=REFERENCE,
        archive_sha256=digest,
        host=platform.platform(),
        architecture=platform.machine(),
        bounds=BOUNDS,
        sources_sha256={n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in ('SliderFriction.sx', 'SliderFrictionOracle.cpp', 'SliderFrictionRun.py', 'Run.py')},
        scope='60 Hz, six seconds; signed passive braking and stopping, offset anchor/free couple, unequal free masses, runtime capacity changes and coasting, motor precedence including zero-capacity velocity/position commands, axial holding and insufficient capacity; no hard-impact, rotating-phase, general-chain or cost parity claim',
        iterations=dict(jolt_velocity=24, jolt_position=8, silex_preparation=12, silex_velocity=12, silex_position=4),
        modes={},
    )
    for mode in ('Debug', 'Release') if o.mode == 'both' else (o.mode,):
        oracle = build_oracle(source, mode, HERE / 'SliderFrictionOracle.cpp', 'slider-friction-oracle')
        silex = build_silex(mode, 'SliderFriction.sx', 'slider-friction-silex', physics=True)
        outputs = dict(jolt=checked([str(oracle)]), silex=checked([str(silex)]))
        for name, out in outputs.items():
            (BUILD / f'slider-friction-{name}-{mode.lower()}.txt').write_text(out)
        reference, actual = (parse_rows(outputs['jolt']), parse_rows(outputs['silex']))
        qualify(reference)
        qualify(actual)
        record['modes'][mode] = dict(samples=192, maximum_absolute_errors=compare(actual, reference))
        print(f'physics3d slider-friction {mode}: 192 samples qualified against Jolt and independent mechanics')
    (BUILD / 'slider-friction-qualification.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as e:
        print(f'physics3d slider-friction: {e}', file=sys.stderr)
        sys.exit(1)
