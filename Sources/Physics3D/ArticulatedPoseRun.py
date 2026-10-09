#!/usr/bin/env python3
"""Qualify a loaded swing/twist shoulder with a motorized hinge elbow."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from SpatialHingesRun import add, sub, mul, dot, norm, cross, vector, rotation, rotate, momentum
from LoadedSwingTwistRun import BASE, FRAME, conjugate, product, distance, target

FIELDS = [name+'_'+c for name in ('bp1','bq1','bv1','bw1','bp2','bq2','bv2','bw2',
          'p1','q1','v1','w1','p2','q2','v2','w2','f1','t1','f2','t2','m','o','a','e1','e2')
          for c in ('xyzw' if name in ('bq1','bq2','q1','q2','o') else 'xyz')]
FIELDS += ['angle','speed','motor']
CASES = {(mass,rate,side,step) for mass in (1,2) for rate in (60,120)
         for side in (-1,1) for step in range(1,rate*12+1)}
BOUNDS = dict(linear_impulse=1e-5,spin_impulse=.001,angular_impulse=.003,
              geometry=.005,motor_projection=.02,final_speed=.003,final_force=.05,
              final_torque=.05,servo_equilibrium=.05)
PARITY = dict(orientation=.005,elbow=.005,speed=.003,force=.05,torque=.05)


def parse(raw):
    rows={}
    for line in raw.splitlines():
        parts=line.split()
        if len(parts)!=len(FIELDS)+5 or parts[0]!='articulatedpose':fail('invalid articulated pose row')
        try:
            key=tuple(map(int,parts[1:5]));values=tuple(map(float,parts[5:]))
        except ValueError:fail('invalid articulated pose number')
        if key not in CASES or key in rows or not all(map(math.isfinite,values)):fail('invalid articulated pose observation')
        rows[key]=dict(zip(FIELDS,values))
    if set(rows)!=CASES:fail('missing articulated pose observations')
    return rows


def mechanics(rows, single_frame_spin=False):
    worst={name:0.0 for name in BOUNDS};cumulative={};equilibria=[];peak_cumulative=0.0
    for key,row in sorted(rows.items()):
        mass,rate,side,step=key;recipe=key[:3];dt=1/rate
        upper=(.5,.2,.4*side);elbow=(.5,-.2,.15*side);lower=(.35,.1,-.3*side)
        previous=rows.get((*recipe,step-1))
        for name in ('p1','q1','v1','w1','p2','q2','v2','w2'):
            initial={'p1':rotate(BASE,upper),'p2':rotate(BASE,add(add(upper,elbow),lower)),
                     'q1':BASE,'q2':BASE}.get(name,(0,0,0))
            read=rotation if name.startswith('q') else vector
            expected=read(previous,name) if previous else initial
            if norm(sub(read(row,'b'+name),expected))>3e-6:fail(f'articulated pose state discontinuity: {key} {name}')
        q1,q2,bq1,bq2,o=(rotation(row,n) for n in ('q1','q2','bq1','bq2','o'))
        if any(abs(norm(v)-1)>2e-5 for v in (q1,q2,bq1,bq2,o)):fail('articulated pose quaternion not unit')
        p1,p2,bp1,bp2,v1,v2,bv1,bv2,w1,w2,bw1,bw2,f1,f2,t1,t2,m,a,e1,e2=(
            vector(row,n) for n in ('p1','p2','bp1','bp2','v1','v2','bv1','bv2','w1','w2',
                                    'bw1','bw2','f1','f2','t1','t2','m','a','e1','e2'))
        axis=rotate(q1,(0,0,1));other_axis=rotate(q2,(0,0,1))
        first_normal=rotate(q1,(1,0,0));second_normal=rotate(q2,(1,0,0))
        elbow_angle=math.atan2(dot(axis,cross(first_normal,second_normal)),dot(first_normal,second_normal))
        if abs(row['angle']-elbow_angle)>1e-5:fail('articulated pose elbow angle observable differs')
        if abs(row['speed']-dot(axis,sub(w2,w1)))>1e-5:fail('articulated pose elbow speed observable differs')
        if distance(o,product(conjugate(product(BASE,FRAME)),product(q1,FRAME)))>1e-5:fail('articulated pose shoulder orientation differs')
        if norm(sub(a,rotate(conjugate(product(q1,FRAME)),w1)))>1e-5:fail('articulated pose shoulder speed differs')
        expected_e1=sub(p1,rotate(q1,upper))
        expected_e2=sub(sub(p2,rotate(q2,lower)),add(p1,rotate(q1,elbow)))
        if max(norm(sub(e1,expected_e1)),norm(sub(e2,expected_e2)))>3e-6:fail('articulated pose anchor observable differs')
        if max(map(abs,m))>60.0001 or abs(row['motor'])>40.0001:fail('articulated pose motor budget')
        twist_length=math.hypot(o[0],o[3]);twist=(o[0]/twist_length,0,0,o[3]/twist_length)
        swing=product(o,conjugate(twist))
        if abs(2*math.atan2(twist[0],twist[3]))>.805 or norm(swing[1:3])>math.sin(.4)+1e-5 or abs(row['angle'])>.805:fail('articulated pose angular limits')
        g1=(0,-2*9.81,0);g2=(0,-mass*9.81,0)
        linear=max(norm(sub(mul(sub(v1,bv1),2),mul(add(sub(f1,f2),g1),dt))),
                   norm(sub(mul(sub(v2,bv2),mass),mul(add(f2,g2),dt))))
        before=add(momentum(bp1,bv1,bw1,2,.4),momentum(bp2,bv2,bw2,mass,.2))
        after=add(momentum(p1,v1,w1,2,.4),momentum(p2,v2,w2,mass,.2))
        residual=sub(sub(after,before),mul(add(t1,add(cross(bp1,g1),cross(bp2,g2))),dt))
        cumulative[recipe]=add(cumulative.get(recipe,(0,0,0)),residual)
        peak_cumulative=max(peak_cumulative,norm(cumulative[recipe]))
        errors=dict(linear_impulse=linear,angular_impulse=norm(residual),
                    geometry=max(norm(e1),norm(e2),math.atan2(norm(cross(axis,other_axis)),dot(axis,other_axis))),
                    motor_projection=max(norm(sub(t1,rotate(product(bq1,FRAME),m))),
                                         abs(dot(t2,rotate(bq1,(0,0,1)))-row['motor'])))
        if single_frame_spin:
            spin1=mul(sub(w1,bw1),.4);spin2=mul(sub(w2,bw2),.2)
            expected1=mul(add(sub(t1,t2),sub(cross(rotate(bq1,mul(upper,-1)),f1),cross(rotate(bq1,elbow),f2))),dt)
            expected2=mul(add(t2,cross(rotate(bq2,mul(lower,-1)),f2)),dt)
            errors['spin_impulse']=max(norm(sub(spin1,expected1)),norm(sub(spin2,expected2)))
        if step in (rate*4,rate*8,rate*12):
            direction=side if step==rate*4 else (-side if step==rate*8 else 0)
            diff=product(conjugate(o),target(direction))
            if diff[3]<0:diff=mul(diff,-1)
            errors.update(final_speed=max(norm(v1),norm(v2),norm(w1),norm(w2)),
                          final_force=max(norm(add(f1,add(g1,g2))),norm(add(f2,g2))),
                          final_torque=max(norm(add(t1,add(cross(p1,g1),cross(p2,g2)))),
                                           norm(add(t2,cross(rotate(q2,mul(lower,-1)),f2)))),
                          servo_equilibrium=max(norm(sub(m,mul(diff[:3],240))),
                                                abs(row['motor']-80*(.35*direction-row['angle']))))
            equilibria.append(dict(key=key,shoulder=o,elbow=row['angle'],force1=f1,force2=f2,torque1=t1,torque2=t2))
        for name,error in errors.items():
            worst[name]=max(worst[name],error)
            if error>BOUNDS[name]:fail(f'articulated pose {name} exceeds bound at {key}: {error}')
    for mass in (1,2):
        for rate in (60,120):
            for side in (-1,1):
                first=rows[mass,rate,side,rate*4];second=rows[mass,rate,side,rate*8]
                if distance(rotation(first,'o'),rotation(second,'o'))<.5 or abs(first['angle']-second['angle'])<.5:fail('articulated pose inversion lost')
    if not single_frame_spin:worst.pop('spin_impulse')
    return dict(worst=worst,equilibria=equilibria,single_frame_spin_qualified=single_frame_spin,
                measured_cumulative_world_residual=peak_cumulative)


def compare(actual,reference):
    steady={name:0.0 for name in PARITY};transient={name:0.0 for name in PARITY}
    for key in CASES:
        a,b=actual[key],reference[key]
        errors=dict(orientation=distance(rotation(a,'o'),rotation(b,'o')),elbow=abs(a['angle']-b['angle']),
                    speed=max(norm(sub(vector(a,n),vector(b,n))) for n in ('w1','w2')),
                    force=max(norm(sub(vector(a,n),vector(b,n))) for n in ('f1','f2')),
                    torque=max(norm(sub(vector(a,n),vector(b,n))) for n in ('t1','t2')))
        for name,error in errors.items():
            transient[name]=max(transient[name],error)
            if key[3] in (key[1]*4,key[1]*8,key[1]*12):
                steady[name]=max(steady[name],error)
                if error>PARITY[name]:fail(f'articulated pose steady parity {name} at {key}: {error}')
    return dict(steady=steady,measured_transient_differences=transient)


def rejected(action):
    try:action()
    except ValueError:return
    fail('articulated pose guard accepted corrupt witness')


def self_test(raw,rows,single_frame_spin):
    lines=raw.splitlines()
    rejected(lambda:parse(raw+'\n'+lines[0]));rejected(lambda:parse('\n'.join(lines[1:])))
    for index,value in ((1,'9'),(1,'1.5'),(5,'nan')):
        altered=lines.copy();parts=altered[0].split();parts[index]=value;altered[0]=' '.join(parts)
        rejected(lambda:parse('\n'.join(altered)))
    for field in ('f1_x','f2_x','t1_x','t2_x','m_x','bp1_x','bp2_x','q1_w','q2_w','a_x','e1_x','e2_x','o_w','w1_x','w2_x','angle','speed','motor'):
        altered={k:r.copy() for k,r in rows.items()};altered[1,60,-1,1][field]+=1
        rejected(lambda:mechanics(altered,single_frame_spin))
    for field in ('angle','o_y','f2_x','t2_x','w2_x'):
        altered={k:r.copy() for k,r in rows.items()};altered[1,60,-1,240][field]+=.1
        rejected(lambda:compare(altered,rows))
    return 28


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path)
    parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='articulated-pose-shoulder-elbow-v1',oracle_revision=REFERENCE,
                archive_sha256=digest,host=platform.platform(),bounds=BOUNDS,steady_parity_bounds=PARITY,
                phase_parity=False,spin_scope='Jolt: per-body spin with pre-pose lever; Silex: separate split-phase proof required. Cumulative uncorrected world residual is measured, not a conservation gate.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'ArticulatedPoseOracle.cpp','articulated-pose-oracle')
        binary=build_silex(mode,'ArticulatedPose.sx','articulated-pose-silex',True)
        rows={};evidence={}
        for engine,exe in (('silex',binary),('jolt',oracle)):
            raw=checked([str(exe)]);(BUILD/f'articulated-pose-{engine}-{mode.lower()}.txt').write_text(raw)
            rows[engine]=parse(raw);evidence[engine]=dict(mechanics=mechanics(rows[engine],engine=='jolt'),
                corrupt_witnesses_rejected=self_test(raw,rows[engine],engine=='jolt'),observations=len(rows[engine]),
                output_sha256=hashlib.sha256(raw.encode()).hexdigest())
        evidence['comparison']=compare(rows['silex'],rows['jolt']);record['modes'][mode]=evidence
        (BUILD/'articulated-pose-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: {len(CASES)} observations per engine; shoulder/elbow mechanics and equilibria green',flush=True)


if __name__=='__main__':main()
