#!/usr/bin/env python3
"""Qualify soft slider stops against pinned Jolt and mechanics."""
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
        if len(tokens) != 19 or tokens[0] != 'slider-soft':
            fail(f'invalid slider-soft-limits row: {line}')
        values = list(map(float, tokens[1:]))
        key = tuple(values[:2])
        if not all(map(math.isfinite, values)) or key not in CASES or key in rows:
            fail('non-finite, duplicate or unknown slider-soft-limits sample')
        rows[tuple(map(int, key))] = dict(zip(FIELDS, values[2:]))
    if set(rows) != CASES:
        fail('missing slider-soft-limits samples')
    return rows

def spring_speed(free_speed, position, dt, mass, k, c, low, high, force):
    if k == 0 or low < position < high:
        return free_speed + dt * force / mass, 0.0
    bound = low if position <= low else high
    speed = (mass * free_speed + dt * force - dt * k * (position - bound)) / (mass + dt * c + dt * dt * k)
    spring = mass * (speed - free_speed) / dt - force
    if low != high:
        spring = max(0.0, spring) if position <= low else min(0.0, spring)
    return free_speed + dt * (force + spring) / mass, spring

def recurrence(case, sample):
    position = 0.0 if case in (2,3,6) else 0.4
    speed = 1.0 if case == 2 else (-1.0 if case == 3 else 0.0)
    mass = 1.6 if case == 4 else 2.0
    k = 8.0 if case == 6 else 32.0
    c = 0.0 if case == 1 else (4.0 if case == 4 else 8.0)
    low = high = 0.0
    if case in (2,3): low, high = -0.205, 0.205
    if case == 6: low, high = -0.3, 0.3
    gravity = -0.3 if case == 7 else 0.0
    dt = 1/60
    for step in range(1, sample+1):
        if case == 7 and step == 121: position,speed,k,c = -0.3,0.2,64.0,4.0
        if case == 7 and step == 241: position,speed,k,c = 0.0,0.4,0.0,0.0
        free = speed + dt*gravity
        motor = 0.0
        if case == 6:
            target = 1.0 if step <= 180 else -1.0
            low_speed,_ = spring_speed(free,position,dt,mass,k,c,low,high,-0.5)
            high_speed,_ = spring_speed(free,position,dt,mass,k,c,low,high,2.0)
            if target < low_speed: motor = -0.5
            elif target > high_speed: motor = 2.0
            else:
                # Within the motor budget the target is met exactly; derive spring effort.
                spring = 0.0
                if position <= low or position >= high:
                    bound = low if position <= low else high
                    spring = -k*(position-bound+dt*target)-c*target
                    spring = max(0.0,spring) if position <= low else min(0.0,spring)
                motor = mass*(target-free)/dt-spring
        speed, spring = spring_speed(free,position,dt,mass,k,c,low,high,motor)
        position += dt*speed
    return position,speed,spring,motor

def qualify(rows):
    for (case,step),r in rows.items():
        if not 0 <= r['anchor_error'] < 0.001 or not 0 <= r['angular_error'] < 0.001:
            fail('soft stop lost transverse or angular alignment')
        position,speed,spring,motor = recurrence(case,step)
        if abs(r['position']-position)>0.0003 or abs(r['speed']-speed)>0.0003:
            fail(f'independent soft trajectory differs at {(case,step)}: {r["position"]}, {position}; {r["speed"]}, {speed}')
        if abs(r['limit_force']-spring)>0.02 or abs(r['motor_force']-motor)>0.02 or abs(r['force_x']-spring-motor)>0.02 or abs(r['friction_force'])>0.0001:
            fail(f'independent soft reaction differs at {(case,step)}')
        if case == 4:
            if abs(2*r['first_velocity_x']+8*r['second_velocity_x'])>0.0001 or abs(r['x']-(0.32+0.2*position))>0.0003:
                fail('soft stop failed to conserve momentum or center of mass')
        elif abs(r['force_y']-19.62)>0.05: fail('soft stop lost transverse support')
        if case == 5 and abs(r['torque_z']-0.5*(spring+motor))>0.02:
            fail('offset soft stop lost its compensating free couple')
        if case == 6 and not -0.5001 <= r['motor_force'] <= 2.0001: fail('soft stop motor exceeded its budget')
    if rows[2,15]['position']<=0.205 or rows[3,15]['position']>=-0.205:
        fail('unilateral spring failed to allow overshoot')
    if rows[1,30]['position']>=0: fail('undamped spring failed to oscillate')
    if rows[6,180]['position']<=0.5: fail('motor failed to compress its soft stop')

def compare(actual, reference):
    errors = dict.fromkeys(FIELDS, 0.0)
    for key in sorted(CASES):
        for name in FIELDS:
            error = abs(actual[key][name] - reference[key][name])
            errors[name] = max(errors[name], error)
            if error > BOUNDS[name]:
                fail(f'slider-soft-limits {key} {name}: error {error}, bound {BOUNDS[name]}')
    return errors

def self_test():
    rows = {key: dict.fromkeys(FIELDS, 0.0) for key in CASES}
    output = '\n'.join(('slider-soft ' + ' '.join(map(str, (case, step, *(r[n] for n in FIELDS)))) for (case, step), r in sorted(rows.items())))
    compare(parse_rows(output), rows)
    for corrupt in (output + '\n' + output.splitlines()[0], '\n'.join(output.splitlines()[1:]), output.replace('slider-soft 0 15 0.0', 'slider-soft 0 15 nan', 1), output.replace('slider-soft 0 15', 'slider-soft 8 15', 1)):
        try:
            parse_rows(corrupt)
        except ValueError:
            continue
        fail('slider-soft-limits guard accepted corrupt evidence')
    altered = {key: r.copy() for key, r in rows.items()}
    altered[0, 15]['position'] = 0.1
    try:
        compare(altered, rows)
    except ValueError:
        pass
    else:
        fail('slider-soft-limits comparator accepted a perturbed position')
    try:
        qualify(rows)
    except ValueError:
        pass
    else:
        fail('slider-soft-limits independent guard accepted motionless or unloaded fixtures')
    print('physics3d slider-soft-limits guard self-test: ok')

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
        fixture='slider-soft-limits-eight-cases-360-steps',
        oracle_revision=REFERENCE,
        archive_sha256=digest,
        host=platform.platform(),
        architecture=platform.machine(),
        bounds=BOUNDS,
        sources_sha256={n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in ('SliderSoftLimits.sx', 'SliderSoftLimitsOracle.cpp', 'SliderSoftLimitsRun.py', 'Run.py')},
        scope='60 Hz, six seconds; damped/undamped bilateral springs, unilateral overshoot both directions, unequal free masses, offset anchor/free couple, signed motor compression, load and spring/limit mutations; no hard-impact, rotating-phase, general-chain or cost parity claim',
        iterations=dict(jolt_velocity=24, jolt_position=8, silex_preparation=12, silex_velocity=12, silex_position=4),
        modes={},
    )
    for mode in ('Debug', 'Release') if o.mode == 'both' else (o.mode,):
        oracle = build_oracle(source, mode, HERE / 'SliderSoftLimitsOracle.cpp', 'slider-soft-limits-oracle')
        silex = build_silex(mode, 'SliderSoftLimits.sx', 'slider-soft-limits-silex', physics=True)
        outputs = dict(jolt=checked([str(oracle)]), silex=checked([str(silex)]))
        for name, out in outputs.items():
            (BUILD / f'slider-soft-limits-{name}-{mode.lower()}.txt').write_text(out)
        reference, actual = (parse_rows(outputs['jolt']), parse_rows(outputs['silex']))
        qualify(reference)
        qualify(actual)
        record['modes'][mode] = dict(samples=192, maximum_absolute_errors=compare(actual, reference))
        print(f'physics3d slider-soft-limits {mode}: 192 samples qualified against Jolt and independent mechanics')
    (BUILD / 'slider-soft-limits-qualification.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as e:
        print(f'physics3d slider-soft-limits: {e}', file=sys.stderr)
        sys.exit(1)
