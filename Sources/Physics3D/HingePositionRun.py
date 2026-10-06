#!/usr/bin/env python3
"""Qualify torque-limited position hinges against pinned Jolt and analytical trajectories."""
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
CASES = {(case, step) for case in range(8) for step in range(15, 361, 15)}
TORQUES = (10.0, 10.0, 0.01, 1.0, 1.0, 20.0, 10.0, 10.0)
BOUNDS = {'x': 0.003, 'y': 0.003, 'angle': 0.003, 'speed': 0.003,
          'first_speed': 0.003, 'second_speed': 0.003, 'motor_torque': 0.03,
          'anchor_error': 0.005, 'axis_error': 0.002, 'force_y': 0.05}
LOAD_BOUNDS = dict(BOUNDS, x=0.03, y=0.03, angle=0.03, speed=0.08,
                   second_speed=0.08, motor_torque=0.3, force_y=0.8)


def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        tokens = line.split()
        if len(tokens) != 13 or tokens[0] != 'position':
            fail(f'invalid position row: {line}')
        values = list(map(float, tokens[1:]))
        if not all(map(math.isfinite, values)):
            fail('non-finite position evidence')
        identity = tuple(values[:2])
        if identity not in CASES or identity in rows:
            fail(f'unknown or duplicate position row: {identity}')
        rows[tuple(map(int, identity))] = dict(zip(FIELDS, values[2:]))
    if set(rows) != CASES:
        fail('missing position samples')
    return rows


def validate_bounds(rows):
    for (case, step), row in rows.items():
        if not 0 <= row['anchor_error'] < 0.005 or not 0 <= row['axis_error'] < 0.002:
            fail(f'position motor lost its anchor or axis: {case}, {step}')
        if abs(row['motor_torque']) > TORQUES[case] + 0.00001:
            fail(f'position motor exceeded torque bound: {case}, {step}')


def qualify(rows):
    validate_bounds(rows)
    for case in (0, 1):
        angle = speed = 0.0
        delta = 1/60
        damping = 0.8 if case == 0 else 0.08
        for step in range(1, 361):
            speed = (0.1*speed + delta*1.6*(0.75-angle))/(0.1+delta*damping+delta*delta*1.6)
            angle += delta*speed
            if (case, step) in rows:
                row = rows[(case, step)]
                if abs(row['angle']-angle) > 0.0002 or abs(row['speed']-speed) > 0.0002:
                    fail(f'implicit spring trajectory differs: {case}, {step}')
    if max(rows[(1, step)]['angle'] for step in range(15, 121, 15)) < 1.0:
        fail('underdamped fixture did not overshoot')
    for (case, step), row in rows.items():
        if case != 5 and (abs(row['x']) > 0.001 or abs(row['y']) > 0.001):
            fail('central position motor translated its center')
        if case == 2 and step <= 60:
            if abs(row['speed']-step/600) > 0.0001 or abs(row['motor_torque']-0.01) > 0.00001:
                fail('saturated servo acceleration differs')
        if case == 3 and step >= 255:
            if abs(row['speed']-0.5) > 0.0001 or (step >= 315 and abs(row['motor_torque']) > 0.00001):
                fail('servo mode switch or coasting differs')
        if case == 4:
            limit = 0.3 if step <= 180 else 0.1
            if not -0.203 <= row['angle'] <= limit+0.003:
                fail('servo escaped current hard limits')
            if step in (180, 360) and abs(row['angle']-limit) > 0.001:
                fail('servo did not follow limited target')
        if case == 5 and step >= 300:
            gravity_torque = 9.81*math.sin(row['angle'])
            if abs(40*(0.7-row['angle'])-gravity_torque) > 0.02 or abs(row['motor_torque']-gravity_torque) > 0.02:
                fail('loaded servo equilibrium differs')
        if case == 6 and step == 360 and abs(row['angle']-3.0) > 0.001:
            fail('servo failed shortest angular path')
        if case == 7 and abs(0.1*row['first_speed']+0.4*row['second_speed']) > 0.00001:
            fail('position motor violated angular momentum')


def compare(actual, reference):
    errors = {name: 0.0 for name in FIELDS}
    for identity in sorted(CASES):
        bounds = LOAD_BOUNDS if identity[0] == 5 else BOUNDS
        for name in FIELDS:
            difference = actual[identity][name]-reference[identity][name]
            error = abs(math.atan2(math.sin(difference),math.cos(difference))) if name == 'angle' else abs(difference)
            errors[name] = max(errors[name], error)
            if identity == (4, 195) and name in ('speed', 'second_speed'):
                # Deep limit narrowing includes different position-recovery phases.
                near = all(abs(rows[identity]['angle']-0.1) < 0.005 and
                           abs(rows[identity]['speed']) < 0.02 for rows in (actual,reference))
                if near and error <= 0.01: continue
            if error > bounds[name]:
                fail(f'position {identity} {name}: error {error}, bound {bounds[name]}')
    return errors


def self_test():
    rows = {key: dict.fromkeys(FIELDS, 0.0) for key in CASES}
    output = '\n'.join('position ' + ' '.join(map(str, (case, step, *(row[name] for name in FIELDS))))
                       for (case, step), row in sorted(rows.items()))
    validate_bounds(parse_rows(output)); compare(rows, rows)
    corrupt = (output+'\n'+output.splitlines()[0], '\n'.join(output.splitlines()[1:]),
               output.replace('position 0 15 0.0','position 0 15 nan',1),
               output.replace('position 0 15','position 8 15',1))
    for evidence in corrupt:
        try: parse_rows(evidence)
        except ValueError: continue
        fail('position guard accepted corrupt evidence')
    for field, value in [('anchor_error',0.1),('motor_torque',1.0)]:
        altered = {key:row.copy() for key,row in rows.items()}; altered[(2,15)][field]=value
        try: validate_bounds(altered)
        except ValueError: continue
        fail('position guard accepted invalid physical bound')
    altered = {key:row.copy() for key,row in rows.items()}; altered[(0,15)]['angle']=0.1
    try: compare(altered,rows)
    except ValueError: pass
    else: fail('position comparator accepted perturbed trajectory')
    reference = {key:row.copy() for key,row in rows.items()}
    reference[(4,195)]['angle'] = 0.1
    actual = {key:row.copy() for key,row in reference.items()}
    actual[(4,195)]['speed'] = 0.005
    compare(actual,reference)
    for key,field,value in [((4,195),'speed',0.03),((4,195),'angle',0.2),((4,210),'speed',0.005)]:
        altered = {key:row.copy() for key,row in actual.items()};altered[key][field]=value
        try: compare(altered,reference)
        except ValueError: continue
        fail('position phase guard accepted an unbounded recovery')
    print('physics3d position guard self-test: ok')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--mode',choices=('Debug','Release','both'),default='both')
    parser.add_argument('--self-test',action='store_true')
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    self_test()
    if options.self_test: return
    source,digest = verified_source(options.archive)
    record = {'schema':1,'fixture':'hinge-position-eight-cases-360-steps-v3',
              'oracle_revision':REFERENCE,'archive_sha256':digest,'host':platform.platform(),
              'architecture':platform.machine(),'bounds':BOUNDS,'loaded_bounds':LOAD_BOUNDS,
              'sources_sha256':{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                               for name in ('HingePositionOracle.cpp','HingePosition.sx','HingePositionRun.py','Run.py')},
              'scope':'60 Hz, six seconds, 8 cases, transients included; direct stiffness/damping, symmetric torque; no asymmetric bounds, friction or soft stops',
              'phase_bound':{'identity':[4,195],'fields':['speed','second_speed'],'difference':0.01,'each_speed':0.02,'each_angle_error':0.005},
              'iterations':{'jolt_velocity':12,'jolt_position':8,'silex_preparation':12,'silex_velocity':12,'silex_position':4},'modes':{}}
    for mode in (('Debug','Release') if options.mode == 'both' else (options.mode,)):
        oracle = build_oracle(source,mode,HERE/'HingePositionOracle.cpp','hinge-position-oracle')
        silex = build_silex(mode,'HingePosition.sx','hinge-position-silex',physics=True)
        outputs = {'jolt':checked([str(oracle)]),'silex':checked([str(silex)])}
        for name,output in outputs.items(): (BUILD/f'hinge-position-{name}-{mode.lower()}.txt').write_text(output)
        reference=parse_rows(outputs['jolt']);actual=parse_rows(outputs['silex']);qualify(reference);qualify(actual)
        record['modes'][mode]={'samples':192,'maximum_absolute_errors':compare(actual,reference)}
        print(f'physics3d position {mode}: 192 samples qualified against Jolt and analytical trajectories')
    (BUILD/'hinge-position-qualification.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')


if __name__ == '__main__':
    try: main()
    except (OSError,ValueError) as error:
        print(f'physics3d position: {error}',file=sys.stderr);sys.exit(1)
