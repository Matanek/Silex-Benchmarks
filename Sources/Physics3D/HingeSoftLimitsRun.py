#!/usr/bin/env python3
"""Qualify soft hinge stops against pinned Jolt and implicit spring trajectories."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS = ('x','y','angle','speed','first_speed','second_speed','limit_torque',
          'motor_torque','anchor_error','axis_error','force_y')
CASES = {(case,step) for case in range(8) for step in range(15,361,15)}
# Frozen before the first oracle run: no phase exclusions.
BOUNDS = dict.fromkeys(FIELDS,0.005)
BOUNDS.update(limit_torque=0.05,motor_torque=0.03,force_y=0.1)
OFFSET_BOUNDS = dict(BOUNDS,x=0.01,y=0.01,angle=0.01,speed=0.03,second_speed=0.03,
                     limit_torque=0.1,force_y=0.2)


def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        tokens = line.split()
        if len(tokens)!=14 or tokens[0]!='soft': fail(f'invalid soft stop row: {line}')
        values = list(map(float,tokens[1:]))
        if not all(map(math.isfinite,values)): fail('non-finite soft stop evidence')
        identity = tuple(values[:2])
        if identity not in CASES or identity in rows: fail(f'unknown or duplicate soft stop row: {identity}')
        rows[tuple(map(int,identity))] = dict(zip(FIELDS,values[2:]))
    if set(rows)!=CASES: fail('missing soft stop samples')
    return rows


def validate_geometry(rows):
    for (case,step),row in rows.items():
        if not 0<=row['anchor_error']<0.003 or not 0<=row['axis_error']<0.002: fail('soft stop lost its frame')
        if abs(row['limit_torque'])>10.0: fail('soft stop effort is unbounded in this fixture')
        if case==6:
            if not -0.10001<=row['motor_torque']<=0.20001: fail('soft stop motor exceeded signed interval')
        elif abs(row['motor_torque'])>0.00001: fail('inactive motor produced effort')
        if case==2 and step==15 and row['limit_torque']>0.00001: fail('upper stop pulled rotor')
        if case==3 and step==15 and row['limit_torque']< -0.00001: fail('lower stop pulled rotor')


def qualify(rows):
    validate_geometry(rows)
    for case in (0,1,2,3,4,7):
        angle=0.4;speed=0.0;inertia=0.08 if case==4 else 0.1
        low=high=0.1 if case==0 else 0.0;k=1.6;c=0.8
        if case==1: c=0.0
        if case==4: c=0.4
        if case in (2,3): angle=0.0;speed=1.0 if case==2 else -1.0;low=-0.205;high=0.205
        for step in range(1,361):
            if case==7 and step==121: angle=-0.3;speed=0.2;low=high=0.0;k=3.2;c=0.4
            if case==7 and step==241: angle=0.2;speed=0.0;k=0.0;low=-0.2;high=0.2
            previous=speed
            if k and (angle<=low or angle>=high):
                target=low if angle<=low else high
                speed=(inertia*speed-k*(angle-target)/60)/(inertia+c/60+k/3600)
                if low!=high:
                    speed=max(previous,speed) if angle<=low else min(previous,speed)
            angle+=speed/60
            if (case,step) in rows:
                row=rows[(case,step)]
                if abs(row['speed']-speed)>0.0002 or abs(row['angle']-angle)>0.0003: fail(f'implicit soft stop trajectory differs: {case}, {step}')
                if abs(row['limit_torque']-inertia*(speed-previous)*60)>0.0002: fail('implicit soft stop effort differs')
                if case==4 and abs(0.1*row['first_speed']+0.4*row['second_speed'])>0.00002: fail('soft stop violated momentum')
    if rows[(2,15)]['angle']<=0.205 or rows[(3,15)]['angle']>=-0.205: fail('soft stop did not allow temporary overshoot')
    if rows[(1,30)]['angle']>=0.0: fail('undamped bilateral stop did not oscillate')
    if abs(rows[(5,360)]['angle']-0.2)>0.001: fail('offset spring failed to settle')
    if abs(rows[(6,180)]['angle']-0.425)>0.003 or abs(rows[(6,360)]['angle']+0.3625)>0.003: fail('soft motor equilibrium differs')


def compare(actual,reference):
    errors = dict.fromkeys(FIELDS,0.0)
    for identity in sorted(CASES):
        bounds=OFFSET_BOUNDS if identity[0]==5 else BOUNDS
        for name in FIELDS:
            error=abs(actual[identity][name]-reference[identity][name]);errors[name]=max(errors[name],error)
            if error>bounds[name]: fail(f'soft {identity} {name}: error {error}, bound {bounds[name]}')
    return errors


def self_test():
    rows={key:dict.fromkeys(FIELDS,0.0) for key in CASES}
    output='\n'.join('soft '+' '.join(map(str,(case,step,*(row[name] for name in FIELDS)))) for (case,step),row in sorted(rows.items()))
    validate_geometry(parse_rows(output));compare(rows,rows)
    for evidence in (output+'\n'+output.splitlines()[0], '\n'.join(output.splitlines()[1:]),
                     output.replace('soft 0 15 0.0','soft 0 15 nan',1),output.replace('soft 0 15','soft 8 15',1)):
        try: parse_rows(evidence)
        except ValueError: continue
        fail('soft stop parser accepted corrupt evidence')
    for key,field,value in [((0,15),'limit_torque',11.0),((2,15),'limit_torque',0.1),
                           ((3,15),'limit_torque',-0.1),((6,15),'motor_torque',0.3),
                           ((0,15),'motor_torque',0.001),((0,15),'anchor_error',0.1),((0,15),'axis_error',0.01)]:
        altered={key:row.copy() for key,row in rows.items()};altered[key][field]=value
        try: validate_geometry(altered)
        except ValueError: continue
        fail('soft stop guard accepted invalid effort or geometry')
    altered={key:row.copy() for key,row in rows.items()};altered[(0,15)]['angle']=0.1
    try: compare(altered,rows)
    except ValueError: pass
    else: fail('soft stop comparator accepted perturbed trajectory')
    print('physics3d soft stop guard self-test: ok')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path)
    parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');parser.add_argument('--self-test',action='store_true')
    options=parser.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    self_test()
    if options.self_test: return
    source,digest=verified_source(options.archive)
    record={'schema':1,'fixture':'hinge-soft-stops-eight-cases-360-steps-v1','oracle_revision':REFERENCE,
            'archive_sha256':digest,'host':platform.platform(),'architecture':platform.machine(),
            'bounds':BOUNDS,'offset_bounds':OFFSET_BOUNDS,
            'iterations':{'jolt_velocity':64,'jolt_position':8,'silex_preparation':12,'silex_velocity':12,'silex_position':4},
            'scope':'60 Hz, six seconds, unilateral/bilateral springs, undamped motion, offset pivot, two inertias, signed motor and mutations; no cost parity',
            'sources_sha256':{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ('HingeSoftLimitsOracle.cpp','HingeSoftLimits.sx','HingeSoftLimitsRun.py','Run.py')},'modes':{}}
    for mode in (('Debug','Release') if options.mode=='both' else (options.mode,)):
        oracle=build_oracle(source,mode,HERE/'HingeSoftLimitsOracle.cpp','hinge-soft-limits-oracle')
        silex=build_silex(mode,'HingeSoftLimits.sx','hinge-soft-limits-silex',physics=True)
        outputs={'jolt':checked([str(oracle)]),'silex':checked([str(silex)])}
        for name,output in outputs.items(): (BUILD/f'hinge-soft-limits-{name}-{mode.lower()}.txt').write_text(output)
        reference=parse_rows(outputs['jolt']);actual=parse_rows(outputs['silex']);qualify(reference);qualify(actual)
        record['modes'][mode]={'samples':192,'maximum_absolute_errors':compare(actual,reference)}
        print(f'physics3d soft stops {mode}: 192 samples qualified against Jolt and implicit trajectories')
    (BUILD/'hinge-soft-limits-qualification.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':
    try: main()
    except (OSError,ValueError) as error:
        print(f'physics3d soft stops: {error}',file=sys.stderr);sys.exit(1)
