#!/usr/bin/env python3
"""Qualify tracked platform ascent, unsupported flight and recovery."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from TrackedGroundRun import wheel, force, sub, PARITY
from TrackedVehicleRun import near, rejected
from VehicleTiresRun import add, cross, dot, norm, scale
from VehicleInclineRun import rotation_error
from MotorcycleReferenceRun import rotate

TOTAL=6
CASES=range(4)
RATES=(60,120)
KEYS={(k,r,t) for k in CASES for r in RATES for t in range(TOTAL*r+1)}


def f32(value):
    return struct.unpack('f',struct.pack('f',value))[0]


def parse(raw):
    rows={}
    for line in raw.splitlines():
        fields=line.split()
        if len(fields)!=131 or fields[0]!='tracked-platform':fail('invalid tracked-platform row')
        key=tuple(map(int,fields[1:4]));values=tuple(f32(float(x)) for x in fields[4:])
        if key not in KEYS or key in rows or not all(map(math.isfinite,values)):fail('invalid tracked-platform key/value')
        rows[key]=values
    if set(rows)!=KEYS:fail('incomplete tracked-platform witness')
    return rows


def velocity(case,step,rate):
    return (2.,0.,0.) if case==1 and 2*rate<=step<4*rate else (0.,0.,2.) if case in (2,3) and 2*rate<=step<4*rate else (0.,0.,0.)


def qualify(rows,engine):
    outcomes={};worst=dict(linear=0.,angular=0.,angle=0.,belt=0.,free_momentum=0.,carrier=0.)
    for case in CASES:
        for rate in RATES:
            initial=rows[case,rate,0];peak=0.;loads_final=[];moving=[];free_roll=[];minimum_supports=6
            for x,y in zip(initial[:18],(0,1.15,0,0,0,0,0,0,0,1,0,0,0,1000,0,1,0,0)):near(x,y,1e-5,'initial neutral chassis')
            carrier=(0.,-.2,0.)
            for t in range(TOTAL*rate+1):
                v=rows[case,rate,t];old=rows[case,rate,t-1] if t else v;vp=velocity(case,t-1,rate)
                if t:carrier=add(carrier,scale(vp,1/rate))
                worst['carrier']=max(worst['carrier'],near(norm(sub(v[114:117],carrier)),0.,1e-4,'prescribed platform integration'))
                near(norm(sub(v[117:120],vp)),0.,1e-4,'prescribed platform velocity')
                for x,y in zip(v[120:127],(0,0,0,1,0,0,0)):near(x,y,1e-5,'unrotated kinematic support')
                if not .3<v[1]<4 or norm(v[:3])>100 or norm(v[3:6])>25 or norm(v[10:13])>5:fail('unbounded platform chassis')
                near(dot(v[6:10],v[6:10]),1.,1e-4,'unit chassis rotation')
                if rotate(v[6:10],(0,1,0))[1]<.8:fail('platform vehicle overturned')
                near(v[13],1000.,.02,'idle neutral engine');near(v[14],0.,0.,'neutral gearbox');near(v[15],1.,1e-5,'engaged neutral clutch')
                loads=(0.,0.,0.);torque=(0.,0.,0.);contacts=0;longitudinal=0.
                for i in range(6):
                    w=wheel(v,i);side=i//3
                    if w[6] not in (0.,1.) or not 0<=w[0]<=.60001 or not 0<=w[1]<100000:fail('invalid platform wheel domain')
                    expected=old[16+side] if engine=='jolt' and t and not w[6] and case==3 else 0. if engine=='jolt' and t and not w[6] else v[16+side]
                    worst['belt']=max(worst['belt'],near(w[2],expected,1e-4,'common belt and wheel speed'))
                    if case!=3:near(v[16+side],0.,1e-4,'brakes lock the track')
                    if t:worst['angle']=max(worst['angle'],near(math.remainder(w[3]-wheel(old,i)[3]-old[16+side]/rate,2*math.pi),0.,1e-4,'wheel angle integral'))
                    if w[6]:
                        contacts+=1;near(norm(sub(w[10:13],(0,1,0))),0.,1e-4,'platform top normal')
                        near(norm(w[13:16]),1.,1e-4,'unit longitudinal');near(dot(w[10:13],w[13:16]),0.,1e-4,'orthogonal wheel frame')
                        anchor=add(old[:3],rotate(old[6:10],(-.6 if i<3 else .6,0,i%3-1)))
                        direction=rotate(old[6:10],(0,-1,0));ray=sub(w[7:10],anchor);distance=dot(ray,direction)
                        near(norm(sub(ray,scale(direction,distance))),0.,1e-4,'contact lies on ray')
                        if not 0<=distance<=.9001:fail('contact outside ray')
                        near(w[0],max(.2,distance-.3),1e-4,'suspension from geometry')
                        local=sub(w[7:10],old[114:117]);near(local[1],.2,2e-5,'finite platform top')
                        if abs(local[0])>4.0001 or abs(local[2])>6.0001:fail('support outside finite platform')
                        if abs(w[4])>w[1]+.003 or abs(w[5])>math.sqrt(.15)*w[1]+.003:fail('platform friction capacity exceeded')
                        value=force(w);loads=add(loads,value);torque=add(torque,cross(sub(w[7:10],old[:3]),value));longitudinal+=w[4]
                    elif any(abs(w[c])>.002 for c in (1,4,5,7,8,9,10,11,12,13,14,15)):fail('unsupported platform wheel effort')
                peak=max(peak,norm(v[3:6]))
                if t>rate:minimum_supports=min(minimum_supports,contacts)
                if t:
                    worst['linear']=max(worst['linear'],near(norm(sub(scale(sub(v[3:6],old[3:6]),100),scale(add(loads,(0,-981,0)),1/rate))),0.,.1,'linear impulse'))
                    worst['angular']=max(worst['angular'],near(norm(sub(scale(sub(v[10:13],old[10:13]),100),scale(torque,1/rate))),0.,.1,'angular impulse'))
                    if norm(sub(v[:3],old[:3]))>(norm(v[3:6])+norm(old[3:6]))/rate+.01:fail('chassis pose discontinuity')
                    if case==3:worst['free_momentum']=max(worst['free_momentum'],near(2*(sum(v[16:18])-sum(old[16:18]))+.3*longitudinal/rate,0.,.002,'free track momentum'))
                if 3*rate<=t<=int(3.75*rate):
                    speed=v[3] if case==1 else v[5];target=0. if case==0 else 2. if case!=3 else 8/13
                    near(speed,target,.03,'steady carried or freely rolling speed');moving.append(speed)
                    if case==3:free_roll.append(sum(v[16:18])/2)
                if t>(TOTAL-1)*rate:
                    if contacts!=6:fail('six final platform supports missing')
                    near(v[1],.88365,.003,'final suspension height');near(sum(wheel(v,i)[1] for i in range(6)),981.,2.,'final supported weight')
                    if norm(v[3:6])>.05 or norm(v[10:13])>.05:fail('platform vehicle failed to stop')
                    loads_final.append(sum(wheel(v,i)[1] for i in range(6)))
            end=rows[case,rate,TOTAL*rate]
            if case==0 and norm((end[0],end[2]))>.01:fail('stationary control moved')
            if case in (1,2) and (end[0] if case==1 else end[2])<3:fail('braked vehicle not carried')
            if case==3 and not .8<end[2]<1.7:fail('free rollers not distinguished from locked tracks')
            outcomes[f'{case}/{rate}']=dict(end_position=end[:3],platform_position=end[114:117],mean_moving_speed=sum(moving)/len(moving),mean_free_omega=sum(free_roll)/len(free_roll) if free_roll else None,peak_speed=peak,minimum_supports=minimum_supports,mean_final_load=sum(loads_final)/len(loads_final))
    return dict(worst=worst,outcomes=outcomes)


def compare(a,b):
    body=[0.]*4;force_error=torque_error=normal_error=angle_error=0.
    for key in KEYS:
        x,y=a[key],b[key]
        errors=norm(sub(x[:3],y[:3])),norm(sub(x[3:6],y[3:6])),rotation_error(x[6:10],y[6:10]),norm(sub(x[10:13],y[10:13]))
        for i,(error,limit) in enumerate(zip(errors,PARITY)):body[i]=max(body[i],near(error,0.,limit,f'chassis parity {key}/{i}'))
    for case in CASES:
        for rate in RATES:
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
    return dict(body=body,force_mean=force_error,torque_mean=torque_error,normal_mean=normal_error,rotation_increment=angle_error)


def self_test(raw,rows,engine):
    lines=raw.splitlines();rejected(lambda:parse('\n'.join(lines[1:])));rejected(lambda:parse(raw+lines[0]+'\n'))
    for index,value in ((0,'other'),(1,'4'),(2,'61'),(4,'nan'),(4,'inf')):
        fields=lines[0].split();fields[index]=value;rejected(lambda:parse(' '.join(fields)+'\n'+'\n'.join(lines[1:])))
    key=(1,60,3*60)
    for channel in range(127):
        altered=dict(rows);row=list(rows[key]);row[channel]+=100.;altered[key]=tuple(row);rejected(lambda:qualify(altered,engine))
    return 134


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from group root {GROUP}')
    source,digest=verified_source(args.archive)
    report=dict(schema=1,fixture='tracked-platform-v1',oracle_revision=REFERENCE,archive_sha256=digest,body_tolerances=PARITY,modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'TrackedPlatformOracle.cpp','tracked-platform-oracle');silex=build_silex(mode,'TrackedPlatform.sx','tracked-platform-silex',True)
        parsed={};evidence={}
        for engine,binary in (('jolt',oracle),('silex',silex)):
            raw=checked([str(binary)]);(BUILD/f'tracked-platform-{engine}-{mode.lower()}.txt').write_text(raw);rows=parse(raw)
            evidence[engine]=dict(states=len(rows),qualification=qualify(rows,engine),guards=self_test(raw,rows,engine),sha256=hashlib.sha256(raw.encode()).hexdigest());parsed[engine]=rows;print(mode,engine,'qualified',flush=True)
        evidence['parity']=compare(parsed['silex'],parsed['jolt']);report['modes'][mode]=evidence;(BUILD/'tracked-platform-qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(mode,'tracked platform parity green',flush=True)
    if args.mode=='both':
        for engine in ('jolt','silex'):
            if (BUILD/f'tracked-platform-{engine}-debug.txt').read_bytes()!=(BUILD/f'tracked-platform-{engine}-release.txt').read_bytes():fail(f'{engine} Debug/Release differ')
        report['debug_release_identical']=True;(BUILD/'tracked-platform-qualification.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
