#!/usr/bin/env python3
"""Qualify simultaneous, offset swing/twist servos under gravity."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from SpatialHingesRun import add, sub, mul, dot, norm, cross, vector, rotation, rotate, momentum

FIELDS = [name + '_' + c for name in ('bp','bq','bv','bw','p','q','v','w','f','t','m','o','a','e')
          for c in ('xyzw' if name in ('bq','q','o') else 'xyz')]
CASES = {(mass,rate,side,step) for mass in (1,2) for rate in (60,120)
         for side in (-1,1) for step in range(1,rate*9+1)}
BOUNDS = dict(linear_impulse=1e-5,spin_impulse=.001,angular_impulse=.003,
              cumulative_angular_impulse=.03,anchor=.005,final_speed=.003,
              final_force=.05,final_torque=.05,motor_projection=.02,
              servo_equilibrium=.05)
PARITY = dict(orientation=.005,speed=.003,force=.05,torque=.05)


def conjugate(q): return (*mul(q[:3],-1),q[3])
def product(a,b): return (*add(add(mul(b[:3],a[3]),mul(a[:3],b[3])),cross(a[:3],b[:3])),a[3]*b[3]-dot(a[:3],b[:3]))
def axis_angle(axis,angle): return (*mul(axis,math.sin(angle/2)/norm(axis)),math.cos(angle/2))
def distance(a,b):
    d=product(conjugate(a),b)
    return 2*math.atan2(norm(d[:3]),abs(d[3]))
BASE=axis_angle((1,2,-1),.7)
FRAME=axis_angle((0,0,1),.35)


def target(direction):
    y=.1*direction;z=-.075*direction
    swing=(0,math.sin(y)*math.cos(z),math.cos(y)*math.sin(z),math.cos(y)*math.cos(z))
    return product(mul(swing,1/norm(swing)),axis_angle((1,0,0),.25*direction))


def parse(raw):
    rows={}
    for line in raw.splitlines():
        parts=line.split()
        if len(parts)!=len(FIELDS)+5 or parts[0]!='loadedswing':fail('invalid loaded swing row')
        try:
            key=tuple(map(int,parts[1:5]));values=tuple(map(float,parts[5:]))
        except ValueError:fail('invalid loaded swing number')
        if key not in CASES or key in rows or not all(map(math.isfinite,values)):fail('invalid loaded swing observation')
        rows[key]=dict(zip(FIELDS,values))
    if set(rows)!=CASES:fail('missing loaded swing observations')
    return rows


def mechanics(rows, single_frame_spin=True):
    worst={name:0.0 for name in BOUNDS};cumulative={};summaries=[]
    for key,row in sorted(rows.items()):
        mass,rate,side,step=key;recipe=key[:3];dt=1/rate;lever=(.5,.2,.4*side)
        previous=rows.get((*recipe,step-1))
        for name in ('p','q','v','w'):
            initial={'p':rotate(BASE,lever),'q':BASE,'v':(0,0,0),'w':(0,0,0)}[name]
            actual=rotation(row,'bq') if name=='q' else vector(row,'b'+name)
            expected=(rotation(previous,name) if name=='q' else vector(previous,name)) if previous else initial
            if norm(sub(actual,expected))>3e-6:fail(f'loaded swing state discontinuity: {key} {name}')
        q,bq,o=(rotation(row,n) for n in ('q','bq','o'))
        if any(abs(norm(v)-1)>2e-5 for v in (q,bq,o)):fail('loaded swing quaternion not unit')
        p,bp,v,bv,w,bw,f,t,m,a,e=(vector(row,n) for n in ('p','bp','v','bv','w','bw','f','t','m','a','e'))
        expected_o=product(conjugate(product(BASE,FRAME)),product(q,FRAME))
        if distance(o,expected_o)>1e-5:fail('loaded swing orientation observable differs')
        if norm(sub(a,rotate(conjugate(product(q,FRAME)),w)))>1e-5:fail('loaded swing speed observable differs')
        if norm(sub(e,sub(p,rotate(q,lever))))>3e-6:fail('loaded swing anchor observable differs')
        if max(map(abs,m))>30.0001:fail('loaded swing motor budget')
        twist_norm=math.hypot(o[0],o[3]);twist=(o[0]/twist_norm,0,0,o[3]/twist_norm)
        swing=product(o,conjugate(twist))
        if abs(2*math.atan2(twist[0],twist[3]))>.805 or (swing[1]**2+swing[2]**2)>math.sin(.4)**2+1e-5:fail('loaded swing angular limits')
        gravity=(0,-mass*9.81,0);radius=rotate(bq,mul(lever,-1))
        linear=norm(sub(mul(sub(v,bv),mass),mul(add(f,gravity),dt)))
        spin=norm(sub(mul(sub(w,bw),.4),mul(add(t,cross(radius,f)),dt)))
        residual=sub(sub(momentum(p,v,w,mass,.4),momentum(bp,bv,bw,mass,.4)),mul(add(t,cross(bp,gravity)),dt))
        cumulative[recipe]=add(cumulative.get(recipe,(0,0,0)),residual)
        errors=dict(linear_impulse=linear,angular_impulse=norm(residual),
                    cumulative_angular_impulse=norm(cumulative[recipe]),anchor=norm(e),
                    motor_projection=norm(sub(t,rotate(product(bq,FRAME),m))))
        if single_frame_spin: errors['spin_impulse']=spin
        if step in (rate*3,rate*6,rate*9):
            direction=side if step<=rate*3 else (-side if step<=rate*6 else 0)
            diff=product(conjugate(o),target(direction))
            if diff[3]<0:diff=mul(diff,-1)
            errors.update(final_speed=max(norm(v),norm(w)),final_force=norm(add(f,gravity)),
                          final_torque=norm(add(t,cross(rotate(q,mul(lever,-1)),f))),
                          servo_equilibrium=norm(sub(m,mul(diff[:3],160))))
            summaries.append(dict(key=key,orientation=o,velocity=w,motor=m,force=f,torque=t))
        for name,error in errors.items():
            worst[name]=max(worst[name],error)
            if error>BOUNDS[name]:fail(f'loaded swing {name} exceeds bound at {key}: {error}')
    for mass in (1,2):
        for rate in (60,120):
            for side in (-1,1):
                first=rows[mass,rate,side,rate*3];second=rows[mass,rate,side,rate*6]
                if distance(rotation(first,'o'),rotation(second,'o'))<.5:fail('loaded swing inversion lost')
    if not single_frame_spin: worst.pop('spin_impulse')
    return dict(worst=worst,equilibria=summaries,single_frame_spin_qualified=single_frame_spin)


def compare(actual,reference):
    worst={name:0.0 for name in PARITY};phase={name:0.0 for name in PARITY}
    for key in CASES:
        a,b=actual[key],reference[key]
        errors=dict(orientation=distance(rotation(a,'o'),rotation(b,'o')),speed=norm(sub(vector(a,'w'),vector(b,'w'))),
                    force=norm(sub(vector(a,'f'),vector(b,'f'))),torque=norm(sub(vector(a,'t'),vector(b,'t'))))
        for name,error in errors.items():
            phase[name]=max(phase[name],error)
            if key[3] in (key[1]*3,key[1]*6,key[1]*9):
                worst[name]=max(worst[name],error)
                if error>PARITY[name]:fail(f'loaded swing steady parity {name} at {key}: {error}')
    return dict(steady=worst,measured_transient_differences=phase)


def rejected(action):
    try:action()
    except ValueError:return
    fail('loaded swing guard accepted corrupt witness')


def self_test(raw,rows,single_frame_spin):
    lines=raw.splitlines()
    rejected(lambda:parse(raw+'\n'+lines[0]));rejected(lambda:parse('\n'.join(lines[1:])))
    for index,value in ((1,'9'),(1,'1.5'),(5,'nan')):
        altered=lines.copy();parts=altered[0].split();parts[index]=value;altered[0]=' '.join(parts)
        rejected(lambda:parse('\n'.join(altered)))
    for field in ('f_x','t_x','m_x','bp_x','q_w','a_x','e_x','o_w','w_x'):
        altered={k:r.copy() for k,r in rows.items()};altered[1,60,-1,1][field]+=1
        rejected(lambda:mechanics(altered,single_frame_spin))
    altered={k:r.copy() for k,r in rows.items()};altered[1,60,-1,180]['o_y']+=.01
    rejected(lambda:compare(altered,rows))
    return 15


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path)
    parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='loaded-swing-twist-three-axis-v1',oracle_revision=REFERENCE,archive_sha256=digest,
                host=platform.platform(),bounds=BOUNDS,steady_parity_bounds=PARITY,phase_parity=False,
                spin_scope='Jolt: single lever before pose; Silex: full world angular momentum gate, separate split-phase witness required for local spin',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'LoadedSwingTwistOracle.cpp','loaded-swing-oracle')
        binary=build_silex(mode,'LoadedSwingTwist.sx','loaded-swing-silex',True)
        rows={};evidence={}
        for engine,exe in (('silex',binary),('jolt',oracle)):
            raw=checked([str(exe)]);(BUILD/f'loaded-swing-{engine}-{mode.lower()}.txt').write_text(raw)
            rows[engine]=parse(raw);evidence[engine]=dict(mechanics=mechanics(rows[engine],engine=='jolt'),
                corrupt_witnesses_rejected=self_test(raw,rows[engine],engine=='jolt'),observations=len(rows[engine]),output_sha256=hashlib.sha256(raw.encode()).hexdigest())
        evidence['comparison']=compare(rows['silex'],rows['jolt']);record['modes'][mode]=evidence
        (BUILD/'loaded-swing-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: {len(CASES)} observations per engine; loaded swing mechanics and equilibria green',flush=True)

if __name__=='__main__':main()
