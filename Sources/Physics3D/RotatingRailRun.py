#!/usr/bin/env python3
"""Qualify world impulses on stationary/rotating rails and preserve motor phase gaps."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS=('position','speed','x','y','vx','vy','before_vx','before_vy','force_x','force_y',
        'end_force_x','end_force_y','motor','angular','anchor','angle','axis_x','axis_y')
CASES={(kind,rate,rotation,step) for kind in (0,1) for rate in (60,120)
       for rotation in (0,1,2) for step in range(1,rate*2+1)}
BOUNDS=dict(world_impulse=0.000002,motor=2.0001,geometry=0.001,angular=0.00001,
            free_position=0.002,free_speed=0.002,fixed_position=0.0001,fixed_speed=0.0001)


def parse(output):
    rows={}
    for line in output.splitlines():
        fields=line.split()
        if len(fields)!=23 or fields[0]!='rail':fail('invalid rail row')
        try:
            numbers=list(map(float,fields[1:5]));values=list(map(float,fields[5:]))
            if not all(math.isfinite(n) and n.is_integer() for n in numbers):fail('invalid rail key')
            key=tuple(map(int,numbers))
        except ValueError:fail('invalid rail number')
        if key not in CASES or key in rows or not all(map(math.isfinite,values)):fail('invalid rail observation')
        rows[key]=dict(zip(FIELDS,values))
    if set(rows)!=CASES:fail('missing rail observations')
    return rows


def mechanics(rows):
    worst={name:0.0 for name in ('world_impulse','end_projection_impulse','free_position','free_speed','fixed_position','fixed_speed')}
    for key,row in sorted(rows.items()):
        kind,rate,rotation,step=key;omega=(0,0.2,-0.2)[rotation]
        p,speed,x,y,vx,vy,bx,by,fx,fy,ex,ey,motor,angular,anchor,angle,ax,ay=(row[name] for name in FIELDS)
        previous=rows.get((kind,rate,rotation,step-1))
        expected_before=(previous['vx'],previous['vy']) if previous else (0,omega)
        if math.hypot(bx-expected_before[0],by-expected_before[1])>0.000002:fail('rail state discontinuity')
        error=math.hypot(2*(vx-bx)-fx/rate,2*(vy-by)-fy/rate)
        wrong=math.hypot(2*(vx-bx)-ex/rate,2*(vy-by)-ey/rate)
        worst['world_impulse']=max(worst['world_impulse'],error);worst['end_projection_impulse']=max(worst['end_projection_impulse'],wrong)
        if error>BOUNDS['world_impulse']:fail('rail world impulse balance')
        if abs(motor)>BOUNDS['motor'] or (kind==0 and motor!=0):fail('rail motor budget')
        if not 0<=anchor<=BOUNDS['geometry'] or not 0<=angle<=BOUNDS['geometry'] or abs(angular-omega)>BOUNDS['angular']:fail('rail frame drift')
        if math.hypot(x-p*ax,y-p*ay)>BOUNDS['geometry']:fail('rail position geometry')
        if math.hypot(ax-math.cos(omega*step/rate),ay-math.sin(omega*step/rate))>0.00001:fail('rail rotation differs')
        if abs(speed-(vx*ax+vy*ay))>0.00001:fail('rail relative speed differs')
        if kind==0:
            errors=dict(free_position=abs(p-math.cosh(omega*step/rate)),free_speed=abs(speed-omega*math.sinh(omega*step/rate)))
        elif rotation==0:
            expected_p=1.0;expected_s=0.0
            for index in range(1,step+1):
                target=0.6 if index<=rate*2//3 else -0.6 if index<=rate*4//3 else 0
                expected_s+=max(-1/rate,min(1/rate,target-expected_s));expected_p+=expected_s/rate
            errors=dict(fixed_position=abs(p-expected_p),fixed_speed=abs(speed-expected_s))
        else:errors={}
        for name,error in errors.items():
            worst[name]=max(worst[name],error)
            if error>BOUNDS[name]:fail('rail analytical '+name)
    return worst


def phase_gaps(actual,reference):
    gaps=[]
    for key in sorted(CASES):
        error=abs(actual[key]['motor']-reference[key]['motor'])
        if error>0.05:gaps.append(dict(key=key,error=error))
    if not any(gap['key']==(1,120,1,70) for gap in gaps):fail('historical rotating effort gap lost')
    return gaps


def rejected(action):
    try:action()
    except ValueError:return
    fail('rail guard accepted corrupt witness')


def self_test(raw,rows):
    rejected(lambda:parse(raw+'\n'+raw.splitlines()[0]))
    rejected(lambda:parse('\n'.join(raw.splitlines()[1:])))
    def altered_raw(index,value):
        lines=raw.splitlines();parts=lines[0].split();parts[index]=value;lines[0]=' '.join(parts);return '\n'.join(lines)
    rejected(lambda:parse(altered_raw(1,'9')));rejected(lambda:parse(altered_raw(5,'nan')))
    for field,value in [('force_x',5),('motor',3),('position',4),('angular',1),('anchor',1),('angle',1),('axis_x',0),('before_vx',1)]:
        altered={key:row.copy() for key,row in rows.items()};altered[0,60,0,1][field]=value
        rejected(lambda:mechanics(altered))
    rejected(lambda:phase_gaps(rows,rows))
    return 13


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);options=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(options.archive)
    record=dict(schema=1,fixture='rotating-rail-impulses-v1',oracle_revision=REFERENCE,archive_sha256=digest,
                host=platform.platform(),bounds=BOUNDS,phase_parity=False,observations_per_engine=len(CASES),modes={})
    for mode in ('Debug','Release'):
        oracle=build_oracle(source,mode,HERE/'RotatingRailOracle.cpp','rotating-rail-oracle')
        binary=build_silex(mode,'RotatingRail.sx','rotating-rail',True)
        outputs={engine:checked([str(exe)]) for engine,exe in [('silex',binary),('jolt',oracle)]}
        rows={engine:parse(output) for engine,output in outputs.items()}
        evidence=dict(mechanics={engine:mechanics(data) for engine,data in rows.items()},
                      legacy_motor_parity_rejected=phase_gaps(rows['silex'],rows['jolt']),
                      corrupt_witnesses_rejected=self_test(outputs['silex'],rows['silex']))
        if evidence['mechanics']['jolt']['end_projection_impulse']<=BOUNDS['world_impulse']:fail('reference frame counterexample lost')
        for engine,output in outputs.items():
            (BUILD/f'rotating-rail-{engine}-{mode.lower()}.txt').write_text(output)
            evidence[engine+'_output_sha256']=hashlib.sha256(output.encode()).hexdigest()
        record['modes'][mode]=evidence;(BUILD/'rotating-rail-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: {len(CASES)} observations per engine; world impulse, analytical motion and budgets green; phase gaps retained; 13 corrupt witnesses rejected',flush=True)


if __name__=='__main__':main()
