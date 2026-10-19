#!/usr/bin/env python3
"""Qualify paired wheel suspension bias against pinned Jolt and impulse balances."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD,GROUP,HERE,REFERENCE,build_oracle,build_silex,checked,fail,verified_source
from LoadedSwingTwistRun import rotate
from RagdollHierarchyRun import rotation_error

MAXIMUM=.77985
PARITY=(.02,.08,.015,.08,.02)
BALANCE=.05
SPRING_RESIDUAL=.05
HEAVE_FORCE_ROUNDOFF=.001

def total(kind,rate): return rate if kind==3 else rate//4 if kind==4 else rate*6
KEYS={(k,b,r,s) for k in range(5) for b in range(3) for r in (60,120) for s in range(total(k,r)+1)}
def add(a,b): return tuple(x+y for x,y in zip(a,b))
def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def mul(a,b): return tuple(x*b for x in a)
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def norm(a): return math.sqrt(dot(a,a))
def wheel(row,i): return row[13+9*i:22+9*i]
def roll(row):
    right=rotate(row[6:10],(1,0,0));up=rotate(row[6:10],(0,1,0));return math.atan2(right[1],up[1])
def mean(items): return sum(items)/len(items)
def parse(raw):
    rows={}
    for line in raw.splitlines():
        f=line.split()
        if len(f)!=67 or f[0]!='antiroll':fail('invalid anti-roll row')
        key=tuple(map(int,f[1:5]));v=tuple(map(float,f[5:]))
        if key not in KEYS or key in rows or not all(map(math.isfinite,v)):fail('invalid anti-roll key/value')
        rows[key]=v
    if set(rows)!=KEYS:fail('incomplete anti-roll witness')
    return rows

def qualify(rows):
    worst=[0.0,0.0,0.0,0.0]
    for key,v in rows.items():
        kind,enabled,rate,step=key;dt=1/rate
        if abs(dot(v[6:10],v[6:10])-1)>.0001 or abs(dot(v[55:59],v[55:59])-1)>.0001:fail('non-unit quaternion')
        if norm(v[:3])>10 or norm(v[3:6])>15 or norm(v[10:13])>10:fail('unbounded chassis')
        for i in range(4):
            length,force,contact,*_=wheel(v,i)
            if not 0<=length<=MAXIMUM+.00001 or not 0<=force<100000 or contact not in (0,1):fail('invalid suspension state')
            if contact==0 and (force!=0 or abs(length-MAXIMUM)>.00001 or any(wheel(v,i)[3:])):fail('unsupported wheel retained force/point/normal')
            if contact and abs(norm(wheel(v,i)[6:9])-1)>.0001:fail('non-unit support normal')
        if kind!=3:
            expected=(2 if kind==4 else 0,-.5,0)+(0,0,0)+(0,0,0,1)+(0,0,0)
            if max(abs(x-y) for x,y in zip(v[49:62],expected))>1e-6:fail('fixed support changed')
        if step==0:
            if abs(v[1]-.875475)>.00001 or norm(v[3:6]+v[10:13])>.00001 or any(wheel(v,i)[1] for i in range(4)):fail('incorrect initial state')
            continue
        prev=rows[kind,enabled,rate,step-1];force=(0,0,0);moment=(0,0,0);support_moment=(0,0,0)
        for i in range(4):
            w=wheel(v,i);point=w[3:6];normal=w[6:9];f=mul(normal,w[1]);radius=sub(point,prev[:3]);ground_radius=sub(point,prev[49:52])
            force=add(force,f);moment=add(moment,cross(radius,f));support_moment=sub(support_moment,cross(ground_radius,f))
            if w[2]:
                x=-.6 if i<2 else .6;z=-1 if i%2==0 else 1
                expected=add(prev[:3],rotate(prev[6:10],(x,-w[0]-.3,z)))
                if norm(sub(point,expected))>.0002:fail('contact point detached from wheel ray')
                if kind!=3 and (abs(point[1])>.0001 or norm(sub(normal,(0,1,0)))>.0001):fail('contact off supporting plane')

            if w[2] and w[0]>.20001:
                alignment=max(.1,dot(rotate(prev[6:10],(0,1,0)),normal));k=1200/alignment;d=160/alignment
                bias=0.0;other=i+2 if i<2 else i-2
                if enabled==1 and wheel(v,other)[2]:bias=(w[0]-wheel(v,other)[0])*1000*dt
                speed=dot(sub(add(v[3:6],cross(v[10:13],radius)),add(v[52:55],cross(v[59:62],ground_radius))),normal)
                residual=speed+k*(w[0]-MAXIMUM)/(d+dt*k)+bias+w[1]/(d+dt*k)
                err=abs(residual) if w[1]>1e-5 else max(0,-residual)
                worst[2]=max(worst[2],err)
                if err>SPRING_RESIDUAL:fail(f'anti-roll spring residual {key}/{i}: {err}')
        gravity=(0,0,0) if kind==3 else (0,-981,0)
        impulse=(0,500,0) if kind==0 and step==2*rate+1 else (0,0,0)
        torque=(0,0,(40 if kind==1 else -40)) if kind in (1,2) and 2*rate<step<=4*rate else (0,0,0)
        linear=norm(sub(sub(mul(sub(v[3:6],prev[3:6]),100),mul(add(force,gravity),dt)),impulse))
        angular=norm(sub(mul(sub(v[10:13],prev[10:13]),100),mul(add(moment,torque),dt)))
        worst[0]=max(worst[0],linear);worst[1]=max(worst[1],angular)
        if max(linear,angular)>BALANCE:fail(f'anti-roll impulse balance {key}: {linear}, {angular}')
        if kind==3:
            p=add(mul(v[3:6],100),mul(v[52:55],200))
            l=add(add(mul(v[10:13],100),mul(v[59:62],100)),add(cross(v[:3],mul(v[3:6],100)),cross(v[49:52],mul(v[52:55],200))))
            support_linear=norm(add(mul(sub(v[52:55],prev[52:55]),200),mul(force,dt)))
            support_angular=norm(sub(mul(sub(v[59:62],prev[59:62]),100),mul(support_moment,dt)))
            err=max(norm(p),norm(l),support_linear,support_angular);worst[3]=max(worst[3],err)
            if err>.01:fail(f'dynamic support failed action/reaction: {key} {err}')
    ratios=[]
    for rate in (60,120):
        for kind in range(5):
            for step in range(total(kind,rate)+1):
                base=rows[kind,0,rate,step];zero=rows[kind,2,rate,step]
                if max(abs(x-y) for x,y in zip(base,zero))>1e-6:fail('zero bar changed suspension')
                if kind in (0,4):
                    for component,(x,y) in enumerate(zip(base,rows[kind,1,rate,step])):
                        tolerance=HEAVE_FORCE_ROUNDOFF if kind==0 and component in (14,23,32,41) else 1e-6
                        if abs(x-y)>tolerance:fail('heave or missing support changed by anti-roll')
        for enabled in range(3):
            for kind in (0,1,2):
                rest=[rows[kind,enabled,rate,s] for s in range(5*rate,6*rate+1)]
                if max(abs(v[1]-.875475) for v in rest)>.003 or abs(mean([sum(wheel(v,i)[1] for i in range(4)) for v in rest])-981)>2:fail('analytic rest differs')
            contacts=[sum(wheel(rows[0,enabled,rate,s],i)[2] for i in range(4)) for s in range(2*rate+1,6*rate+1)]
            if 0 not in contacts or 4 not in contacts[contacts.index(0)+1:]:fail('support not lost and regained')
        for kind in (1,2):
            sign=1 if kind==1 else -1
            a=mean([roll(rows[kind,1,rate,s])*sign for s in range(3*rate,4*rate+1)])
            b=mean([roll(rows[kind,0,rate,s])*sign for s in range(3*rate,4*rate+1)])
            if not 0<a<.8*b or b<.01:fail('anti-roll failed to reduce loaded roll')
            ratios.append(a/b)
        for enabled in range(3):
            for step in range(6*rate+1):
                a=rows[1,enabled,rate,step];b=rows[2,enabled,rate,step]
                if abs(roll(a)+roll(b))>.0001 or abs(a[1]-b[1])>.0001:fail('opposite roll symmetry differs')
    return dict(linear=worst[0],angular=worst[1],spring_residual=worst[2],dynamic_momentum=worst[3],loaded_roll_ratios=ratios)

def compare(a,b):
    worst=[0.0]*5
    for key in KEYS:
        x,y=a[key],b[key]
        errors=[norm(sub(x[:3],y[:3])),norm(sub(x[3:6],y[3:6])),rotation_error(x[6:10],y[6:10]),norm(sub(x[10:13],y[10:13])),max(abs(wheel(x,i)[0]-wheel(y,i)[0]) for i in range(4))]
        if any(e>t for e,t in zip(errors,PARITY)):fail(f'anti-roll parity {key}: {errors}')
        worst=[max(p,q) for p,q in zip(worst,errors)]
    for kind in (0,1,2):
        for enabled in range(3):
            for rate in (60,120):
                for start,end in ((1,2),(3,4),(5,6)):
                    for i in range(4):
                        x=mean([wheel(a[kind,enabled,rate,s],i)[1] for s in range(start*rate,end*rate+1)])
                        y=mean([wheel(b[kind,enabled,rate,s],i)[1] for s in range(start*rate,end*rate+1)])
                        if abs(x-y)>10:fail('phase mean force parity differs')
    return worst

def rejected(action):
    try:action()
    except (ValueError,OverflowError):return
    fail('corrupt anti-roll witness accepted')
def self_test(raw,rows):
    lines=raw.splitlines()
    bad=lines[0].split();bad[5]='nan'
    for changed in (raw+'\n'+lines[0],'\n'.join(lines[1:]),raw.replace('antiroll 0 0 60 0','antiroll 9 0 60 0',1),' '.join(bad)+'\n'+'\n'.join(lines[1:])):
        rejected(lambda:parse(changed))
    key=(1,1,60,190)
    for c in range(62):
        changed={key:rows[key],**rows};v=list(changed[key]);v[c]+=1000 if c in (14,23,32,41) else 1;changed[key]=tuple(v)
        rejected(lambda:qualify(changed))
    changed={key:rows[key],**rows};v=list(changed[key]);v[0]+=.1;changed[key]=tuple(v);rejected(lambda:compare(changed,rows))
    return 67

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='paired-anti-roll-v1',oracle_revision=REFERENCE,archive_sha256=digest,settings=dict(mass=100,inertia=100,stiffness=1200,damping=160,lengths=[.2,MAXIMUM],bar_stiffness=[0,1000],velocity_position_iterations=[12,4],workers=1),tolerances=dict(parity=PARITY,impulse_balance=BALANCE,spring_residual=SPRING_RESIDUAL,heave_force_roundoff=HEAVE_FORCE_ROUNDOFF,dynamic_momentum=.01,phase_mean_force=10),scope='Paired spring bias, unilateral contacts, missing support, heave/jump and dynamic reactions. No tire/steering contact parity or time-step invariant torsional stiffness.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'VehicleAntiRollOracle.cpp','vehicle-anti-roll-oracle');binary=build_silex(mode,'VehicleAntiRoll.sx','vehicle-anti-roll-silex',True);rows={};evidence={}
        for name,exe in (('silex',binary),('jolt',oracle)):
            raw=checked([str(exe)]);(BUILD/f'vehicle-anti-roll-{name}-{mode.lower()}.txt').write_text(raw);rows[name]=parse(raw)
            evidence[name]=dict(observations=len(rows[name]),worst=qualify(rows[name]),guards=self_test(raw,rows[name]),sha256=hashlib.sha256(raw.encode()).hexdigest())
        evidence['parity']=compare(rows['silex'],rows['jolt']);record['modes'][mode]=evidence
        (BUILD/'vehicle-anti-roll-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(f'{mode}: paired anti-roll, lost support, spring law and reactions green',flush=True)
if __name__=='__main__':main()
