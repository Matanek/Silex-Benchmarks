#!/usr/bin/env python3
"""Compare kinematic ragdoll driving, release and contact with pinned Jolt."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from RagdollHierarchyRun import quaternion, rotation_error
from LoadedSwingTwistRun import product, rotate

TIMES = (0, .25, .5, .75, 1.25)
KEYS = {(kind, rate, stage, part) for kind in range(3) for rate in (60,120)
        for stage in range(5) for part in range(2 if kind == 2 else 3)}
TOLERANCE = .0001
CONTACT_TOLERANCE = .03

def parse(raw):
    rows = {}
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 18 or fields[0] != 'kinematic':
            fail('invalid kinematic row')
        key = tuple(map(int,fields[1:5])); values = tuple(map(float,fields[5:]))
        if key not in KEYS or key in rows or not all(map(math.isfinite,values)):
            fail('invalid kinematic key or value')
        rows[key] = values
    if set(rows) != KEYS:
        fail('incomplete kinematic observations')
    return rows

def offset(part):
    return (((.2,0,0),quaternion((0,1,0),.3)),
            ((0,.2,0),quaternion((1,0,0),.2)),
            ((0,0,.1),(0,0,0,1)))[part]

def expected(kind, stage, part):
    t = TIMES[stage]
    if kind == 2:
        if part == 0:
            return (min(t,1),0,0,0,0,0,1,1 if t < 1 else 0,0,0,0,0,0)
        return (.75+max(0,t-.25),0,0,0,0,0,1,0 if t == 0 else 1,0,0,0,0,0)
    p, q = offset(part)
    mass = rotate(q,(.1,-.2,.3))
    initial = tuple(a+b+c for a,b,c in zip((part,3,0),p,mass))
    if kind == 1:
        return (initial[0]+2*t,*initial[1:],*q,2,0,0,0,0,0)
    end_q = product(quaternion((0,1,0),.6),q)
    endpoint = tuple(a+b+c for a,b,c in zip((part+1,3,.5),rotate(quaternion((0,1,0),.6),p),rotate(end_q,(.1,-.2,.3))))
    velocity = tuple(b-a for a,b in zip(initial,endpoint))
    position = tuple(a+min(t,1)*v for a,v in zip(initial,velocity))
    orientation = product(quaternion((0,1,0),min(t,1)*.6),q)
    return (*position,*orientation,*(velocity if t < 1 else (0,0,0)),0,.6 if t < 1 else 0,0)

def errors(a,b):
    return [max(abs(x-y) for x,y in zip(a[:3],b[:3])),rotation_error(a[3:7],b[3:7]),
            max(abs(x-y) for x,y in zip(a[7:10],b[7:10])),max(abs(x-y) for x,y in zip(a[10:],b[10:]))]

def qualify(rows):
    worst = [0.0]*4
    for key, values in rows.items():
        kind, rate, stage, part = key
        if abs(sum(q*q for q in values[3:7])-1) > TOLERANCE:
            fail(f'non-unit rotation at {key}')
        error = errors(values,expected(kind,stage,part))
        bounds = [TOLERANCE]*4
        if kind == 2 and part == 1:
            if stage == 1:
                error[0] = error[2] = 0 # Contact onset differs between discrete predictors.
            bounds[0] = bounds[2] = CONTACT_TOLERANCE
        if any(value > bound for value,bound in zip(error,bounds)):
            fail(f'kinematic analytic mismatch {key}: {error}')
        worst = [max(a,b) for a,b in zip(worst,error)]
    return worst

def compare(first,second):
    worst = [0.0]*4
    for key in KEYS:
        error = errors(first[key],second[key]);bounds = [TOLERANCE]*4
        if key[0] == 2 and key[3] == 1:
            if key[2] == 1:
                error[0] = error[2] = 0
            bounds[0] = bounds[2] = CONTACT_TOLERANCE
        if any(value > bound for value,bound in zip(error,bounds)):
            fail(f'kinematic oracle mismatch {key}: {error}')
        worst = [max(a,b) for a,b in zip(worst,error)]
    return worst

def rejected(action):
    try:
        action()
    except (ValueError,OverflowError):
        return
    fail('corrupt kinematic witness accepted')

def self_test(raw,rows):
    lines = raw.splitlines()
    rejected(lambda: parse(raw+'\n'+lines[0]))
    rejected(lambda: parse('\n'.join(lines[1:])))
    rejected(lambda: parse(raw.replace('kinematic 0 60 0 0','kinematic 9 60 0 0')))
    rejected(lambda: parse(raw.replace(lines[0].split()[-1],'nan',1)))
    for key in ((0,60,2,1),(1,120,4,2),(2,60,2,1)):
        for component in range(13):
            changed = dict(rows);values = list(changed[key]);values[component] += .1
            changed[key] = tuple(values)
            rejected(lambda: qualify(changed))
            rejected(lambda: compare(changed,rows))
    return 82

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--mode',choices=('Debug','Release','both'),default='both')
    args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:
        fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='ragdoll-kinematic-pose-v1',oracle_revision=REFERENCE,archive_sha256=digest,
                tolerance=TOLERANCE,contact_tolerance=CONTACT_TOLERANCE,
                scope='Jolt DriveToPoseUsingKinematics; body offsets map joint poses to origins. Explicit Jolt stop at 1s adapts finite-duration Silex targets. Contact onset excluded; free motion, center velocities and moving release compared.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'RagdollKinematicOracle.cpp','ragdoll-kinematic-oracle')
        binary=build_silex(mode,'RagdollKinematic.sx','ragdoll-kinematic-silex',True)
        rows={};evidence={}
        for name,executable in (('silex',binary),('jolt',oracle)):
            raw=checked([str(executable)])
            (BUILD/f'ragdoll-kinematic-{name}-{mode.lower()}.txt').write_text(raw)
            rows[name]=parse(raw)
            evidence[name]=dict(observations=len(rows[name]),worst=qualify(rows[name]),guards=self_test(raw,rows[name]),sha256=hashlib.sha256(raw.encode()).hexdigest())
        evidence['parity']=compare(rows['silex'],rows['jolt'])
        record['modes'][mode]=evidence
        (BUILD/'ragdoll-kinematic-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: kinematic poses, COM velocities, release and contact green',flush=True)

if __name__=='__main__':
    main()
