#!/usr/bin/env python3
"""Qualify the loaded spatial hinge and fixed payload against pinned Jolt."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS = ('x', 'y', 'z', 'payload_x', 'payload_y', 'payload_z', 'angle', 'speed',
          'motor', 'axis', 'anchor', 'fixed_anchor', 'fixed_angle', 'force_y', 'moment_x', 'payload_force_y')
RATES = (60, 60, 60, 60, 120, 60, 60)
CASES = {(case, step) for case, rate in enumerate(RATES) for step in range(1, rate*3+1)}
POSE_BOUNDS = {name: 0.01 for name in FIELDS[:6]}
POSE_BOUNDS.update(angle=0.005, speed=0.005, motor=0.00001, axis=0.006,
                   anchor=0.01, fixed_anchor=0.01, fixed_angle=0.01)
SETTLED_BOUNDS = dict(POSE_BOUNDS, axis=0.002, force_y=0.5, moment_x=0.5, payload_force_y=0.5)


def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        tokens = line.split()
        if len(tokens) != len(FIELDS)+3 or tokens[0] != 'loaded':
            fail(f'invalid loaded hinge row: {line}')
        values = list(map(float, tokens[1:]))
        if not all(map(math.isfinite, values)):
            fail('non-finite loaded hinge evidence')
        identity = tuple(values[:2])
        if identity not in CASES or identity in rows:
            fail(f'unknown or duplicate loaded hinge row: {identity}')
        rows[tuple(map(int, identity))] = dict(zip(FIELDS, values[2:]))
    if set(rows) != CASES:
        fail('missing loaded hinge samples')
    return rows


def qualify(rows):
    inertia = math.pi/6*1.1+2.2
    for (case, step), row in rows.items():
        rate = RATES[case]
        for name in ('axis', 'anchor', 'fixed_anchor', 'fixed_angle'):
            if row[name] < 0:
                fail(f'negative loaded hinge error: {name}')
        if max(row['anchor'], row['fixed_anchor'], row['fixed_angle']) >= 0.01:
            fail(f'loaded hinge lost its frame: {case}, {step}, {row}')
        if abs(row['motor']) > 0.20001:
            fail(f'loaded hinge exceeded its per-step motor budget: {case}, {step}')
        if step >= rate*2.5:
            if row['axis'] >= 0.002:
                fail(f'loaded hinge axis did not settle: {case}, {step}, {row}')
            if case not in (2, 3):
                expected = {'force_y': (2+math.pi/6)*9.81, 'payload_force_y': 19.62,
                            'moment_x': 19.62 if case == 5 else 0 if case == 6 else -19.62}
                for name, value in expected.items():
                    if abs(row[name]-value) > 0.5:
                        fail(f'loaded hinge differs from the weight and lever moment: {case}, {step}, {name}')
        # Cold constraint iteration is kept in the output, without claiming
        # exact rigid-body acceleration before the assembly has converged.
        if case in (2, 3) and step == rate*3:
            half = rate*3//2
            positive = min(step, half)
            negative = max(0, step-half)
            speed = 0.2/inertia/rate*(positive-negative)
            angle = 0.2/inertia/rate**2*(positive*(positive+1)/2 + negative*half-negative*(negative+1)/2)
            if abs(row['speed']-speed) > 0.0002 or abs(row['angle']-angle) > 0.0002:
                fail(f'loaded hinge differs from its complete pivot inertia: {case}, {step}, {row}')


def compare(actual, reference, *, settled_only=False):
    errors = dict.fromkeys(FIELDS, 0.0)
    for identity in sorted(CASES):
        case, step = identity
        if settled_only and step < RATES[case]*2.5: continue
        bounds = SETTLED_BOUNDS if step >= RATES[case]*2.5 else POSE_BOUNDS
        for name, bound in bounds.items():
            error = abs(actual[identity][name]-reference[identity][name])
            errors[name] = max(errors[name], error)
            if error > bound:
                fail(f'loaded hinge {identity} {name}: error {error}, bound {bound}')
    return errors


def self_test():
    rows = {}
    inertia = math.pi/6*1.1+2.2
    for case, step in CASES:
        row = dict.fromkeys(FIELDS, 0.0)
        if case not in (2, 3):
            row.update(force_y=(2+math.pi/6)*9.81, payload_force_y=19.62,
                       moment_x=19.62 if case == 5 else 0 if case == 6 else -19.62)
        else:
            half=RATES[case]*3//2;positive=min(step,half);negative=max(0,step-half)
            row.update(speed=0.2/inertia/RATES[case]*(positive-negative),
                       angle=0.2/inertia/RATES[case]**2*(positive*(positive+1)/2+negative*half-negative*(negative+1)/2))
        rows[(case, step)] = row
    output = '\n'.join('loaded '+' '.join(map(str,(case,step,*(row[name] for name in FIELDS))))
                       for (case,step),row in sorted(rows.items()))
    qualify(parse_rows(output));compare(rows,rows)
    for corrupt in (output+'\n'+output.splitlines()[0], '\n'.join(output.splitlines()[1:]),
                    output.replace('loaded 0 1 0', 'loaded 0 1 nan', 1),
                    output.replace('loaded 0 1 ', 'loaded 7 1 ', 1),
                    output.replace('loaded 0 1 ', 'loaded 0 1.5 ', 1)):
        try: parse_rows(corrupt)
        except ValueError: continue
        fail('loaded hinge parser accepted corrupt evidence')
    for key,name,value in (((0,180),'axis',0.01),((0,1),'motor',0.21),((0,1),'anchor',-1),
                           ((0,1),'fixed_anchor',0.02),((0,1),'fixed_angle',0.02),
                           ((5,180),'moment_x',-19.62),((0,180),'force_y',0),
                           ((0,180),'payload_force_y',0),((3,180),'speed',0.01),((2,180),'angle',0)):
        altered={identity:row.copy() for identity,row in rows.items()};altered[key][name]=value
        try: qualify(altered)
        except ValueError: continue
        fail('loaded hinge guard accepted invalid physical evidence')
    altered={identity:row.copy() for identity,row in rows.items()};altered[(0,1)]['z']=0.02
    try: compare(altered,rows)
    except ValueError: pass
    else: fail('loaded hinge comparator accepted a perturbed trajectory')
    altered={identity:row.copy() for identity,row in rows.items()};altered[(0,180)]['z']=0.02
    try: compare(altered,rows,settled_only=True)
    except ValueError: pass
    else: fail('loaded hinge settled comparator accepted a perturbed trajectory')
    print('physics3d loaded hinge guards: 17 invalid witnesses rejected')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--mode',choices=('Debug','Release','both'),default='both')
    parser.add_argument('--self-test',action='store_true')
    options=parser.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from the workspace or Spec group root: {GROUP}')
    self_test()
    if options.self_test: return
    source,digest=verified_source(options.archive)
    record={'schema':1,'fixture':'loaded-spatial-hinge-seven-cases-v1','oracle_revision':REFERENCE,
            'archive_sha256':digest,'host':platform.platform(),'architecture':platform.machine(),
            'sources_sha256':{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                              for name in ('LoadedHinge.sx','LoadedHingeOracle.cpp','LoadedHingeRun.py','Run.py')},
            'rates':RATES,'materials':{'friction':0.6,'restitution':0},'steps_seconds':3,'reversal_seconds':1.5,'settled_seconds':2.5,
            'original_full_trajectory_bounds':POSE_BOUNDS,'settled_bounds':SETTLED_BOUNDS,
            'scope':'Offset Z ±1 m or centered; gravity or free motion; floor present/absent; 60/120 Hz. Automatic sphere mass pi/6 kg and inertia mass/10; payload 2 kg, isotropic inertia 0.2. Origin-local anchors equal COM-local anchors.',
            'scope_limit':'Comparison only after 2.5 s; complete trajectory output retained with the rejected cold comparison. Analytical complete pivot inertia at the final sample. No exact cold acceleration, impulse-by-impulse parity, contact-phase parity, general chain qualification or arbitrarily heavy load claim.',
            'iterations':{'jolt_velocity':12,'jolt_position':4,'silex_preparation':12,'silex_velocity':12,'silex_position':4},'modes':{}}
    for mode in (('Debug','Release') if options.mode=='both' else (options.mode,)):
        oracle=build_oracle(source,mode,HERE/'LoadedHingeOracle.cpp','loaded-hinge-oracle')
        silex=build_silex(mode,'LoadedHinge.sx','loaded-hinge-silex',physics=True)
        outputs={'jolt':checked([str(oracle)]),'silex':checked([str(silex)])}
        for name,output in outputs.items(): (BUILD/f'loaded-hinge-{name}-{mode.lower()}.txt').write_text(output)
        reference=parse_rows(outputs['jolt']);actual=parse_rows(outputs['silex'])
        qualify(reference);qualify(actual)
        cold_comparison = 'passes'
        try: compare(actual,reference)
        except ValueError as error: cold_comparison = str(error)
        record['modes'][mode]={'samples':len(CASES),'settled_comparison_samples':sum(step>=RATES[case]*2.5 for case,step in CASES),'maximum_absolute_errors':compare(actual,reference,settled_only=True),
                               'full_trajectory_comparison':cold_comparison,
                               'full_trajectory_maximum_errors':{name:max(abs(actual[k][name]-reference[k][name]) for k in CASES) for name in FIELDS},
                               'maximum_axis':{name:max(row['axis'] for row in rows.values()) for name,rows in (('silex',actual),('jolt',reference))}}
        print(f'physics3d loaded hinge {mode}: {len(CASES)} samples qualified',flush=True)
    (BUILD/'loaded-hinge-qualification.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':
    try: main()
    except (OSError,ValueError) as error:
        print(f'physics3d loaded hinge: {error}',file=sys.stderr);sys.exit(1)
