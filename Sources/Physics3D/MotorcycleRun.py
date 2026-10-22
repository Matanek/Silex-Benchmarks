#!/usr/bin/env python3
"""Compare the public Silex motorcycle consumer with pinned Jolt and step balances."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from MotorcycleReferenceRun import KEYS, TOLERANCES, add, sub, mul, dot, cross, norm, unit, angle, sign, near, enabled, max_lean, steering, parse as parse_jolt
from MotorcycleReferenceRun import qualify as qualify_jolt
from RagdollHierarchyRun import rotation_error
from LoadedSwingTwistRun import rotate

PARITY=(.05,.1,.02,.15)


def parse(raw):
    rows={}
    for line in raw.splitlines():
        f=line.split()
        if len(f)!=50 or f[0]!='motorcycle-silex': fail('invalid public motorcycle record')
        key=tuple(map(int,f[1:4]))
        values=tuple(struct.unpack('f',struct.pack('f',float(x)))[0] for x in f[4:])
        if key not in KEYS or key in rows or not all(map(math.isfinite,values)): fail('invalid public motorcycle key/value')
        rows[key]=values
    if set(rows)!=KEYS: fail('incomplete public motorcycle witness')
    return rows


def qualify(rows):
    worst=dict(steering=0.,target=0.,linear_impulse=0.,angular_impulse=0.,position_step=0.)
    for k in range(16):
        for r in (60,120):
            integral=0.;fallen=False
            for t in range(4*r+1):
                v=rows[k,r,t]
                near(norm(v[6:10]),1.,3e-5,'unit motorcycle rotation')
                if norm(v[:3])>250 or norm(v[3:6])>60 or norm(v[10:13])>30: fail('unbounded public motorcycle state')
                for off in (16,30):
                    if not 0<=v[off+1]<=.60001 or not 0<=v[off+2]<100000 or v[off+3] not in (0,1): fail('invalid public motorcycle wheel')
                    if 8<=k<=12 and (v[off+2]!=0 or v[off+3]!=0): fail('unsupported motorcycle received wheel force')
                if not t: continue
                old=rows[k,r,t-1];fwd=rotate(old[6:10],(0,0,1));up=rotate(old[6:10],(0,1,0))
                if v[44]!=float(enabled(k,r,t)) or v[45]!=float(k not in (10,15)): fail('public motorcycle toggles differ')
                magnitude=abs(steering(k,r,t))*.6
                speed=dot(old[3:6],fwd)
                if k not in (10,15) and speed*speed>1e-6:
                    caster=math.sqrt(.75) if k==11 else 1.
                    limit=math.asin(min(1.,2*math.tan(max_lean(k))*(3. if k==12 else 9.81)/(speed*speed*caster)))
                    magnitude=min(magnitude,limit)
                expected=-sign(steering(k,r,t))*magnitude
                worst['steering']=max(worst['steering'],near(v[16],expected,TOLERANCES['steering'],'public lean steering'),near(v[30],0.,TOLERANCES['steering'],'public rear steering'))
                target=(0.,1.,0.)
                if enabled(k,r,t):
                    impulse=(0.,0.,0.)
                    for off in (16,30):
                        if old[off+3]: impulse=add(impulse,add(mul(old[off+4:off+7],old[off+2]/r),mul(old[off+7:off+10],old[off+10])))
                    smoothing=0. if k==13 else .8
                    target=add(mul(old[13:16],smoothing),mul(unit(impulse),1-smoothing))
                    target=unit(sub(target,mul(fwd,dot(target,fwd))))
                    vertical=unit(sub((0.,1.,0.),mul(fwd,fwd[1])))
                    a=angle(target,vertical,fwd)
                    if abs(a)>max_lean(k):
                        radians=sign(a)*max_lean(k)
                        target=add(add(mul(vertical,math.cos(radians)),mul(cross(fwd,vertical),math.sin(radians))),mul(fwd,dot(fwd,vertical)*(1-math.cos(radians))))
                worst['target']=max(worst['target'],near(norm(sub(v[13:16],target)),0.,TOLERANCES['target'],'public contact-derived lean target'))
                error=angle(v[13:16],up,fwd)
                integral=integral+error/r if enabled(k,r,t) else 0.
                if k==2 and v[1]<.2: fallen=True
                if k<6 and not fallen:
                    normal_impulse=(0.,0.,0.);normal_torque=(0.,0.,0.);arm=(0.,0.,0.);load=0.
                    for off in (16,30):
                        force=mul(v[off+4:off+7],v[off+2]/r)
                        lever=sub(v[off+11:off+14],old[:3])
                        normal_impulse=add(normal_impulse,force)
                        normal_torque=add(normal_torque,cross(lever,force))
                        load+=v[off+2]/r;arm=add(arm,mul(lever,v[off+2]/r))
                    external=(0.,0.,30./r) if k==4 and r<t<=2*r else (0.,0.,0.)
                    actuator=sub(sub(mul(sub(v[10:13],old[10:13]),100),normal_torque),external)
                    if not enabled(k,r,t) or not (v[19] and v[33] and v[18]>0 and v[32]>0):
                        near(norm(actuator),0.,.005,'no unsupported/disabled balance impulse')
                        compensation=(0.,0.,0.)
                    else:
                        compensation=mul(cross(mul(actuator,.01),arm),-100/load)
                        if k!=5:
                            predicted=(5000*error-1000*dot(v[10:13],fwd)+(250*integral if k==4 else 0))/r
                            worst['angular_impulse']=max(worst['angular_impulse'],near(dot(actuator,fwd),predicted,TOLERANCES['angular_impulse'],'assembled once-per-step PID balance'))
                    expected_impulse=add(add((0.,-981./r,0.),normal_impulse),compensation)
                    if k==5 and t==r+1: expected_impulse=add(expected_impulse,(0.,400.,0.))
                    actual=mul(sub(v[3:6],old[3:6]),100)
                    worst['linear_impulse']=max(worst['linear_impulse'],near(norm(sub(actual,expected_impulse)),0.,.005,'public normal and lean compensated momentum'))
                    worst['position_step']=max(worst['position_step'],near(norm(sub(sub(v[:3],old[:3]),mul(v[3:6],1/r))),0.,3e-5,'public semi-implicit position'))
                if 8<=k<=12:
                    expected=(0.,-(3. if k==12 else 9.81)/r,0.)
                    near(norm(sub(sub(v[3:6],old[3:6]),expected)),0.,3e-5,'free flight without lean actuator')
            end=rows[k,r,4*r];upright=rotate(end[6:10],(0,1,0))
            if k in (0,1,3) and abs(math.atan2(upright[0],upright[1]))>.03: fail('public assistance did not recover')
            if k==2 and abs(math.atan2(upright[0],upright[1]))<.2: fail('public disabled assistance did not fall')
            if k in (0,1,3,4,5) and (end[19]+end[33]!=2 or abs(end[18]+end[32]-981)>.5): fail('public balance did not regain loaded support')
            if k==5:
                contacts=[rows[k,r,t][19]+rows[k,r,t][33] for t in range(r+1,4*r+1)]
                if 0 not in contacts or 2 not in contacts[contacts.index(0)+1:]: fail('public jump missed loss/recovery')
    for left,right in ((0,1),(6,7)):
        for r in (60,120):
            for t in range(4*r+1):
                a,b=rows[left,r,t],rows[right,r,t]
                position=(-a[0],a[1],a[2]);velocity=(-a[3],a[4],a[5])
                rotation=(a[6],-a[7],-a[8],a[9]);angular=(a[10],-a[11],-a[12])
                errors=(norm(sub(position,b[:3])),norm(sub(velocity,b[3:6])),rotation_error(rotation,b[6:10]),norm(sub(angular,b[10:13])))
                if any(e>limit for e,limit in zip(errors,PARITY)): fail('public roll/turn mirror symmetry differs')
    return worst


def compare(rows,reference):
    worst=[0.]*4;compared=0
    for k in range(16):
        for r in (60,120):
            fallen=False
            for t in range(4*r+1):
                key=k,r,t;a,b=rows[key],reference[key]
                if k==2 and min(a[1],b[1])<.2: fallen=True
                if fallen: continue
                errors=(norm(sub(a[:3],b[:3])),norm(sub(a[3:6],b[3:6])),rotation_error(a[6:10],b[6:10]),norm(sub(a[10:13],b[10:13])))
                if any(e>limit for e,limit in zip(errors,PARITY)): fail(f'motorcycle parity {key}: {errors}')
                worst=[max(x,y) for x,y in zip(worst,errors)];compared+=1
    return dict(worst=worst,pointwise_states=compared,fallen_scope='after first center height below .2 m: bounded fall event, no chaotic rebound angle parity')


def self_test(raw,rows,reference):
    lines=raw.splitlines();bad=lines[0].split();bad[4]='nan'
    for changed in (raw+'\n'+lines[0],'\n'.join(lines[1:]),raw.replace('motorcycle-silex 0 60 0','motorcycle-silex 99 60 0',1),' '.join(bad)+'\n'+'\n'.join(lines[1:])):
        try: parse(changed)
        except (ValueError,OverflowError): pass
        else: fail('corrupt public motorcycle record accepted')
    key=0,60,60
    for component in (0,3,6,10,13,16,17,18,19,30,44,45):
        changed=dict(rows);v=list(rows[key]);v[component]+=2;changed[key]=tuple(v)
        try: qualify(changed);compare(changed,reference)
        except (ValueError,OverflowError): pass
        else: fail(f'corrupt public motorcycle observable accepted: {component}')
    return 16


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');parser.add_argument('--archive',type=Path);args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='motorcycle-silex-v1',oracle_revision=REFERENCE,archive_sha256=digest,parity=PARITY,scope='Public two-wheel motorcycle, ideal balance actuator, plane/ray contacts. Previous-step target and fixed per-step geometry. No terrain, every detector or performance claim.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'MotorcycleOracle.cpp','motorcycle-oracle')
        binary=build_silex(mode,'Motorcycle.sx','motorcycle-silex',True)
        raw_jolt=checked([str(oracle)]);reference,calls=parse_jolt(raw_jolt)
        qualify_jolt(reference,calls)
        (BUILD/f'motorcycle-jolt-{mode.lower()}.txt').write_text(raw_jolt)
        raw=checked([str(binary)]);(BUILD/f'motorcycle-silex-{mode.lower()}.txt').write_text(raw)
        rows=parse(raw);result=dict(states=len(rows),independent=qualify(rows),parity=compare(rows,reference),guards=self_test(raw,rows,reference),sha256=hashlib.sha256(raw.encode()).hexdigest(),jolt_sha256=hashlib.sha256(raw_jolt.encode()).hexdigest())
        record['modes'][mode]=result;(BUILD/'motorcycle-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: public motorcycle balance, steering and Jolt parity verified',flush=True)
    if args.mode=='both':
        if (BUILD/'motorcycle-silex-debug.txt').read_bytes()!=(BUILD/'motorcycle-silex-release.txt').read_bytes(): fail('motorcycle Native Debug/Release differ')
        record['debug_release_identical']=True;(BUILD/'motorcycle-qualification.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__': main()
