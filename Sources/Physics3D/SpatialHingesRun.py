#!/usr/bin/env python3
"""Qualify a gravity-loaded chain with perpendicular Z/X hinges."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS=[name+'_'+component for name in ('p1','v1','w1','q1','p2','v2','w2','q2',
        'bp1','bv1','bw1','bq1','bp2','bv2','bw2','bq2','f1','t1','f2','t2')
        for component in ('xyzw' if 'q' in name else 'xyz')]
FIELDS += [joint+'_'+field for joint in ('first','second') for field in ('angle','speed','motor','anchor','axis')]
CASES={(mode,mass,rate,side,step) for mode in (0,1) for mass in (0,1)
       for rate in (60,120) for side in (-1,1) for step in range(1,rate*2+1)}
BOUNDS=dict(linear_impulse=0.00001,spin_impulse=0.001,angular_impulse=0.001,
            cumulative_angular_impulse=0.01,geometry=0.005,root_angle=0.02,
            held_angle=0.02,final_speed=0.005,final_force=0.05,final_torque=0.05,motor_projection=0.01)


def add(a,b):return tuple(x+y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def mul(a,s):return tuple(x*s for x in a)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(a):return math.sqrt(dot(a,a))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def vector(row,name):return tuple(row[name+'_'+c] for c in 'xyz')
def rotation(row,name):return tuple(row[name+'_'+c] for c in 'xyzw')
def rotate(q,v):return add(v,add(mul(cross(q[:3],v),2*q[3]),mul(cross(q[:3],cross(q[:3],v)),2)))
def angle(a,b):return math.atan2(norm(cross(a,b)),dot(a,b))
def momentum(p,v,w,mass,inertia):return add(mul(cross(p,v),mass),mul(w,inertia))


def parse(raw):
    rows={}
    for line in raw.splitlines():
        parts=line.split()
        if len(parts)!=80 or parts[0]!='spatialhinges':fail('invalid spatial hinge row')
        try:
            key_values=list(map(float,parts[1:6]));values=list(map(float,parts[6:]))
            if not all(math.isfinite(v) and v.is_integer() for v in key_values):fail('invalid spatial hinge key')
            key=tuple(map(int,key_values))
        except ValueError:fail('invalid spatial hinge number')
        if key not in CASES or key in rows or not all(map(math.isfinite,values)):fail('invalid spatial hinge observation')
        rows[key]=dict(zip(FIELDS,values))
    if set(rows)!=CASES:fail('missing spatial hinge observations')
    return rows


def mechanics(rows):
    worst={name:0.0 for name in BOUNDS};recipes={};cumulative={}
    for key,row in sorted(rows.items()):
        mode,mass_id,rate,side,step=key;mass=mass_id+1;recipe=key[:4];delta=1/rate
        previous=rows.get((*recipe,step-1))
        for name in ('p1','v1','w1','q1','p2','v2','w2','q2'):
            components='xyzw' if 'q' in name else 'xyz'
            initial={'p1':(.5,0,0),'p2':(1,0,.8*side),'q1':(0,0,0,1),'q2':(0,0,0,1)}.get(name,(0,0,0))
            expected=tuple(previous[name+'_'+c] for c in components) if previous else initial
            actual=tuple(row['b'+name+'_'+c] for c in components)
            if norm(sub(actual,expected))>0.000003:fail('spatial hinge state discontinuity')
        for name in ('q1','q2','bq1','bq2'):
            if abs(norm(rotation(row,name))-1)>0.00002:fail('spatial hinge quaternion is not unit')
        p1,v1,w1,p2,v2,w2=(vector(row,n) for n in ('p1','v1','w1','p2','v2','w2'))
        bp1,bv1,bw1,bp2,bv2,bw2=(vector(row,n) for n in ('bp1','bv1','bw1','bp2','bv2','bw2'))
        q1,q2,bq1,bq2=(rotation(row,n) for n in ('q1','q2','bq1','bq2'))
        f1,t1,f2,t2=(vector(row,n) for n in ('f1','t1','f2','t2'))
        gravity1=(0,-2*9.81,0);gravity2=(0,-mass*9.81,0)
        r1=rotate(bq1,(-.5,0,0));r12=rotate(bq1,(.5,0,0));r2=rotate(bq2,(0,0,-.8*side))
        linear=max(norm(sub(mul(sub(v1,bv1),2),mul(add(sub(f1,f2),gravity1),delta))),
                   norm(sub(mul(sub(v2,bv2),mass),mul(add(f2,gravity2),delta))))
        spin=max(norm(sub(mul(sub(w1,bw1),.4),mul(add(sub(t1,t2),sub(cross(r1,f1),cross(r12,f2))),delta))),
                 norm(sub(mul(sub(w2,bw2),.2),mul(add(t2,cross(r2,f2)),delta))))
        before=add(momentum(bp1,bv1,bw1,2,.4),momentum(bp2,bv2,bw2,mass,.2))
        after=add(momentum(p1,v1,w1,2,.4),momentum(p2,v2,w2,mass,.2))
        external=add(t1,add(cross(bp1,gravity1),cross(bp2,gravity2)))
        residual=sub(sub(after,before),mul(external,delta))
        cumulative[recipe]=add(cumulative.get(recipe,(0,0,0)),residual)
        axis1=rotate(q1,(0,0,1));axis2=rotate(q1,(1,0,0));payload_axis=rotate(q2,(1,0,0))
        anchors=(norm(add(p1,rotate(q1,(-.5,0,0)))),norm(sub(add(p2,rotate(q2,(0,0,-.8*side))),add(p1,rotate(q1,(.5,0,0))))))
        axes=(angle((0,0,1),axis1),angle(axis2,payload_axis))
        for joint,anchor,axis in zip(('first','second'),anchors,axes):
            if row[joint+'_anchor']<0 or row[joint+'_axis']<0:fail('negative spatial hinge geometry')
            if abs(anchor-row[joint+'_anchor'])>0.000003 or abs(axis-row[joint+'_axis'])>0.000003:fail('spatial hinge geometry observable differs')
        normals=(rotate(q1,(1,0,0)),rotate(q1,(0,1,0)),rotate(q2,(0,1,0)))
        angles=(math.atan2(normals[0][1],normals[0][0]),math.atan2(dot(axis2,cross(normals[1],normals[2])),dot(normals[1],normals[2])))
        if abs(angles[0]-row['first_angle'])>0.00001 or abs(angles[1]-row['second_angle'])>0.00001:fail('spatial hinge angle observable differs')
        if abs(w1[2]-row['first_speed'])>0.00001 or abs(dot(sub(w2,w1),axis2)-row['second_speed'])>0.00001:fail('spatial hinge speed observable differs')
        if abs(row['first_motor'])>60.0001 or abs(row['second_motor'])>40.0001:fail('spatial hinge motor budget')
        errors=dict(linear_impulse=linear,spin_impulse=spin,angular_impulse=norm(residual),cumulative_angular_impulse=norm(cumulative[recipe]),
                    geometry=max(*anchors,*axes),root_angle=abs(row['first_angle']),
                    motor_projection=max(abs(t1[2]-row['first_motor']),abs(dot(t2,rotate(bq1,(1,0,0)))-row['second_motor'])))
        if mode==0:errors['held_angle']=abs(row['second_angle'])
        if step==rate*2:
            expected1=mul(add(cross(p1,gravity1),cross(p2,gravity2)),-1)
            expected2=mul(cross(rotate(q2,(0,0,-.8*side)),mul(gravity2,-1)),-1)
            errors.update(final_speed=max(norm(v1),norm(v2),norm(w1),norm(w2)),
                          final_force=max(norm(add(f1,add(gravity1,gravity2))),norm(add(f2,gravity2))),
                          final_torque=max(norm(sub(t1,expected1)),norm(sub(t2,expected2))))
        for name,error in errors.items():
            worst[name]=max(worst[name],error)
            if error>BOUNDS[name]:fail('spatial hinge '+name+' exceeds bound')
        recipes.setdefault(recipe,[]).append(row)
    summaries=[]
    for key,data in sorted(recipes.items()):
        mode,mass_id,rate,side=key
        if mode==1 and (max(abs(r['second_angle']) for r in data)<.08 or max(side*r['second_speed'] for r in data)<.15 or min(side*r['second_speed'] for r in data)>-.15):fail('spatial hinge motion or reversal lost')
        summaries.append(dict(key=key,final_angle=data[-1]['second_angle'],peak_angle=max(abs(r['second_angle']) for r in data),final_first_torque=vector(data[-1],'t1'),final_second_torque=vector(data[-1],'t2')))
    return dict(worst=worst,recipes=summaries)


def rejected(action):
    try:action()
    except ValueError:return
    fail('spatial hinge guard accepted corrupt witness')


def self_test(raw,rows):
    rejected(lambda:parse(raw.rstrip()+'\n'+raw.splitlines()[0]))
    rejected(lambda:parse('\n'.join(raw.splitlines()[1:])))
    for index,value in ((1,'9'),(6,'nan'),(1,'0.5')):
        lines=raw.splitlines();parts=lines[0].split();parts[index]=value;lines[0]=' '.join(parts)
        rejected(lambda:parse('\n'.join(lines)))
    witnesses=[('f1_y',100),('f2_y',100),('t1_x',50),('t2_x',50),('first_motor',65),('second_motor',45),
               ('first_anchor',1),('second_axis',1),('p2_z',0),('q2_w',0),('bv2_y',1),('second_speed',1),('first_angle',1)]
    for field,value in witnesses:
        altered={key:row.copy() for key,row in rows.items()};altered[0,0,60,1,1][field]=value
        rejected(lambda:mechanics(altered))
    altered={key:row.copy() for key,row in rows.items()}
    for key in CASES:
        if key[0]==1:altered[key]=rows[(0,*key[1:])].copy()
    rejected(lambda:mechanics(altered))
    return 6+len(witnesses)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);options=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(options.archive)
    record=dict(schema=1,fixture='spatial-hinges-v1',oracle_revision=REFERENCE,archive_sha256=digest,host=platform.platform(),bounds=BOUNDS,phase_parity=False,modes={})
    for mode in ('Debug','Release'):
        oracle=build_oracle(source,mode,HERE/'SpatialHingesOracle.cpp','spatial-hinges-oracle')
        binary=build_silex(mode,'SpatialHinges.sx','spatial-hinges',True)
        evidence={};rows={}
        for engine,exe in [('silex',binary),('jolt',oracle)]:
            raw=checked([str(exe)]);(BUILD/f'spatial-hinges-{engine}-{mode.lower()}.txt').write_text(raw)
            rows[engine]=parse(raw);evidence[engine]=dict(mechanics=mechanics(rows[engine]),corrupt_witnesses_rejected=self_test(raw,rows[engine]),observations=len(rows[engine]),output_sha256=hashlib.sha256(raw.encode()).hexdigest())
        evidence['measured_phase_differences']={field:max(abs(rows['silex'][key][field]-rows['jolt'][key][field]) for key in CASES) for field in ('first_angle','second_angle','second_speed','first_motor','second_motor','t1_x','t2_x')}
        record['modes'][mode]=evidence;(BUILD/'spatial-hinges-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: 2880 observations per engine; spatial balances and final weights green; 19 corrupt witnesses rejected per engine',flush=True)


if __name__=='__main__':main()
