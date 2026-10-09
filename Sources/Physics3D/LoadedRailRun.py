#!/usr/bin/env python3
"""Qualify a hinged rail under gravity, with optional axial wall contact."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS='position speed rx ry rvx rvy rw x y vx vy w torque hfx hfy sfx sfy motor spin_torque hinge_anchor hinge_axis slider_anchor slider_angle ax ay bvx bvy brvx brvy bw ix iy contacts penetration angle measured'.split()
CASES={(kind,mass,rate,direction,step) for kind in (0,1) for mass in (0,1)
       for rate in (60,120) for direction in (-1,1) for step in range(1,rate*2+1)}
BOUNDS=dict(impulse=0.00001,spin_impulse=0.00001,geometry=0.003,angle=0.02,
            final_speed=0.005,final_gravity_force=0.05,final_gravity_torque=0.05,penetration=0.003)


def parse(raw,engine):
    rows={}
    for line in raw.splitlines():
        parts=line.split()
        if len(parts)!=42 or parts[0]!='loadedrail':fail('invalid loaded rail row')
        try:
            numbers=list(map(float,parts[1:6]));values=list(map(float,parts[6:]))
            if not all(math.isfinite(n) and n.is_integer() for n in numbers):fail('invalid loaded rail key')
            key=tuple(map(int,numbers))
        except ValueError:fail('invalid loaded rail number')
        if key not in CASES or key in rows or not all(map(math.isfinite,values)):fail('invalid loaded rail observation')
        row=dict(zip(FIELDS,values))
        if row['contacts'] not in (0,1) or row['measured']!=int(engine=='silex'):fail('contact provenance differs')
        rows[key]=row
    if set(rows)!=CASES:fail('missing loaded rail observations')
    return rows


def mechanics(rows,engine):
    worst={name:0.0 for name in BOUNDS};recipes={}
    for key,row in sorted(rows.items()):
        kind,mass_id,rate,direction,step=key;mass=mass_id+1;recipe=key[:4]
        previous=rows.get((*recipe,step-1))
        expected=tuple(previous[name] for name in ('vx','vy','rvx','rvy','w')) if previous else (0,0,0,0,0)
        actual=tuple(row[name] for name in ('bvx','bvy','brvx','brvy','bw'))
        if max(abs(a-b) for a,b in zip(actual,expected))>0.000002:fail('loaded rail state discontinuity')
        cart_x=mass*(row['vx']-row['bvx'])-row['sfx']/rate
        cart_y=mass*(row['vy']-row['bvy'])-row['sfy']/rate+mass*9.81/rate
        rail_x=2*(row['rvx']-row['brvx'])-(row['hfx']-row['sfx'])/rate
        rail_y=2*(row['rvy']-row['brvy'])-(row['hfy']-row['sfy'])/rate+2*9.81/rate
        # Only Silex publishes a measured post-solve normal impulse. Jolt's X
        # residual is retained as inference, never used to validate itself.
        impulse=max(abs(cart_y),math.hypot(rail_x,rail_y))
        if engine=='silex':impulse=max(impulse,math.hypot(cart_x-row['ix'],cart_y-row['iy']))
        elif abs(cart_x-row['ix'])>0.000002 or abs(cart_y-row['iy'])>0.000002:fail('Jolt inferred contact observable differs')
        if abs(row['iy'])>BOUNDS['impulse'] or direction*row['ix']>BOUNDS['impulse']:fail('loaded rail contact direction differs')
        if (kind==0 or row['contacts']==0) and abs(row['ix'])>BOUNDS['impulse']:fail('contact impulse without contact')
        if kind==0 and row['contacts']!=0:fail('unexpected contact in free recipe')
        errors=dict(impulse=impulse,spin_impulse=abs(0.2*(row['w']-row['bw'])-row['spin_torque']/rate),
                    geometry=max(row[name] for name in ('hinge_anchor','hinge_axis','slider_anchor','slider_angle')),
                    angle=abs(row['angle']))
        if kind==1:errors['penetration']=row['penetration']
        if any(row[name]<0 for name in ('hinge_anchor','hinge_axis','slider_anchor','slider_angle','penetration')):fail('negative loaded rail error')
        if abs(row['penetration']-max(0,direction*row['x']+0.25-1.4))>0.000002:fail('loaded rail penetration observable differs')
        if abs(row['torque'])>30.0001 or abs(row['motor'])>2.0001:fail('loaded rail motor budget')
        axis=(row['ax'],row['ay']);offset=(row['x']-row['rx'],row['y']-row['ry'])
        if abs(math.hypot(*axis)-1)>0.00001 or abs(math.atan2(axis[1],axis[0])-row['angle'])>0.00001:fail('loaded rail frame differs')
        if math.hypot(offset[0]-row['position']*axis[0],offset[1]-row['position']*axis[1])>BOUNDS['geometry']:fail('loaded rail position geometry differs')
        speed=(row['vx']-row['rvx']+row['rw']*offset[1])*axis[0]+(row['vy']-row['rvy']-row['rw']*offset[0])*axis[1]
        if abs(speed-row['speed'])>0.00001:fail('loaded rail radial speed differs')
        if step==rate*2:
            errors.update(final_speed=max(abs(row['speed']),abs(row['rw']),abs(row['w']),math.hypot(row['vx'],row['vy']),math.hypot(row['rvx'],row['rvy'])),
                          final_gravity_force=max(abs(row['sfy']-mass*9.81),abs(row['hfy']-(mass+2)*9.81)),
                          final_gravity_torque=abs(row['torque']-9.81*(mass*row['x']+2*row['rx'])))
        for name,error in errors.items():
            worst[name]=max(worst[name],error)
            if error>BOUNDS[name]:fail('loaded rail '+name+' exceeds bound')
        recipes.setdefault(recipe,[]).append(row)
    summaries=[]
    for recipe,data in sorted(recipes.items()):
        kind,mass_id,rate,direction=recipe;last=data[-1]
        if max(direction*r['position'] for r in data)<1.08 or min(direction*r['speed'] for r in data)>-0.01:fail('loaded rail travel or reversal lost')
        if kind==1:
            if not any(r['contacts'] for r in data) or max(abs(r['ix']) for r in data)<0.1:fail('wall recipe never produced a contact')
            if last['contacts'] or direction*last['x']>1.1:fail('wall contact did not release')
        summaries.append(dict(key=recipe,final_position=last['position'],final_torque=last['torque'],
                              contact_steps=sum(r['contacts'] for r in data),peak_contact_impulse=max(abs(r['ix']) for r in data)))
    return dict(worst=worst,recipes=summaries,normal_impulse='measured' if engine=='silex' else 'inferred; no independent normal balance claim')


def rejected(action):
    try:action()
    except ValueError:return
    fail('loaded rail guard accepted corrupt witness')


def self_test(raw,rows,engine):
    rejected(lambda:parse(raw+'\n'+raw.splitlines()[0],engine))
    rejected(lambda:parse('\n'.join(raw.splitlines()[1:]),engine))
    for index,value in ((1,'9'),(6,'nan'),(1,'0.5')):
        lines=raw.splitlines();parts=lines[0].split();parts[index]=value;lines[0]=' '.join(parts)
        rejected(lambda:parse('\n'.join(lines),engine))
    witnesses=[('sfy',100),('hfy',100),('spin_torque',5),('torque',35),('motor',3),
               ('hinge_anchor',1),('hinge_axis',1),('slider_anchor',1),('slider_angle',1),
               ('ax',0),('speed',1),('bvy',1),('penetration',1),('iy',1)]
    for field,value in witnesses:
        altered={key:row.copy() for key,row in rows.items()};altered[0,0,60,1,1][field]=value
        rejected(lambda:mechanics(altered,engine))
    parts=raw.splitlines()[0].split();parts[-1]=str(1-int(engine=='silex'))
    rejected(lambda:parse('\n'.join([' '.join(parts),*raw.splitlines()[1:]]),engine))
    altered={key:row.copy() for key,row in rows.items()}
    for row in altered.values():row['contacts']=row['ix']=row['iy']=0
    rejected(lambda:mechanics(altered,engine))
    return 7+len(witnesses)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);options=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(options.archive)
    record=dict(schema=1,fixture='loaded-rail-contact-v1',oracle_revision=REFERENCE,archive_sha256=digest,
                host=platform.platform(),bounds=BOUNDS,phase_parity=False,observations_per_engine=len(CASES),modes={})
    for mode in ('Debug','Release'):
        oracle=build_oracle(source,mode,HERE/'LoadedRailOracle.cpp','loaded-rail-oracle')
        binary=build_silex(mode,'LoadedRail.sx','loaded-rail',True)
        outputs={engine:checked([str(exe)]) for engine,exe in [('silex',binary),('jolt',oracle)]}
        rows={engine:parse(raw,engine) for engine,raw in outputs.items()}
        evidence=dict(mechanics={engine:mechanics(data,engine) for engine,data in rows.items()},
                      corrupt_witnesses_rejected={engine:self_test(outputs[engine],data,engine) for engine,data in rows.items()},
                      measured_phase_differences={field:max(abs(rows['silex'][key][field]-rows['jolt'][key][field]) for key in CASES) for field in ('position','speed','angle','torque','motor','sfy','hfy')})
        for engine,raw in outputs.items():
            (BUILD/f'loaded-rail-{engine}-{mode.lower()}.txt').write_text(raw)
            evidence[engine+'_output_sha256']=hashlib.sha256(raw.encode()).hexdigest()
        record['modes'][mode]=evidence;(BUILD/'loaded-rail-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: {len(CASES)} observations per engine; gravity reactions, budgets and real contact/release green; 21 corrupt witnesses rejected per engine',flush=True)


if __name__=='__main__':main()
