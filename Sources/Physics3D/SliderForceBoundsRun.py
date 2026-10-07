#!/usr/bin/env python3
"""Qualify signed slider force bounds against pinned Jolt and mechanics."""
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
        if len(tokens) != 19 or tokens[0] != 'slider-force-bounds':
            fail(f'invalid slider-force-bounds row: {line}')
        values = list(map(float, tokens[1:]))
        key = tuple(values[:2])
        if not all(map(math.isfinite, values)) or key not in CASES or key in rows:
            fail('non-finite, duplicate or unknown slider-force-bounds sample')
        rows[tuple(map(int, key))] = dict(zip(FIELDS, values[2:]))
    if set(rows) != CASES:
        fail('missing slider-force-bounds samples')
    return rows

def command(case, step):
    low, high, target, position_mode = -0.5, 2.0, (0.6 if step <= 180 else -0.6), False
    if case == 1: low, high, target = (-2.0, 0.0, -0.6) if step <= 180 else (0.0, 2.0, 0.6)
    if case == 2: low = high = -0.5 if step <= 180 else 0.5; target = 0.0
    if case == 3: low, high = (-0.8, -0.3) if step <= 120 else (0.3, 0.8); target = 0.0
    if case == 5: low, high, target, position_mode = -2.0, 8.0, (0.75 if step <= 180 else -0.4), True
    if case == 6: low, high = -0.2, 0.8
    if case == 7:
        low, high, target, position_mode = -0.2, 1.0, (-0.4 if step <= 120 else 0.3), step > 120
        if step > 300: return -1.0, 1.0, 0.0, False, False
    return low, high, target, position_mode, True

def recurrence(case, step):
    speed = position = force = 0.0
    mass = 1.6 if case == 6 else 2.0
    gravity = -0.3 if case == 7 else 0.0
    dt = 1 / 60
    for index in range(1, step + 1):
        low, high, target, position_mode, powered = command(case, index)
        free_speed = speed + gravity * dt
        desired = (mass * free_speed + dt * 8 * (target - position)) / (mass + dt * 8 + dt * dt * 8) if position_mode else target
        force = max(low, min(high, mass * (desired - free_speed) / dt))
        speed = free_speed + force * dt / mass
        position += speed * dt
    return position, speed, (force if powered else 0.0), (0.0 if powered else force)

def qualify(rows):
    for (case, step), r in rows.items():
        low, high, target, position_mode, powered = command(case, step)
        if not 0 <= r['anchor_error'] < 0.001 or not 0 <= r['angular_error'] < 0.001:
            fail('slider signed force lost transverse or angular alignment')
        if powered and not low - 0.0001 <= r['motor_force'] <= high + 0.0001:
            fail('slider motor exceeded its signed force interval')
        if (powered and abs(r['friction_force']) > 0.0001) or (not powered and abs(r['motor_force']) > 0.0001):
            fail('slider signed force violated motor precedence')
        position, speed, motor_force, friction_force = recurrence(case, step)
        if abs(r['position'] - position) > 0.0003 or abs(r['speed'] - speed) > 0.0003:
            fail(f'independent slider signed trajectory differs at {(case, step)}: {r["position"]}, {position}; {r["speed"]}, {speed}')
        total = motor_force + friction_force
        if abs(r['motor_force'] - motor_force) > 0.02 or abs(r['friction_force'] - friction_force) > 0.02 or abs(r['force_x'] - total) > 0.02 or abs(r['limit_force']) > 0.001:
            fail(f'slider signed reaction differs at {(case, step)}')
        if case == 6:
            if abs(2 * r['first_velocity_x'] + 8 * r['second_velocity_x']) > 0.0001 or abs(r['x'] - 0.2 * position) > 0.0003:
                fail('slider signed force failed to conserve momentum for unequal masses')
        elif abs(r['force_y'] - 19.62) > 0.05:
            fail('slider signed force lost transverse support')
        if case == 4 and abs(r['torque_z'] - 0.5 * total) > 0.02:
            fail('offset signed force lost its compensating free couple')
    if rows[2, 15]['speed'] >= 0 or rows[3, 15]['speed'] >= 0:
        fail('negative upper bound or imposed signed force failed to move a zero-target carriage')
    if rows[1, 360]['speed'] < 0.59 or rows[7, 360]['friction_force'] < 0.59:
        fail('slider failed to switch direction or restore passive load holding')

def compare(actual, reference):
    errors = dict.fromkeys(FIELDS, 0.0)
    for key in sorted(CASES):
        for name in FIELDS:
            error = abs(actual[key][name] - reference[key][name])
            errors[name] = max(errors[name], error)
            if error > BOUNDS[name]:
                fail(f'slider-force-bounds {key} {name}: error {error}, bound {BOUNDS[name]}')
    return errors

def self_test():
    rows = {key: dict.fromkeys(FIELDS, 0.0) for key in CASES}
    output = '\n'.join(('slider-force-bounds ' + ' '.join(map(str, (case, step, *(r[n] for n in FIELDS)))) for (case, step), r in sorted(rows.items())))
    compare(parse_rows(output), rows)
    for corrupt in (output + '\n' + output.splitlines()[0], '\n'.join(output.splitlines()[1:]), output.replace('slider-force-bounds 0 15 0.0', 'slider-force-bounds 0 15 nan', 1), output.replace('slider-force-bounds 0 15', 'slider-force-bounds 8 15', 1)):
        try:
            parse_rows(corrupt)
        except ValueError:
            continue
        fail('slider-force-bounds guard accepted corrupt evidence')
    altered = {key: r.copy() for key, r in rows.items()}
    altered[0, 15]['position'] = 0.1
    try:
        compare(altered, rows)
    except ValueError:
        pass
    else:
        fail('slider-force-bounds comparator accepted a perturbed position')
    try:
        qualify(rows)
    except ValueError:
        pass
    else:
        fail('slider-force-bounds independent guard accepted motionless or unloaded fixtures')
    print('physics3d slider-force-bounds guard self-test: ok')

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
        fixture='slider-force-bounds-eight-cases-360-steps',
        oracle_revision=REFERENCE,
        archive_sha256=digest,
        host=platform.platform(),
        architecture=platform.machine(),
        bounds=BOUNDS,
        sources_sha256={n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in ('SliderForceBounds.sx', 'SliderForceBoundsOracle.cpp', 'SliderForceBoundsRun.py', 'Run.py')},
        scope='60 Hz, six seconds; asymmetric and one-sided velocity reversal, equal/same-sign forced effort, offset anchor/free couple, clamped signed spring, unequal free masses, load and velocity/position/off mutation with friction recovery; no hard-impact, rotating-phase, general-chain or cost parity claim',
        iterations=dict(jolt_velocity=24, jolt_position=8, silex_preparation=12, silex_velocity=12, silex_position=4),
        modes={},
    )
    for mode in ('Debug', 'Release') if o.mode == 'both' else (o.mode,):
        oracle = build_oracle(source, mode, HERE / 'SliderForceBoundsOracle.cpp', 'slider-force-bounds-oracle')
        silex = build_silex(mode, 'SliderForceBounds.sx', 'slider-force-bounds-silex', physics=True)
        outputs = dict(jolt=checked([str(oracle)]), silex=checked([str(silex)]))
        for name, out in outputs.items():
            (BUILD / f'slider-force-bounds-{name}-{mode.lower()}.txt').write_text(out)
        reference, actual = (parse_rows(outputs['jolt']), parse_rows(outputs['silex']))
        qualify(reference)
        qualify(actual)
        record['modes'][mode] = dict(samples=192, maximum_absolute_errors=compare(actual, reference))
        print(f'physics3d slider-force-bounds {mode}: 192 samples qualified against Jolt and independent mechanics')
    (BUILD / 'slider-force-bounds-qualification.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as e:
        print(f'physics3d slider-force-bounds: {e}', file=sys.stderr)
        sys.exit(1)
