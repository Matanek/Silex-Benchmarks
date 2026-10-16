#!/usr/bin/env python3
"""Qualify cylindrical wheel width, geometry and suspension against pinned Jolt."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from VehicleSphereContactsRun import parse, wheels, force, cross, mean
from RagdollHierarchyRun import rotation_error

CONTACT_KEYS={(k,r,0) for k in range(21) for r in (60,120)}
MOTION_KEYS={(k,r,i) for k in (0,2) for r in (60,120) for i in range(6*r+1)}
GEOMETRY=.0002
POSITION=.01
VELOCITY=.05
QUATERNION=.005
ANGULAR=.05
LENGTH=.01
BALANCE=.05


def expected_contact(kind):
    n=(0,1,0);length=.5;label=1
    if kind in (4,14,17): return 0,.6,(0,0,0),0
    if kind in (1,18):
        angle=math.radians(20);length=.5-.2*math.tan(angle);n=(-math.sin(angle),math.cos(angle),0)
    elif kind in (2,5,8,15):
        length=.45
        if kind==5:label=2
    elif kind==3:length=.75-math.sqrt(.0675);n=(0,math.sqrt(.75),.5)
    elif kind==6:length=.5-math.sqrt(.07);n=(.75,math.sqrt(.4375),0)
    elif kind==7:length=.3-math.sqrt(.08);n=(1/3,math.sqrt(8)/3,0)
    elif kind in (12,13):
        length=0
        if kind==12:label=2
    elif kind==20:length=.8-.2*math.sin(.4)-.3*math.cos(.4)
    return 1,length,n,label


def local_point(p,kind):
    if kind==15:
        c,s=math.cos(.4),math.sin(.4);return (c*p[0]-s*p[2],p[1],s*p[0]+c*p[2])
    return p


def cylinder_boundary(p,length,kind):
    p=local_point(p,kind)
    origin=(0,.8,0);width=.4
    if kind in (2,4,14,15):origin=(.65,.75,0)
    if kind in (3,):origin=(.65,.75,.65)
    if kind in (5,8):origin=(.79,.6,0)
    if kind==6:origin=(.5,.8,0)
    if kind==7:origin=(.3,.9,0)
    if kind==16:width=.8
    d=[p[i]-origin[i]+(length if i==1 else 0) for i in range(3)]
    if kind==19:
        c,s=math.cos(.6),math.sin(.6);d=[c*d[0]-s*d[2],d[1],s*d[0]+c*d[2]]
    if kind==20:
        c,s=math.cos(.4),math.sin(.4);d=[c*d[0]+s*d[1],-s*d[0]+c*d[1],d[2]]
    axial=abs(d[0])-width/2;radial=math.hypot(d[1],d[2])-.3
    return abs(math.hypot(max(0,axial),max(0,radial))+min(0,max(axial,radial)))


def target_boundary(p,kind):
    x,y,z=local_point(p,kind)
    if kind in (1,18):return abs(-math.sin(math.radians(20))*x+math.cos(math.radians(20))*y)
    if kind==6:return abs(math.sqrt(x*x+y*y+z*z)-.4)
    if kind==7:return abs(math.sqrt(x*x+max(0,abs(y)-.3)**2+z*z)-.3)
    height=-.15 if kind in (5,8) else .1 if kind in (12,13) else 0
    half_x=.5 if kind in (2,3,15) else 2.5
    half_z=.5 if kind==3 else 1 if kind in (2,15) else 2.5
    if abs(x)>half_x+GEOMETRY or abs(z)>half_z+GEOMETRY:fail('contact outside target face')
    return abs(y-height)


def qualify_contact(rows,engine):
    length_error=normal_error=boundary=limited_normal=limited_point=0.
    for (kind,rate,_),v in rows.items():
        present,length,normal,label=expected_contact(kind)
        if v[0]!=present or v[8]!=label:fail(f'cylinder presence/support differs {(engine,kind,rate)}')
        error=abs(v[1]-length);length_error=max(length_error,error)
        if error>GEOMETRY:fail(f'cylinder length differs {(engine,kind,rate)}: {error}')
        e=max(abs(x-y) for x,y in zip(v[5:8],normal))
        if engine=='jolt' and kind==3:limited_normal=max(limited_normal,e)
        else:
            normal_error=max(normal_error,e)
            if e>GEOMETRY:fail(f'cylinder normal differs {(engine,kind,rate)}: {e}')
        if not present:
            if any(v[i]!=0 for i in range(2,9)):fail('miss retains contact data')
            continue
        if abs(sum(x*x for x in v[5:8])-1)>.0001:fail('non-unit cylinder normal')
        if engine=='jolt' and kind==1:limited_point=max(limited_point,target_boundary(v[2:5],kind));continue
        e=target_boundary(v[2:5],kind)
        if kind not in (12,13):e=max(e,cylinder_boundary(v[2:5],v[1],kind))
        boundary=max(boundary,e)
        if e>GEOMETRY:fail(f'cylinder point is not on both boundaries {(engine,kind,rate)}: {e}')
    return dict(length_error=length_error,normal_error=normal_error,boundary_error=boundary,jolt_corner_normal_error=limited_normal,jolt_rotated_plane_point_error=limited_point)


def compare_contact(a,b):
    worst=0.
    for key in CONTACT_KEYS:
        for i in (0,1,5,6,7,8):
            if key[0]==3 and i in (5,6,7):continue
            e=abs(a[key][i]-b[key][i]);worst=max(worst,e)
            if e>GEOMETRY:fail(f'cylinder geometry parity differs {key} channel {i}: {e}')
    return dict(qualified_error=worst,point_comparison='independent boundary membership; contacts may be lines',corner_normal_parity=False)


def qualify_motion(rows,engine):
    linear=angular=0.
    for (kind,rate,step),v in sorted(rows.items()):
        if abs(sum(x*x for x in v[6:10])-1)>.0001:fail('non-unit chassis quaternion')
        if max(abs(x) for x in v[:6])>20:fail('unbounded cylinder suspension')
        for w in wheels(v):
            if not 0<=w[0]<=.60001 or not 0<=w[1]<100000 or w[2] not in (0,1):fail('invalid cylinder wheel state')
            if not w[2] and (abs(w[0]-.6)>.00001 or any(w[i]!=0 for i in range(1,13))):fail('unsupported cylinder retained contact data')
            if w[2] and abs(sum(x*x for x in w[6:9])-1)>.0001:fail('non-unit cylinder contact frame')
            if w[9]!=0:fail('unconfigured cylinder lateral friction produced a force')
            if w[2] and engine=='jolt':
                if abs(sum(x*x for x in w[10:13])-1)>.0001 or abs(sum(x*y for x,y in zip(w[6:9],w[10:13])))>.0001:fail('invalid Jolt tire frame')
            elif any(w[10:13]):fail('cylinder retained an unconfigured tire frame')
        if not step:
            if abs(v[1]-1.4)>.00001 or max(abs(x) for x in v[3:6]+v[10:13])>.00001:fail('incorrect initial cylinder vehicle')
            continue
        old=rows[kind,rate,step-1];total=[0.,-981.,0.];torque=[0.,0.,0.]
        for w in wheels(v):
            f=force(w);radius=[x-y for x,y in zip(w[3:6],old[:3])]
            total=[x+y for x,y in zip(total,f)];torque=[x+y for x,y in zip(torque,cross(radius,f))]
            if w[2]:
                if abs(w[4])>GEOMETRY:fail('dynamic contact outside horizontal face')
                if kind==2 and abs(w[3])>.5+GEOMETRY:fail('dynamic contact outside narrow support')
        jump=500 if kind==0 and step==rate*2+1 else 0
        e=max(abs(100*(v[3+i]-old[3+i])-total[i]/rate-(jump if i==1 else 0)) for i in range(3));linear=max(linear,e)
        if e>BALANCE:fail(f'cylinder linear balance {(kind,rate,step)}: {e}')
        e=max(abs(100*(v[10+i]-old[10+i])-torque[i]/rate) for i in range(3));angular=max(angular,e)
        if e>BALANCE:fail(f'cylinder angular balance {(kind,rate,step)}: {e}')
    for kind in (0,2):
        for rate in (60,120):
            windows=((1.5,1.9),(5.5,6)) if kind==0 else ((5.5,6),)
            for start,end in windows:
                rest=[v for (k,r,i),v in rows.items() if k==kind and r==rate and start<=i/r<=end]
                if max(abs(v[1]-.875475) for v in rest)>.002:fail('cylinder rest height differs from spring equilibrium')
                if abs(mean([sum(force(w)[1] for w in wheels(v)) for v in rest])-981)>1:fail('cylinder mean force differs from weight')
            if kind==0:
                contact=[sum(w[2] for w in wheels(v)) for (k,r,i),v in rows.items() if k==kind and r==rate and 2.1<=i/r<=4.5]
                if 0 not in contact or 4 not in contact[contact.index(0)+1:]:fail('cylinder jump did not lose/regain supports')
    return dict(linear_balance=linear,angular_balance=angular)


def compare_motion(a,b):
    worst=[0.]*4;instantaneous_angular=phase_angular=0.
    for key in MOTION_KEYS:
        x,y=a[key],b[key]
        err=[max(abs(u-v) for u,v in zip(x[:3],y[:3])),max(abs(u-v) for u,v in zip(x[3:6],y[3:6])),rotation_error(x[6:10],y[6:10]),max(abs(u[0]-v[0]) for u,v in zip(wheels(x),wheels(y)))]
        for i,(e,t) in enumerate(zip(err,(POSITION,VELOCITY,QUATERNION,LENGTH))):
            worst[i]=max(worst[i],e)
            if e>t:fail(f'cylinder trajectory differs {key} channel {i}: {e}')
        instantaneous_angular=max(instantaneous_angular,max(abs(u-v) for u,v in zip(x[10:13],y[10:13])))
        if any(u[2]!=v[2] for u,v in zip(wheels(x),wheels(y))):fail(f'cylinder support presence differs {key}')
    for kind in (0,2):
        for rate in (60,120):
            for phase in range(24):
                keys=[key for key in MOTION_KEYS if key[0]==kind and key[1]==rate and phase/4<key[2]/rate<=(phase+1)/4]
                for channel in range(10,13):
                    e=abs(mean([a[k][channel] for k in keys])-mean([b[k][channel] for k in keys]));phase_angular=max(phase_angular,e)
                    if e>ANGULAR:fail(f'cylinder phase angular response differs {(kind,rate,phase)}: {e}')
    return dict(position_velocity_quaternion_length=worst,quarter_second_mean_angular=phase_angular,unqualified_instantaneous_angular=instantaneous_angular)


def rejected(action):
    try:action()
    except (ValueError,OverflowError):return
    fail('corrupt cylinder witness accepted')


def guards(raw,rows,kind,engine):
    tag,keys,count=('cylinder_contact',CONTACT_KEYS,9) if kind=='contact' else ('cylinder_motion',MOTION_KEYS,65)
    lines=raw.splitlines();rejected(lambda:parse('\n'.join(lines[1:]),tag,keys,count));rejected(lambda:parse('\n'.join(lines+[lines[0]]),tag,keys,count))
    fields=lines[0].split();fields[4]='nan';rejected(lambda:parse(' '.join(fields)+'\n'+'\n'.join(lines[1:]),tag,keys,count))
    key=(2,60,0) if kind=='contact' else (2,60,120)
    for channel in range(count):
        changed=dict(rows);v=list(changed[key]);v[channel]+=1000 if kind=='motion' and channel>=13 and (channel-13)%13 in (1,9) else 1;changed[key]=tuple(v)
        if kind=='contact':rejected(lambda:(qualify_contact(changed,engine),compare_contact(changed,rows)))
        else:rejected(lambda:(qualify_motion(changed,engine),compare_motion(changed,rows)))
    return count+3


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');parser.add_argument('--archive',type=Path);args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='cylindrical-wheel-contact-v1',oracle_revision=REFERENCE,archive_sha256=digest,tolerances=dict(geometry=GEOMETRY,position=POSITION,velocity=VELOCITY,quaternion=QUATERNION,angular=ANGULAR,length=LENGTH,impulse_balance=BALANCE),scope='Sharp cylinders, Jolt convex radius fraction zero. Contact points qualified by independent boundary membership, not equality along a contact line. Jolt rotated infinite plane point and sharp corner normal retained as oracle limitations; Silex analytic channels and equivalent tilted box face qualified. Cylinder trajectories compare position, velocity, orientation and suspension length; angular velocity uses fixed quarter-second means because contact-line witness choice changes instantaneous landing moments. All per-step physical balances use actual observed points/normals/forces.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        evidence={}
        for kind in ('contact','motion'):
            stem='VehicleCylinder'+kind.title();oracle=build_oracle(source,mode,HERE/(stem+'Oracle.cpp'),'vehicle-cylinder-'+kind+'-oracle');binary=build_silex(mode,stem+'.sx','vehicle-cylinder-'+kind+'-silex',True)
            rows={};result={}
            for engine,exe in (('silex',binary),('jolt',oracle)):
                raw=checked([str(exe)]);(BUILD/f'vehicle-cylinder-{kind}-{engine}-{mode.lower()}.txt').write_text(raw)
                rows[engine]=parse(raw,'cylinder_'+kind,CONTACT_KEYS if kind=='contact' else MOTION_KEYS,9 if kind=='contact' else 65)
                result[engine]=dict(observations=len(rows[engine]),sha256=hashlib.sha256(raw.encode()).hexdigest(),worst=qualify_contact(rows[engine],engine) if kind=='contact' else qualify_motion(rows[engine],engine),guards=guards(raw,rows[engine],kind,engine))
            result['parity']=compare_contact(rows['silex'],rows['jolt']) if kind=='contact' else compare_motion(rows['silex'],rows['jolt']);evidence[kind]=result
        record['modes'][mode]=evidence;(BUILD/'vehicle-cylinder-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(f'{mode}: cylindrical wheel geometry, width, suspension balances and corruption guards green',flush=True)

if __name__=='__main__':main()
