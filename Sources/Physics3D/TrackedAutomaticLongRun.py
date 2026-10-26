#!/usr/bin/env python3
"""Qualify 20-second tracked driving with a documented 48/4 solver profile."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from TrackedBrakeOracle import build_tracked_oracle
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from TrackedGroundRun import wheel, force, sub, PARITY
from TrackedVehicleRun import near, rejected
from VehicleTiresRun import add, cross, dot, norm, scale
from VehicleInclineRun import rotation_error
from MotorcycleReferenceRun import rotate

TOTAL=20
CASES=range(4)
RATES=(60,120)
KEYS={(k,r,t) for k in CASES for r in RATES for t in range(TOTAL*r+1)}
EVENT_TIME=.05


def f32(value):
    return struct.unpack('f',struct.pack('f',value))[0]


def parse(raw):
    rows={}
    for line in raw.splitlines():
        fields=line.split()
        if len(fields)!=118 or fields[0]!='tracked-auto-long':fail('invalid tracked-auto-long row')
        key=tuple(map(int,fields[1:4]));values=tuple(f32(float(x)) for x in fields[4:])
        if key not in KEYS or key in rows or not all(map(math.isfinite,values)):fail('invalid tracked-auto-long key/value')
        rows[key]=values
    if set(rows)!=KEYS:fail('incomplete tracked-auto-long witness')
    return rows


def command(case,step,rate):
    gas=0.;brake=.04
    if 2*rate<=step<10*rate:gas= -.8 if case==1 else .8;brake=0.
    return gas,(-1.,1.) if case==2 else (1.,1.),brake


def ratio(gear):
    return math.copysign((2.,f32(1.4),1.)[abs(int(gear))-1],gear) if gear else 0.


def gearbox(old,row,case,step,rate,timers):
    gas,tracks,_=command(case,step,rate);gear=int(old[14]);clutch=old[15]
    switch,release,latency=timers;dt=f32(1/rate)
    rpm=old[13]
    if gear and clutch>.001:
        speed=(max if gear>0 else min)(f32(old[16]*6),f32(old[17]*6))
        rpm=max(1000.,min(6000.,f32(f32(speed*ratio(gear))*f32(60/f32(2*math.pi)))))
    near(row[13],rpm,.02,'engine speed from old tracks or disconnected engine')
    previous=gear;touching=any(wheel(row,i)[6] for i in range(6))
    if gear==0 or gas*gear<0:gear=1 if gas>0 else -1 if gas<0 else 0
    elif latency==0:
        if tracks[0]*tracks[1]>0 and touching and old[15]>.001 and row[13]>1800:
            if abs(gear)<3:gear+=1 if gear>0 else -1
        elif row[13]<1200:
            if abs(gear)>(1 if gas else 0):gear-=1 if gear>0 else -1
    if previous!=gear:switch=f32(.5) if previous else 0.;release=f32(.3);latency=f32(.5);clutch=0.
    elif switch>0:switch=max(0.,f32(switch-dt));clutch=0.
    elif release>0:release=max(0.,f32(release-dt));clutch=f32(1.-f32(release/f32(.3)))
    else:clutch=1.;latency=max(0.,f32(latency-dt))
    near(row[14],gear,0.,'automatic gear state');near(row[15],clutch,1e-5,'automatic clutch ramp and shift timers')
    return switch,release,latency


def free_speeds(old,row,case,step,rate):
    gas,ratios,brake=command(case,step,rate);speeds=list(old[16:18]);gear=ratio(row[14])
    torque=row[15]*gear*15*abs(gas)
    if torque:
        for i in (0,1):
            limit=row[13]/(gear*6*ratios[i]*60/(2*math.pi))*1.001
            if speeds[i]*limit<0 or abs(speeds[i])<abs(limit):speeds[i]+=6*ratios[i]*torque/rate/2
    if ratios[0]>0:speeds=[sum(speeds)/2]*2
    else:
        speed=(speeds[0]-speeds[1])/2;speeds=[speed,-speed]
    return [math.copysign(max(0.,abs(x)-brake*1500/rate/2),x) for x in speeds]


def qualify(rows,engine):
    outcomes={};worst=dict(linear=0.,angular=0.,angle=0.,belt=0.,drive=0.)
    for case in CASES:
        for rate in RATES:
            initial=rows[case,rate,0];timers=(0.,0.,0.);events=[];peak_rpm=1000.;peak_speed=0.;clutch_open=0
            for x,y in zip(initial[:18],(0,1.15,0,0,0,0,0,0,0,1,0,0,0,1000,0,1,0,0)):near(x,y,1e-5,'initial chassis and neutral gearbox')
            for t in range(TOTAL*rate+1):
                v=rows[case,rate,t];old=rows[case,rate,t-1] if t else v
                if not .3<v[1]<4 or norm(v[:3])>300 or norm(v[3:6])>25 or norm(v[10:13])>5:fail('unbounded automatic chassis')
                near(dot(v[6:10],v[6:10]),1.,1e-4,'unit chassis rotation')
                if v[14]!=int(v[14]) or not -3<=v[14]<=3 or not 0<=v[15]<=1 or not 1000<=v[13]<=6000:fail('invalid powertrain domain')
                if t:
                    timers=gearbox(old,v,case,t-1,rate,timers)
                    if v[14]!=old[14]:events.append((t,int(v[14])))
                peak_rpm=max(peak_rpm,v[13]);peak_speed=max(peak_speed,norm(v[3:6]));clutch_open+=int(t>=2*rate and v[15]==0)
                loads=(0.,0.,0.);torque=(0.,0.,0.);contacts=0;longitudinal=0.
                free=free_speeds(old,v,case,t-1,rate) if t else [0.,0.]
                for i in range(6):
                    w=wheel(v,i);side=i//3
                    if w[6] not in (0.,1.) or not 0<=w[0]<=.60001 or not 0<=w[1]<100000:fail('invalid wheel domain')
                    expected=free[side] if engine=='jolt' and t and not w[6] else v[16+side]
                    worst['belt']=max(worst['belt'],near(w[2],expected,1e-4,'published angular speed'))
                    if t:worst['angle']=max(worst['angle'],near(math.remainder(w[3]-wheel(old,i)[3]-old[16+side]/rate,2*math.pi),0.,1e-4,'wheel rotation integral'))
                    if w[6]:
                        contacts+=1;near(norm(sub(w[10:13],(0,1,0))),0.,1e-4,'plane normal')
                        near(norm(w[13:16]),1.,1e-4,'unit longitudinal');near(dot(w[10:13],w[13:16]),0.,1e-4,'orthogonal frame')
                        anchor=add(old[:3],rotate(old[6:10],(-.6 if i<3 else .6,0,i%3-1)))
                        direction=rotate(old[6:10],(0,-1,0));ray=sub(w[7:10],anchor);distance=dot(ray,direction)
                        near(norm(sub(ray,scale(direction,distance))),0.,1e-4,'support on wheel ray')
                        if not 0<=distance<=.9001:fail('support outside ray')
                        near(w[0],max(.2,distance-.3),1e-4,'suspension geometry');near(w[8],0.,2e-5,'plane height')
                        friction=0. if case==2 else 1.;lateral=0. if case==2 else math.sqrt(.15)
                        if abs(w[4])>friction*w[1]+.003 or abs(w[5])>lateral*w[1]+.003:fail('friction capacity exceeded')
                        value=force(w);loads=add(loads,value);torque=add(torque,cross(sub(w[7:10],old[:3]),value));longitudinal+=w[4]
                    elif any(abs(w[c])>.002 for c in (1,4,5,7,8,9,10,11,12,13,14,15)):fail('unsupported effort/geometry')
                if t:
                    gravity=(0,0,0) if case==3 else (0,-981,0)
                    worst['linear']=max(worst['linear'],near(norm(sub(scale(sub(v[3:6],old[3:6]),100),scale(add(loads,gravity),1/rate))),0.,.1,'linear impulse'))
                    worst['angular']=max(worst['angular'],near(norm(sub(scale(sub(v[10:13],old[10:13]),100),scale(torque,1/rate))),0.,.1,'angular impulse'))
                    if norm(sub(v[:3],old[:3]))>(norm(v[3:6])+norm(old[3:6]))/rate+.01:fail('position discontinuity')
                    if not contacts:
                        near(norm(sub(sub(v[:3],old[:3]),scale(v[3:6],1/rate))),0.,1e-4,'unsupported position integration')
                        for i in (0,1):near(v[16+i],free[i],1e-4,'unsupported track response')
                    if command(case,t-1,rate)[2]==0 and case!=2:
                        worst['drive']=max(worst['drive'],near(2*(sum(v[16:18])-sum(free))+.3*longitudinal/rate,0.,.002,'driving track momentum'))
                if case==3:
                    if contacts:fail('air control unexpectedly supported')
                    near(norm(sub(v[:13],initial[:13])),0.,1e-5,'air body fixed without gravity')
                elif t>(TOTAL-1)*rate:
                    if contacts!=6:fail('six recovered supports missing')
                    near(v[1],.88365,.003,'final height');near(sum(wheel(v,i)[1] for i in range(6)),981.,2.,'final load')
                    if norm(v[3:6])>.05 or norm(v[10:13])>.05:fail('automatic vehicle did not stop')
            sequence=[gear for _,gear in events]
            if case<2:
                for tick in range(TOTAL*rate+1):
                    row=rows[case,rate,tick]
                    near(row[0],0.,.005,'absolute lateral straightness')
                    near(2*math.atan2(row[7],row[9]),0.,.0001,'absolute heading straightness')
                sign=1 if case==0 else -1
                if sequence!=[sign,2*sign,3*sign,2*sign,sign,0] or peak_speed<8:fail(f'missing launch/upshift/downshift/neutral: {case}/{rate} {events}')
                if rows[case,rate,TOTAL*rate][2]*sign<20:fail('automatic displacement missing')
            elif sequence!=[1,0] or peak_rpm<1800:fail(f'upshift inhibition not demonstrated: {case}/{rate} {events} {peak_rpm}')
            if clutch_open<rate/2:fail('shift torque interruption missing')
            outcomes[f'{case}/{rate}']=dict(events=events,peak_rpm=peak_rpm,peak_speed=peak_speed,clutch_open_steps=clutch_open,end_position=rows[case,rate,TOTAL*rate][:3])
    return dict(worst=worst,outcomes=outcomes)


def compare(a,b):
    body=[0.]*4;force_error=torque_error=normal_error=angle_error=event_error=0.
    for key in KEYS:
        x,y=a[key],b[key]
        errors=norm(sub(x[:3],y[:3])),norm(sub(x[3:6],y[3:6])),rotation_error(x[6:10],y[6:10]),norm(sub(x[10:13],y[10:13]))
        for i,(error,limit) in enumerate(zip(errors,PARITY)):body[i]=max(body[i],near(error,0.,limit,f'chassis parity {key}/{i}'))
    for case in CASES:
        for rate in RATES:
            events=[]
            for rows in (a,b):events.append([(t,int(rows[case,rate,t][14])) for t in range(1,TOTAL*rate+1) if rows[case,rate,t][14]!=rows[case,rate,t-1][14]])
            if [g for _,g in events[0]]!=[g for _,g in events[1]]:fail('different shift sequence')
            for (x,_),(y,_) in zip(*events):event_error=max(event_error,near((x-y)/rate,0.,EVENT_TIME,'shift event timing'))
            for phase in range(TOTAL):
                sums=[]
                for rows in (a,b):
                    f=(0,0,0);torque=(0,0,0);normal=[0.]*6;angles=[0.]*6
                    for t in range(phase*rate+1,(phase+1)*rate+1):
                        row,old=rows[case,rate,t],rows[case,rate,t-1]
                        for i in range(6):
                            w=wheel(row,i);value=force(w);f=add(f,scale(value,1/rate));torque=add(torque,scale(cross(sub(w[7:10],old[:3]),value),1/rate));normal[i]+=w[1]/rate;angles[i]+=math.remainder(w[3]-wheel(old,i)[3],2*math.pi)
                    sums.append((f,torque,normal,angles))
                x,y=sums
                force_error=max(force_error,near(norm(sub(x[0],y[0])),0.,20.,'window force'))
                torque_error=max(torque_error,near(norm(sub(x[1],y[1])),0.,30.,'window torque'))
                for i in range(6):
                    normal_error=max(normal_error,near(x[2][i]-y[2][i],0.,20.,'window normal'))
                    angle_error=max(angle_error,near(x[3][i]-y[3][i],0.,.1,'window rotation'))
    return dict(body=body,shift_time=event_error,force_mean=force_error,torque_mean=torque_error,normal_mean=normal_error,rotation_increment=angle_error)


def self_test(raw,rows,engine):
    lines=raw.splitlines();rejected(lambda:parse('\n'.join(lines[1:])));rejected(lambda:parse(raw+lines[0]+'\n'))
    for index,value in ((0,'other'),(1,'4'),(2,'61'),(4,'nan'),(4,'inf')):
        fields=lines[0].split();fields[index]=value;rejected(lambda:parse(' '.join(fields)+'\n'+'\n'.join(lines[1:])))
    for channel in range(114):
        altered=dict(rows);key=(0,120,800);row=list(rows[key]);row[channel]+=100.;altered[key]=tuple(row)
        rejected(lambda:qualify(altered,engine))
    return 121


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from group root {GROUP}')
    source,digest=verified_source(args.archive)
    report=dict(schema=1,fixture='tracked-automatic-long-ground-v1',oracle_revision=REFERENCE,archive_sha256=digest,solver={'velocity_iterations':48,'position_iterations':4,'substeps':1},default_profile_qualified=False,body_tolerances=PARITY,shift_time_tolerance=EVENT_TIME,modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle,provenance=build_tracked_oracle(source,mode,HERE/'TrackedAutomaticLongOracle.cpp','tracked-automatic-long-oracle',stable=True);silex=build_silex(mode,'TrackedAutomaticLong.sx','tracked-automatic-long-silex',True)
        parsed={};evidence={'oracle':provenance}
        for engine,binary in (('jolt',oracle),('silex',silex)):
            raw=checked([str(binary)]);(BUILD/f'tracked-automatic-long-{engine}-{mode.lower()}.txt').write_text(raw);rows=parse(raw)
            evidence[engine]=dict(states=len(rows),qualification=qualify(rows,engine),guards=self_test(raw,rows,engine),sha256=hashlib.sha256(raw.encode()).hexdigest());parsed[engine]=rows;print(mode,engine,'qualified',flush=True)
        evidence['parity']=compare(parsed['silex'],parsed['jolt']);report['modes'][mode]=evidence;(BUILD/'tracked-automatic-long-qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(mode,'automatic tracked parity green',flush=True)
    if args.mode=='both':
        for engine in ('jolt','silex'):
            if (BUILD/f'tracked-automatic-long-{engine}-debug.txt').read_bytes()!=(BUILD/f'tracked-automatic-long-{engine}-release.txt').read_bytes():fail(f'{engine} Debug/Release differ')
        report['debug_release_identical']=True;(BUILD/'tracked-automatic-long-qualification.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
