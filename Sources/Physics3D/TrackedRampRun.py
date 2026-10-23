#!/usr/bin/env python3
"""Qualify six-wheel tracks climbing a finite ramp, flying and recovering support."""
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

TOTAL=14
KEYS={(k,r,t) for k in (0,1) for r in (60,120) for t in range(TOTAL*r+1)}
NORMAL=(0.,math.cos(.1),-math.sin(.1))


def parse(raw):
    rows={}
    for line in raw.splitlines():
        f=line.split()
        if len(f)!=118 or f[0]!='tracked-ramp':fail('invalid tracked-ramp row')
        key=tuple(map(int,f[1:4]));v=tuple(struct.unpack('f',struct.pack('f',float(x)))[0] for x in f[4:])
        if key not in KEYS or key in rows or not all(map(math.isfinite,v)):fail('invalid tracked-ramp key/value')
        rows[key]=v
    if set(rows)!=KEYS:fail('incomplete tracked-ramp witness')
    return rows


def free_speeds(old,step,rate):
    speeds=list(old[16:18]);rpm=max(1000.,min(6000.,max(speeds)*6*60/(2*math.pi)))
    driving=2*rate<=step<7*rate
    if driving:
        for i in (0,1):
            limit=rpm/(6*60/(2*math.pi))*1.001
            if speeds[i]*limit<0 or abs(speeds[i])<abs(limit):speeds[i]+=6*15*.8/rate/2
    speeds=[sum(speeds)/2]*2
    if not driving:speeds=[math.copysign(max(0.,abs(x)-60/rate/2),x) for x in speeds]
    return speeds


def qualify(rows,engine,cases=(0,1),rates=(60,120)):
    worst=dict(linear_impulse=0.,angular_impulse=0.,rotation_step=0.,belt=0.,position_step=0.,rpm=0.,drive_balance=0.)
    outcomes={}
    for k in cases:
        for rate in rates:
            ramp_samples=0;flight=[];landing=None;peak=0.;peak_pitch=0.
            initial=rows[k,rate,0]
            near(norm(sub(initial[:3],(0.,1.15,0.))),0.,1e-5,'initial chassis')
            for c in list(range(3,9))+list(range(10,13))+[16,17]:near(initial[c],0.,1e-5,'initial body/track')
            near(initial[9],1.,1e-5,'initial rotation')
            for t in range(TOTAL*rate+1):
                v=rows[k,rate,t];old=rows[k,rate,t-1] if t else v
                if norm(v[:3])>100 or not .3<v[1]<4 or norm(v[3:6])>20 or norm(v[10:13])>5:fail('unbounded tracked ramp chassis')
                near(dot(v[6:10],v[6:10]),1.,1e-4,'unit tracked rotation')
                if not 1000<=v[13]<=6000 or v[14]!=1 or v[15]!=1:fail('tracked manual powertrain changed')
                peak=max(peak,v[1]);peak_pitch=max(peak_pitch,abs(math.asin(max(-1.,min(1.,rotate(v[6:10],(0,0,1))[1])))))
                loads=(0.,0.,0.);torque=(0.,0.,0.);contacts=0;longitudinal=0.
                for i in range(6):
                    w=wheel(v,i);side=i//3
                    if w[6] not in (0.,1.) or not 0<=w[0]<=.60001 or not 0<=w[1]<100000:fail('invalid tracked ramp wheel')
                    expected=v[16+side]
                    if engine=='jolt' and t and not w[6]:expected=free_speeds(old,t-1,rate)[side]
                    worst['belt']=max(worst['belt'],near(w[2],expected,1e-4,'track angular observation boundary'))
                    if t:worst['rotation_step']=max(worst['rotation_step'],near(math.remainder(w[3]-wheel(old,i)[3]-old[16+side]/rate,2*math.pi),0.,1e-4,'wheel rotation step'))
                    if w[6]:
                        contacts+=1
                        near(norm(w[10:13]),1.,1e-4,'unit normal');near(norm(w[13:16]),1.,1e-4,'unit tangent');near(dot(w[10:13],w[13:16]),0.,1e-4,'orthogonal contact frame')
                        anchor=add(old[:3],rotate(old[6:10],(-.6 if i<3 else .6,0,i%3-1)))
                        direction=rotate(old[6:10],(0,-1,0));ray=sub(w[7:10],anchor);distance=dot(ray,direction)
                        near(norm(sub(ray,scale(direction,distance))),0.,1e-4,'contact belongs to suspension ray')
                        if not 0<=distance<=.9001:fail('support outside suspension ray range')
                        near(w[0],max(.2,distance-.3),1e-4,'ray suspension length')
                        if norm(sub(w[10:13],(0,1,0)))<1e-4:near(w[8],0.,2e-5,'ground geometry')
                        else:
                            if k!=1:fail('unexpected inclined support')
                            near(norm(sub(w[10:13],NORMAL)),0.,1e-4,'ramp normal')
                            local=rotate((math.sin(.05),0,0,math.cos(.05)),sub(w[7:10],(0,.1,15)))
                            near(local[1],.2,2e-5,'finite ramp top')
                            if abs(local[0])>4.0001 or abs(local[2])>3.0151:fail('contact outside finite ramp')
                            ramp_samples+=1
                        if abs(w[4])>w[1]+.003 or abs(w[5])>math.sqrt(.15)*w[1]+.003:fail('friction capacity exceeded')
                        value=force(w);loads=add(loads,value);torque=add(torque,cross(sub(w[7:10],old[:3]),value));longitudinal+=w[4]
                    elif any(abs(w[c])>.002 for c in (1,4,5,7,8,9,10,11,12,13,14,15)):fail('unsupported wheel has contact effort or geometry')
                if t>2*rate and contacts==0:flight.append(t)
                if flight and t>flight[-1] and contacts>0 and landing is None:landing=t
                if t:
                    worst['linear_impulse']=max(worst['linear_impulse'],near(norm(sub(scale(sub(v[3:6],old[3:6]),100),scale(add(loads,(0,-981,0)),1/rate))),0.,.1,'linear momentum'))
                    worst['angular_impulse']=max(worst['angular_impulse'],near(norm(sub(scale(sub(v[10:13],old[10:13]),100),scale(torque,1/rate))),0.,.1,'angular momentum'))
                    if contacts==0:
                        worst['position_step']=max(worst['position_step'],near(norm(sub(sub(v[:3],old[:3]),scale(v[3:6],1/rate))),0.,1e-4,'ballistic position integration'))
                    if norm(sub(v[:3],old[:3]))>(norm(v[3:6])+norm(old[3:6]))/rate+.01:fail('unphysical tracked position jump')
                    rpm=max(1000.,min(6000.,max(old[16:18])*6*60/(2*math.pi)))
                    worst['rpm']=max(worst['rpm'],near(v[13],rpm,.02,'connected engine rpm'))
                    if 2*rate<=t-1<7*rate:
                        pre=free_speeds(old,t-1,rate)
                        worst['drive_balance']=max(worst['drive_balance'],near(2*(sum(v[16:18])-sum(pre))+.3*longitudinal/rate,0.,.002,'track angular momentum sum'))
                if t>13*rate:
                    if contacts!=6:fail('missing recovered track support')
                    near(v[1],.88365,.003,'recovered height');near(sum(wheel(v,i)[1] for i in range(6)),981.,2.,'recovered load')
                    if norm(v[3:6])>.05 or norm(v[10:13])>.05:fail('tracked ramp did not settle')
            if k==1 and (ramp_samples<rate or len(flight)<rate/20 or landing is None or peak<1.1 or rows[k,rate,TOTAL*rate][2]<20):fail('ramp ascent, unsupported flight or landing missing')
            if k==0 and (ramp_samples or flight):fail('flat control is not grounded')
            outcomes[f'{k}/{rate}']=dict(ramp_samples=ramp_samples,air_steps=len(flight),first_air=flight[0] if flight else None,landing=landing,peak_height=peak,peak_pitch=peak_pitch,end_position=rows[k,rate,TOTAL*rate][:3])
    return dict(worst=worst,outcomes=outcomes)


def compare(first,second):
    maxima=[0.]*4;force_error=torque_error=normal_error=angle_error=0.
    for key in KEYS:
        a,b=first[key],second[key]
        errors=norm(sub(a[:3],b[:3])),norm(sub(a[3:6],b[3:6])),rotation_error(a[6:10],b[6:10]),norm(sub(a[10:13],b[10:13]))
        for i,(error,limit) in enumerate(zip(errors,PARITY)):maxima[i]=max(maxima[i],near(error,0.,limit,f'body parity {key} {i}'))
    for k in (0,1):
        for rate in (60,120):
            for phase in range(TOTAL):
                sums=[]
                for rows in (first,second):
                    f=(0,0,0);torque=(0,0,0);normal=[0.]*6;angles=[0.]*6
                    for t in range(phase*rate+1,(phase+1)*rate+1):
                        row,old=rows[k,rate,t],rows[k,rate,t-1]
                        for i in range(6):
                            w=wheel(row,i);value=force(w);f=add(f,scale(value,1/rate));torque=add(torque,scale(cross(sub(w[7:10],old[:3]),value),1/rate))
                            normal[i]+=w[1]/rate;angles[i]+=math.remainder(w[3]-wheel(old,i)[3],2*math.pi)
                    sums.append((f,torque,normal,angles))
                a,b=sums
                force_error=max(force_error,near(norm(sub(a[0],b[0])),0.,20.,'window resultant force'))
                torque_error=max(torque_error,near(norm(sub(a[1],b[1])),0.,30.,'window resultant torque'))
                for i in range(6):
                    normal_error=max(normal_error,near(a[2][i]-b[2][i],0.,20.,'window normal load'))
                    angle_error=max(angle_error,near(a[3][i]-b[3][i],0.,.1,'window wheel rotation'))
    return dict(body=maxima,force_mean=force_error,torque_mean=torque_error,normal_mean=normal_error,rotation_increment=angle_error)


def self_test(raw,rows,engine):
    lines=raw.splitlines();rejected(lambda:parse('\n'.join(lines[1:])));rejected(lambda:parse(raw+lines[0]+'\n'))
    for index,value in ((0,'other'),(1,'2'),(2,'61'),(4,'nan'),(4,'inf')):
        fields=lines[0].split();fields[index]=value;rejected(lambda:parse(' '.join(fields)+'\n'+'\n'.join(lines[1:])))
    for index in range(114):
        altered=dict(rows);v=list(rows[1,120,720]);v[index]+=100.;altered[1,120,720]=tuple(v)
        try:qualify(altered,engine,cases=(1,),rates=(120,))
        except (ValueError,OverflowError):continue
        fail(f'corrupt tracked ramp channel {index} accepted')
    return 121


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path);p.add_argument('--mode',choices=('Debug','Release','both'),default='both');args=p.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    report=dict(schema=1,fixture='tracked-finite-ramp-v1',oracle_revision=REFERENCE,archive_sha256=digest,body_parity=PARITY,window_limits=dict(force=20,torque=30,normal=20,rotation=.1),scope='Six ray-contact wheels, two ideal tracks, historical 100kg/I100 15Nm manual powertrain and suspension; flat control and box 8x.4x6.03 at(0,.1,15), rotationX=-.1rad, 2s settle/5s drive/7s brake at4%, 60/120Hz,12/4 iterations,one worker. No articulated links, volumetric track contact, automatic ground gearbox or general terrain claim.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'TrackedRampOracle.cpp','tracked-ramp-oracle');silex=build_silex(mode,'TrackedRamp.sx','tracked-ramp-silex',True)
        parsed={};evidence={}
        for engine,binary in (('jolt',oracle),('silex',silex)):
            raw=checked([str(binary)]);(BUILD/f'tracked-ramp-{engine}-{mode.lower()}.txt').write_text(raw);rows=parse(raw)
            proof=qualify(rows,engine);parsed[engine]=rows;evidence[engine]=dict(states=len(rows),qualification=proof,guards=self_test(raw,rows,engine),sha256=hashlib.sha256(raw.encode()).hexdigest());print(mode,engine,'qualified',flush=True)
        evidence['parity']=compare(parsed['silex'],parsed['jolt']);report['modes'][mode]=evidence
        (BUILD/'tracked-ramp-qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(mode,'tracked finite ramp parity green',flush=True)
    if args.mode=='both':
        for engine in ('jolt','silex'):
            if (BUILD/f'tracked-ramp-{engine}-debug.txt').read_bytes()!=(BUILD/f'tracked-ramp-{engine}-release.txt').read_bytes():fail(f'{engine} Debug/Release differ')
        report['debug_release_identical']=True;(BUILD/'tracked-ramp-qualification.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
