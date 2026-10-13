#!/usr/bin/env python3
"""Qualify a mobile three-member ragdoll with two motors and floor contacts."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from SpatialHingesRun import add, sub, mul, norm, cross
from LoadedSwingTwistRun import product, conjugate, axis_angle, distance, rotate
from RagdollContactRun import decomposition

CONFIGS = [(rate, side, frame) for rate in (60, 120) for side in (-1, 1) for frame in (0, 1)]
KEYS = {(tag, *config, step, part) for config in CONFIGS for tag in ('mobilecontact', 'mobilebefore', 'mobileafter')
        for step in (range(config[0]*12+1) if tag == 'mobilecontact' else tuple(config[0]*t for t in (2,4,7,10)))
        for part in range(3)}
BOUNDS = dict(anchor=.02, penetration=.02, angular_excess=.08, torque=30.001, speed=40,
    reconstruction=.0001, linear_residual=.0002, horizontal_momentum=.0001,
    horizontal_center=.001, vertical_angular_momentum=.02, angular_residual=.02, settled_speed=.15)
PARITY = dict(orientation=.04, position=.05, speed=.05, force=1, normal_force=1)


def parse(raw):
    rows = {}
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 35:fail('invalid mobile contact row length')
        try:
            key = (fields[0], *map(int, fields[1:6]));values = tuple(map(float, fields[6:]))
        except (ValueError, OverflowError):fail('invalid mobile contact number')
        if key not in KEYS or key in rows or not all(map(math.isfinite, values)):
            fail('unknown, duplicate or nonfinite mobile contact observation')
        rows[key] = values
    if set(rows) != KEYS:fail('missing mobile contact observations')
    return rows


def state(rows, config, step, tag='mobilecontact'):
    return [rows[tag, *config, step, part] for part in range(3)]


def totals(batch):
    p = (0,0,0);angular = (0,0,0);center = (0,0,0)
    for row in batch:
        momentum = mul(row[7:10],2)
        p = add(p,momentum);angular = add(angular,add(cross(row[:3],momentum),mul(row[10:13],.2)))
        center = add(center,mul(row[:3],1/3))
    return p,angular,center


def normal_impulses(batch, previous, rate):
    inferred = []
    for part,row in enumerate(batch):
        force = row[20:23]
        if part < 2:force = sub(force,batch[part+1][20:23])
        inferred.append(sub(mul(sub(row[7:10],previous[part][7:10]),2),mul(add(force,(0,-19.62,0)),1/rate)))
    return inferred


def qualify(rows,engine):
    worst = dict.fromkeys(BOUNDS,0)
    for config in CONFIGS:
        rate,side,frame = config;base=axis_angle((0,1,0),.7*frame);expected_center = rotate(base,(1,0,0))
        for part,row in enumerate(state(rows,config,0)):
            expected=add((0,1,0),rotate(base,(part,0,0)))
            if norm(sub(row[:3],expected))>.00001 or distance(row[3:7],base)>.00001 or norm(row[7:13])>.00001:
                fail('initial mobile pose or velocity differs from fixed recipe')
        for step in range(rate*12+1):
            batch = state(rows,config,step);p,angular,center = totals(batch)
            values = dict(horizontal_momentum=math.hypot(p[0],p[2]),horizontal_center=math.hypot(center[0]-expected_center[0],center[2]-expected_center[2]),vertical_angular_momentum=abs(angular[1]))
            for part,row in enumerate(batch):
                pos,q,v,w,o,m,f,e = row[:3],row[3:7],row[7:10],row[10:13],row[13:17],row[17:20],row[20:23],row[23:26]
                if max(abs(norm(q)-1),abs(norm(o)-1)) > .00001 or row[27] not in (0,1) or row[28] != int(engine=='silex'):
                    fail('invalid quaternion, contact count or contact impulse provenance')
                if norm(pos)>10:fail('unbounded mobile member position')
                reconstruction = 0
                if part:
                    parent=batch[part-1]
                    predicted=sub(add(pos,rotate(q,(-.5,0,0))),add(parent[:3],rotate(parent[3:7],(.5,0,0))))
                    reconstruction=max(norm(sub(predicted,e)),distance(product(conjugate(parent[3:7]),q),o))
                elif norm(sub(o,(0,0,0,1)))+norm(m)+norm(f)+norm(e)> .00001:
                    fail('root declares a nonexistent parent constraint')
                swing,twist=decomposition(o);inclination=2*math.asin(min(1,math.hypot(swing[1],swing[2])))
                own=dict(anchor=norm(e),penetration=max(0,.25-pos[1]),angular_excess=max(0,inclination-.6,-.2-twist,twist-.35),torque=max(map(abs,m)),speed=max(norm(v),norm(w)),reconstruction=reconstruction)
                if step>rate*10 and norm(m)>.00001:fail('motor reaction remains after release')
                for name,value in own.items():values[name]=max(values.get(name,0),value)
            if step:
                previous=state(rows,config,step-1)
                if step-1 in (rate*2,rate*4,rate*7,rate*10):previous=state(rows,config,step-1,'mobileafter')
                normals=normal_impulses(batch,previous,rate);external=(0,0,0);residual=0
                for part,(row,normal) in enumerate(zip(batch,normals)):
                    residual=max(residual,abs(normal[0]),abs(normal[2]),max(0,-normal[1]))
                    if engine=='silex':residual=max(residual,abs(normal[1]-row[26]))
                    elif row[26]!=0:fail('Jolt declares a contact impulse it does not expose')
                    if not row[27]:residual=max(residual,norm(normal),abs(row[26]))
                    if row[26]<-.00001:fail('negative measured floor impulse')
                    external=add(external,cross(previous[part][:3],(0,normal[1]-19.62/rate,0)))
                values['linear_residual']=residual
                values['angular_residual']=norm(sub(sub(angular,totals(previous)[1]),external))
            for end in (4,7,10):
                if rate*(end-.5)<=step<rate*end:
                    if not sum(row[27] for row in batch):fail('established floor contact absent')
                    values['settled_speed']=max(max(norm(row[7:10]),norm(row[10:13])) for row in batch)
            if rate*10.15<=step<=rate*10.3 and any(row[27] for row in batch):fail('uniform impulse never detached the whole chain')
            if rate*11.5<=step<=rate*12 and not any(row[27] for row in batch):fail('floor contact not regained')
            for name,value in values.items():
                worst[name]=max(worst[name],value)
                if value>=BOUNDS[name]:fail(f'{engine} {name} exceeded {value} at {config}/{step}')
        for step in (rate*2,rate*4,rate*7,rate*10):
            current=state(rows,config,step);before=state(rows,config,step,'mobilebefore');after=state(rows,config,step,'mobileafter')
            for a,b,c in zip(current,before,after):
                if norm(sub(a[:13],b[:13]))>.00001:fail('before-command observation differs from actual state')
                if max(norm(sub(b[:3],c[:3])),distance(b[3:7],c[3:7]),norm(sub(b[10:13],c[10:13])))>.00001:
                    fail('target or launch moved a body or injected angular velocity')
                impulse=(0,2,0) if step==rate*10 else (0,0,0)
                if norm(sub(sub(c[7:10],b[7:10]),impulse))>.00001:fail('linear velocity changed outside declared uniform impulse')
                if norm(c[17:20])>.00001:fail('motor command retained previous motor impulse')
    return worst


def mean_vector(rows,config,interval,part,start,end):
    return tuple(sum(rows['mobilecontact',*config,step,part][i] for step in interval)/len(interval) for i in range(start,end))


def compare(first,second):
    worst=dict.fromkeys(PARITY,0)
    for config in CONFIGS:
        rate=config[0]
        for end in (4,7,10):
            interval=range(int(rate*(end-.5)),rate*end)
            for step in interval:
                a,b=state(first,config,step),state(second,config,step);ca,cb=totals(a)[2],totals(b)[2]
                for x,y in zip(a,b):
                    errors=dict(orientation=distance(x[13:17],y[13:17]),position=norm(sub(sub(x[:3],ca),sub(y[:3],cb))))
                    for name,value in errors.items():
                        worst[name]=max(worst[name],value)
                        if value>=PARITY[name]:fail(f'mobile established {name} parity differs: {value} at {config}/{step}')
            for part in range(3):
                for name,start,end_index in [('speed',10,13),('force',20,23)]:
                    value=norm(sub(mean_vector(first,config,interval,part,start,end_index),mean_vector(second,config,interval,part,start,end_index)))
                    worst[name]=max(worst[name],value)
                    if value>=PARITY[name]:fail(f'mobile mean {name} parity differs: {value} at {config}/{end}/{part}')
            sums=[]
            for rows in (first,second):
                sums.append(sum(sum(n[1] for n in normal_impulses(state(rows,config,step),state(rows,config,step-1),rate)) for step in interval)*rate/len(interval))
            value=abs(sums[0]-sums[1]);worst['normal_force']=max(worst['normal_force'],value)
            if value>=PARITY['normal_force']:fail('mobile mean normal force parity differs')
    return worst


def rejected(action):
    try:action()
    except ValueError:return
    fail('mobile contact guard accepted corrupted evidence')


def self_test(raw,rows,engine):
    lines=raw.splitlines();count=0
    for altered in (raw+'\n'+lines[0],'\n'.join(lines[1:]),raw.replace('mobilecontact 60','mobilecontact 61',1)):
        rejected(lambda altered=altered:parse(altered));count+=1
    altered=lines.copy();parts=altered[0].split();parts[6]='nan';altered[0]=' '.join(parts)
    rejected(lambda:parse('\n'.join(altered)));count+=1
    for component in range(29):
        key=('mobilecontact',60,-1,0,239,1);altered=rows.copy();v=list(altered[key]);v[component]+=300 if 17<=component<20 else 5
        altered[key]=tuple(v);rejected(lambda:qualify(altered,engine));count+=1
    for tag,component in [('mobilebefore',0),('mobileafter',0),('mobileafter',7),('mobileafter',10)]:
        key=(tag,60,-1,0,240,1);altered=rows.copy();v=list(altered[key]);v[component]+=1
        altered[key]=tuple(v);rejected(lambda:qualify(altered,engine));count+=1
    config=(60,-1,0);interval=range(210,240)
    for name in PARITY:
        altered=rows.copy()
        for step in interval:
            key=('mobilecontact',*config,step,1);v=list(altered[key])
            if name=='orientation':v[13:17]=product(axis_angle((1,0,0),.1),v[13:17])
            if name=='position':v[0]+=.2
            if name=='speed':v[10]+=1
            if name=='force':v[20]+=2
            if name=='normal_force':v[8]+=1
            altered[key]=tuple(v)
        rejected(lambda:compare(rows,altered));count+=1
    return count


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both')
    parser.add_argument('--archive',type=Path);parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='ragdoll-mobile-two-motors-floor-v2',oracle_revision=REFERENCE,archive_sha256=digest,bounds=BOUNDS,parity_bounds=PARITY,
        configuration=dict(radius=.25,mass=2,inertia=[.2,.2,.2],centers_x=[0,1,2],height=1,gravity=[0,-9.81,0],cone_half_angle=.6,twist_limits=[-.2,.35],motor=dict(torque=30,stiffness=80,damping=15),command_seconds=[2,4,7,10],duration=12,uniform_launch_impulse=[0,4,0],friction=0,restitution=0,allow_sleep=False,jolt=dict(velocity_steps=24,position_steps=16,penetration_slop=1e-6,workers=1,substeps=1,warm_start=True),silex=dict(position_steps=16,velocity_steps_per_stage=48,velocity_stages=2,workers=1)),scope='Three freely moving spheres with two planar clamped motor targets and floor contacts. Established states and window-mean parity only; arbitrary impacts and trajectories remain unqualified.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=BUILD/f'ragdoll-mobile-contact-oracle-{mode.lower()}' if args.check_only else build_oracle(source,mode,HERE/'RagdollMobileContactOracle.cpp','ragdoll-mobile-contact-oracle')
        binary=BUILD/f'ragdoll-mobile-contact-silex-{mode.lower()}' if args.check_only else build_silex(mode,'RagdollMobileContact.sx','ragdoll-mobile-contact-silex',True)
        parsed={};witnesses={}
        for name,exe in [('silex',binary),('jolt',oracle)]:
            output=BUILD/f'ragdoll-mobile-contact-{name}-{mode.lower()}.txt';raw=output.read_text() if args.check_only else checked([str(exe)])
            if not args.check_only:output.write_text(raw)
            rows=parse(raw);parsed[name]=rows
            witnesses[name]=dict(observations=len(rows),worst=qualify(rows,name),corrupt_witnesses_rejected=self_test(raw,rows,name),output_sha256=hashlib.sha256(raw.encode()).hexdigest())
        record['modes'][mode]=dict(witnesses=witnesses,established_parity=compare(parsed['silex'],parsed['jolt']))
        (BUILD/'ragdoll-mobile-contact-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: mobile ragdoll motors, floor contacts and declared launch qualified',flush=True)


if __name__=='__main__':main()
