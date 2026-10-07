#!/usr/bin/env python3
"""Qualify a force-bounded position slider servo against pinned Jolt and mechanics."""
import argparse, hashlib, json, math, platform, sys
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
FIELDS = ('position', 'speed', 'first_velocity_x', 'second_velocity_x', 'x', 'y',
          'first_angular_speed', 'second_angular_speed', 'anchor_error', 'angular_error',
          'force_x', 'force_y', 'limit_force', 'motor_force', 'torque_z')
CASES = {(case, step) for case in range(8) for step in range(15, 361, 15)}
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
        if len(tokens) != 18 or tokens[0] != 'slider-position':
            fail(f'invalid slider-position row: {line}')
        values = list(map(float, tokens[1:]))
        key = tuple(values[:2])
        if not all(map(math.isfinite, values)) or key not in CASES or key in rows:
            fail('non-finite, duplicate or unknown slider-position sample')
        rows[tuple(map(int, key))] = dict(zip(FIELDS, values[2:]))
    if set(rows) != CASES:
        fail('missing slider-position samples')
    return rows

def recurrence(case, step):
    speed = position = force = 0.0
    mass = 1.6 if case == 6 else 2.0
    stiffness = damping = 6.4 if case == 6 else 8.0
    if case == 1: damping = 0.8
    capacity = 0.2 if case == 2 else (10.0 if case in (5, 6) else 100.0)
    gravity = -2.0 if case == 5 else 0.0
    dt = 1 / 60
    for index in range(1, step + 1):
        target = 5.0 if case == 2 else 0.75
        if case == 4: target = 0.3 if index <= 180 else -0.2
        if case == 3 and index > 120: target = -0.4
        previous = speed
        if case == 3 and index > 300:
            force = 0.0
        elif case == 3 and index > 240:
            force = max(-capacity, min(capacity, mass * (0.4 - speed) / dt))
        else:
            next_speed = (mass * speed + dt * stiffness * (target - position) + mass * gravity * dt) / (mass + dt * damping + dt * dt * stiffness)
            force = max(-capacity, min(capacity, mass * (next_speed - speed - gravity * dt) / dt))
        speed = previous + gravity * dt + force * dt / mass
        position += speed * dt
    return position, speed, force

def qualify(rows):
    for (case, step), r in rows.items():
        capacity = 0.2 if case == 2 else (10.0 if case in (5, 6) else 100.0)
        if not 0 <= r['anchor_error'] < 0.001 or not 0 <= r['angular_error'] < 0.001:
            fail('slider position lost transverse or angular alignment')
        if abs(r['motor_force']) > capacity + 0.0001:
            fail('slider position exceeded its force budget')
        position, speed, force = recurrence(case, step)
        if abs(r['position'] - position) > 0.0003 or abs(r['speed'] - speed) > 0.0003:
            fail(f'independent slider position trajectory differs at {(case, step)}: {r["position"]}, {position}; {r["speed"]}, {speed}')
        if abs(r['motor_force'] - force) > 0.02 or abs(r['force_x'] - force) > 0.02 or abs(r['limit_force']) > 0.001:
            fail(f'slider position reaction differs at {(case, step)}')
        if case == 6:
            if abs(2 * r['first_velocity_x'] + 8 * r['second_velocity_x']) > 0.0001 or abs(r['x'] - 0.2 * position) > 0.0003:
                fail('slider position failed to conserve momentum for unequal masses')
        elif abs(r['force_y'] - 19.62) > 0.05:
            fail('slider position lost transverse support')
        if case == 7 and abs(r['torque_z'] - 0.5 * force) > 0.02:
            fail('offset slider position lost its compensating free couple')
        if case == 4 and not -0.20001 <= r['position'] <= 0.30001:
            fail('slider position passed a rigid limit')
    if rows[1, 90]['position'] <= 1.0 or rows[0, 90]['position'] >= 0.75:
        fail('slider position failed to distinguish damping and overshoot')
    if abs(rows[5, 360]['position'] - 0.25) > 0.0001:
        fail('slider position lost its physical load offset')

def compare(actual, reference):
    errors = dict.fromkeys(FIELDS, 0.0)
    for key in sorted(CASES):
        for name in FIELDS:
            error = abs(actual[key][name] - reference[key][name])
            errors[name] = max(errors[name], error)
            if error > BOUNDS[name]:
                fail(f'slider-position {key} {name}: error {error}, bound {BOUNDS[name]}')
    return errors

def self_test():
    rows = {key: dict.fromkeys(FIELDS, 0.0) for key in CASES}
    output = '\n'.join(('slider-position ' + ' '.join(map(str, (case, step, *(r[n] for n in FIELDS)))) for (case, step), r in sorted(rows.items())))
    compare(parse_rows(output), rows)
    for corrupt in (output + '\n' + output.splitlines()[0], '\n'.join(output.splitlines()[1:]), output.replace('slider-position 0 15 0.0', 'slider-position 0 15 nan', 1), output.replace('slider-position 0 15', 'slider-position 8 15', 1)):
        try:
            parse_rows(corrupt)
        except ValueError:
            continue
        fail('slider-position guard accepted corrupt evidence')
    altered = {key: r.copy() for key, r in rows.items()}
    altered[0, 15]['position'] = 0.1
    try:
        compare(altered, rows)
    except ValueError:
        pass
    else:
        fail('slider-position comparator accepted a perturbed position')
    try:
        qualify(rows)
    except ValueError:
        pass
    else:
        fail('slider-position independent guard accepted motionless or unloaded fixtures')
    print('physics3d slider-position guard self-test: ok')

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
        fixture='slider-position-eight-cases-360-steps',
        oracle_revision=REFERENCE,
        archive_sha256=digest,
        host=platform.platform(),
        architecture=platform.machine(),
        bounds=BOUNDS,
        sources_sha256={n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in ('SliderPosition.sx', 'SliderPositionOracle.cpp', 'SliderPositionRun.py', 'Run.py')},
        scope='60 Hz, six seconds; critical and underdamped spring recurrence, saturation, target changes and velocity/off modes, targets projected on limits, axial and transverse load, unequal free masses, offset anchor and free couple; no hard-impact, rotating-phase or general-chain parity claim',
        iterations=dict(jolt_velocity=24, jolt_position=8, silex_preparation=12, silex_velocity=12, silex_position=4),
        modes={},
    )
    for mode in ('Debug', 'Release') if o.mode == 'both' else (o.mode,):
        oracle = build_oracle(source, mode, HERE / 'SliderPositionOracle.cpp', 'slider-position-oracle')
        silex = build_silex(mode, 'SliderPosition.sx', 'slider-position-silex', physics=True)
        outputs = dict(jolt=checked([str(oracle)]), silex=checked([str(silex)]))
        for name, out in outputs.items():
            (BUILD / f'slider-position-{name}-{mode.lower()}.txt').write_text(out)
        reference, actual = (parse_rows(outputs['jolt']), parse_rows(outputs['silex']))
        qualify(reference)
        qualify(actual)
        record['modes'][mode] = dict(samples=192, maximum_absolute_errors=compare(actual, reference))
        print(f'physics3d slider-position {mode}: 192 samples qualified against Jolt and independent mechanics')
    (BUILD / 'slider-position-qualification.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as e:
        print(f'physics3d slider-position: {e}', file=sys.stderr)
        sys.exit(1)
