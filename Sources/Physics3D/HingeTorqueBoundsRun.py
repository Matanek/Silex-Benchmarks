#!/usr/bin/env python3
"""Qualify signed hinge motor torque bounds against pinned Jolt and analytical trajectories."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS = ('x','y','angle','speed','first_speed','second_speed','motor_torque',
          'friction_torque','anchor_error','axis_error','force_y')
CASES = {(case,step) for case in range(8) for step in range(15,361,15)}
BOUNDS = dict.fromkeys(FIELDS,0.005)
BOUNDS.update(motor_torque=0.03,friction_torque=0.00001,force_y=0.1)
LOAD_BOUNDS = dict(BOUNDS,x=0.01,y=0.01,angle=0.01,speed=0.03,second_speed=0.03,
                   motor_torque=0.1,force_y=0.2)


def torque_bounds(case,step):
    if case in (0,1): return (-0.025,0.1)
    if case == 2: return (-0.1,0.0) if step<=240 else (0.0,0.1)
    if case == 3: return (0.03,0.03) if step<=180 else (-0.02,-0.02)
    return ((-0.055,0.22),(-0.08,0.32),(-0.02,0.08),(-0.1,0.2))[case-4]


def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        tokens = line.split()
        if len(tokens)!=14 or tokens[0]!='bounds': fail(f'invalid bounds row: {line}')
        values = list(map(float,tokens[1:]))
        if not all(map(math.isfinite,values)): fail('non-finite torque bounds evidence')
        identity = tuple(values[:2])
        if identity not in CASES or identity in rows: fail(f'unknown or duplicate bounds row: {identity}')
        rows[tuple(map(int,identity))] = dict(zip(FIELDS,values[2:]))
    if set(rows)!=CASES: fail('missing torque bounds samples')
    return rows


def validate_bounds(rows):
    for (case,step),row in rows.items():
        if not 0<=row['anchor_error']<0.003 or not 0<=row['axis_error']<0.002: fail('signed motor lost its frame')
        low,high=torque_bounds(case,step)
        if not low-0.00001<=row['motor_torque']<=high+0.00001: fail(f'signed effort exceeded interval: {case}, {step}')
        if abs(row['friction_torque'])>0.00001: fail('friction acted with an installed signed motor')
        if case==7 and not -0.303<=row['angle']<=0.303: fail('signed motor escaped hard stops')


def qualify(rows):
    validate_bounds(rows)
    for case in (0,1,2,3,6):
        speed=0.0;angle=0.0
        inertia=0.08 if case==6 else 0.1
        for step in range(1,361):
            target=10.0 if case==0 else (-10.0 if case==1 else 0.0)
            if case==2: target=-1.0 if step<=120 else 1.0
            if case==6: target=0.8 if step<=180 else -0.8
            low,high=torque_bounds(case,step)
            impulse=max(low/60,min(high/60,(target-speed)*inertia))
            speed+=impulse/inertia;angle+=speed/60
            if (case,step) in rows:
                row=rows[(case,step)]
                error=abs(math.atan2(math.sin(row['angle']-angle),math.cos(row['angle']-angle)))
                if abs(row['speed']-speed)>0.0002 or error>0.0003: fail(f'analytical signed trajectory differs: {case}, {step}')
                if abs(row['motor_torque']-impulse*60)>0.0001: fail('analytical signed effort differs')
                if case==6 and abs(0.1*row['first_speed']+0.4*row['second_speed'])>0.00002: fail('signed effort violated momentum')
    if rows[(5,180)]['angle']<0.3 or rows[(5,360)]['angle']>0.65: fail('asymmetric servo did not follow inversion')
    if abs(rows[(7,180)]['angle']-0.3)>0.003 or abs(rows[(7,360)]['angle']+0.3)>0.003: fail('signed motor did not reach both hard stops')


def compare(actual,reference):
    errors = dict.fromkeys(FIELDS,0.0)
    for identity in sorted(CASES):
        bounds = LOAD_BOUNDS if identity[0] == 4 else BOUNDS
        for name in FIELDS:
            difference = actual[identity][name]-reference[identity][name]
            error = abs(math.atan2(math.sin(difference),math.cos(difference))) if name=='angle' else abs(difference)
            errors[name] = max(errors[name],error)
            if error>bounds[name]: fail(f'bounds {identity} {name}: error {error}, bound {bounds[name]}')
    return errors


def self_test():
    rows={key:dict.fromkeys(FIELDS,0.0) for key in CASES}
    for (case,step),row in rows.items():
        low,high=torque_bounds(case,step);row['motor_torque']=max(low,min(high,0.0))
    output='\n'.join('bounds '+' '.join(map(str,(case,step,*(row[name] for name in FIELDS)))) for (case,step),row in sorted(rows.items()))
    validate_bounds(parse_rows(output));compare(rows,rows)
    for evidence in (output+'\n'+output.splitlines()[0], '\n'.join(output.splitlines()[1:]),
                     output.replace('bounds 0 15 0.0','bounds 0 15 nan',1),output.replace('bounds 0 15','bounds 8 15',1)):
        try: parse_rows(evidence)
        except ValueError: continue
        fail('torque bounds guard accepted corrupt evidence')
    for key,field,value in [((0,15),'motor_torque',-0.05),((0,15),'motor_torque',0.2),
                           ((3,15),'motor_torque',0.0),((3,195),'motor_torque',0.0),
                           ((2,15),'motor_torque',0.01),((5,15),'friction_torque',0.001),
                           ((0,15),'anchor_error',0.1),((7,15),'angle',0.4)]:
        altered={key:row.copy() for key,row in rows.items()};altered[key][field]=value
        try: validate_bounds(altered)
        except ValueError: continue
        fail('torque bounds guard accepted invalid effort or geometry')
    altered={key:row.copy() for key,row in rows.items()};altered[(0,15)]['angle']=0.1
    try: compare(altered,rows)
    except ValueError: pass
    else: fail('torque bounds comparator accepted a perturbed trajectory')
    print('physics3d signed torque guard self-test: ok')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--mode',choices=('Debug','Release','both'),default='both')
    parser.add_argument('--self-test',action='store_true');options=parser.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    self_test()
    if options.self_test: return
    source,digest=verified_source(options.archive)
    record={'schema':1,'fixture':'hinge-torque-bounds-eight-cases-360-steps-v1','oracle_revision':REFERENCE,
            'archive_sha256':digest,'host':platform.platform(),'architecture':platform.machine(),
            'bounds':BOUNDS,'offset_and_loaded_bounds':LOAD_BOUNDS,
            'iterations':{'jolt_velocity':64,'jolt_position':8,'silex_preparation':12,'silex_velocity':12,'silex_position':4},
            'scope':'60 Hz, six seconds, signed motor effort, velocity/position, same-sign intervals, transients and hard stops; no cost parity or soft stops',
            'sources_sha256':{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ('HingeTorqueBoundsOracle.cpp','HingeTorqueBounds.sx','HingeTorqueBoundsRun.py','Run.py')},'modes':{}}
    for mode in (('Debug','Release') if options.mode=='both' else (options.mode,)):
        oracle=build_oracle(source,mode,HERE/'HingeTorqueBoundsOracle.cpp','hinge-torque-bounds-oracle')
        silex=build_silex(mode,'HingeTorqueBounds.sx','hinge-torque-bounds-silex',physics=True)
        outputs={'jolt':checked([str(oracle)]),'silex':checked([str(silex)])}
        for name,output in outputs.items(): (BUILD/f'hinge-torque-bounds-{name}-{mode.lower()}.txt').write_text(output)
        reference=parse_rows(outputs['jolt']);actual=parse_rows(outputs['silex']);qualify(reference);qualify(actual)
        record['modes'][mode]={'samples':192,'maximum_absolute_errors':compare(actual,reference)}
        print(f'physics3d signed torque {mode}: 192 samples qualified against Jolt and analytical trajectories')
    (BUILD/'hinge-torque-bounds-qualification.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':
    try:main()
    except (OSError,ValueError) as error:
        print(f'physics3d signed torque: {error}',file=sys.stderr);sys.exit(1)
