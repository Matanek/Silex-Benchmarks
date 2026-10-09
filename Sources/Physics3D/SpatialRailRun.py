#!/usr/bin/env python3
"""Qualify a spatial hinge and vertical slider under load, contact and reversal."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from SpatialHingesRun import FIELDS as BASE_FIELDS, CASES, add, sub, mul, dot, norm, cross, vector, rotation, rotate, angle, momentum

FIELDS=[('second_position' if f=='second_angle' else f) for f in BASE_FIELDS]+['ix','iy','iz','contacts','penetration','measured','cp_x','cp_y','cp_z','cr_x','cr_y','cr_z','points']
BOUNDS=dict(linear_impulse=0.00001,spin_impulse=0.001,angular_impulse=0.003,
            cumulative_angular_impulse=0.03,geometry=0.005,root_angle=0.02,
            final_speed=0.005,final_force=0.05,final_torque=0.05,motor_projection=0.02,penetration=0.003)


def parse(raw,engine):
    rows={}
    for line in raw.splitlines():
        parts=line.split()
        if len(parts)!=93 or parts[0]!='spatialrail':fail('invalid spatial rail row')
        try:
            key_values=list(map(float,parts[1:6]));values=list(map(float,parts[6:]))
            if not all(math.isfinite(v) and v.is_integer() for v in key_values):fail('invalid spatial rail key')
            key=tuple(map(int,key_values))
        except ValueError:fail('invalid spatial rail number')
        if key not in CASES or key in rows or not all(map(math.isfinite,values)):fail('invalid spatial rail observation')
        row=dict(zip(FIELDS,values))
        if row['contacts'] not in (0,1) or row['measured']!=int(engine=='silex') or row['points']!=row['contacts']:fail('spatial rail provenance differs')
        rows[key]=row
    if set(rows)!=CASES:fail('missing spatial rail observations')
    return rows


def mechanics(rows,engine):
    worst={name:0.0 for name in BOUNDS};recipes={};cumulative={}
    for key,row in sorted(rows.items()):
        floor,mass_id,rate,side,step=key;mass=mass_id+1;recipe=key[:4];delta=1/rate
        previous=rows.get((*recipe,step-1))
        for name in ('p1','v1','w1','q1','p2','v2','w2','q2'):
            components='xyzw' if 'q' in name else 'xyz'
            initial={'p1':(.5,0,0),'p2':(1,0,.8*side),'q1':(0,0,0,1),'q2':(0,0,0,1)}.get(name,(0,0,0))
            expected=tuple(previous[name+'_'+c] for c in components) if previous else initial
            actual=tuple(row['b'+name+'_'+c] for c in components)
            if norm(sub(actual,expected))>0.000003:fail('spatial rail state discontinuity')
        for name in ('q1','q2','bq1','bq2'):
            if abs(norm(rotation(row,name))-1)>0.00002:fail('spatial rail quaternion is not unit')
        p1,v1,w1,p2,v2,w2=(vector(row,n) for n in ('p1','v1','w1','p2','v2','w2'))
        bp1,bv1,bw1,bp2,bv2,bw2=(vector(row,n) for n in ('bp1','bv1','bw1','bp2','bv2','bw2'))
        q1,q2,bq1,bq2=(rotation(row,n) for n in ('q1','q2','bq1','bq2'))
        f1,t1,f2,t2=(vector(row,n) for n in ('f1','t1','f2','t2'));contact=(row['ix'],row['iy'],row['iz'])
        gravity1=(0,-2*9.81,0);gravity2=(0,-mass*9.81,0)
        point=vector(row,'cp');contact_lever=vector(row,'cr');spin_contact=cross(contact_lever,contact)
        if row['contacts']==0 and (norm(point)>0 or norm(contact_lever)>0):fail('spatial point without contact')
        if row['contacts']:
            if engine=='jolt' and norm(sub(sub(point,bp2),contact_lever))>0.000003:fail('Jolt contact lever observable differs')
            if engine=='silex' and (math.hypot(contact_lever[0],contact_lever[2])>0.000001 or abs(contact_lever[1]+point[1]+.37)>0.000003):fail('Silex sphere-plane contact lever differs')
        r1=rotate(bq1,(-.5,0,0));r12=sub(bp2,bp1);r2=(0,0,0)
        arm_change=sub(mul(sub(v1,bv1),2),mul(add(sub(f1,f2),gravity1),delta))
        payload_change=sub(mul(sub(v2,bv2),mass),mul(add(f2,gravity2),delta))
        linear=max(norm(arm_change),math.hypot(payload_change[0],payload_change[2]))
        if engine=='silex' or row['contacts']==0:linear=max(linear,norm(sub(payload_change,contact)))
        elif abs(payload_change[1]-row['iy'])>0.000002:fail('Jolt inferred contact observable differs')
        if math.hypot(row['ix'],row['iz'])>BOUNDS['linear_impulse'] or row['iy']< -BOUNDS['linear_impulse']:fail('spatial rail direction differs')
        if row['contacts']==0 and norm(contact)>BOUNDS['linear_impulse']:fail('spatial impulse without contact')
        if floor==0 and row['contacts']!=0:fail('unexpected spatial rail')
        spin=max(norm(sub(mul(sub(w1,bw1),.4),mul(add(sub(t1,t2),sub(cross(r1,f1),cross(r12,f2))),delta))),
                 norm(sub(sub(mul(sub(w2,bw2),.2),mul(add(t2,cross(r2,f2)),delta)),spin_contact)))
        before=add(momentum(bp1,bv1,bw1,2,.4),momentum(bp2,bv2,bw2,mass,.2))
        after=add(momentum(p1,v1,w1,2,.4),momentum(p2,v2,w2,mass,.2))
        external=add(t1,add(cross(bp1,gravity1),cross(bp2,gravity2)))
        residual=sub(sub(sub(after,before),mul(external,delta)),cross(point,contact))
        cumulative[recipe]=add(cumulative.get(recipe,(0,0,0)),residual)
        axis1=rotate(q1,(0,0,1));axis2=rotate(q1,(0,1,0))
        offset=sub(sub(p2,p1),rotate(q1,(.5,0,.8*side)))
        anchors=(norm(add(p1,rotate(q1,(-.5,0,0)))),norm(sub(offset,mul(axis2,dot(offset,axis2)))))
        relative_vector=sub(sub(mul(q2[:3],q1[3]),mul(q1[:3],q2[3])),cross(q2[:3],q1[:3]))
        axes=(angle((0,0,1),axis1),2*math.atan2(norm(relative_vector),abs(dot(q1,q2))))
        for joint,anchor,axis in zip(('first','second'),anchors,axes):
            if row[joint+'_anchor']<0 or row[joint+'_axis']<0:fail('negative spatial rail geometry')
            if abs(anchor-row[joint+'_anchor'])>0.000003 or abs(axis-row[joint+'_axis'])>0.000003:fail('spatial rail geometry observable differs')
        normal=rotate(q1,(1,0,0))
        positions=(math.atan2(normal[1],normal[0]),dot(offset,axis2))
        if abs(positions[0]-row['first_angle'])>0.00001 or abs(positions[1]-row['second_position'])>0.00001:fail('spatial rail position observable differs')
        speed=dot(sub(sub(v2,v1),cross(w1,sub(p2,p1))),axis2)
        if abs(w1[2]-row['first_speed'])>0.00001 or abs(speed-row['second_speed'])>0.00001:fail('spatial rail speed observable differs')
        if abs(row['first_motor'])>60.0001 or abs(row['second_motor'])>40.0001:fail('spatial rail motor budget')
        if row['penetration']<0 or abs(row['penetration']-max(0,-.07-p2[1]))>0.000003:fail('spatial rail penetration observable differs')
        errors=dict(linear_impulse=linear,spin_impulse=spin,angular_impulse=norm(residual),cumulative_angular_impulse=norm(cumulative[recipe]),
                    geometry=max(*anchors,*axes),root_angle=abs(row['first_angle']),
                    motor_projection=max(abs(t1[2]-row['first_motor']),abs(dot(f2,rotate(bq1,(0,1,0)))-row['second_motor'])))
        if floor:errors['penetration']=row['penetration']
        if step==rate*2:
            if row['contacts'] or norm(contact)>BOUNDS['linear_impulse']:fail('spatial rail did not release')
            expected1=mul(add(cross(p1,gravity1),cross(p2,gravity2)),-1)
            expected2=(0,0,0)
            errors.update(final_speed=max(norm(v1),norm(v2),norm(w1),norm(w2)),
                          final_force=max(norm(add(f1,add(gravity1,gravity2))),norm(add(f2,gravity2))),
                          final_torque=max(norm(sub(t1,expected1)),norm(sub(t2,expected2))))
        for name,error in errors.items():
            worst[name]=max(worst[name],error)
            if error>BOUNDS[name]:fail(f'spatial rail {name} exceeds bound at {key}: {error}')
        recipes.setdefault(recipe,[]).append(row)
    summaries=[]
    for key,data in sorted(recipes.items()):
        expected_depth=.07 if key[0] else 2/15
        if abs(min(r['second_position'] for r in data)+expected_depth)>BOUNDS['geometry'] or max(r['second_speed'] for r in data)<.15 or min(r['second_speed'] for r in data)>-.15:fail('spatial rail geometric descent or reversal lost')
        if key[0] and (not any(r['contacts'] for r in data) or max(r['iy'] for r in data)<.1):fail('spatial floor never produced a contact')
        summaries.append(dict(key=key,final_position=data[-1]['second_position'],peak_position=max(abs(r['second_position']) for r in data),
                              contact_steps=sum(r['contacts'] for r in data),peak_contact_impulse=max(r['iy'] for r in data)))
    return dict(worst=worst,recipes=summaries,normal_impulse='measured' if engine=='silex' else 'inferred; no independent normal or contact angular balance claim')


def rejected(action):
    try:action()
    except ValueError:return
    fail('spatial rail guard accepted corrupt witness')


def self_test(raw,rows,engine):
    rejected(lambda:parse(raw.rstrip()+'\n'+raw.splitlines()[0],engine))
    rejected(lambda:parse('\n'.join(raw.splitlines()[1:]),engine))
    for index,value in ((1,'9'),(6,'nan'),(1,'0.5'),(85,str(1-int(engine=='silex'))),(83,'2')):
        lines=raw.splitlines();parts=lines[0].split();parts[index]=value;lines[0]=' '.join(parts)
        rejected(lambda:parse('\n'.join(lines),engine))
    witnesses=[('f1_y',100),('f2_y',100),('t1_x',50),('t2_x',50),('first_motor',65),('second_motor',45),
               ('first_anchor',1),('second_axis',1),('p2_z',0),('q2_w',0),('bv2_y',1),('second_speed',1),('first_angle',1),
               ('penetration',1),('iy',-1),('ix',1)]
    for field,value in witnesses:
        altered={key:row.copy() for key,row in rows.items()};altered[0,0,60,1,1][field]=value
        rejected(lambda:mechanics(altered,engine))
    contact_key=next(key for key,row in rows.items() if row['contacts'] and row['iy']>.1)
    for field in ('cp_z','cr_z','points'):
        altered={key:row.copy() for key,row in rows.items()};altered[contact_key][field]+=1
        rejected(lambda:mechanics(altered,engine) if field!='points' else parse('\n'.join('spatialrail '+' '.join(map(str,(*key,*(row[f] for f in FIELDS)))) for key,row in altered.items()),engine))
    altered={key:row.copy() for key,row in rows.items()}
    for row in altered.values():
        for field in ('contacts','ix','iy','iz','cp_x','cp_y','cp_z','cr_x','cr_y','cr_z','points'):row[field]=0
    rejected(lambda:mechanics(altered,engine))
    held={}
    for key in CASES:
        mass=key[1]+1;side=key[3];row={field:0.0 for field in FIELDS}
        for prefix in ('','b'):
            row[prefix+'p1_x']=.5;row[prefix+'p2_x']=1;row[prefix+'p2_z']=.8*side
            row[prefix+'q1_w']=row[prefix+'q2_w']=1
        row.update(f1_y=(mass+2)*9.81,f2_y=mass*9.81,t1_x=-mass*9.81*.8*side,t1_z=(mass+1)*9.81,
                   t2_x=0,first_motor=(mass+1)*9.81,second_motor=mass*9.81,measured=int(engine=='silex'))
        held[key]=row
    rejected(lambda:mechanics(held,engine))
    return 12+len(witnesses)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);options=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(options.archive)
    record=dict(schema=1,fixture='spatial-hinge-slider-v1',oracle_revision=REFERENCE,archive_sha256=digest,host=platform.platform(),bounds=BOUNDS,phase_parity=False,modes={})
    for mode in ('Debug','Release'):
        oracle=build_oracle(source,mode,HERE/'SpatialRailOracle.cpp','spatial-rail-oracle')
        binary=build_silex(mode,'SpatialRail.sx','spatial-rail',True)
        evidence={};rows={}
        for engine,exe in [('silex',binary),('jolt',oracle)]:
            raw=checked([str(exe)]);(BUILD/f'spatial-rail-{engine}-{mode.lower()}.txt').write_text(raw)
            rows[engine]=parse(raw,engine);evidence[engine]=dict(mechanics=mechanics(rows[engine],engine),corrupt_witnesses_rejected=self_test(raw,rows[engine],engine),observations=len(rows[engine]),output_sha256=hashlib.sha256(raw.encode()).hexdigest())
        evidence['measured_phase_differences']={field:max(abs(rows['silex'][key][field]-rows['jolt'][key][field]) for key in CASES) for field in ('second_position','second_speed','first_motor','second_motor','t1_x','t2_x','iy')}
        record['modes'][mode]=evidence;(BUILD/'spatial-rail-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: 2880 observations per engine; spatial rail and release green; 28 corrupt witnesses rejected per engine',flush=True)


if __name__=='__main__':main()
