#!/usr/bin/env python3
"""Qualify combined hinge targets against pinned Jolt and independent implicit trajectories."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS = ('x', 'y', 'angle', 'speed', 'first_speed', 'second_speed',
          'motor_torque', 'anchor_error', 'axis_error', 'force_y')
CASES = {(case, step) for case in range(8) for step in range(15, 361, 15)}
BOUNDS = dict(x=.003, y=.003, angle=.003, speed=.003, first_speed=.003,
              second_speed=.003, motor_torque=.03, anchor_error=.003,
              axis_error=.002, force_y=.05)
OFFSET_BOUNDS = dict(BOUNDS, x=.01, y=.01, angle=.01, speed=.03,
                     second_speed=.03, motor_torque=.1, force_y=.2)


def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        tokens = line.split()
        if len(tokens) != 13 or tokens[0] != 'combined':
            fail(f'invalid combined row: {line}')
        values = list(map(float, tokens[1:]))
        if not all(map(math.isfinite, values)):
            fail('non-finite combined evidence')
        identity = tuple(values[:2])
        if identity not in CASES or identity in rows:
            fail(f'unknown or duplicate combined row: {identity}')
        rows[tuple(map(int, identity))] = dict(zip(FIELDS, values[2:]))
    if set(rows) != CASES:
        fail('missing combined samples')
    return rows


def validate_bounds(rows):
    for (case, step), row in rows.items():
        minimum, maximum = (-.02, .01) if case == 2 else (-20, 20) if case == 5 else (-10, 10)
        if not minimum-.00001 <= row['motor_torque'] <= maximum+.00001:
            fail(f'combined torque escaped signed bounds: {case}, {step}')
        if not 0 <= row['anchor_error'] < .003 or not 0 <= row['axis_error'] < .002:
            fail(f'combined anchor or axis lost: {case}, {step}')


def qualify(rows):
    validate_bounds(rows)
    dt = 1/60
    for case in (0, 1, 2, 3, 6, 7):
        angle = -3.0 if case == 6 else 0.0
        speed = 0.0
        inertia = .08 if case == 7 else .1
        for step in range(1, 361):
            target = 3.0 if case == 6 else .5
            velocity = -.1 if case == 6 else .4
            k, c, low, high = 1.6, .8, -10.0, 10.0
            if case == 1:
                time = (step-1)*dt
                target, velocity = .75*math.sin(.8*time), .6*math.cos(.8*time)
            if case == 2:
                target, velocity = (1.0, .5) if step <= 180 else (-1.0, -.5)
                k, c, low, high = 100.0, 1.0, -.02, .01
            if case == 3 and step > 120:
                target, velocity = -.5, 0.0
            if case == 3 and step > 240:
                torque = max(low, min(high, inertia*(.5-speed)/dt)) if step <= 300 else 0.0
            else:
                error = math.atan2(math.sin(angle-target), math.cos(angle-target))
                expected = (inertia*speed-dt*k*error+dt*(c+dt*k)*velocity)/(inertia+dt*c+dt*dt*k)
                torque = max(low, min(high, inertia*(expected-speed)/dt))
            speed += dt*torque/inertia
            angle = math.atan2(math.sin(angle+dt*speed), math.cos(angle+dt*speed))
            if (case, step) in rows:
                row = rows[(case, step)]
                error = abs(math.atan2(math.sin(row['angle']-angle), math.cos(row['angle']-angle)))
                if error > .0002 or abs(row['speed']-speed) > .0002 or abs(row['motor_torque']-torque) > .0002:
                    fail(f'independent combined trajectory differs: {case}, {step}')
    for (case, step), row in rows.items():
        if case != 5 and max(abs(row['x']), abs(row['y'])) > .001:
            fail('central combined motor translated its center')
        if case == 4 and not -.203 <= row['angle'] <= .303:
            fail('combined servo escaped hard limits')
        if case == 4:
            target = .3 if step <= 180 else -.2
            if abs(row['angle']-target) > .003:
                fail('combined servo did not reach the rigid stop')
        if case == 5 and step == 360:
            target = .5+(.8+dt*1.6)*.4/1.6
            if abs(row['angle']-target) > .003 or abs(row['speed']) > .002:
                fail('offset combined servo equilibrium differs')
        if case == 7 and abs(.1*row['first_speed']+.4*row['second_speed']) > .00001:
            fail('combined drive violated angular momentum')


def compare(actual, reference):
    errors = dict.fromkeys(FIELDS, 0.0)
    for identity in sorted(CASES):
        bounds = OFFSET_BOUNDS if identity[0] == 5 else BOUNDS
        for name in FIELDS:
            difference = actual[identity][name]-reference[identity][name]
            error = abs(math.atan2(math.sin(difference), math.cos(difference))) if name == 'angle' else abs(difference)
            errors[name] = max(errors[name], error)
            if error > bounds[name]:
                fail(f'combined {identity} {name}: error {error}, bound {bounds[name]}')
    return errors


def self_test():
    rows = {key: dict.fromkeys(FIELDS, 0.0) for key in CASES}
    output = '\n'.join('combined '+' '.join(map(str, (case, step, *(row[name] for name in FIELDS))))
                       for (case, step), row in sorted(rows.items()))
    validate_bounds(parse_rows(output)); compare(rows, rows)
    for corrupt in (output+'\n'+output.splitlines()[0], '\n'.join(output.splitlines()[1:]),
                    output.replace('combined 0 15 0.0', 'combined 0 15 nan', 1),
                    output.replace('combined 0 15', 'combined 8 15', 1)):
        try: parse_rows(corrupt)
        except ValueError: continue
        fail('combined guard accepted corrupt evidence')
    for name, value in [('motor_torque', -.03), ('motor_torque', .02), ('anchor_error', .1), ('axis_error', .1)]:
        altered = {key: row.copy() for key, row in rows.items()}; altered[(2, 15)][name] = value
        try: validate_bounds(altered)
        except ValueError: continue
        fail('combined guard accepted a physical bound violation')
    altered = {key: row.copy() for key, row in rows.items()}; altered[(0, 15)]['angle'] = .1
    try: compare(altered, rows)
    except ValueError: pass
    else: fail('combined comparator accepted a perturbed trajectory')
    try: qualify(rows)
    except ValueError: pass
    else: fail('combined analytical guard accepted motionless trajectories')
    print('physics3d combined guard self-test: ok')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--mode', choices=('Debug', 'Release', 'both'), default='both')
    parser.add_argument('--self-test', action='store_true')
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    self_test()
    if options.self_test: return
    source, digest = verified_source(options.archive)
    record = dict(schema=1, fixture='hinge-combined-eight-cases-360-steps-v2',
                  oracle_revision=REFERENCE, archive_sha256=digest,
                  host=platform.platform(), architecture=platform.machine(),
                  bounds=BOUNDS, offset_bounds=OFFSET_BOUNDS,
                  sources_sha256={name: hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                                  for name in ('HingeCombinedOracle.cpp', 'HingeCombined.sx', 'HingeCombinedRun.py', 'Run.py')},
                  scope='60 Hz, six seconds, eight cases, all transients sampled; fixed/moving targets, signed effort, modes, static hard-stop loads with pose reset, offset pivot, seam, unequal free bodies; soft stops and contacts qualified in package tests',
                  iterations=dict(jolt_velocity=12, jolt_position=8, silex_preparation=12, silex_velocity=12, silex_position=4),
                  modes={})
    for mode in (('Debug', 'Release') if options.mode == 'both' else (options.mode,)):
        oracle = build_oracle(source, mode, HERE/'HingeCombinedOracle.cpp', 'hinge-combined-oracle')
        silex = build_silex(mode, 'HingeCombined.sx', 'hinge-combined-silex', physics=True)
        outputs = dict(jolt=checked([str(oracle)]), silex=checked([str(silex)]))
        for name, output in outputs.items(): (BUILD/f'hinge-combined-{name}-{mode.lower()}.txt').write_text(output)
        reference, actual = parse_rows(outputs['jolt']), parse_rows(outputs['silex'])
        qualify(reference); qualify(actual)
        record['modes'][mode] = dict(samples=192, maximum_absolute_errors=compare(actual, reference))
        print(f'physics3d combined {mode}: 192 samples qualified against Jolt and analytical trajectories')
    (BUILD/'hinge-combined-qualification.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError) as error:
        print(f'physics3d combined: {error}', file=sys.stderr); sys.exit(1)
