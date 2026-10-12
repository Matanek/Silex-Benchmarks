#!/usr/bin/env python3
"""Qualify passive ragdoll twist stops under opposed angular impulses."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from SpatialHingesRun import add, sub, mul, norm, dot, cross, rotate

KEYS={(rate,side,frame,step,part) for rate in (60,120) for side in (-1,1)
      for frame in (0,1) for step in range(rate*4+1) for part in range(3)}
BEFORE={("before",rate,side,frame,step,part) for rate in (60,120) for side in (-1,1)
        for frame in (0,1) for step in (0,rate*2) for part in range(3)}
BOUNDS=dict(momentum=.0001,geometry=.001,observable=.00002,energy_increase=.0001,
            settled_angle=.02,settled_speed=.01,settled_parity=.02)

def parse(raw):
    rows={}
    for line in raw.splitlines():
        fields=line.split()
        if len(fields)!=23 or fields[0] not in ('ragdolllimit','ragdollimpulse'):fail('invalid ragdoll limit row')
        try:
            key=tuple(map(int,fields[1:6]))
            if fields[0]=="ragdollimpulse":key=("before",)+key
            values=tuple(map(float,fields[6:]))
        except (ValueError,OverflowError):fail('invalid ragdoll limit number')
        if key not in KEYS|BEFORE or key in rows or not all(map(math.isfinite,values)):
            fail('invalid, duplicate or nonfinite ragdoll limit observation')
        rows[key]=values
    if set(rows)!=KEYS|BEFORE:fail('missing ragdoll limit observations')
    return rows

def conjugate(q):return (-q[0],-q[1],-q[2],q[3])
def product(a,b):return (*add(add(mul(b[:3],a[3]),mul(a[:3],b[3])),cross(a[:3],b[:3])),a[3]*b[3]-dot(a[:3],b[:3]))
def base_rotation(frame):
    if frame==0:return (0,0,0,1)
    axis=mul((1,2,-1),1/math.sqrt(6))
    return (*mul(axis,math.sin(.3)),math.cos(.3))

def qualify(rows):
    worst={key:0.0 for key in BOUNDS if key!="settled_parity"}
    for rate in (60,120):
        for side in (-1,1):
            for frame in (0,1):
                base=base_rotation(frame);axis=rotate(base,(1,0,0));previous_energy=0.0
                for step in range(rate*4+1):
                    members=[rows[rate,side,frame,step,part] for part in range(3)]
                    momentum=(0,0,0);energy=0.0
                    for part,row in enumerate(members):
                        p,q,v,w=row[:3],row[3:7],row[7:10],row[10:13]
                        twist,sy,sz,anchor=row[13:]
                        expected=add((0,3,0),mul(axis,part))
                        geometry=max(norm(sub(p,expected)),norm(v),abs(norm(q)-1),abs(sy),abs(sz),norm(cross(w,axis)))
                        observable=0.0
                        if part>0:
                            parent=members[part-1];relative=product(conjugate(parent[3:7]),q)
                            if relative[3]<0:relative=tuple(-x for x in relative)
                            angle=2*math.atan2(relative[0],relative[3])
                            first=add(parent[:3],rotate(parent[3:7],(.5,0,0)))
                            second=add(p,rotate(q,(-.5,0,0)))
                            observable=max(abs(angle-twist),abs(norm(sub(second,first))-anchor))
                            # Bound at most one step of the initial 3 rad/s relative
                            # speed beyond a stop, separately from settled states.
                            if not -.2-3/rate-.005<=twist<=.35+3/rate+.005 or anchor<0:
                                fail('ragdoll stop or anchor escaped its bound')
                        if step==0:
                            initial_speed=mul(axis,3*side) if part==2 else (0,0,0)
                            observable=max(observable,norm(sub(w,initial_speed)),abs(dot(q,base)-1),abs(twist),abs(anchor))
                        if part==0 and max(abs(twist),abs(sy),abs(sz),abs(anchor))>0:fail('root has a parent observation')
                        momentum=add(momentum,add(mul(cross(p,v),2),mul(w,.2)))
                        energy+=dot(v,v)+.1*dot(w,w)
                        for name,error in (('geometry',geometry),('observable',observable)):
                            worst[name]=max(worst[name],error)
                            if error>BOUNDS[name]:fail(f'ragdoll {name} differs: {error}')
                    expected_momentum=mul(axis,.6*side if step<rate*2 else 0)
                    residual=norm(sub(momentum,expected_momentum));worst['momentum']=max(worst['momentum'],residual)
                    if residual>BOUNDS['momentum']:fail(f'ragdoll momentum differs: {residual}')
                    if step not in (0,rate*2):
                        increase=max(0,energy-previous_energy);worst['energy_increase']=max(worst['energy_increase'],increase)
                        if increase>BOUNDS['energy_increase']:fail('passive ragdoll injects kinetic energy')
                    else:
                        direction=side if step==0 else -side
                        for part in range(3):
                            prior=rows["before",rate,side,frame,step,part]
                            after=members[part]
                            expected_jump=mul(axis,3*direction) if part==2 else (0,0,0)
                            if norm(sub(sub(after[10:13],prior[10:13]),expected_jump))>.00002:
                                fail('angular impulse differs or changes another body')
                            if max(abs(after[i]-prior[i]) for i in (*range(10),*range(13,17)))>.000001:
                                fail('impulse places a body or changes constraints')
                    previous_energy=energy
                    if step in (rate*2-1,rate*4):
                        direction=side if step<rate*2 else -side
                        target=.35 if direction>0 else -.2
                        speed=side if step<rate*2 else 0
                        angle_error=max(abs(row[13]-target) for row in members[1:])
                        speed_error=max(norm(sub(row[10:13],mul(axis,speed))) for row in members)
                        worst['settled_angle']=max(worst['settled_angle'],angle_error)
                        worst['settled_speed']=max(worst['settled_speed'],speed_error)
                        if angle_error>BOUNDS['settled_angle'] or speed_error>BOUNDS['settled_speed']:
                            fail(f'ragdoll failed to transmit and settle at both stops: {angle_error}, {speed_error}')
    return worst

def compare(first,second):
    error=max(max(abs(first[key][i]-second[key][i]) for i in (10,11,12,13))
              for key in KEYS if key[3] in (key[0]*2-1,key[0]*4))
    if error>BOUNDS['settled_parity']:fail('settled ragdoll stop parity differs')
    return error

def rejected(action):
    try:action()
    except ValueError:return
    fail('ragdoll limit guard accepted corrupt evidence')

def self_test(raw,rows):
    lines=raw.splitlines()
    rejected(lambda:parse(raw+'\n'+lines[0]));rejected(lambda:parse('\n'.join(lines[1:])))
    rejected(lambda:parse(raw.replace('ragdollimpulse 60 -1 0 0 0','ragdollimpulse 30 -1 0 0 0')))
    rejected(lambda:parse(raw.replace(lines[0],lines[0]+' 0')))
    fields=lines[0].split();fields[6]='nan'
    rejected(lambda:parse('\n'.join([' '.join(fields)]+lines[1:])))
    for index in range(17):
        altered=rows.copy();key=(60,1,1,90,2);values=list(altered[key]);values[index]+=2
        altered[key]=tuple(values);rejected(lambda:qualify(altered))
    zero=rows.copy();key=(60,1,0,119,0);values=list(zero[key]);values[10]=0;zero[key]=tuple(values)
    rejected(lambda:qualify(zero))
    parity=rows.copy();key=(60,1,0,119,2);values=list(parity[key]);values[13]+=.1;parity[key]=tuple(values)
    rejected(lambda:compare(rows,parity))
    for index in (0,10):
        altered=rows.copy();key=("before",60,1,0,120,2);values=list(altered[key]);values[index]+=.1
        altered[key]=tuple(values);rejected(lambda:qualify(altered))
    injected=rows.copy()
    for part,jump in ((1,2),(2,-2)):
        key=(60,1,0,90,part);values=list(injected[key]);values[10]+=jump;injected[key]=tuple(values)
    rejected(lambda:qualify(injected))
    return 27

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both')
    parser.add_argument('--archive',type=Path);parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='ragdoll-passive-twist-stops-v1',oracle_revision=REFERENCE,archive_sha256=digest,bounds=BOUNDS,
                scope='Free three-sphere ragdoll, locked swing, asymmetric twist stops and opposed angular impulses; two world frames, no gravity or contacts. Physical invariants and settled stop states, no general transient impact parity.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        if not args.check_only:
            oracle=build_oracle(source,mode,HERE/'RagdollLimitsOracle.cpp','ragdoll-limits-oracle')
            binary=build_silex(mode,'RagdollLimits.sx','ragdoll-limits-silex',True)
            for name,exe in (('silex',binary),('jolt',oracle)):
                (BUILD/f'ragdoll-limits-{name}-{mode.lower()}.txt').write_text(checked([str(exe)]))
        evidence={};all_rows={}
        for name in ('silex','jolt'):
            raw=(BUILD/f'ragdoll-limits-{name}-{mode.lower()}.txt').read_text();rows=parse(raw);all_rows[name]=rows
            evidence[name]=dict(observations=len(rows),worst=qualify(rows),corrupt_witnesses_rejected=self_test(raw,rows),output_sha256=hashlib.sha256(raw.encode()).hexdigest())
        evidence['settled_parity']=compare(all_rows['silex'],all_rows['jolt']);record['modes'][mode]=evidence
        (BUILD/'ragdoll-limits-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: passive ragdoll stop transmission, momentum, energy and settled parity green',flush=True)

if __name__=='__main__':main()
