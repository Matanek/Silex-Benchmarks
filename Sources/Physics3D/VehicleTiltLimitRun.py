#!/usr/bin/env python3
"""Qualify the vehicle tilt cone against pinned Jolt and independent free-flight impulses."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD,GROUP,HERE,REFERENCE,build_oracle,build_silex,checked,fail,verified_source
from LoadedSwingTwistRun import rotate
from RagdollHierarchyRun import rotation_error

FREE_PARITY=(.002,.005,.005,.005)
CONTACT_PARITY=(.02,.08,.015,.08)
IMPULSE=.005
CONE=.003

def total(kind,rate):return (4 if kind==10 else 2)*rate
KEYS={(k,e,r,s) for k in range(11) for e in (0,1) for r in (60,120) for s in range(total(k,r)+1)}
def add(a,b):return tuple(x+y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def mul(a,b):return tuple(x*b for x in a)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def norm(a):return math.sqrt(dot(a,a))
def unit(a):return mul(a,1/norm(a))
def tilt(v,kind):
    up=rotate(v[6:10],(0,0,1) if kind==6 else (0,1,0))
    return math.atan2(norm(cross(v[25:28],up)),dot(v[25:28],up))
def parse(raw):
    rows={}
    for line in raw.splitlines():
        f=line.split()
        if len(f)!=34 or f[0]!='tilt':fail('invalid vehicle tilt row')
        key=tuple(map(int,f[1:5]));v=tuple(map(float,f[5:]))
        if key not in KEYS or key in rows or not all(map(math.isfinite,v)):fail('invalid vehicle tilt key/value')
        rows[key]=v
    if set(rows)!=KEYS:fail('incomplete vehicle tilt witness')
    return rows

def torque(kind,rate,previous):
    if kind==10 and rate//4<=previous<3*rate//4:return (0,0,40)
    if rate//2<=previous<3*rate//2:
        if kind==0:return (0,0,50)
        if kind==1:return (0,0,-50)
        if kind==2:return mul(unit((1,0,1)),50)
        if kind==3:return (0,2,0)
        if kind==4:return (0,0,100)
    return (0,0,0)
def gravity(kind,rate,previous):
    if kind==5:
        if previous>=rate:return (0,0,0)
        if previous>=rate//2:return (-9.81,0,0)
    return (0,-9.81,0)
def limit(kind,enabled,rate,step):
    if enabled==0:return math.pi
    if kind==4 and step>rate//2:
        return .35 if step>3*rate//2 else math.pi
    return .0025 if kind==10 else .5

def qualify(rows):
    worst=[0.0,0.0,0.0];finals={}
    for kind in range(11):
        for enabled in (0,1):
            for rate in (60,120):
                axis=(0,1,0)
                for step in range(total(kind,rate)+1):
                    v=rows[kind,enabled,rate,step];dt=1/rate
                    if abs(dot(v[6:10],v[6:10])-1)>.0001 or abs(norm(v[25:28])-1)>.0001:fail('non-unit tilt quaternion/vertical')
                    if norm(v[:3])>100 or norm(v[3:6])>100 or norm(v[10:13])>20:fail('unbounded vehicle tilt state')
                    if abs(math.cos(v[28])-math.cos(limit(kind,enabled,rate,step)))>.0000001:fail('incorrect mutable tilt limit')
                    for i in range(4):
                        length,force,contact=v[13+3*i:16+3*i]
                        if not 0<=length<=.77986 or not 0<=force<100000 or contact not in (0,1):fail('invalid tilt wheel observation')
                        if kind!=10 and (force!=0 or contact!=0):fail('free-flight tilt received wheel contact')
                    if step==0:continue
                    prev=rows[kind,enabled,rate,step-1];g=gravity(kind,rate,step-1)
                    expected_vertical=(0,0,1) if kind==6 and step==0 else (1,0,0) if kind==5 and step>rate//2 else (0,1,0)
                    if norm(sub(v[25:28],expected_vertical))>.000001:fail('gravity vertical or zero-gravity retention differs')
                    if kind==10:continue
                    linear=norm(sub(mul(sub(v[3:6],prev[3:6]),100),mul(g,100*dt)))
                    position=norm(sub(sub(v[:3],prev[:3]),mul(v[3:6],dt)))
                    worst[0]=max(worst[0],linear);worst[2]=max(worst[2],position)
                    if linear>IMPULSE or position>.00003:fail('tilt changed translational momentum/integration')
                    q=prev[6:10]
                    if kind==9 and step==rate//2+1:q=(1,0,0,0)
                    up=rotate(q,(0,0,1) if kind==6 else (0,1,0));normal=v[25:28]
                    candidate=cross(normal,up)
                    if norm(candidate)>0:axis=unit(candidate)
                    incoming=add(prev[10:13],mul(torque(kind,rate,step-1),dt/100))
                    angle_limit=limit(kind,enabled,rate,step)
                    expected=incoming
                    cosine=dot(normal,up);border=abs(cosine-math.cos(angle_limit))<.000001
                    projected=sub(incoming,mul(axis,max(0,dot(incoming,axis))))
                    if angle_limit<math.pi-1e-6 and cosine<math.cos(angle_limit):expected=projected
                    angular=norm(mul(sub(v[10:13],expected),100))
                    if border:angular=min(angular,norm(mul(sub(v[10:13],incoming),100)),norm(mul(sub(v[10:13],projected),100)))
                    worst[1]=max(worst[1],angular)
                    if angular>IMPULSE:fail(f'tilt angular projection/one-sided impulse {kind,enabled,rate,step}: {angular}')
                end=rows[kind,enabled,rate,total(kind,rate)];angle=tilt(end,kind)
                if enabled and kind!=8 and angle>limit(kind,enabled,rate,total(kind,rate))+CONE:fail('tilt failed to recover inside cone')
                if kind==8 and abs(angle-math.pi)>.0001:fail('exact inverted fresh-axis singularity changed')
                finals[f'{kind}/{enabled}/{rate}']=angle
                if kind==10:
                    contacts=[sum(rows[kind,enabled,rate,t][15+3*i] for i in range(4)) for t in range(rate+1,total(kind,rate)+1)]
                    if 0 not in contacts or 4 not in contacts[contacts.index(0)+1:]:fail('tilt suspension did not lose and regain contact')
    return dict(linear_impulse=worst[0],angular_impulse=worst[1],translation_step=worst[2],final_tilt=finals)

def compare(a,b):
    worst=[0.0]*4
    for key in KEYS:
        x,y=a[key],b[key]
        errors=(norm(sub(x[:3],y[:3])),norm(sub(x[3:6],y[3:6])),rotation_error(x[6:10],y[6:10]),norm(sub(x[10:13],y[10:13])))
        tolerance=CONTACT_PARITY if key[0]==10 else FREE_PARITY
        if any(e>t for e,t in zip(errors,tolerance)):fail(f'vehicle tilt parity {key}: {errors}')
        worst=[max(x,y) for x,y in zip(worst,errors)]
    return worst

def rejected(action):
    try:action()
    except (ValueError,OverflowError):return
    fail('corrupt vehicle tilt witness accepted')
def self_test(raw,rows):
    lines=raw.splitlines();bad=lines[0].split();bad[5]='nan'
    for changed in (raw+'\n'+lines[0],'\n'.join(lines[1:]),raw.replace('tilt 0 0 60 0','tilt 99 0 60 0',1),' '.join(bad)+'\n'+'\n'.join(lines[1:])):rejected(lambda:parse(changed))
    key=(0,1,60,90)
    for component in range(29):
        changed=dict(rows);v=list(rows[key]);v[component]+=1;changed[key]=tuple(v)
        rejected(lambda:qualify(changed))
    changed=dict(rows);v=list(rows[key]);v[0]+=.1;changed[key]=tuple(v);rejected(lambda:compare(changed,rows))
    return 34

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='vehicle-tilt-limit-v1',oracle_revision=REFERENCE,archive_sha256=digest,tolerances=dict(free_parity=FREE_PARITY,contact_parity=CONTACT_PARITY,free_impulse=IMPULSE,recovered_cone=CONE),scope='Vehicle cone relative to gravity, free yaw, mutations, local up, antipodal fallback and suspension coupling. Fresh exactly inverted fallback is characterized, not advertised as self-righting.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'VehicleTiltLimitOracle.cpp','vehicle-tilt-limit-oracle');binary=build_silex(mode,'VehicleTiltLimit.sx','vehicle-tilt-limit-silex',True);rows={};evidence={}
        for name,exe in (('silex',binary),('jolt',oracle)):
            raw=checked([str(exe)]);(BUILD/f'vehicle-tilt-limit-{name}-{mode.lower()}.txt').write_text(raw);rows[name]=parse(raw)
            evidence[name]=dict(observations=len(rows[name]),worst=qualify(rows[name]),guards=self_test(raw,rows[name]),sha256=hashlib.sha256(raw.encode()).hexdigest())
        evidence['parity']=compare(rows['silex'],rows['jolt']);record['modes'][mode]=evidence
        (BUILD/'vehicle-tilt-limit-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(f'{mode}: vehicle tilt cone, free-flight impulses, gravity and suspension green',flush=True)
if __name__=='__main__':main()
