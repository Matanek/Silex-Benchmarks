#!/usr/bin/env python3
"""Qualify six inclination, reactions and mutations without a renderer."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS = ('px','py','pz','twist','sy','sz','vx','vy','vz','wx','wy','wz','first_vx','fx','fy','fz','mfx','mfy','mfz','mtx','mty','mtz')
BOUNDS = dict(zip(FIELDS,(0.005,)*6+(0.003,)*7+(0.05,)*6+(0.02,)*3))
CASES = {(case,step) for case in range(16) for step in range(15,361,15)}

def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        values = line.split()
        if len(values) != len(FIELDS) + 3 or values[0] != 'six': fail('invalid six row')
        try:
            case, step = map(int, values[1:3])
            data = list(map(float, values[3:]))
        except ValueError:
            fail('invalid numeric six data')
        key = case, step
        if key not in CASES or key in rows or not all(map(math.isfinite, data)): fail('duplicate, unknown or nonfinite six row')
        rows[key] = dict(zip(FIELDS, data))
    if set(rows) != CASES: fail('missing six observations')
    return rows

def servo_samples(angular=False):
    position = velocity = 0.0
    samples = {}
    dt=1/60
    mass,stiffness,damping=(0.2,2,0.8) if angular else (2,20,8)
    for step in range(1,361):
        error=2*math.sin((position-0.6)/2) if angular else position-0.6
        next_velocity=(mass*velocity-dt*stiffness*error+dt*(damping+dt*stiffness)*0.1)/(mass+dt*damping+dt*dt*stiffness)
        effort=mass*(next_velocity-velocity)/dt
        velocity=next_velocity;position+=dt*velocity
        samples[step]=(position,velocity,effort)
    return samples

def spring_samples():
    position=-0.8;velocity=0.0;samples={};dt=1/60
    for step in range(1,361):
        stiffness,damping=(200,14) if step<=180 else (400,20)
        free_velocity=velocity-9.81*dt
        next_velocity=free_velocity
        if position<=-0.4:
            next_velocity=max(free_velocity,(2*free_velocity-dt*stiffness*(position+0.4))/(2+dt*damping+dt*dt*stiffness))
        elif position>=0.4:
            next_velocity=min(free_velocity,(2*free_velocity-dt*stiffness*(position-0.4))/(2+dt*damping+dt*dt*stiffness))
        force=2*(next_velocity-free_velocity)/dt
        velocity=next_velocity;position+=dt*velocity
        samples[step]=(position,velocity,force)
    return samples

def qualify(rows):
    linear=servo_samples();angular=servo_samples(True);spring=spring_samples()
    for (case,step),r in rows.items():
        if case in (0,1):
            field='px' if case==0 else 'py'
            if abs(r[field]-step/120)>0.0002 or abs(r['twist']-step/120)>0.0002 or abs(r['wx']-0.5)>0.0001: fail('six blocked a free degree')
            if case==1 and (abs(r['px'])>0.002 or abs(r['vx'])>0.0001): fail('six did not lock only X')
        if case in (2,11,12):
            limit=0.2 if case==12 and step>180 else 0.5
            if not -0.405<=r['px']<=limit+0.005: fail('six lost X bounds')
            if step>=30 and abs(r['px']-limit)>0.005: fail('six did not reach or mutate X stop')
        if case==3 and step>=30:
            if abs(r['py']+0.4)>0.005 or abs(r['vy'])>0.003: fail('six lost negative Y stop')
        if case in (4,5):
            names=('px','vx','mfx') if case==4 else ('sz','wz','mtz')
            expected=(linear if case==4 else angular)[step]
            if any(abs(r[n]-e)>0.0003 for n,e in zip(names,expected)): fail(f'six lost independent servo {(case,step)}')
        if case in (6,7):
            name,budget,effort=('vz',2,'mfz') if case==6 else ('wx',0.2,'mtx')
            if abs(r[name]-max(0,1-step/60))>0.0002 or abs(r[effort])>budget+0.0001: fail('six lost passive friction')
        if case==8:
            if any(abs(r[n]-e)>0.0003 for n,e in zip(('py','vy','fy'),spring[step])): fail(f'six lost independent spring {(case,step)}')
        if case==9:
            if abs(2*r['first_vx']+8*r['vx']-8)>0.0001 or abs(r['px'])>0.002: fail('six lost unequal-mass momentum')
        if case==10:
            if max(abs(r[n]) for n in ('px','py','pz'))>0.002 or abs(r['fy']-19.62)>0.05: fail('six lost offset weight support')
        if case==13 and step>=15:
            if abs(r['sy']-0.3)>0.005 or abs(r['wy'])>0.003: fail('six lost swing stop')
        if case==15 and (abs(r['sy']-0.2)>0.005 or abs(r['wy'])>0.003): fail('six lost an asymmetric pyramid excluding zero')
        if case==14:
            expected=0.05*(1/60)**2*step*(step+1)/2
            if abs(r['px']-expected)>0.0002 or abs(r['vx']-0.05*step/60)>0.0001 or abs(r['mfx']-0.1)>0.0001: fail('six lost signed forced effort')

def compare(actual, reference):
    errors = dict.fromkeys(FIELDS, 0.0)
    for key in sorted(CASES):
        for name in FIELDS:
            error = abs(actual[key][name]-reference[key][name])
            errors[name] = max(errors[name],error)
            if error>BOUNDS[name]: fail(f'six {key} {name}: error {error}, bound {BOUNDS[name]}')
    return errors

def self_test():
    rows = {key:dict.fromkeys(FIELDS,0.0) for key in CASES}
    output = '\n'.join('six '+' '.join(map(str,(case,step,*(r[n] for n in FIELDS)))) for (case,step),r in sorted(rows.items()))
    compare(parse_rows(output),rows)
    for bad in (output+'\n'+output.splitlines()[0], '\n'.join(output.splitlines()[1:]), output.replace('six 0 15 0.0','six 0 15 nan',1),output.replace('six 0 15','six 16 15',1)):
        try: parse_rows(bad)
        except ValueError: continue
        fail('six parser accepted corrupt evidence')
    changed = {key:r.copy() for key,r in rows.items()};changed[0,15]['twist']=0.1
    try: compare(changed,rows)
    except ValueError: pass
    else: fail('six comparator accepted changed twist')
    try: qualify(rows)
    except ValueError: pass
    else: fail('six mechanics accepted inert fixtures')
    print('physics3d six guard self-test: ok')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path);p.add_argument('--self-test',action='store_true');p.add_argument('--mode',choices=('Debug','Release','both'),default='both');o=p.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from Spec group: {GROUP}')
    self_test()
    if o.self_test: return
    source,digest=verified_source(o.archive)
    record=dict(schema=1,fixture='six-sixteen-cases-360-steps',oracle_revision=REFERENCE,archive_sha256=digest,host=platform.platform(),bounds=BOUNDS,
        sources_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ('SixDOF.sx','SixDOFOracle.cpp','SixDOFRun.py','Run.py')},
        scope='free/locked/bounded translations and rotations, independent linear/angular servos, friction, soft limits and mutation, unequal masses, offset weight, rotated frame and signed effort; no general-chain, loaded offset-servo or exact impact-step parity claim',modes={})
    for mode in ('Debug','Release') if o.mode=='both' else (o.mode,):
        oracle=build_oracle(source,mode,HERE/'SixDOFOracle.cpp','six-oracle');silex=build_silex(mode,'SixDOF.sx','six-silex',physics=True)
        outputs=dict(jolt=checked([str(oracle)]),silex=checked([str(silex)]))
        for name,out in outputs.items(): (BUILD/f'six-{name}-{mode.lower()}.txt').write_text(out)
        reference,actual=(parse_rows(outputs['jolt']),parse_rows(outputs['silex']))
        qualify(reference);qualify(actual)
        record['modes'][mode]=dict(samples=len(CASES),maximum_absolute_errors=compare(actual,reference))
        print(f'physics3d six {mode}: {len(CASES)} samples qualified against Jolt and independent mechanics')
    (BUILD/'six-qualification.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':
    try: main()
    except (OSError,ValueError) as e: print(f'physics3d six: {e}',file=sys.stderr);sys.exit(1)
