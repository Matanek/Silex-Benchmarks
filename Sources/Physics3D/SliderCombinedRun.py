#!/usr/bin/env python3
"""Qualify a combined position and velocity slider drive against pinned Jolt and mechanics."""
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
        if len(tokens) != 18 or tokens[0] != 'slider-combined':
            fail(f'invalid slider-combined row: {line}')
        values = list(map(float, tokens[1:]))
        key = tuple(values[:2])
        if not all(map(math.isfinite, values)) or key not in CASES or key in rows:
            fail('non-finite, duplicate or unknown slider-combined sample')
        rows[tuple(map(int, key))] = dict(zip(FIELDS, values[2:]))
    if set(rows) != CASES:
        fail('missing slider-combined samples')
    return rows

def recurrence(case, sample):
    velocity = 0.0
    position = 0.4 if case == 4 else 0.0
    mass = 1.6 if case == 6 else 2.0
    k = c = 6.4 if case == 6 else 8.0
    if case == 1: c = 4.0
    capacity = 0.4 if case == 2 else (10.0 if case in (5,6) else 100.0)
    minimum = -0.2 if case == 2 else -capacity
    gravity = -2.0 if case == 5 else 0.0
    dt = 1/60
    for step in range(1,sample+1):
        target = 5.0 if case == 2 else (0.0 if case == 4 else 0.75)
        speed = -0.2 if case == 7 else 0.3
        if case == 1:
            time = (step-1)*dt
            target = 0.75*math.sin(0.8*time)
            speed = 0.6*math.cos(0.8*time)
        if case == 3 and step>120: target,speed = -0.4,-0.2
        free = velocity + dt*gravity
        if case == 3 and step>300: force = 0.0
        elif case == 3 and step>240: force = max(minimum,min(capacity,mass*(0.4-free)/dt))
        else:
            kl,cl = (16.0,4.0) if case == 4 else (0.0,0.0)
            next_speed = (mass*free+dt*k*(target-position)+dt*(c+dt*k)*speed-dt*kl*position)/(mass+dt*(c+cl)+dt*dt*(k+kl))
            spring = -kl*(position+dt*next_speed)-cl*next_speed
            force = max(minimum,min(capacity,mass*(next_speed-free)/dt-spring))
        if case == 4:
            velocity = (mass*free+dt*force-dt*16.0*position)/(mass+dt*4.0+dt*dt*16.0)
            spring = -16.0*(position+dt*velocity)-4.0*velocity
        else: velocity,spring = free+dt*force/mass,0.0
        position += dt*velocity
    return position,velocity,force,spring

def qualify(rows):
    for (case,step),r in rows.items():
        capacity = 0.4 if case == 2 else (10.0 if case in (5,6) else 100.0)
        minimum = -0.2 if case == 2 else -capacity
        if not 0<=r['anchor_error']<0.001 or not 0<=r['angular_error']<0.001:
            fail('combined slider lost transverse or angular alignment')
        if not minimum-0.0001<=r['motor_force']<=capacity+0.0001: fail('combined drive exceeded signed budget')
        position,velocity,force,spring = recurrence(case,step)
        if abs(r['position']-position)>0.0003 or abs(r['speed']-velocity)>0.0003:
            fail(f'independent combined trajectory differs at {(case,step)}: {r["position"]}, {position}; {r["speed"]}, {velocity}')
        if abs(r['motor_force']-force)>0.02 or abs(r['force_x']-force-spring)>0.02 or abs(r['limit_force']-spring)>0.02:
            fail(f'independent combined reaction differs at {(case,step)}')
        if case==6:
            if abs(2*r['first_velocity_x']+8*r['second_velocity_x'])>0.0001 or abs(r['x']-0.2*position)>0.0003:
                fail('combined drive failed momentum or center of mass')
        elif abs(r['force_y']-19.62)>0.05: fail('combined drive lost transverse support')
        if case==7 and abs(r['torque_z']-0.5*force)>0.02: fail('combined offset lost free couple')
    if abs(rows[0,360]['position']-1.055)>0.0002: fail('fixed combined target lost velocity bias')
    if abs(rows[5,360]['position']-0.555)>0.0002: fail('combined drive lost load offset')
    if rows[4,360]['position']<=0.09 or rows[4,360]['limit_force']>=-1.5: fail('combined drive failed to compress soft stop')

def compare(actual, reference):
    errors = dict.fromkeys(FIELDS, 0.0)
    for key in sorted(CASES):
        for name in FIELDS:
            error = abs(actual[key][name] - reference[key][name])
            errors[name] = max(errors[name], error)
            if error > BOUNDS[name]:
                fail(f'slider-combined {key} {name}: error {error}, bound {BOUNDS[name]}')
    return errors

def self_test():
    rows = {key: dict.fromkeys(FIELDS, 0.0) for key in CASES}
    output = '\n'.join(('slider-combined ' + ' '.join(map(str, (case, step, *(r[n] for n in FIELDS)))) for (case, step), r in sorted(rows.items())))
    compare(parse_rows(output), rows)
    for corrupt in (output + '\n' + output.splitlines()[0], '\n'.join(output.splitlines()[1:]), output.replace('slider-combined 0 15 0.0', 'slider-combined 0 15 nan', 1), output.replace('slider-combined 0 15', 'slider-combined 8 15', 1)):
        try:
            parse_rows(corrupt)
        except ValueError:
            continue
        fail('slider-combined guard accepted corrupt evidence')
    altered = {key: r.copy() for key, r in rows.items()}
    altered[0, 15]['position'] = 0.1
    try:
        compare(altered, rows)
    except ValueError:
        pass
    else:
        fail('slider-combined comparator accepted a perturbed position')
    try:
        qualify(rows)
    except ValueError:
        pass
    else:
        fail('slider-combined independent guard accepted motionless or unloaded fixtures')
    print('physics3d slider-combined guard self-test: ok')

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
        fixture='slider-combined-eight-cases-360-steps',
        oracle_revision=REFERENCE,
        archive_sha256=digest,
        host=platform.platform(),
        architecture=platform.machine(),
        bounds=BOUNDS,
        sources_sha256={n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in ('SliderCombined.sx', 'SliderCombinedOracle.cpp', 'SliderCombinedRun.py', 'Run.py')},
        scope='60 Hz, six seconds; fixed and moving combined targets, signed saturation, velocity/off mutations, equal soft stop, axial and transverse load, unequal free masses and offset anchor; no hard-impact, rotating-phase or general-chain parity claim',
        iterations=dict(jolt_velocity=24, jolt_position=8, silex_preparation=12, silex_velocity=12, silex_position=4),
        modes={},
    )
    for mode in ('Debug', 'Release') if o.mode == 'both' else (o.mode,):
        oracle = build_oracle(source, mode, HERE / 'SliderCombinedOracle.cpp', 'slider-combined-oracle')
        silex = build_silex(mode, 'SliderCombined.sx', 'slider-combined-silex', physics=True)
        outputs = dict(jolt=checked([str(oracle)]), silex=checked([str(silex)]))
        for name, out in outputs.items():
            (BUILD / f'slider-combined-{name}-{mode.lower()}.txt').write_text(out)
        reference, actual = (parse_rows(outputs['jolt']), parse_rows(outputs['silex']))
        qualify(reference)
        qualify(actual)
        record['modes'][mode] = dict(samples=192, maximum_absolute_errors=compare(actual, reference))
        print(f'physics3d slider-combined {mode}: 192 samples qualified against Jolt and independent mechanics')
    (BUILD / 'slider-combined-qualification.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as e:
        print(f'physics3d slider-combined: {e}', file=sys.stderr)
        sys.exit(1)
