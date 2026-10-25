#!/usr/bin/env python3
"""Qualify a responsive motorcycle scene profile and its physical rider controls."""
import argparse
from MotorcycleLeanOracle import build_motorcycle_oracle
import hashlib
import json
import math
import struct
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from MotorcycleReferenceRun import add, sub, mul, dot, norm, rotate, near
from VehicleInclineRun import rotation_error

KEYS={(k,r,t) for k in range(6) for r in (60,120) for t in range(16*r+1)}
PARITY=(.05,.1,.02,.15)
ROTOR=1e-4


def parse(raw):
    rows={}
    for line in raw.splitlines():
        f=line.split()
        if len(f)!=63 or f[0]!='motorcycle-handling': fail('invalid handling record')
        key=tuple(map(int,f[1:4]));v=tuple(struct.unpack('f',struct.pack('f',float(x)))[0] for x in f[4:])
        if key not in KEYS or key in rows or not all(map(math.isfinite,v)): fail('invalid handling key/value')
        rows[key]=v
    if set(rows)!=KEYS: fail('incomplete handling witness')
    return rows


def wheel(v,i): return v[19+17*i:36+17*i]
def tilt(v): return math.acos(max(-1.,min(1.,rotate(v[6:10],(0,1,0))[1])))


def inputs(k,r,t):
    step=t-1;throttle=0.;steering=0.;brake=.35
    if k<3 and 2*r<=step<(4 if k==0 else 8)*r: throttle=.4;brake=0.
    if k in (1,2) and 4*r<=step<8*r: steering=(.35 if step//r%2==0 else -.35)*(1 if k==1 else -1)
    if k==3 and 2*r<=step<5*r: throttle=1.;brake=0.
    return throttle,steering,brake


def commands(old,k,r,t):
    throttle,steering,brake=inputs(k,r,t);q=old[6:10];fwd=rotate(q,(0,0,1))
    crashed=bool(old[56]) or rotate(q,(0,1,0))[1]<.3
    pitch=math.asin(max(-1.,min(1.,fwd[1])));pitch_rate=-dot(old[10:13],rotate(q,(1,0,0)))
    throttle*=max(0.,min(1.,(.25-pitch-.15*pitch_rate)/.15))
    if crashed: throttle=0.;steering=0.;brake=.35
    speed=dot(old[3:6],fwd)
    cap=min(.35,math.asin(min(1.,2*math.tan(.5)*9.81/max(1e-6,speed*speed)))/.6)
    desired=max(-cap,min(cap,steering));before=max(-cap,min(cap,old[55]));increment=2*cap/(.3*r)
    return throttle,before+max(-increment,min(increment,desired-before)),brake,crashed


def rotors(old,v,throttle,brake,r):
    dt=1/r;conversion=60/(2*math.pi);ratio=3*3.42;strength=10. if throttle>0 else 0.;braking=300*brake
    damped=[wheel(old,i)[4]*(1-.2*dt) for i in (0,1)]
    estimate=math.copysign(braking*dt,damped[1] if damped[1] else 1.)
    if wheel(v,1)[3]: estimate+=wheel(old,1)[6]*dt*.3
    a=1+dt*strength*ratio*ratio/.9;b=-dt*strength*ratio/.9;c=-dt*strength*ratio/.05;d=1+dt*strength/.05
    x=damped[1]-estimate/.9;y=old[16]/conversion+dt*80*throttle/.05
    rear=(x*d-b*y)/(a*d-b*c);engine=(a*y-c*x)/(a*d-b*c)
    worst=near(v[16]/conversion*.05,max(0,min(6000/conversion,engine))*.05,ROTOR,'engine angular momentum recurrence')
    for i,before in enumerate((damped[0],rear+estimate/.9)):
        w=wheel(v,i);locked=braking>abs(before)*.9/dt
        expected=0. if locked else math.copysign(max(0.,abs(before)-braking*dt/.9),before)-w[6]*dt*.3/.9
        worst=max(worst,near(.9*w[4],.9*expected,ROTOR,'wheel angular momentum recurrence'))
        near(math.remainder(w[5]-wheel(old,i)[5]-damped[i]*dt,2*math.pi),0.,ROTOR,'wheel angle recurrence')
    return worst


def qualify(rows):
    worst=dict(rotor=0.,command=0.,steering=0.);outcomes={}
    for k in range(6):
        for r in (60,120):
            air=0;peak_tilt=0.;signs=set()
            for t in range(16*r+1):
                v=rows[k,r,t]
                if norm(v[:3])>250 or not .1<v[1]<3 or norm(v[3:6])>30 or norm(v[10:13])>50: fail('unbounded handling body')
                near(dot(v[6:10],v[6:10]),1.,1e-4,'unit handling quaternion')
                if not 0<=v[16]<=6000 or v[17]!=1 or v[57]!=float(k!=5) or v[54]!=1 or v[56] not in (0.,1.): fail('invalid handling powertrain/flags')
                if v[53]!=float(k!=5 and not v[56]): fail('crashed rider reactivated balance')
                if v[56] and v[58]!=0: fail('crashed rider kept throttle')
                near(norm(v[13:16]),0. if t==0 else 1.,1e-4,'unit lean target')
                for i in (0,1):
                    w=wheel(v,i)
                    if not 0<=w[1]<=.60001 or not 0<=w[2]<100000 or w[3] not in (0.,1.) or abs(w[4])>100: fail('invalid handling wheel')
                    if max(abs(w[6]),abs(w[7]))>w[2]+.003: fail('handling tire exceeds capacity')
                if k<4:
                    peak_tilt=max(peak_tilt,tilt(v))
                    if v[56] or tilt(v)>.7: fail('rider overturned during normal driving/reversals/wheelie')
                if not wheel(v,0)[3] and wheel(v,1)[3] and rotate(v[6:10],(0,0,1))[1]>.06: air+=1
                if 4*r<t<8*r and abs(wheel(v,0)[0])>.005: signs.add(wheel(v,0)[0]>0)
                if not t:
                    near(norm(sub(v[:3],(0.,1.05,0.))),0.,1e-5,'initial handling position')
                    continue
                old=rows[k,r,t-1];throttle,steering,brake,crashed=commands(old,k,r,t)
                worst['command']=max(worst['command'],near(v[58],throttle,3e-6,'pitch and pitch-rate throttle governor'),near(v[55],steering,3e-6,'bounded progressive steering'))
                if v[56]!=float(crashed) or v[18]!=float(throttle>0): fail('crash latch/clutch transition differs')
                worst['steering']=max(worst['steering'],near(wheel(v,0)[0],-.6*v[55],3e-6,'physical front steering'))
                near(wheel(v,1)[0],0.,3e-6,'unsteered rear')
                worst['rotor']=max(worst['rotor'],rotors(old,v,throttle,brake,r))
            end=rows[k,r,16*r]
            if k<4:
                if norm(end[3:6])>.05 or norm(end[10:13])>.05 or tilt(end)>.05: fail('driving did not return to rest')
                near(wheel(end,0)[2]+wheel(end,1)[2],981.,2.,'final supported weight')
                if k<3 and norm(rows[k,r,4*r][3:6])<10: fail('responsive acceleration missing')
                if k in (1,2) and len(signs)!=2: fail('steering reversal did not reach both signs')
                if k==3 and (air<r/10 or peak_tilt<.1): fail('physical rear-wheel ride missing')
            else:
                if not end[56] or tilt(end)<1.: fail('crash/passive fall event missing')
                base=rows[k,r,14*r]
                for t in range(14*r,16*r+1):
                    v=rows[k,r,t]
                    if norm(sub(v[:3],base[:3]))>.02 or rotation_error(v[6:10],base[6:10])>.05: fail('fallen body keeps travelling/rolling')
                if k==4 and (rows[k,r,4*r][56] or tilt(rows[k,r,4*r])>.05): fail('assisted push did not recover before collision')
            outcomes[f'{k}/{r}']=dict(peak_tilt=peak_tilt,front_air_steps=air,crashed=bool(end[56]),final_speed=norm(end[3:6]),final_spin=norm(end[10:13]))
    for r in (60,120):
        for t in range(16*r+1):
            a,b=rows[1,r,t],rows[2,r,t]
            if norm(sub((-a[0],a[1],a[2]),b[:3]))>.01 or rotation_error((a[6],-a[7],-a[8],a[9]),b[6:10])>.01: fail('handling mirrored slalom differs')
    return dict(worst=worst,outcomes=outcomes)


def compare(rows,reference):
    worst=[0.]*4;rpm=0.;count=0
    for k in range(6):
        for r in (60,120):
            fallen=False
            for t in range(16*r+1):
                a,b=rows[k,r,t],reference[k,r,t]
                if k==4 and t>4*r or k==5 and (min(a[1],b[1])<.45 or a[56] or b[56]): fallen=True
                if fallen: continue
                errors=(norm(sub(a[:3],b[:3])),norm(sub(a[3:6],b[3:6])),rotation_error(a[6:10],b[6:10]),norm(sub(a[10:13],b[10:13])))
                if any(x>limit for x,limit in zip(errors,PARITY)): fail(f'handling parity {k,r,t}: {errors}')
                worst=[max(x,y) for x,y in zip(worst,errors)];rpm=max(rpm,abs(a[16]-b[16]));count+=1
    return dict(worst=worst,pointwise_states=count,rpm_difference_observed=rpm,rpm_proof='independent angular-momentum recurrence, no accumulated-RPM parity claim for this new rider profile',fall_scope='case4 pointwise until forced collision at4s; case5 until first crash/center below.45m; later event/cutout/pose settling')


def self_test(raw,rows,reference):
    lines=raw.splitlines();bad=lines[0].split();bad[4]='nan'
    for changed in (raw+'\n'+lines[0],'\n'.join(lines[1:]),raw.replace('motorcycle-handling 0 60 0','motorcycle-handling 99 60 0',1),' '.join(bad)+'\n'+'\n'.join(lines[1:])):
        try: parse(changed)
        except (ValueError,OverflowError): pass
        else: fail('corrupt handling record accepted')
    fields=(0,3,6,10,13,16,17,18,19,20,21,22,23,24,25,53,54,55,56,57,58)
    for component in fields:
        key=(0,60,960) if component==21 else (0,60,180)
        changed=dict(rows);v=list(rows[key]);v[component]+=20000 if component==21 else 2;changed[key]=tuple(v)
        try: qualify(changed);compare(changed,reference)
        except (ValueError,OverflowError): pass
        else: fail(f'corrupt handling observable accepted: {component}')
    return 4+len(fields)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=('Debug','Release','both'),default='both');p.add_argument('--archive',type=Path);p.add_argument('--stable-lean',action='store_true',help='Explicit atan2 variant of the pinned motorcycle controller; original source stays intact');args=p.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    output_stem='motorcycle-handling'+('-stable-lean' if args.stable_lean else '')
    record=dict(schema=1,fixture='motorcycle-handling-v1',oracle_revision=REFERENCE,archive_sha256=digest,body_parity=PARITY,rotor_recurrence=ROTOR,scope='100kg/I100,80Nm,shifted wheelbase,plane rays; application input smoothing,pitch governor,latched crash cutout. Jolt coefficient c/(1+c*dt) matches Silex rational damping. No calibrated real motorcycle or arbitrary terrain claim.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        j,adapter=build_motorcycle_oracle(source,mode,HERE/'MotorcycleHandlingOracle.cpp','motorcycle-handling-oracle',stable=args.stable_lean);b=build_silex(mode,'MotorcycleHandling.sx','motorcycle-handling-silex',True)
        raw_j=checked([str(j)]);raw=checked([str(b)]);(BUILD/f'{output_stem}-jolt-{mode.lower()}.txt').write_text(raw_j);(BUILD/f'{output_stem}-silex-{mode.lower()}.txt').write_text(raw)
        reference=parse(raw_j);rows=parse(raw)
        record['modes'][mode]=dict(oracle_adapter=adapter,states=len(rows),jolt=qualify(reference),silex=qualify(rows),parity=compare(rows,reference),guards=self_test(raw,rows,reference),sha256=hashlib.sha256(raw.encode()).hexdigest(),jolt_sha256=hashlib.sha256(raw_j.encode()).hexdigest())
        (BUILD/f'{output_stem}-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(mode,'handling, wheelie and crash cutout qualified',flush=True)
    if args.mode=='both':
        for engine in ('jolt','silex'):
            if (BUILD/f'{output_stem}-{engine}-debug.txt').read_bytes()!=(BUILD/f'{output_stem}-{engine}-release.txt').read_bytes(): fail(f'{engine} handling Native Debug/Release differ')
        record['debug_release_identical']=True;(BUILD/f'{output_stem}-qualification.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__': main()
