#!/usr/bin/env python3
"""Qualify passive hinge friction against pinned Jolt and analytical braking."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS = ('x','y','angle','speed','first_speed','second_speed','friction_torque',
          'motor_torque','anchor_error','axis_error','force_y')
CASES = {(case,step) for case in range(8) for step in range(15,361,15)}
BOUNDS = dict.fromkeys(FIELDS,0.003)
BOUNDS.update(friction_torque=0.03,motor_torque=0.03,force_y=0.05)
LOAD_BOUNDS = dict(BOUNDS,x=0.01,y=0.01,angle=0.01,speed=0.03,second_speed=0.03,
                   friction_torque=0.1,force_y=0.2)


def capacity(case,step):
    if case == 4: return 0.05 if step <= 60 else (0.2 if step <= 180 else (0.0 if step <= 240 else 0.1))
    if case == 5: return 0.0 if step <= 300 else 0.4
    if case == 6: return 1.0 if 120 < step <= 180 else 0.0
    if case == 7: return 4.0 if step <= 180 else 1.0
    return (0.1,0.1,0.3,0.02)[case]


def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        tokens = line.split()
        if len(tokens) != 14 or tokens[0] != 'friction': fail(f'invalid friction row: {line}')
        values = list(map(float,tokens[1:]))
        if not all(map(math.isfinite,values)): fail('non-finite friction evidence')
        identity = tuple(values[:2])
        if identity not in CASES or identity in rows: fail(f'unknown or duplicate friction row: {identity}')
        rows[tuple(map(int,identity))] = dict(zip(FIELDS,values[2:]))
    if set(rows) != CASES: fail('missing friction samples')
    return rows


def validate_bounds(rows):
    for (case,step),row in rows.items():
        if not 0 <= row['anchor_error'] < 0.003 or not 0 <= row['axis_error'] < 0.002:
            fail(f'friction lost its anchor or axis: {case}, {step}')
        if abs(row['friction_torque']) > capacity(case,step)+0.00001:
            fail(f'friction exceeded capacity or acted with a motor: {case}, {step}')
        motor = (0.2 if step <= 120 else 1.0) if case == 5 and step <= 300 else 0.0
        if abs(row['motor_torque']) > motor+0.00001: fail('friction fixture exceeded motor bound')


def qualify(rows):
    validate_bounds(rows)
    for case in (0,1,3,4,6):
        sign = -1.0 if case == 1 else 1.0
        speed = sign; angle = 0.0
        inertia = 0.08 if case == 3 else 0.1
        for step in range(1,361):
            if (case == 4 and step == 181) or (case == 6 and step == 181): speed = -1.0
            speed = math.copysign(max(0.0,abs(speed)-capacity(case,step)/60/inertia),speed)
            angle += speed/60
            if (case,step) in rows:
                row = rows[(case,step)]
                angle_error = abs(math.atan2(math.sin(row['angle']-angle),math.cos(row['angle']-angle)))
                if abs(row['speed']-speed)>0.0001 or angle_error>0.0002:
                    fail(f'analytical friction trajectory differs: {case}, {step}')
                if case == 3 and abs(row['first_speed']*0.1+row['second_speed']*0.4-0.4)>0.00002:
                    fail('friction violated angular momentum')
    for (case,step),row in rows.items():
        if case not in (2,7) and (abs(row['x'])>0.001 or abs(row['y'])>0.001): fail('central hinge translated')
        if case == 2 and step >= 240 and abs(row['speed'])>0.001: fail('offset friction failed to stop')
        if case == 5 and step == 120 and abs(row['speed']-0.5)>0.0001: fail('motor did not take precedence')
        if case == 7 and step <= 180:
            if abs(row['angle']-0.3)>0.003 or abs(row['speed'])>0.003: fail('static friction failed to hold gravity load')
            if abs(row['friction_torque']-9.81*math.sin(row['angle']))>0.03: fail('static friction reaction differs')
        if case == 7 and step == 360 and abs(row['angle']-0.3)<0.02: fail('reduced friction did not release the load')


def compare(actual,reference):
    errors = dict.fromkeys(FIELDS,0.0)
    for identity in sorted(CASES):
        bounds = LOAD_BOUNDS if identity[0] in (2,7) else BOUNDS
        for name in FIELDS:
            difference = actual[identity][name]-reference[identity][name]
            error = abs(math.atan2(math.sin(difference),math.cos(difference))) if name=='angle' else abs(difference)
            errors[name] = max(errors[name],error)
            if error>bounds[name]: fail(f'friction {identity} {name}: error {error}, bound {bounds[name]}')
    return errors


def self_test():
    rows = {key:dict.fromkeys(FIELDS,0.0) for key in CASES}
    output = '\n'.join('friction '+' '.join(map(str,(case,step,*(row[name] for name in FIELDS)))) for (case,step),row in sorted(rows.items()))
    validate_bounds(parse_rows(output)); compare(rows,rows)
    for evidence in (output+'\n'+output.splitlines()[0], '\n'.join(output.splitlines()[1:]),
                     output.replace('friction 0 15 0.0','friction 0 15 nan',1),
                     output.replace('friction 0 15','friction 8 15',1)):
        try: parse_rows(evidence)
        except ValueError: continue
        fail('friction guard accepted corrupt evidence')
    for key,field,value in [((0,15),'anchor_error',0.1),((0,15),'friction_torque',0.2),
                           ((5,15),'friction_torque',0.001),((6,15),'motor_torque',0.001)]:
        altered = {key:row.copy() for key,row in rows.items()};altered[key][field]=value
        try: validate_bounds(altered)
        except ValueError: continue
        fail('friction guard accepted invalid effort or geometry')
    altered = {key:row.copy() for key,row in rows.items()};altered[(0,15)]['angle']=0.1
    try: compare(altered,rows)
    except ValueError: pass
    else: fail('friction comparator accepted a perturbed trajectory')
    print('physics3d friction guard self-test: ok')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--mode',choices=('Debug','Release','both'),default='both')
    parser.add_argument('--self-test',action='store_true');options=parser.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    self_test()
    if options.self_test: return
    source,digest=verified_source(options.archive)
    record={'schema':1,'fixture':'hinge-friction-eight-cases-360-steps-v1','oracle_revision':REFERENCE,
            'archive_sha256':digest,'host':platform.platform(),'architecture':platform.machine(),
            'bounds':BOUNDS,'offset_and_loaded_bounds':LOAD_BOUNDS,
            'iterations':{'jolt_velocity':64,'jolt_position':8,'silex_preparation':12,'silex_velocity':12,'silex_position':4},
            'scope':'60 Hz, six seconds, passive friction, motor precedence including zero effort; no cost parity, asymmetric effort or soft stops',
            'sources_sha256':{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ('HingeFrictionOracle.cpp','HingeFriction.sx','HingeFrictionRun.py','Run.py')},'modes':{}}
    for mode in (('Debug','Release') if options.mode=='both' else (options.mode,)):
        oracle=build_oracle(source,mode,HERE/'HingeFrictionOracle.cpp','hinge-friction-oracle')
        silex=build_silex(mode,'HingeFriction.sx','hinge-friction-silex',physics=True)
        outputs={'jolt':checked([str(oracle)]),'silex':checked([str(silex)])}
        for name,output in outputs.items(): (BUILD/f'hinge-friction-{name}-{mode.lower()}.txt').write_text(output)
        reference=parse_rows(outputs['jolt']);actual=parse_rows(outputs['silex']);qualify(reference);qualify(actual)
        record['modes'][mode]={'samples':192,'maximum_absolute_errors':compare(actual,reference)}
        print(f'physics3d friction {mode}: 192 samples qualified against Jolt and analytical trajectories')
    (BUILD/'hinge-friction-qualification.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':
    try:main()
    except (OSError,ValueError) as error:
        print(f'physics3d friction: {error}',file=sys.stderr);sys.exit(1)
