#!/usr/bin/env python3
"""Qualify spherical wheel contacts and suspension against pinned Jolt."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from LoadedSwingTwistRun import rotate
from RagdollHierarchyRun import rotation_error

SECONDS={0:6,1:3,2:6,3:6}
CONTACT_KEYS={(kind,rate,0) for kind in range(19) for rate in (60,120)}
MOTION_KEYS={(kind,rate,step) for kind,seconds in SECONDS.items() for rate in (60,120) for step in range(rate*seconds+1)}
GEOMETRY=.0002
POSITION=.01
VELOCITY=.05
QUATERNION=.005
ANGULAR=.05
LENGTH=.01
BALANCE=.05


def parse(raw,tag,keys,count):
    rows={}
    for line in raw.splitlines():
        fields=line.split()
        if len(fields)!=count+4 or fields[0]!=tag: fail(f'invalid {tag} row')
        key=tuple(map(int,fields[1:4]));values=tuple(map(float,fields[4:]))
        if key not in keys or key in rows or not all(map(math.isfinite,values)): fail(f'invalid {tag} key/value')
        rows[key]=values
    if set(rows)!=keys: fail(f'incomplete {tag} witness')
    return rows


def analytic_contact(kind):
    sine=math.sin(math.radians(20));cosine=math.cos(math.radians(20))
    if kind in (4,14,17): return (0,.6,0,0,0,0,0,0,0)
    if kind in (1,18): return (1,.8-.3/cosine,.3*sine,.3/cosine-.3*cosine,0,-sine,cosine,0,1)
    if kind in (2,15):
        c=math.cos(.4) if kind==15 else 1;s=math.sin(.4) if kind==15 else 0
        return (1,.75-math.sqrt(.05),.5*c,0,-.5*s,2/3*c,math.sqrt(5)/3,-2/3*s,1)
    if kind==3: return (1,.75-math.sqrt(.045),.5,0,.5,.5,math.sqrt(.5),.5,1)
    if kind in (5,8): return (1,.45,.79,-.15,0,0,1,0,2 if kind==5 else 1)
    if kind==6:
        n=(.5/.7,math.sqrt(.24)/.7,0)
        return (1,.8-math.sqrt(.24),*(.4*x for x in n),*n,1)
    if kind==7: return (1,.1,.18,.54,0,.6,.8,0,1)
    if kind in (12,13): return (1,0,0,.1,0,0,1,0,2 if kind==12 else 1)
    return (1,.5,0,0,0,0,1,0,1)


def qualify_contact(rows,engine):
    maximum=0;plane_residual=0
    for (kind,rate,_),value in rows.items():
        expected=analytic_contact(kind)
        for index,(actual,target) in enumerate(zip(value,expected)):
            if engine=='jolt' and kind==1 and 2<=index<5: continue
            error=abs(actual-target);maximum=max(maximum,error)
            if error>GEOMETRY: fail(f'{engine} analytic contact mismatch {(kind,rate,index)}: {actual} vs {target}')
        if kind==1: plane_residual=max(plane_residual,abs(sum(x*y for x,y in zip(value[2:5],value[5:8]))))
    return dict(analytic_error=maximum,rotated_infinite_plane_point_residual=plane_residual)


def compare_contact(first,second):
    maximum=0
    for key in CONTACT_KEYS:
        for index,(a,b) in enumerate(zip(first[key],second[key])):
            if key[0]==1 and 2<=index<5: continue
            maximum=max(maximum,abs(a-b))
            if abs(a-b)>GEOMETRY: fail(f'contact oracle mismatch {key} channel {index}')
    return dict(qualified_geometry_error=maximum,rotated_infinite_plane_point_parity=False)


def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def wheels(row): return [row[13+13*i:26+13*i] for i in range(4)]
def force(wheel): return [wheel[1]*wheel[6+i]+wheel[9]*wheel[10+i] for i in range(3)]
def mean(values): return sum(values)/len(values)
def phase(rows,kind,rate,start,end): return [v for (k,r,step),v in rows.items() if k==kind and r==rate and start<=step/r<=end]


def qualify_motion(rows):
    linear=angular=0
    for (kind,rate,step),value in sorted(rows.items()):
        if abs(sum(x*x for x in value[6:10])-1)>.0001: fail('non-unit vehicle quaternion')
        if max(abs(x) for x in value[:3])>20 or max(abs(x) for x in value[3:6])>20: fail('unbounded sphere suspension')
        for wheel in wheels(value):
            if not 0<=wheel[0]<=.60001 or not 0<=wheel[1]<100000 or wheel[2] not in (0,1): fail('invalid sphere wheel state')
            if wheel[2]==0 and (abs(wheel[0]-.6)>.00001 or any(wheel[i]!=0 for i in range(1,13))): fail('unsupported wheel retained contact data or force')
            if wheel[2] and abs(sum(x*x for x in wheel[6:9])-1)>.0001: fail('non-unit sphere normal')
            if kind==3 and wheel[2] and abs(sum(x*x for x in wheel[10:13])-1)>.0001: fail('non-unit tire lateral direction')
        if not step:
            if abs(value[1]-(.7 if kind==1 else 1.4))>.00001 or max(abs(x) for x in value[3:6]+value[10:13])>.00001: fail('incorrect initial sphere vehicle')
            continue
        previous=rows[kind,rate,step-1];total=[0.,-981.-(20000 if kind==1 else 0),0.];torque=[0.,0.,0.]
        for wheel in wheels(value):
            f=force(wheel);radius=[x-y for x,y in zip(wheel[3:6],previous[:3])]
            total=[x+y for x,y in zip(total,f)];torque=[x+y for x,y in zip(torque,cross(radius,f))]
        jump=500 if kind==0 and step==rate*2+1 else 0
        e=max(abs(100*(value[3+i]-previous[3+i])-total[i]/rate-(jump if i==1 else 0)) for i in range(3));linear=max(linear,e)
        if e>BALANCE: fail(f'linear sphere balance {(kind,rate,step)}: {e}')
        e=max(abs(100*(value[10+i]-previous[10+i])-torque[i]/rate) for i in range(3));angular=max(angular,e)
        if e>BALANCE: fail(f'angular sphere balance {(kind,rate,step)}: {e}')
    for rate in (60,120):
        for start,end in ((1.5,1.9),(5.5,6)):
            rest=phase(rows,0,rate,start,end)
            if max(abs(v[1]-.875475) for v in rest)>.002 or abs(mean([sum(force(w)[1] for w in wheels(v)) for v in rest])-981)>1: fail('flat sphere support differs from analytic equilibrium')
        contacts=[sum(w[2] for w in wheels(v)) for v in phase(rows,0,rate,2.1,4.5)]
        if 0 not in contacts or 4 not in contacts[contacts.index(0)+1:]: fail('sphere jump did not lose and regain supports')
        loaded=phase(rows,1,rate,2,3)
        if max(abs(v[1]-.5) for v in loaded)>.002 or abs(mean([sum(force(w)[1] for w in wheels(v)) for v in loaded])-20981)>20: fail('sphere hard stop geometry/mean support differs')
        initial=phase(rows,2,rate,1,1.5)
        if max(abs(v[1]-(.6-.024525+math.sqrt(.08))) for v in initial)>.002: fail('sphere edge initial equilibrium differs')
        gripped=phase(rows,3,rate,5.5,6)
        if max(abs(v[0]) for v in gripped)>.01 or max(abs(v[1]-.84) for v in gripped)>.01: fail('lateral grip did not retain edge support')
        if abs(mean([sum(force(w)[1] for w in wheels(v)) for v in gripped])-981)>1: fail('edge net mean force differs from weight')
    return dict(linear_balance=linear,angular_balance=angular)


def compare_motion(first,second):
    worst=[0.]*5;point=normal=0
    for key in MOTION_KEYS:
        kind,rate,step=key
        if kind==2 and step/rate>1.5: continue
        a,b=first[key],second[key]
        error=[max(abs(x-y) for x,y in zip(a[:3],b[:3])),max(abs(x-y) for x,y in zip(a[3:6],b[3:6])),rotation_error(a[6:10],b[6:10]),max(abs(x-y) for x,y in zip(a[10:13],b[10:13])),max(abs(x[0]-y[0]) for x,y in zip(wheels(a),wheels(b)))]
        for index,(e,tolerance) in enumerate(zip(error,(POSITION,VELOCITY,QUATERNION,ANGULAR,LENGTH))):
            if kind==1 and index in (1,3): continue
            worst[index]=max(worst[index],e)
            if e>tolerance: fail(f'sphere trajectory mismatch {key} channel {index}: {e}')
        for x,y in zip(wheels(a),wheels(b)):
            if x[2]!=y[2]: fail(f'sphere contact presence differs {key}')
            if not x[2]: continue
            p=max(abs(u-v) for u,v in zip(x[3:6],y[3:6]));n=max(abs(u-v) for u,v in zip(x[6:9],y[6:9]));point=max(point,p);normal=max(normal,n)
            if p>.01 or n>.002: fail(f'sphere contact frame mismatch {key}: {p}, {n}')
            if kind==3 and max(abs(u-v) for u,v in zip(x[10:13],y[10:13]))>.002: fail('sphere lateral frame differs')
    return dict(position_velocity_quaternion_angular_length=worst,contact_point=point,contact_normal=normal)


def rejected(action):
    try: action()
    except (ValueError,OverflowError): return
    fail('corrupt sphere vehicle witness accepted')


def guards(raw,rows,kind,engine):
    tag,keys,count=('sphere_contact',CONTACT_KEYS,9) if kind=='contact' else ('sphere_motion',MOTION_KEYS,65)
    lines=raw.splitlines()
    rejected(lambda:parse('\n'.join(lines[1:]),tag,keys,count));rejected(lambda:parse('\n'.join(lines+[lines[0]]),tag,keys,count))
    fields=lines[0].split();fields[4]='nan';rejected(lambda:parse(' '.join(fields)+'\n'+'\n'.join(lines[1:]),tag,keys,count))
    key=(2,60,0) if kind=='contact' else (3,60,120)
    for channel in range(count):
        changed=dict(rows);v=list(changed[key]);v[channel]+=1000 if (kind=='motion' and channel>=13 and (channel-13)%13 in (1,9)) else 1;changed[key]=tuple(v)
        if kind=='contact': rejected(lambda:(qualify_contact(changed,engine),compare_contact(changed,rows)))
        else: rejected(lambda:(qualify_motion(changed),compare_motion(changed,rows)))
    return count+3


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');parser.add_argument('--archive',type=Path);args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='spherical-wheel-contact-v1',oracle_revision=REFERENCE,archive_sha256=digest,tolerances=dict(geometry=GEOMETRY,position=POSITION,velocity=VELOCITY,quaternion=QUATERNION,angular=ANGULAR,length=LENGTH,impulse_balance=BALANCE),scope='Per-wheel sphere casts. Rotated infinite PlaneShape: Jolt point channel is off-plane, so only normal/length are compared; rotated box face proves physical point. Hard stop: geometry/phase means, no instantaneous velocity parity. Ungripped edge: initial trajectory through 1.5 s and full balances, no long trajectory parity; 1e-6 m Jolt-only perturbation also tips. Gripped edge and flat soft suspension: full trajectory. Lateral impulses are actual public wheel snapshots in both engines.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        evidence={};data={}
        for kind in ('contact','motion'):
            stem='VehicleSphere'+kind.title();oracle=build_oracle(source,mode,HERE/(stem+'Oracle.cpp'),'vehicle-sphere-'+kind+'-oracle');binary=build_silex(mode,stem+'.sx','vehicle-sphere-'+kind+'-silex',True)
            rows={};result={}
            for engine,exe in (('silex',binary),('jolt',oracle)):
                raw=checked([str(exe)]);(BUILD/f'vehicle-sphere-{kind}-{engine}-{mode.lower()}.txt').write_text(raw)
                rows[engine]=parse(raw,'sphere_'+kind,CONTACT_KEYS if kind=='contact' else MOTION_KEYS,9 if kind=='contact' else 65)
                result[engine]=dict(observations=len(rows[engine]),sha256=hashlib.sha256(raw.encode()).hexdigest(),worst=qualify_contact(rows[engine],engine) if kind=='contact' else qualify_motion(rows[engine]),guards=guards(raw,rows[engine],kind,engine))
            result['parity']=compare_contact(rows['silex'],rows['jolt']) if kind=='contact' else compare_motion(rows['silex'],rows['jolt']);evidence[kind]=result
        record['modes'][mode]=evidence;(BUILD/'vehicle-sphere-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(f'{mode}: spherical wheel geometry, support response, public impulse balances and corruption guards green',flush=True)

if __name__=='__main__': main()
