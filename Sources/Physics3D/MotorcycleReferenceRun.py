#!/usr/bin/env python3
"""Qualify pinned Jolt motorcycle balance and lean-dependent steering before Silex."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, checked, fail, verified_source
from LoadedSwingTwistRun import rotate

TOLERANCES = dict(steering=3e-6, target=3e-4, angular_impulse=.1,
                  compensated_velocity=3e-6, integral=3e-6, unit=3e-5,
                  frame_linear_impulse=.005, position_step=3e-5)
KEYS = {(k, r, t) for k in range(16) for r in (60, 120) for t in range(4*r+1)}


def add(a, b): return tuple(x+y for x, y in zip(a, b))
def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def mul(a, b): return tuple(x*b for x in a)
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a): return math.sqrt(dot(a, a))
def unit(a): return mul(a, 1/norm(a)) if norm(a)>1e-10 else (0., 1., 0.)
def sign(x): return -1 if x<0 else 1
def angle(target, up, axis): return -sign(dot(cross(target, up), axis))*math.acos(max(-1., min(1., dot(target, up))))
def near(a, b, tolerance, label):
    error = abs(a-b)
    if not math.isfinite(error) or error>tolerance: fail(f'{label}: {a} versus {b}; error {error}, bound {tolerance}')
    return error


def parse(raw):
    rows, solves = {}, {}
    for line in raw.splitlines():
        f = line.split()
        if not f or f[0] not in ('motorcycle', 'motorcycle-solve'): fail('unknown motorcycle record')
        solve = f[0]=='motorcycle-solve'
        if len(f)!=(36 if solve else 47): fail(f'invalid motorcycle width {len(f)}')
        n = 5 if solve else 4
        key = tuple(map(int, f[1:n]))
        values = tuple(struct.unpack('f', struct.pack('f', float(x)))[0] for x in f[n:])
        target = solves if solve else rows
        if (key[:3] not in KEYS or key in target or not all(map(math.isfinite, values))
                or solve and (key[2]==0 or not 0<=key[3]<12 or not key[0]<6)):
            fail('invalid/duplicate motorcycle key or value')
        target[key] = values
    if set(rows)!=KEYS: fail('incomplete motorcycle witness')
    observed = {}
    for key in solves:
        observed.setdefault(key[:3], set()).add(key)
    for (k, r, t), v in rows.items():
        if v[18]!=int(v[18]) or not (v[18]==0 if t==0 else 1<=v[18]<=12):
            fail('invalid motorcycle solver call count')
        if t and k<6:
            expected = {(k, r, t, i) for i in range(int(v[18]))}
            actual = observed.get((k, r, t), set())
            if actual!=expected or not expected: fail('missing motorcycle solver iteration')
    return rows, solves


def enabled(k, r, t): return k!=2 and not (k==3 and r<t<=2*r)
def max_lean(k): return .05 if k>=14 else math.pi/4
def steering(k, r, t):
    if 8<=k<=12: return -.75 if k==9 else .75
    if k in (6,7,13,14,15) and r<=t-1<3*r: return -.35 if k==7 else .35
    return 0.


def qualify(rows, solves):
    worst = dict(steering=0., target=0., angular_impulse=0., compensated_velocity=0., integral=0., frame_linear_impulse=0.)
    outcomes = {}
    for (k, r, t), v in rows.items():
        near(norm(v[6:10]), 1., TOLERANCES['unit'], 'unit body rotation')
        if norm(v[:3])>250 or norm(v[3:6])>60 or norm(v[10:13])>30: fail('unbounded motorcycle state')
        for off in (19, 30):
            if not 0<=v[off+1]<=.60001 or not 0<=v[off+2]<100000 or v[off+3] not in (0., 1.): fail('invalid motorcycle wheel')
            if 8<=k<=12 and (v[off+2]!=0 or v[off+3]!=0): fail('airborne motorcycle has ground force')
        if not t: continue
        previous = rows[k, r, t-1]
        if v[18]!=int(v[18]) or not 1<=v[18]<=12: fail('invalid motorcycle solver call count')
        if k not in (2,6,7,13,14,15):
            expected_impulse=(0.,-(3. if k==12 else 9.81)*100/r,0.)
            for off in (19,30):
                expected_impulse=add(expected_impulse,mul(v[off+4:off+7],v[off+2]/r))
            if k<6:
                for i in range(int(v[18])):
                    call=solves[k,r,t,i]
                    expected_impulse=add(expected_impulse,mul(sub(call[9:12],call[6:9]),100))
            if k==5 and t==r+1: expected_impulse=add(expected_impulse,(0.,400.,0.))
            actual_impulse=mul(sub(v[3:6],previous[3:6]),100)
            worst['frame_linear_impulse']=max(worst['frame_linear_impulse'],near(norm(sub(actual_impulse,expected_impulse)),0.,TOLERANCES['frame_linear_impulse'],'gravity, suspension and lean linear momentum'))
            near(norm(sub(sub(v[:3],previous[:3]),mul(v[3:6],1/r))),0.,TOLERANCES['position_step'],'semi implicit body position')
        if v[41]!=float(enabled(k,r,t)) or v[42]!=float(k not in (10,15)): fail('incorrect controller toggles')
        fwd = rotate(previous[6:10], (0,0,1))
        strength = abs(steering(k,r,t))*.6
        speed = dot(previous[3:6], fwd)
        if k not in (10,15) and speed*speed>1e-6:
            caster = math.sqrt(.75) if k==11 else 1.
            limit = math.asin(min(1., 2*math.tan(max_lean(k))*(3. if k==12 else 9.81)/(speed*speed*caster)))
            strength = min(strength, limit)
        expected = -sign(steering(k,r,t))*strength
        worst['steering'] = max(worst['steering'],near(v[19],expected,TOLERANCES['steering'],'lean steering'),near(v[30],0.,TOLERANCES['steering'],'fixed rear steering'))
        if not enabled(k,r,t): target = (0.,1.,0.)
        else:
            impulse = (0.,0.,0.)
            for off in (19,30):
                if previous[off+3]:
                    impulse = add(impulse,add(mul(previous[off+4:off+7],previous[off+2]/r),mul(previous[off+7:off+10],previous[off+10])))
            smoothing = 0. if k==13 else .8
            target = add(mul(previous[13:16],smoothing),mul(unit(impulse),1-smoothing))
            target = unit(sub(target,mul(fwd,dot(target,fwd))))
            up = unit(sub((0.,1.,0.),mul(fwd,fwd[1])))
            a = angle(target,up,fwd)
            if abs(a)>max_lean(k):
                radians = sign(a)*max_lean(k)
                target = add(add(mul(up,math.cos(radians)),mul(cross(fwd,up),math.sin(radians))),mul(fwd,dot(fwd,up)*(1-math.cos(radians))))
        worst['target'] = max(worst['target'],near(norm(sub(v[13:16],target)),0.,TOLERANCES['target'],'smoothed contact target'))
        if k in (14,15):
            up=unit(sub((0.,1.,0.),mul(fwd,fwd[1])))
            if abs(angle(v[13:16],up,fwd))>.0503: fail('target escaped the lean cone')
        if k<6:
            first = solves[k,r,t,0]
            a = angle(v[13:16],rotate(previous[6:10],(0,1,0)),fwd)
            expected_integral = previous[16]+a/r if enabled(k,r,t) else 0.
            # ACos of float32 unit vectors is ill-conditioned within one milliradian of zero.
            bound = TOLERANCES['integral']+.001/r
            worst['integral'] = max(worst['integral'],near(first[21],expected_integral,bound,'pre-contact integrated lean error'))
            near(v[16],solves[k,r,t,int(v[18])-1][22],TOLERANCES['integral'],'final integrated error')
            near(v[17],solves[k,r,t,int(v[18])-1][24],1e-6,'final applied impulse')
        if t==4*r:
            outcomes[f'{k}/{r}'] = dict(roll=math.atan2(rotate(v[6:10],(0,1,0))[0],rotate(v[6:10],(0,1,0))[1]),position=v[:3],speed=norm(v[3:6]),integral=v[16])
    for (k,r,t,i), v in solves.items():
        old_w,new_w,old_v,new_v = v[:3],v[3:6],v[6:9],v[9:12]
        axis,up,target = v[12:15],v[15:18],v[18:21]
        integral,new_integral,old_impulse,new_impulse = v[21:25]
        supported,active = v[29:31]
        if supported not in (0,1) or active not in (0,1): fail('invalid solver flags')
        expected_integral = integral
        expected_impulse = old_impulse
        expected_w,expected_v = old_w,old_v
        if active and supported:
            expected_impulse = (5000*angle(target,up,axis)-1000*dot(old_w,axis)+(250 if k in (4,5) else 0)*integral)/r
            expected_w = add(old_w,mul(axis,(new_impulse-old_impulse)/100))
            if v[28]<=0: fail('supported lean has no suspension impulse')
            expected_v = sub(old_v,mul(cross(sub(new_w,old_w),v[25:28]),1/v[28]))
        elif active:
            expected_integral *= max(0.,1-4/r)
        worst['angular_impulse'] = max(worst['angular_impulse'],near(new_impulse,expected_impulse,TOLERANCES['angular_impulse'],'PID total impulse'),near(norm(sub(new_w,expected_w))*100,0.,.0002,'angular impulse applied once'))
        worst['compensated_velocity'] = max(worst['compensated_velocity'],near(norm(sub(new_v,expected_v)),0.,TOLERANCES['compensated_velocity'],'contact weighted velocity compensation'))
        near(new_integral,expected_integral,TOLERANCES['integral'],'per-iteration unsupported integral decay')
    for r in (60,120):
        if abs(outcomes[f'0/{r}']['roll'])>.01 or abs(outcomes[f'1/{r}']['roll'])>.01: fail('enabled balance failed to return upright')
        if abs(outcomes[f'2/{r}']['roll'])<.2: fail('disabled balance did not fall')
        if abs(outcomes[f'3/{r}']['roll'])>.03: fail('re-enabled balance did not recover')
        contacts = [rows[5,r,t][22]+rows[5,r,t][33] for t in range(r+1,4*r+1)]
        if 0 not in contacts or 2 not in contacts[contacts.index(0)+1:]: fail('jump failed to lose and regain support')
        for k in (6,7):
            peak=max(abs(rotate(rows[k,r,t][6:10],(0,1,0))[0]) for t in range(r,3*r+1))
            if peak<.01: fail('coasting turn produced no lean')
        peak=max(abs(angle(rows[15,r,t][13:16],(0.,1.,0.),rotate(rows[15,r,t-1][6:10],(0,0,1)))) for t in range(1,4*r+1))
        if peak<.049: fail('unlimited steering never exercised lean clamp')
        distance=max(norm(sub(rows[6,r,t][13:16],rows[13,r,t][13:16])) for t in range(1,4*r+1))
        if distance<.01: fail('smoothing comparison produced no distinct response')
    return dict(worst=worst,outcomes=outcomes,states=len(rows),solver_calls=len(solves))


def self_test(raw,rows,solves):
    lines=raw.splitlines()
    for changed in (raw+'\n'+lines[-1], '\n'.join(lines[1:]), raw.replace('motorcycle 0 60 0','motorcycle 99 60 0',1),raw.replace('motorcycle 0 60 0 0','motorcycle 0 60 0 nan',1)):
        try: parse(changed)
        except (ValueError,OverflowError): pass
        else: fail('corrupt motorcycle witness accepted')
    key=(0,60,60)
    for component in (6,13,16,17,19,20,21,22,30,41,42):
        changed=dict(rows);v=list(rows[key]);v[component]+=2;changed[key]=tuple(v)
        try: qualify(changed,solves)
        except (ValueError,OverflowError): pass
        else: fail(f'corrupt motorcycle state accepted: {component}')
    key=(0,60,60,0)
    for component in (3,9,22,24):
        changed=dict(solves);v=list(solves[key]);v[component]+=2;changed[key]=tuple(v)
        try: qualify(rows,changed)
        except (ValueError,OverflowError): pass
        else: fail(f'corrupt motorcycle solve accepted: {component}')
    return 19


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--mode',choices=('Debug','Release','both'),default='both')
    args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='motorcycle-reference-v1',oracle_revision=REFERENCE,archive_sha256=digest,tolerances=TOLERANCES,modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        binary=build_oracle(source,mode,HERE/'MotorcycleOracle.cpp','motorcycle-oracle')
        raw=checked([str(binary)])
        (BUILD/f'motorcycle-jolt-{mode.lower()}.txt').write_text(raw)
        rows,solves=parse(raw)
        result=qualify(rows,solves)
        result.update(guards=self_test(raw,rows,solves),sha256=hashlib.sha256(raw.encode()).hexdigest())
        record['modes'][mode]=result
        (BUILD/'motorcycle-reference-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: motorcycle target, spring, compensation, contact gating and steering verified',flush=True)
    if args.mode=='both':
        if (BUILD/'motorcycle-jolt-debug.txt').read_bytes()!=(BUILD/'motorcycle-jolt-release.txt').read_bytes():
            fail('motorcycle reference Debug/Release outputs differ')
        record['debug_release_identical']=True
        (BUILD/'motorcycle-reference-qualification.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__': main()
