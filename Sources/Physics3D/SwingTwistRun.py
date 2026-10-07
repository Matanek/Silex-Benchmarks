#!/usr/bin/env python3
"""Qualify swing inclination, reactions and mutations without a renderer."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS = ('twist', 'swing_y', 'swing_z', 'wx', 'wy', 'wz', 'first_wx', 'anchor_error', 'fx', 'fy', 'fz', 'mx', 'my', 'mz')
BOUNDS = dict(zip(FIELDS, (0.005, 0.005, 0.005, 0.003, 0.003, 0.003, 0.003, 0.002, 0.05, 0.05, 0.05, 0.02, 0.02, 0.02)))
CASES = {(case, step) for case in range(12) for step in range(15, 361, 15)}

def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        values = line.split()
        if len(values) != len(FIELDS) + 3 or values[0] != 'swing': fail('invalid swing row')
        try:
            case, step = map(int, values[1:3])
            data = list(map(float, values[3:]))
        except ValueError:
            fail('invalid numeric swing data')
        key = case, step
        if key not in CASES or key in rows or not all(map(math.isfinite, data)): fail('duplicate, unknown or nonfinite swing row')
        rows[key] = dict(zip(FIELDS, data))
    if set(rows) != CASES: fail('missing swing observations')
    return rows

def servo_samples(target, speed):
    angle = velocity = 0.0
    samples = {}
    dt = 1/60
    for step in range(1,361):
        error = 2 * math.sin((angle-target)/2)
        next_velocity = (0.2*velocity - dt*2*error + dt*(0.8+dt*2)*speed)/(0.2+dt*0.8+dt*dt*2)
        torque = 0.2*(next_velocity-velocity)/dt
        velocity = next_velocity
        angle += dt*velocity
        samples[step] = angle, velocity, torque
    return samples

def qualify(rows):
    twist_servo = servo_samples(0.25,0.05)
    swing_servo = servo_samples(0.2,0.05)
    for (case, step), r in rows.items():
        if not 0 <= r['anchor_error'] < 0.002: fail(f'swing lost anchor {(case, step)}')
        if abs(r['swing_y'])>0.305 or abs(r['swing_z'])>0.605: fail(f'swing lost angular stops {(case, step)}')
        if case == 0:
            if abs(r['twist']-step/120)>0.0002 or abs(r['wx']-0.5)>0.0001: fail('swing blocked free twist')
        if case in (1,2,3,9,10) and step>=30:
            field, expected = ('twist',-0.4) if case==1 else (('swing_z',-0.6) if case==3 else ('swing_y',0.3))
            if abs(r[field]-expected)>0.005 or max(abs(r[n]) for n in ('wx','wy','wz'))>0.003: fail('swing did not arrest limited axis')
        if case in (4,5):
            angle, velocity, torque = (twist_servo if case==4 else swing_servo)[step]
            names = ('twist','wx','mx') if case==4 else ('swing_y','wy','my')
            if any(abs(r[n]-e)>0.0003 for n,e in zip(names,(angle,velocity,torque))): fail(f'swing lost independent nonlinear servo {(case,step)}')
        if case == 6:
            expected = max(0.0,1-step/60)
            if abs(r['wx']-expected)>0.0002 or abs(r['mx'])>0.2001: fail('swing lost passive friction budget')
        if case == 7:
            if abs(0.2*r['first_wx']+0.8*r['wx']-0.8)>0.0001 or abs(r['twist'])>0.005: fail('swing lost locked unequal-inertia momentum')
        if case == 8:
            if abs(r['fy']-19.62)>0.05 or max(abs(r[n]) for n in ('twist','swing_y','swing_z'))>0.0001: fail('swing lost offset weight support')
        if case == 11:
            if step==15 and (abs(r['twist']-1.7*step/60)>0.0002 or abs(r['wx']-1.7)>0.0001): fail('swing mutation fixture lost independent free motion')
            limit = 0.2 if step>180 else 0.5
            if r['twist']>limit+0.005: fail('swing lost mutated twist stop')
    if abs(rows[11,360]['twist']-0.2)>0.005: fail('swing mutation did not tighten twist')

def compare(actual, reference):
    errors = dict.fromkeys(FIELDS, 0.0)
    for key in sorted(CASES):
        for name in FIELDS:
            error = abs(actual[key][name]-reference[key][name])
            errors[name] = max(errors[name],error)
            if error>BOUNDS[name]: fail(f'swing {key} {name}: error {error}, bound {BOUNDS[name]}')
    return errors

def self_test():
    rows = {key:dict.fromkeys(FIELDS,0.0) for key in CASES}
    output = '\n'.join('swing '+' '.join(map(str,(case,step,*(r[n] for n in FIELDS)))) for (case,step),r in sorted(rows.items()))
    compare(parse_rows(output),rows)
    for bad in (output+'\n'+output.splitlines()[0], '\n'.join(output.splitlines()[1:]), output.replace('swing 0 15 0.0','swing 0 15 nan',1),output.replace('swing 0 15','swing 12 15',1)):
        try: parse_rows(bad)
        except ValueError: continue
        fail('swing parser accepted corrupt evidence')
    changed = {key:r.copy() for key,r in rows.items()};changed[0,15]['twist']=0.1
    try: compare(changed,rows)
    except ValueError: pass
    else: fail('swing comparator accepted changed twist')
    try: qualify(rows)
    except ValueError: pass
    else: fail('swing mechanics accepted inert fixtures')
    print('physics3d swing guard self-test: ok')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path);p.add_argument('--self-test',action='store_true');p.add_argument('--mode',choices=('Debug','Release','both'),default='both');o=p.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from Spec group: {GROUP}')
    self_test()
    if o.self_test: return
    source,digest=verified_source(o.archive)
    record=dict(schema=1,fixture='swing-twelve-cases-360-steps',oracle_revision=REFERENCE,archive_sha256=digest,host=platform.platform(),bounds=BOUNDS,
        sources_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ('SwingTwist.sx','SwingTwistOracle.cpp','SwingTwistRun.py','Run.py')},
        scope='free twist, signed twist/swing stops, separate nonlinear servos, passive friction, locked unequal inertias, offset weight, rotated frame, pyramid and mutable twist limit; no general-chain or exact impact-step parity claim',modes={})
    for mode in ('Debug','Release') if o.mode=='both' else (o.mode,):
        oracle=build_oracle(source,mode,HERE/'SwingTwistOracle.cpp','swing-oracle');silex=build_silex(mode,'SwingTwist.sx','swing-silex',physics=True)
        outputs=dict(jolt=checked([str(oracle)]),silex=checked([str(silex)]))
        for name,out in outputs.items(): (BUILD/f'swing-{name}-{mode.lower()}.txt').write_text(out)
        reference,actual=(parse_rows(outputs['jolt']),parse_rows(outputs['silex']))
        qualify(reference);qualify(actual)
        record['modes'][mode]=dict(samples=len(CASES),maximum_absolute_errors=compare(actual,reference))
        print(f'physics3d swing {mode}: {len(CASES)} samples qualified against Jolt and independent mechanics')
    (BUILD/'swing-qualification.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':
    try: main()
    except (OSError,ValueError) as e: print(f'physics3d swing: {e}',file=sys.stderr);sys.exit(1)
