#!/usr/bin/env python3
"""Qualify physical path guidance and retain pinned-reference motor/transport gaps without rendering."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
FIELDS='px py pz vx vy vz wx wy wz angle drive normal binormal'.split()
BOUNDS=dict(zip(FIELDS,(.002,.002,.002,.003,.003,.003,.002,.002,.002,.002,.01,.01,.01)))
STEPS=(1,*range(15,121,15))
CASES={(case,step) for case in range(14) for step in STEPS}
PARITY={key for key in CASES if key[0]<12}
def parse(output):
    rows={}
    for line in output.splitlines():
        values=line.split()
        if len(values)!=16 or values[0]!='path': fail('invalid path observation')
        try: key=tuple(map(int,values[1:3]));data=list(map(float,values[3:]))
        except ValueError: fail('invalid numeric path observation')
        if key not in CASES or key in rows or not all(map(math.isfinite,data)): fail('invalid path key or value')
        rows[key]=dict(zip(FIELDS,data))
    if set(rows)!=CASES: fail('missing path observations')
    return rows

def wrapped(value): return value-2*math.pi*math.floor((value+math.pi)/(2*math.pi))
def require(row,name,expected,key):
    error=row[name]-expected
    if name=='angle': error=wrapped(error)
    if abs(error)>BOUNDS[name]: fail(f'path independent mechanics {key} {name}: {row[name]} vs {expected}')
def mechanics(rows,reference=False):
    for case in range(14):
        position=0. if case in (2,3,12) else 2.
        speed=1. if case in (0,4) else 0.
        for step in range(1,121):
            previous=speed;drive=0.
            if case in (1,10): speed=min(1.,speed+.1)
            if case==4: speed=max(0.,speed-.05)
            if case in (2,3,12):
                # Jolt uses segment fraction as C but a metric linear Jacobian. Preserve that measured reference behavior separately.
                error=position-.5
                if case==12 and reference: error*=.5
                target_speed=.1 if case==3 else 0.
                dt=1/60;next_speed=(2*speed-dt*40*error+dt*(12+dt*40)*target_speed)/(2+dt*12+dt*dt*40)
                speed=max(speed-.1,min(speed+.1,next_speed))
            drive=120*(speed-previous);position+=speed/60
            if step not in STEPS: continue
            row=rows[case,step];key=(case,step)
            if case<5 or case in (10,12):
                require(row,'px',position,key);require(row,'vx',speed,key);require(row,'drive',drive,key)
            if 5<=case<=9:
                expected=(1,0,0) if case==5 else (0,2,0) if case==6 else (0,0,3) if case==7 else (0,0,0)
                for name,value in zip(('wx','wy','wz'),expected): require(row,name,value,key)
                require(row,'angle',3*step/60 if case==7 else 0,key)
            if case==0:
                require(row,'normal',-240 if step==1 else 0,key);require(row,'binormal',360 if step==1 else 0,key)
            if case in (11,13):
                if abs(math.hypot(row['px'],row['py'])-1)>.003: fail('path loop lost its independent radial guide')
    # Physical frame transport exchanges linear and angular kinetic energy and must do zero net instantaneous work.
    h=1.6568542495;curvature=(6-2*h)/(h*h);v=2/(2+.2*curvature*curvature)
    first=rows[13,1]
    require(first,'vy',1. if reference else v,(13,1));require(first,'wz',0. if reference else curvature*v,(13,1))
    if not reference and first['vx']**2+first['vy']**2+.1*first['wz']**2>1.00001: fail('curved transport injected energy')

def compare(actual,reference):
    errors=dict.fromkeys(FIELDS,0.)
    for key in PARITY:
        for name in FIELDS:
            value=actual[key][name]-reference[key][name]
            error=abs(wrapped(value) if name=='angle' else value);errors[name]=max(errors[name],error)
            if error>BOUNDS[name]: fail(f'path parity {key} {name}: {error} > {BOUNDS[name]}')
    gaps={case:{name:max(abs(actual[key][name]-reference[key][name]) for key in CASES if key[0]==case) for name in FIELDS} for case in (12,13)}
    if gaps[12]['vx']<.2 or gaps[13]['wz']<.5: fail('pinned path dimensional/transport witness no longer reproduces; review reference scope')
    return errors,gaps

def self_test():
    rows={key:dict.fromkeys(FIELDS,0.) for key in CASES}
    output='\n'.join('path '+' '.join(map(str,(*key,*(row[name] for name in FIELDS)))) for key,row in sorted(rows.items()))
    parse(output)
    for bad in (output+'\n'+output.splitlines()[0],'\n'.join(output.splitlines()[1:]),output.replace('path 0 1 0.0','path 0 1 nan',1)):
        try: parse(bad)
        except ValueError: continue
        fail('path parser accepted corrupted evidence')
    try: mechanics(rows)
    except ValueError: pass
    else: fail('path mechanics accepted inert fixtures')
    changed={key:row.copy() for key,row in rows.items()};changed[1,1]['drive']=1
    try: compare(changed,rows)
    except ValueError: pass
    else: fail('path comparison accepted a changed reaction')
    print('path qualification guards: ok',flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);parser.add_argument('--self-test',action='store_true');options=parser.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from Spec group: {GROUP}')
    self_test()
    if options.self_test: return
    source,digest=verified_source(options.archive)
    record=dict(schema=1,fixture='path-fourteen-cases-120-steps',oracle_revision=REFERENCE,archive_sha256=digest,host=platform.platform(),bounds=BOUNDS,
        sources_sha256={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ('Path.sx','PathOracle.cpp','PathRun.py','Run.py')},
        scope='twelve parity cases: line guidance, metric speed, unit-length position/combined drives, friction, five orientations, rotated frame and free loop; two measured reference gaps: 2m dimensional position servo and curved angular transport, independently qualified in Silex',modes={})
    for mode in ('Debug','Release'):
        oracle=build_oracle(source,mode,HERE/'PathOracle.cpp','path-oracle');silex=build_silex(mode,'Path.sx','path-silex',physics=True)
        outputs=dict(jolt=checked([str(oracle)]),silex=checked([str(silex)]));parsed={}
        for name,output in outputs.items():
            (BUILD/f'path-{name}-{mode.lower()}.txt').write_text(output);parsed[name]=parse(output);mechanics(parsed[name],reference=name=='jolt')
        errors,gaps=compare(parsed['silex'],parsed['jolt']);record['modes'][mode]=dict(parity_observations=len(PARITY),gap_observations=len(CASES)-len(PARITY),maximum_errors=errors,reference_gaps=gaps,independent_mechanics=True)
        print(f'path {mode}: {len(PARITY)} parity observations, {len(CASES)-len(PARITY)} gap witnesses, errors {errors}',flush=True)
    (BUILD/'path-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print('physics3d path qualification: ok')
if __name__=='__main__': main()
