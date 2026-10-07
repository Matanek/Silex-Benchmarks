#!/usr/bin/env python3
"""Qualify cone inclination, reactions and mutations without a renderer."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS = ('angle', 'wx', 'wy', 'wz', 'first_wx', 'anchor_error', 'fx', 'fy', 'fz', 'tx', 'ty', 'tz')
BOUNDS = dict(zip(FIELDS, (0.005, 0.003, 0.003, 0.003, 0.003, 0.002, 0.05, 0.05, 0.05, 0.02, 0.02, 0.02)))
CASES = {(case, step) for case in range(8) for step in range(15, 361, 15)}

def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        values = line.split()
        if len(values) != len(FIELDS) + 3 or values[0] != 'cone': fail('invalid cone row')
        try:
            case, step = map(int, values[1:3])
            data = list(map(float, values[3:]))
        except ValueError:
            fail('invalid numeric cone data')
        key = case, step
        if key not in CASES or key in rows or not all(map(math.isfinite, data)): fail('duplicate, unknown or nonfinite cone row')
        rows[key] = dict(zip(FIELDS, data))
    if set(rows) != CASES: fail('missing cone observations')
    return rows

def qualify(rows):
    for (case, step), r in rows.items():
        limit = 0.2 if case == 4 and step > 180 else 0.4
        if not 0 <= r['angle'] <= limit + 0.005 or not 0 <= r['anchor_error'] < 0.002:
            fail(f'cone lost limit or anchor {(case, step)}')
        if case == 0:
            if abs(r['wz']-0.5)>0.0001 or abs(r['wx'])>0.0001 or r['angle']>0.0001: fail('cone blocked free twist')
        if case in (1, 2, 7) and step>=30:
            if abs(r['angle']-0.4)>0.005 or max(abs(r[n]) for n in ('wx','wy','wz'))>0.003: fail('cone did not arrest swing')
        if case == 3:
            if step<=45:
                expected = (1/60)**2 * step*(step+1)/2
                if abs(r['wx']-step/60)>0.0001 or abs(r['angle']-expected)>0.0002: fail('cone lost independent free acceleration')
            if step>=90:
                if abs(r['angle']-0.4)>0.005 or abs(r['tx']+0.2)>0.02: fail('cone lost torque balance')
        if case == 5:
            if abs(0.2*r['first_wx']+0.8*r['wx']-1.6)>0.0001: fail('cone lost unequal-inertia angular momentum')
        if case == 6:
            if abs(r['fy']-19.62)>0.05 or r['angle']>0.0001 or max(abs(r[n]) for n in ('tx','ty','tz'))>0.0001: fail('cone lost offset weight support')
    if abs(rows[4,360]['angle']-0.2)>0.005: fail('cone mutation did not tighten inclination')

def compare(actual, reference):
    errors = dict.fromkeys(FIELDS, 0.0)
    for key in sorted(CASES):
        for name in FIELDS:
            error = abs(actual[key][name]-reference[key][name])
            errors[name] = max(errors[name],error)
            if error>BOUNDS[name]: fail(f'cone {key} {name}: error {error}, bound {BOUNDS[name]}')
    return errors

def self_test():
    rows = {key:dict.fromkeys(FIELDS,0.0) for key in CASES}
    output = '\n'.join('cone '+' '.join(map(str,(case,step,*(r[n] for n in FIELDS)))) for (case,step),r in sorted(rows.items()))
    compare(parse_rows(output),rows)
    for bad in (output+'\n'+output.splitlines()[0], '\n'.join(output.splitlines()[1:]), output.replace('cone 0 15 0.0','cone 0 15 nan',1),output.replace('cone 0 15','cone 8 15',1)):
        try: parse_rows(bad)
        except ValueError: continue
        fail('cone parser accepted corrupt evidence')
    changed = {key:r.copy() for key,r in rows.items()};changed[0,15]['angle']=0.1
    try: compare(changed,rows)
    except ValueError: pass
    else: fail('cone comparator accepted changed angle')
    try: qualify(rows)
    except ValueError: pass
    else: fail('cone mechanics accepted inert fixtures')
    print('physics3d cone guard self-test: ok')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path);p.add_argument('--self-test',action='store_true');p.add_argument('--mode',choices=('Debug','Release','both'),default='both');o=p.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from Spec group: {GROUP}')
    self_test()
    if o.self_test: return
    source,digest=verified_source(o.archive)
    record=dict(schema=1,fixture='cone-eight-cases-360-steps',oracle_revision=REFERENCE,archive_sha256=digest,host=platform.platform(),bounds=BOUNDS,
        sources_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ('Cone.sx','ConeOracle.cpp','ConeRun.py','Run.py')},
        scope='free twist, signed swing stops, constant torque, mutable half-angle, unequal free inertias, offset weight and rotated frame; no general-chain or exact impact-step parity claim',modes={})
    for mode in ('Debug','Release') if o.mode=='both' else (o.mode,):
        oracle=build_oracle(source,mode,HERE/'ConeOracle.cpp','cone-oracle');silex=build_silex(mode,'Cone.sx','cone-silex',physics=True)
        outputs=dict(jolt=checked([str(oracle)]),silex=checked([str(silex)]))
        for name,out in outputs.items(): (BUILD/f'cone-{name}-{mode.lower()}.txt').write_text(out)
        reference,actual=(parse_rows(outputs['jolt']),parse_rows(outputs['silex']))
        qualify(reference);qualify(actual)
        record['modes'][mode]=dict(samples=len(CASES),maximum_absolute_errors=compare(actual,reference))
        print(f'physics3d cone {mode}: {len(CASES)} samples qualified against Jolt and independent mechanics')
    (BUILD/'cone-qualification.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':
    try: main()
    except (OSError,ValueError) as e: print(f'physics3d cone: {e}',file=sys.stderr);sys.exit(1)
