#!/usr/bin/env python3
"""Qualify continuous driving, material transitions and variable tire curves."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_silex, checked, fail, verified_source
from VehicleDriveCompositionOracle import build_composed_oracle
from VehicleTerrainsRun import inverse_rotate
from VehicleTiresRun import add, cross, dot, norm, scale
from VehicleInclineRun import rotation_error, sub
from LoadedSwingTwistRun import rotate
from TrackedVehicleRun import rejected

CURVES={(f,d,s,r) for f in range(3) for d in range(3) for s in (-1,1) for r in (60,120)}
KEYS={(*c,k) for c in CURVES for k in range(12*c[3]+1)}
def count(family):return 2 if family==2 else 4
WKEYS={(*key,i) for key in KEYS for i in range(count(key[0]))}
BUDGETS=(.05,.1,.02,.15)


def phase(step,rate):
    for index,end in enumerate((1.5,3.5,4.5,5.5,8,10)):
        if step<end*rate:return index
    return 6


def parse(raw):
    bodies={};wheels={}
    for line in raw.splitlines():
        fields=line.split()
        if len(fields)==30 and fields[0]=='drive-body':
            key=tuple(map(int,fields[1:6]));values=tuple(map(float,fields[6:]));target=bodies;expected=KEYS
        elif len(fields)==26 and fields[0]=='drive-wheel':
            key=tuple(map(int,fields[1:7]));values=tuple(map(float,fields[7:]));target=wheels;expected=WKEYS
        else:fail('invalid driving schema')
        if key not in expected or key in target or not all(map(math.isfinite,values)):fail('invalid driving key or number')
        target[key]=values
    if set(bodies)!=KEYS or set(wheels)!=WKEYS:fail('incomplete driving witness')
    return bodies,wheels


def interpolation(points,value):
    for (x,y),(xx,yy) in zip(points,points[1:]):
        if value<xx:return y+(yy-y)*max(0.,(value-x)/(xx-x))
    return points[-1][1]


def force(wheel):
    return add(scale(wheel[13:16],wheel[1]),add(scale(wheel[16:19],wheel[6]),scale(cross(wheel[16:19],wheel[13:16]),wheel[7])))


def resultant(data,key):
    b,w=data;old=b[*key[:4],max(0,key[4]-1)];total=(0.,0.,0.);moment=total
    for i in range(count(key[0])):
        wheel=w[*key,i];f=force(wheel);total=add(total,f);moment=add(moment,cross(sub(wheel[10:13],old[:3]),f))
    return total,moment


def qualify(data,curves=CURVES,*,reference=False,allow_profile_limits=False):
    bodies,wheels=data
    worst={name:0. for name in ('linear_impulse','angular_impulse','wheel_angle','surface','wheel_boundary','unqualified_reference_boundary','capacity','band_speed','zero_grip_speed','position_step','unqualified_wide_cylinder_motorcycle_stop')}
    for curve in sorted(curves):
        family,detector,sign,rate=curve;n=count(family)
        for step in range(12*rate+1):
            key=(*curve,step);b=bodies[key];old=bodies[*curve,max(0,step-1)];previous=max(0,step-1);command=phase(previous,rate)
            if not .4<b[1]<2 or norm(b[3:6])>=15 or norm(b[10:13])>=8:fail(f'driving chassis bounds {key}')
            if abs(dot(b[6:10],b[6:10])-1)>1e-4:fail('driving quaternion not unit')
            grip=0. if 4.5*rate<=previous<5*rate else 1.
            clutch=1. if command in (1,2,3,5) else 0.
            torque=(15 if family==1 else 20)*(.6 if command==1 else .5 if command in (2,3) else .45 if command==5 else 0.)
            if step==0:torque=0.
            expected=(float(-1 if command>=5 else 1),clutch,torque,grip,float(command))
            if any(abs(x-y)>1e-5 for x,y in zip(b[14:19],expected)):fail(f'driving command/material state {key}: {b[14:19]} != {expected}')
            if not (999.99 if family==1 else 0)<=b[13]<=6000.01:fail('driving engine speed domain')
            if step and family==2 and abs(norm(b[19:22])-1)>1e-4:fail('motorcycle target is not unit')
            if family!=2 and norm(b[19:22])!=0:fail('nonmotorcycle lean target')
            if family!=1 and norm(b[22:24])!=0:fail('nontracked band state')
            for i in range(n):
                w=wheels[*key,i];length,load,omega,angle,long_slip,lat_slip,fx,fy,hit,steer=w[:10]
                if not 0<=length<=.60001 or load<0 or hit not in (0.,1.) or long_slip<0 or not 0<=lat_slip<=math.pi/2+.00001 or abs(steer)>(.60001 if family==2 else .50001):fail(f'driving wheel state {key}/{i}')
                if step:
                    before=wheels[*curve,step-1,i]
                    old_speed=old[22+i//2] if family==1 else before[2]
                    error=abs(math.remainder(angle-before[3]-old_speed/rate,2*math.pi));worst['wheel_angle']=max(worst['wheel_angle'],error)
                    if error>1e-4:fail(f'driving wheel angle before torque {key}/{i}: {error}')
                if step:
                    steering_input=.25*sign if command==2 else -.25*sign if command==3 else 0.
                    maximum=.6 if family==2 and i==0 else .5 if family==0 and i%2==1 else 0.
                    expected_steer=-steering_input*maximum
                    if family==2:
                        speed=dot(old[3:6],rotate(old[6:10],(0,0,1)))
                        if speed*speed>1e-6:
                            limit=math.asin(min(1.,2*9.81/(speed*speed)))
                            expected_steer=math.copysign(min(abs(expected_steer),limit),expected_steer)
                    if abs(steer-expected_steer)>3e-6:fail('driving steering command')
                if not hit:
                    if load!=0 or fx!=0 or fy!=0 or norm(w[10:])!=0:fail('unsupported driving wheel response')
                    continue
                point=w[10:13];normal=w[13:16];forward=w[16:19]
                if abs(norm(normal)-1)>1e-4 or abs(norm(forward)-1)>1e-4 or abs(dot(normal,forward))>1e-4:fail('driving contact basis')
                surface=abs(point[1]);worst['surface']=max(worst['surface'],surface)
                if surface>.003:fail(f'driving point off support {key}/{i}: {surface}')
                if (not reference or detector!=2) and norm(sub(normal,(0,1,0)))>.003:fail('driving plane normal')
                anchor=(0.,0.,1. if i==0 else -1.) if family==2 else (-.6 if i<2 else .6,0.,-1. if i%2==0 else 1.)
                center=add(old[:3],rotate(old[6:10],add(anchor,(0.,-length,0.))))
                offset=sub(point,center)
                if detector==2:
                    axle=rotate(old[6:10],(-math.cos(steer),0.,math.sin(steer)));axial=dot(offset,axle);radial=norm(sub(offset,scale(axle,axial)))
                    boundary=max(abs(axial)-.2,radial-.3,min(abs(abs(axial)-.2),abs(radial-.3)))
                else:boundary=abs(norm(offset)-.3)
                channel='unqualified_reference_boundary' if reference and detector==2 else 'wheel_boundary';worst[channel]=max(worst[channel],boundary)
                if boundary>.003 and channel=='wheel_boundary':fail(f'driving wheel boundary {key}/{i}: {boundary}')
                ml=1. if family==1 else interpolation(((0,0),(.06,1.2),(.2,1)),long_slip)
                mt=.15 if family==1 else interpolation(((0,0),(math.radians(3),1.2),(math.radians(20),1)),lat_slip)
                excess=max(abs(fx)-math.sqrt(ml*grip)*load,abs(fy)-math.sqrt(mt*grip)*load,0.)
                worst['capacity']=max(worst['capacity'],excess)
                if excess>.05:fail(f'driving tire capacity {key}/{i}: {excess}')
                if family==1:
                    error=abs(omega-b[22+i//2]);worst['band_speed']=max(worst['band_speed'],error)
                    if error>1e-4:fail('driving track and wheel speed differ')
            if not step:continue
            position_error=norm(sub(sub(b[:3],old[:3]),scale(b[3:6],1/rate)))
            worst['position_step']=max(worst['position_step'],position_error)
            if position_error>3e-5:fail('driving semi-implicit position step')
            if clutch==0. and abs(b[13]-old[13])>.001:fail('disconnected unpowered engine RPM changed')
            total,moment=resultant(data,key)
            compensation=(0.,0.,0.)
            if family==2:
                actuator=sub(scale(sub(b[10:13],old[10:13]),100),scale(moment,1/rate))
                load=sum(wheels[*key,i][1] for i in range(n))
                if load>0:
                    arm=(0.,0.,0.)
                    for i in range(n):arm=add(arm,scale(sub(wheels[*key,i][10:13],old[:3]),wheels[*key,i][1]))
                    compensation=scale(cross(scale(actuator,.01),arm),-100/load)
            linear=norm(sub(sub(scale(sub(b[3:6],old[3:6]),100),compensation),scale(add(total,(0.,-981.,0.)),1/rate)))
            worst['linear_impulse']=max(worst['linear_impulse'],linear)
            if linear>.1:fail(f'driving linear impulse {key}: {linear}')
            if family!=2:
                angular=norm(sub(scale(sub(b[10:13],old[10:13]),100),scale(moment,1/rate)));worst['angular_impulse']=max(worst['angular_impulse'],angular)
                if angular>.1:fail(f'driving angular impulse {key}: {angular}')
            if grip==0:
                error=math.hypot(b[3]-old[3]-compensation[0]/100,b[5]-old[5]-compensation[2]/100);worst['zero_grip_speed']=max(worst['zero_grip_speed'],error)
                if error>1e-5:fail('zero grip changes horizontal chassis velocity')
        forward=bodies[*curve,7*rate//2];reverse=bodies[*curve,10*rate]
        if dot(forward[3:6],rotate(forward[6:10],(0,0,1)))<.5:fail('forward driving missing')
        if dot(reverse[3:6],rotate(reverse[6:10],(0,0,1)))>-.1:fail('reverse driving missing')
        if max(abs(bodies[*curve,k][0]) for k in range(7*rate//2,11*rate//2+1))<.001:fail('lateral driving missing')
        for k in (8*rate,12*rate):
            speed=norm(bodies[*curve,k][3:6])
            if family==2 and detector==2 and allow_profile_limits:
                worst['unqualified_wide_cylinder_motorcycle_stop']=max(worst['unqualified_wide_cylinder_motorcycle_stop'],speed)
            elif speed>.05:fail(f'driving stop missing {curve}/{k}: {speed}')
        before=sum(abs(wheels[*curve,k,i][6])+abs(wheels[*curve,k,i][7]) for k in range(4*rate,9*rate//2) for i in range(n))
        after=sum(abs(wheels[*curve,k,i][6])+abs(wheels[*curve,k,i][7]) for k in range(5*rate+1,11*rate//2) for i in range(n))
        if min(before,after)<1:fail('grip transition has no tangible driving forces')
    return worst


def mirror(data):
    b,w=data;bb={};ww={}
    for key,value in b.items():
        f,d,s,r,k=key;v=list(b[f,d,-s,r,k])
        for channel in (0,3,7,8,11,12,19):v[channel]*=-1
        if f==1:v[22],v[23]=v[23],v[22]
        bb[key]=tuple(v)
    for key,value in w.items():
        f,d,s,r,k,i=key;j=i if f==2 else (i+2)%4;v=list(w[f,d,-s,r,k,j])
        for channel in (7,9,10,13,16):v[channel]*=-1
        ww[key]=tuple(v)
    return bb,ww


def compare(first,second,*,allow_reference_limits=False):
    a,wa=first;b,wb=second
    report={'qualified':{},'unqualified':{},'budget_exceedances':{},'scope':'Strict default; explicit limits only for composed cylinder responses and absolute disconnected-engine RPM'}
    def observe(channel,error,budget,key,unqualified=False):
        limited=budget is None or (allow_reference_limits and unqualified)
        target=report['unqualified' if limited else 'qualified']
        if error>target.get(channel,{}).get('maximum',-1):target[channel]={'maximum':error,'key':key,'budget':budget}
        if budget is not None and error>budget:
            if not limited:fail(f'driving {channel} parity {key}: {error}')
            report['budget_exceedances'][channel]=report['budget_exceedances'].get(channel,0)+1
    for key in sorted(KEYS):
        x=a[key];y=b[key];errors=(norm(sub(x[:3],y[:3])),norm(sub(x[3:6],y[3:6])),rotation_error(x[6:10],y[6:10]),norm(sub(x[10:13],y[10:13])))
        for i,(channel,error,budget) in enumerate(zip(('position','velocity','rotation','angular'),errors,BUDGETS)):
            if i==3 and key[1]==2:
                observe('cylinder_instantaneous_angular',error,None,key,True)
            else:observe(channel,error,budget,key,key[1]==2)
    for curve in sorted(CURVES):
        rate=curve[3];cylinder=curve[1]==2
        forces_a={k:resultant(first,(*curve,k)) for k in range(1,12*rate+1)}
        forces_b={k:resultant(second,(*curve,k)) for k in range(1,12*rate+1)}
        if cylinder:
            for quarter in range(48):
                steps=range(quarter*rate//4+1,(quarter+1)*rate//4+1)
                error=norm(tuple(sum(a[*curve,k][c]-b[*curve,k][c] for k in steps)/len(steps) for c in range(10,13)))
                observe('cylinder_mean_angular',error,.05,(*curve,quarter),True)
        for half in range(24):
            steps=range(half*rate//2+1,(half+1)*rate//2+1);n=len(steps)
            for index,(name,budget) in enumerate((('force_mean',20.),('moment_mean',30.))):
                error=norm(tuple(sum(forces_a[k][index][c]-forces_b[k][index][c] for k in steps)/n for c in range(3)))
                observe(name,error,budget,(*curve,half),cylinder)
            for i in range(2 if curve[0]==1 else count(curve[0])):
                # Compare both engines at the band boundary. A Jolt wheel that
                # lost contact can retain an earlier angular-velocity snapshot.
                error=abs(sum((a[*curve,k][22+i]-b[*curve,k][22+i]) if curve[0]==1 else (wa[*curve,k,i][2]-wb[*curve,k,i][2]) for k in steps)/n)
                observe('rotor_mean',error,.25,(*curve,half,i),cylinder)
            error=abs(sum(a[*curve,k][13]-b[*curve,k][13] for k in steps)/n)
            disconnected=all(a[*curve,k][15]==0 and b[*curve,k][15]==0 for k in steps)
            observe('disconnected_absolute_rpm_mean' if disconnected else 'connected_rpm_mean',error,2.,(*curve,half),cylinder or disconnected)
    report['full_parity']=not bool(report['unqualified'])
    return report


def self_test(raw,data,*,reference=False):
    checks=0
    def reject(action):
        nonlocal checks
        rejected(action);checks+=1
    lines=raw.splitlines()
    reject(lambda:parse('\n'.join(lines[1:])))
    reject(lambda:parse(raw+lines[0]+'\n'))
    for field,value in ((0,'unknown'),(1,'3'),(2,'3'),(3,'0'),(4,'61'),(6,'nan'),(6,'inf')):
        changed=lines[0].split();changed[field]=value
        reject(lambda:parse(' '.join(changed)+'\n'+'\n'.join(lines[1:])))
    bodies,wheels=data
    for curve in sorted(CURVES):
        # Positive controls cover exactly the profiles whose mutations follow.
        qualify(data,{curve},reference=reference,allow_profile_limits=True)
        final=(*curve,12*curve[3]);changed=list(bodies[final]);changed[0]+=.1
        mutated=bodies.copy();mutated[final]=tuple(changed)
        reject(lambda:qualify((mutated,wheels),{curve},reference=reference,allow_profile_limits=True))
        key=(*curve,2*curve[3]);wheel_key=(*key,0)
        for channel,value in ((1,5.),(3,100.),(6,2.),(13,9000.),(14,2.),(15,.5),(16,99.),(17,.5),(18,9.)):
            changed=list(bodies[key]);changed[channel]=value;mutated=bodies.copy();mutated[key]=tuple(changed)
            reject(lambda:qualify((mutated,wheels),{curve},reference=reference,allow_profile_limits=True))
        for channel,value in ((0,-.1),(1,-1.),(3,10.),(4,-1.),(5,-1.),(6,1e6),(7,1e6),(8,2.),(10,1e3),(11,.02),(13,2.),(16,2.)):
            changed=list(wheels[wheel_key]);changed[channel]=value;mutated=wheels.copy();mutated[wheel_key]=tuple(changed)
            reject(lambda:qualify((bodies,mutated),{curve},reference=reference,allow_profile_limits=True))
    compare(data,data,allow_reference_limits=True)
    base=(0,0,1,60,120)
    for channel,delta in ((0,.1),(3,.2),(7,.1),(10,.3)):
        changed=list(bodies[base]);changed[channel]+=delta;mutated=bodies.copy();mutated[base]=tuple(changed)
        reject(lambda:compare(data,(mutated,wheels),allow_reference_limits=True))
    # The scope declaration never disables the independent physics checks.
    cylinder=(0,2,1,60,120);changed=list(bodies[cylinder]);changed[3]+=.5
    mutated=bodies.copy();mutated[cylinder]=tuple(changed)
    report=compare(data,(mutated,wheels),allow_reference_limits=True)
    if report['unqualified']['velocity']['maximum']<.49:fail('declared limit disappeared from report')
    reject(lambda:compare(data,(mutated,wheels)))
    reject(lambda:qualify((mutated,wheels),{cylinder[:4]},reference=reference,allow_profile_limits=True))
    # Preserve the original red stop and absolute RPM criteria as executable controls.
    reject(lambda:qualify(data,{(2,2,-1,60)},reference=reference))
    return {'rejected_corruptions':checks,'positive_profile_controls':len(CURVES),'declared_limit_positive_control':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both')
    options=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from {GROUP}')
    source,digest=verified_source(options.archive);record={'oracle_revision':REFERENCE,'archive_sha256':digest,'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('VehicleDriveComposition*')) if p.is_file()},'modes':{}}
    previous_raw=None
    for mode in (('Debug','Release') if options.mode=='both' else (options.mode,)):
        oracle,provenance=build_composed_oracle(source,mode,HERE/'VehicleDriveCompositionOracle.cpp','vehicle-drive-composition-oracle')
        silex=build_silex(mode,'VehicleDriveComposition.sx','vehicle-drive-composition-silex',physics=True)
        raw={engine:checked([str(binary)]) for engine,binary in [('jolt',oracle),('silex',silex)]}
        if previous_raw is not None and raw!=previous_raw:fail('vehicle driving Debug/Release traces differ')
        previous_raw=raw
        data={engine:parse(value) for engine,value in raw.items()}
        for engine,value in raw.items():(BUILD/f'vehicle-drive-composition-{engine}-{mode.lower()}.txt.gz').write_bytes(gzip.compress(value.encode()))
        record['modes'][mode]={'reference':provenance,'guards':{engine:self_test(raw[engine],value,reference=engine=='jolt') for engine,value in data.items()},'qualifications':{engine:qualify(value,reference=engine=='jolt',allow_profile_limits=True) for engine,value in data.items()},'parity':compare(data['jolt'],data['silex'],allow_reference_limits=True),'mirrors':{engine:compare(value,mirror(value),allow_reference_limits=True) for engine,value in data.items()},'trace_sha256':{engine:hashlib.sha256(value.encode()).hexdigest() for engine,value in raw.items()}}
    (BUILD/'vehicle-drive-composition-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))

if __name__=='__main__':main()
