#!/usr/bin/env python3
"""Qualify powered motorcycles, braking, mirrored turns and assisted/unassisted pushes."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from MotorcycleReferenceRun import add, sub, mul, dot, cross, norm, rotate, near
from VehicleInclineRun import rotation_error

KEYS = {(k,r,t) for k in range(6) for r in (60,120) for t in range(8*r+1)}
PARITY = (.05,.1,.02,.15)
RPM = .02
ROTOR = 1e-4


def parse(raw):
    rows = {}
    for line in raw.splitlines():
        f = line.split()
        if len(f)!=59 or f[0]!='motorcycle-driving': fail('invalid driving row')
        key = tuple(map(int,f[1:4]))
        v = tuple(struct.unpack('f',struct.pack('f',float(x)))[0] for x in f[4:])
        if key not in KEYS or key in rows or not all(map(math.isfinite,v)): fail('invalid driving key/value')
        rows[key]=v
    if set(rows)!=KEYS: fail('incomplete driving witness')
    return rows


def driving(k,r,t): return k<4 and 2*r<=t-1<4*r

def wheel(row,i): return row[19+17*i:36+17*i]

def tilt(row): return math.acos(max(-1.,min(1.,rotate(row[6:10],(0,1,0))[1])))


def rotors(old,row,k,r,t):
    dt=1/r;on=driving(k,r,t);brake=0. if on else 105.;strength=10. if on else 0.
    conversion=60/(2*math.pi);ratio=3*3.42
    damped=[wheel(old,i)[4]*(1-.2*dt) for i in range(2)]
    estimate=math.copysign(brake*dt,damped[1] if damped[1] else 1.)
    if wheel(row,1)[3]: estimate+=wheel(old,1)[6]*dt*.3
    # Two inertias connected by a compliant clutch; solve their 2x2 angular-momentum system.
    a=1+dt*strength*ratio*ratio/.9;b=-dt*strength*ratio/.9
    c=-dt*strength*ratio/.05;d=1+dt*strength/.05
    x=damped[1]-estimate/.9;y=old[16]/conversion+dt*(16. if on else 0.)/.05
    rear=(x*d-b*y)/(a*d-b*c);engine=(a*y-c*x)/(a*d-b*c)
    worst=near(row[16]/conversion*.05,max(0,min(6000/conversion,engine))*.05,ROTOR,'engine angular recurrence')
    before=(damped[0],rear+estimate/.9)
    for i in range(2):
        w=wheel(row,i);locked=brake>abs(before[i])*.9/dt
        expected=0. if locked else math.copysign(max(0.,abs(before[i])-brake*dt/.9),before[i])-w[6]*dt*.3/.9
        worst=max(worst,near(.9*w[4],.9*expected,ROTOR,'wheel angular recurrence'))
        angle=math.remainder(w[5]-wheel(old,i)[5]-damped[i]*dt,2*math.pi)
        near(angle,0.,ROTOR,'damped wheel rotation increment')
    return worst


def qualify(rows):
    worst=dict(rotor=0.,steering=0.,straight_linear_impulse=0.);outcomes={}
    for k in range(6):
        for r in (60,120):
            initial=rows[k,r,0]
            near(norm(sub(initial[:3],(0.,1.05,0.))),0.,1e-5,'initial box center')
            near(norm(initial[3:9]),0.,1e-6,'initial velocity/rotation');near(initial[9],1,1e-6,'initial rotation')
            fallen=False
            for t in range(8*r+1):
                v=rows[k,r,t]
                if norm(v[:3])>30 or not .1<v[1]<2 or norm(v[3:6])>20 or norm(v[10:13])>20: fail('unbounded driving body')
                near(dot(v[6:10],v[6:10]),1.,1e-4,'unit driving rotation')
                if not 0<=v[16]<=6000 or v[17]!=1 or v[18]!=float(driving(k,r,t)) or v[53]!=float(k!=5) or v[54]!=1: fail('incorrect powertrain or balance state')
                if k==5 and v[1]<.45: fallen=True
                for i in range(2):
                    w=wheel(v,i)
                    if not 0<=w[1]<=.60001 or not 0<=w[2]<100000 or w[3] not in (0.,1.) or abs(w[4])>100: fail('invalid driving wheel')
                    if w[3]:
                        near(w[9],0.,1e-4,'plane contact point')
                        near(norm(w[11:14]),1.,1e-4,'unit contact normal')
                        near(norm(w[14:17]),1.,1e-4,'unit contact tangent')
                        grip=0. if k==3 else 1.
                        if max(abs(w[6]),abs(w[7]))>grip*w[2]+.003: fail('Coulomb capacity exceeded')
                    elif max(abs(w[j]) for j in (2,6,7))>.003: fail('unsupported wheel force')
                if not t: continue
                old=rows[k,r,t-1]
                worst['rotor']=max(worst['rotor'],rotors(old,v,k,r,t))
                if k in (0,3):
                    force=(0.,-981.,0.)
                    for i in (0,1):
                        w=wheel(v,i)
                        if w[3]: force=add(force,add(mul(w[11:14],w[2]),add(mul(w[14:17],w[6]),mul(cross(w[11:14],w[14:17]),w[7]))))
                    residual=sub(mul(sub(v[3:6],old[3:6]),100),mul(force,1/r))
                    worst['straight_linear_impulse']=max(worst['straight_linear_impulse'],near(norm(residual[1:3]),0.,.005,'straight vertical/forward contact momentum'))
                steer=.35 if k==1 and driving(k,r,t) else -.35 if k==2 and driving(k,r,t) else 0.
                fwd=rotate(old[6:10],(0,0,1));speed=dot(old[3:6],fwd)
                magnitude=abs(steer)*.6
                if speed*speed>1e-6: magnitude=min(magnitude,math.asin(min(1.,2*9.81/(speed*speed))))
                expected=-math.copysign(magnitude,steer)
                worst['steering']=max(worst['steering'],near(wheel(v,0)[0],expected,3e-6,'lean limited front steering'))
                near(wheel(v,1)[0],0.,3e-6,'unsteered rear wheel')
                if k==3:
                    near(norm((v[0],v[2],v[3],v[5])),0.,1e-4,'no traction without grip')
            end=rows[k,r,8*r];powered=rows[k,r,4*r]
            if k<3:
                if norm(powered[3:6])<5 or powered[2]<4 or powered[16]<1500: fail('missing powered acceleration')
                if norm(end[3:6])>.03 or tilt(end)>.01: fail('missing braking or upright recovery')
                if k==1 and powered[0]>-2 or k==2 and powered[0]<2: fail('missing mirrored curve')
            if k==3 and powered[16]<4500: fail('zero grip rear wheel did not spin')
            if k==4:
                if max(tilt(rows[k,r,t]) for t in range(2*r+1,4*r))<.05 or tilt(end)>.01 or end[1]<.8: fail('assisted push did not perturb/recover')
            if k==5 and (not fallen or tilt(end)<1.): fail('unassisted push did not fall')
            if k!=5:
                if sum(wheel(end,i)[3] for i in (0,1))!=2: fail('final two supports missing')
                near(sum(wheel(end,i)[2] for i in (0,1)),981.,2.,'final supported weight')
            outcomes[f'{k}/{r}']=dict(position=end[:3],powered_speed=norm(powered[3:6]),final_speed=norm(end[3:6]),final_tilt=tilt(end))
    for r in (60,120):
        for t in range(8*r+1):
            a,b=rows[1,r,t],rows[2,r,t]
            for x,y in zip((-a[0],a[1],a[2],-a[3],a[4],a[5]),b[:6]): near(x,y,1e-5,'mirrored powered curve')
            if rotation_error((a[6],-a[7],-a[8],a[9]),b[6:10])>1e-5: fail('mirrored curve rotation')
    return dict(worst=worst,outcomes=outcomes)


def compare(rows,reference):
    worst=[0.]*5;count=0
    for k in range(6):
        for r in (60,120):
            fallen=False
            for t in range(8*r+1):
                a,b=rows[k,r,t],reference[k,r,t]
                if k==5 and min(a[1],b[1])<.45: fallen=True
                if fallen: continue
                errors=(norm(sub(a[:3],b[:3])),norm(sub(a[3:6],b[3:6])),rotation_error(a[6:10],b[6:10]),norm(sub(a[10:13],b[10:13])),abs(a[16]-b[16]))
                if any(x>limit for x,limit in zip(errors,(*PARITY,RPM))): fail(f'driving parity {k,r,t}: {errors}')
                worst=[max(x,y) for x,y in zip(worst,errors)];count+=1
    return dict(worst=worst,pointwise_states=count,fall_scope='pointwise stops permanently at first center below .45 m; later only bounded fall event')


def self_test(raw,rows,reference):
    lines=raw.splitlines();bad=lines[0].split();bad[4]='nan'
    for changed in (raw+'\n'+lines[0],'\n'.join(lines[1:]),raw.replace('motorcycle-driving 0 60 0','motorcycle-driving 99 60 0',1),' '.join(bad)+'\n'+'\n'.join(lines[1:])):
        try: parse(changed)
        except (ValueError,OverflowError): pass
        else: fail('corrupt driving record accepted')
    for component in (0,3,6,10,16,17,18,19,20,21,22,23,24,25,26,36,53,54):
        changed=dict(rows);v=list(rows[0,60,180]);v[component]+=10000 if component==26 else 2;changed[0,60,180]=tuple(v)
        try: qualify(changed);compare(changed,reference)
        except (ValueError,OverflowError): pass
        else: fail(f'corrupt driving observable accepted: {component}')
    return 22


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');parser.add_argument('--archive',type=Path);args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='motorcycle-driving-v1',oracle_revision=REFERENCE,archive_sha256=digest,parity=PARITY,rpm=RPM,rotor=ROTOR,scope='Ray contacts on plane, ideal 20 Nm engine, manual rear drive; unassisted chassis impact only bounded, no bounce parity or performance claim.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'MotorcycleDrivingOracle.cpp','motorcycle-driving-oracle')
        binary=build_silex(mode,'MotorcycleDriving.sx','motorcycle-driving-silex',True)
        raw_jolt=checked([str(oracle)]);(BUILD/f'motorcycle-driving-jolt-{mode.lower()}.txt').write_text(raw_jolt);reference=parse(raw_jolt)
        raw=checked([str(binary)]);(BUILD/f'motorcycle-driving-silex-{mode.lower()}.txt').write_text(raw);rows=parse(raw)
        result=dict(states=len(rows),jolt=qualify(reference),silex=qualify(rows),parity=compare(rows,reference),guards=self_test(raw,rows,reference),sha256=hashlib.sha256(raw.encode()).hexdigest(),jolt_sha256=hashlib.sha256(raw_jolt.encode()).hexdigest())
        record['modes'][mode]=result;(BUILD/'motorcycle-driving-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: motorcycle propulsion, braking, turns and balance pushes verified',flush=True)
    if args.mode=='both':
        for engine in ('jolt','silex'):
            if (BUILD/f'motorcycle-driving-{engine}-debug.txt').read_bytes()!=(BUILD/f'motorcycle-driving-{engine}-release.txt').read_bytes(): fail(f'{engine} driving Debug/Release differ')
        record['debug_release_identical']=True;(BUILD/'motorcycle-driving-qualification.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__': main()
