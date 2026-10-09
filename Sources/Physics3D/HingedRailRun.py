#!/usr/bin/env python3
"""Qualify a dynamic hinged rail carrying a driven radial slider."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS='radius speed rx ry rvx rvy rw x y vx vy w before_L L torque hfx hfy sfx sfy motor spin_torque hinge_anchor hinge_axis slider_anchor slider_angle ax ay bvx bvy brvx brvy bw'.split()
CASES={(kind,mass,rate,direction,step) for kind in (0,1) for mass in (0,1)
       for rate in (60,120) for direction in (-1,1) for step in range(1,rate*2+1)}
BOUNDS=dict(body_impulse=0.000002,system_impulse=0.000002,spin_impulse=0.000002,
            step_angular_balance=0.0001,integrated_angular_balance=0.002,geometry=0.001,angular_speed=0.001)
BEHAVIOR=dict(outward_excursion=0.08,minimum_reverse_speed=-0.01,final_radial_speed=0.005,
              free_omega_change=0.005,final_driven_omega=0.001)


def parse(raw):
    rows={}
    for line in raw.splitlines():
        parts=line.split()
        if len(parts)!=38 or parts[0]!='assembly':fail('invalid assembly row')
        try:
            numbers=list(map(float,parts[1:6]));values=list(map(float,parts[6:]))
            if not all(math.isfinite(n) and n.is_integer() for n in numbers):fail('invalid assembly key')
            key=tuple(map(int,numbers))
        except ValueError:fail('invalid assembly number')
        if key not in CASES or key in rows or not all(map(math.isfinite,values)):fail('invalid assembly observation')
        rows[key]=dict(zip(FIELDS,values))
    if set(rows)!=CASES:fail('missing assembly observations')
    return rows


def momentum(row,mass):
    return (0.4*row['rw']+0.2*row['w']+mass*(row['x']*row['vy']-row['y']*row['vx'])
            +2*(row['rx']*row['rvy']-row['ry']*row['rvx']))


def mechanics(rows):
    worst={name:0.0 for name in BOUNDS};integrated={};recipes={}
    for key,row in sorted(rows.items()):
        kind,mass_id,rate,direction,step=key;mass=mass_id+1;recipe=key[:4]
        previous=rows.get((*recipe,step-1));initial=(0.6+mass)*0.2*direction
        before=previous['L'] if previous else initial
        expected=tuple(previous[name] for name in ('vx','vy','rvx','rvy','w')) if previous else (0,0.2*direction,0,0,0.2*direction)
        actual=tuple(row[name] for name in ('bvx','bvy','brvx','brvy','bw'))
        if max(abs(a-b) for a,b in zip(actual,expected))>0.000002 or abs(row['before_L']-before)>0.000002:fail('assembly state discontinuity')
        if abs(momentum(row,mass)-row['L'])>0.000002:fail('assembly momentum observable differs')
        integrated[recipe]=integrated.get(recipe,0)+row['torque']/rate
        errors=dict(
            body_impulse=math.hypot(mass*(row['vx']-row['bvx'])-row['sfx']/rate,mass*(row['vy']-row['bvy'])-row['sfy']/rate),
            system_impulse=math.hypot(2*(row['rvx']-row['brvx'])+mass*(row['vx']-row['bvx'])-row['hfx']/rate,2*(row['rvy']-row['brvy'])+mass*(row['vy']-row['bvy'])-row['hfy']/rate),
            spin_impulse=abs(0.2*(row['w']-row['bw'])-row['spin_torque']/rate),
            step_angular_balance=abs(row['L']-row['before_L']-row['torque']/rate),
            integrated_angular_balance=abs(row['L']-initial-integrated[recipe]),
            geometry=max(row['hinge_anchor'],row['hinge_axis'],row['slider_anchor'],row['slider_angle']),
            angular_speed=abs(row['rw']-row['w']))
        if any(row[name]<0 for name in ('hinge_anchor','hinge_axis','slider_anchor','slider_angle')):fail('negative assembly error')
        for name,error in errors.items():
            worst[name]=max(worst[name],error)
            if error>BOUNDS[name]:fail('assembly '+name+' exceeds bound')
        if abs(row['torque'])>0.4001 or abs(row['motor'])>2.0001 or (kind==0 and row['torque']!=0):fail('assembly motor budget')
        offset=(row['x']-row['rx'],row['y']-row['ry']);axis=(row['ax'],row['ay'])
        if abs(math.hypot(*axis)-1)>0.00001:fail('assembly axis differs')
        if math.hypot(offset[0]-row['radius']*axis[0],offset[1]-row['radius']*axis[1])>BOUNDS['geometry']:fail('assembly geometry differs')
        relative=(row['vx']-row['rvx']+row['rw']*offset[1],row['vy']-row['rvy']-row['rw']*offset[0])
        if abs(relative[0]*axis[0]+relative[1]*axis[1]-row['speed'])>0.00001:fail('assembly radial speed differs')
        recipes.setdefault(recipe,[]).append(row)
    summaries=[]
    for recipe,data in sorted(recipes.items()):
        kind,mass_id,rate,direction=recipe;out=max(data,key=lambda r:r['radius']);last=data[-1]
        if out['radius']<1+BEHAVIOR['outward_excursion'] or min(r['speed'] for r in data)>BEHAVIOR['minimum_reverse_speed']:fail('assembly radial reversal lost')
        if abs(last['speed'])>BEHAVIOR['final_radial_speed']:fail('assembly radial stop lost')
        if kind==0 and direction*out['rw']>0.2-BEHAVIOR['free_omega_change']:fail('free assembly did not slow with radius')
        if kind==1 and abs(last['rw']-0.2*direction)>BEHAVIOR['final_driven_omega']:fail('driven assembly did not recover target')
        summaries.append(dict(key=recipe,max_radius=out['radius'],omega_at_max=out['rw'],final_speed=last['speed'],final_omega=last['rw']))
    return dict(worst=worst,recipes=summaries)


def rejected(action):
    try:action()
    except ValueError:return
    fail('assembly guard accepted corrupt witness')


def self_test(raw,rows):
    rejected(lambda:parse(raw+'\n'+raw.splitlines()[0]))
    rejected(lambda:parse('\n'.join(raw.splitlines()[1:])))
    for index,value in ((1,'9'),(6,'nan'),(1,'0.5')):
        lines=raw.splitlines();parts=lines[0].split();parts[index]=value;lines[0]=' '.join(parts)
        rejected(lambda:parse('\n'.join(lines)))
    witnesses=[('sfx',5),('hfy',5),('spin_torque',5),('L',1),('before_L',1),('torque',1),
               ('motor',3),('hinge_anchor',1),('hinge_axis',1),('slider_anchor',1),
               ('slider_angle',1),('ax',0),('speed',1),('bvx',1),('w',1)]
    for field,value in witnesses:
        altered={key:row.copy() for key,row in rows.items()};altered[0,0,60,1,1][field]=value
        rejected(lambda:mechanics(altered))
    return 5+len(witnesses)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);options=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(options.archive)
    record=dict(schema=1,fixture='hinged-rail-v1',oracle_revision=REFERENCE,archive_sha256=digest,
                host=platform.platform(),bounds=BOUNDS,behavior=BEHAVIOR,phase_parity=False,
                observations_per_engine=len(CASES),modes={})
    for mode in ('Debug','Release'):
        oracle=build_oracle(source,mode,HERE/'HingedRailOracle.cpp','hinged-rail-oracle')
        binary=build_silex(mode,'HingedRail.sx','hinged-rail',True)
        outputs={engine:checked([str(exe)]) for engine,exe in [('silex',binary),('jolt',oracle)]}
        rows={engine:parse(raw) for engine,raw in outputs.items()}
        evidence=dict(mechanics={engine:mechanics(data) for engine,data in rows.items()},
                      corrupt_witnesses_rejected={engine:self_test(outputs[engine],data) for engine,data in rows.items()},
                      measured_phase_differences={field:max(abs(rows['silex'][key][field]-rows['jolt'][key][field]) for key in CASES) for field in ('radius','speed','rw','L','torque','motor')})
        for engine,raw in outputs.items():
            (BUILD/f'hinged-rail-{engine}-{mode.lower()}.txt').write_text(raw)
            evidence[engine+'_output_sha256']=hashlib.sha256(raw.encode()).hexdigest()
        record['modes'][mode]=evidence;(BUILD/'hinged-rail-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: {len(CASES)} observations per engine; coupled momentum, reactions and budgets green; 20 corrupt witnesses rejected per engine',flush=True)


if __name__=='__main__':main()
