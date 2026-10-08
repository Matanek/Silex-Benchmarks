#!/usr/bin/env python3
"""Qualify finite-stroke rack servo commands and preserve rejected transient gates."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS = ('target', 'hinge', 'angle', 'travel', 'phase', 'speed_error', 'speed', 'torque', 'pinion_torque', 'rack_force')
CASES = {(rate, case, phase, step) for rate in (60, 120) for case in range(3)
         for phase in (0, 1) for step in range(rate*3)}
BOUNDS = dict(angle=0.002, travel=0.002, phase=0.002, speed_error=0.001, speed=0.001, torque=0.1)
ALL_STEP_PARITY = {(60, 0), (60, 1), (120, 1), (120, 2)}
LEGACY_PHASE_FAILURES = {(120, 0), (60, 2)}


def parse(output):
    rows = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) != len(FIELDS)+5 or parts[0] != 'servo': fail(f'invalid servo row: {line}')
        try:
            key = tuple(map(int, parts[1:5])); values = list(map(float, parts[5:]))
        except ValueError: fail('invalid numeric servo evidence')
        if key not in CASES or key in rows or not all(map(math.isfinite, values)): fail('invalid servo observation')
        rows[key] = dict(zip(FIELDS, values))
    if set(rows) != CASES: fail('missing servo observations')
    return rows


def mechanics(rows):
    for key in sorted(CASES):
        rate, case, phase, step = key; row = rows[key]
        amplitude = 2 if case == 0 else 1.5
        target = amplitude if phase == 0 else -amplitude
        extent = 0.6 if case == 2 else 1.1
        if row['target'] != target: fail('servo command differs')
        if abs(row['torque']) > 12.0001 or abs(row['speed_error']) > 0.001: fail('servo lost effort or speed relation')
        if abs(row['angle']-2*row['travel']-row['phase']) > 0.00001: fail('inconsistent observed servo phase')
        previous = rows.get((rate, case, phase, step-1))
        if previous is None and phase == 1: previous = rows[rate, case, 0, rate*3-1]
        previous_speed = previous['speed'] if previous else 0
        previous_phase = abs(previous['phase']) if previous else 0
        advance = (abs(previous_speed)+30/rate)/rate
        previous_penetration = max(0,abs(previous['travel'])-extent) if previous else 0
        if abs(row['travel']) > extent+max(previous_penetration,advance/2)+0.00001: fail('servo exceeded one free stop advance')
        if abs(row['phase']) > previous_phase+advance+0.00001: fail('servo phase grew beyond one free advance')
        if step >= rate*2.5:
            if abs(row['phase']) >= 0.002: fail('servo phase did not settle under original gate')
            blocked = case == 2 or (case == 0 and phase == 1)
            if blocked:
                sign = 1 if case == 0 or phase == 0 else -1
                torque = 12 if case == 0 else sign*4.5
                if abs(row['travel']-sign*extent) >= 0.002 or abs(row['angle']-sign*2*extent) >= 0.002: fail('servo stop did not settle')
                if abs(row['speed']) > 0.001: fail('servo rail stop keeps moving')
                if abs(row['torque']-torque) > 0.01 or abs(row['pinion_torque']+torque) > 0.01 or abs(row['rack_force']-2*torque) > 0.02: fail('servo stop lost independent reaction balance')
            elif abs(row['angle']-target) > 0.01: fail('reachable servo target did not settle')
        if case == 0 and phase == 1 and step == 0 and row['speed'] <= 0: fail('historical servo lost its short angular route')
        if case == 2 and phase == 1 and step == 0 and row['speed'] >= 0: fail('reachable servo command did not reverse')


def compare(actual, reference, rate, case, settled_only=False):
    errors = dict.fromkeys(BOUNDS, 0.0)
    for key in sorted(CASES):
        if key[:2] != (rate, case) or (settled_only and key[3] < rate*2.5): continue
        for name, bound in BOUNDS.items():
            error = abs(actual[key][name]-reference[key][name]); errors[name] = max(errors[name], error)
            if error > bound: fail(f'servo {key} {name}: {error} > {bound}')
    return errors


def rejected(action):
    try: action()
    except ValueError: return
    fail('servo guard accepted corrupt evidence')


def self_test(outputs):
    raw = outputs['silex']; rows = parse(raw)
    rejected(lambda: parse(raw+'\n'+raw.splitlines()[0]))
    rejected(lambda: parse('\n'.join(raw.splitlines()[1:])))
    rejected(lambda: parse(raw.replace('servo 60 0 0 0 2.0', 'servo 60 0 0 0 nan', 1)))
    rejected(lambda: parse(raw.replace('servo 60 0 0 0 ', 'servo 60 9 0 0 ', 1)))
    for field, value in (('torque',13), ('speed_error',1), ('phase',1), ('travel',3), ('angle',4), ('pinion_torque',0), ('rack_force',0)):
        altered = {k:r.copy() for k,r in rows.items()};altered[120,2,0,359][field]=value
        rejected(lambda: mechanics(altered))
    altered={k:r.copy() for k,r in rows.items()};altered[120,1,0,359]['travel']+=0.01
    rejected(lambda: compare(altered,rows,120,1))
    print('rack servo guards: 12 corrupt witnesses rejected')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path)
    options=parser.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(options.archive)
    record=dict(schema=1,fixture='rack-servo-three-cases-two-rates-v1',oracle_revision=REFERENCE,
                archive_sha256=digest,host=platform.platform(),rates=[60,120],seconds_per_command=3,
                torque=12,stiffness=15,damping=8,ratio=2,mass=2,inertia=0.4,
                iterations=dict(jolt_velocity=12,jolt_position=4,silex_preparation=12,silex_velocity=12,silex_position=4,rack_local_sweeps=2),
                bounds=BOUNDS,original_all_step_phase_bound=0.002,settled_seconds=2.5,
                source_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ('RackServo.sx','RackServoOracle.cpp','RackServoRun.py','Run.py')},
                scope='Fixed-axis hinge + slider + transmission; no shape collisions or gravity. Historical ±2 short-route block, free ±1.5 stroke, ±1.5 against rail ±0.6. Finite-step advance, settled phase and reaction balance at both rates. Manual fixture fixed 120 Hz.',
                scope_limit='Original all-step phase gate fails for historical 120 Hz and rail-contact 60 Hz in both engines. Full trajectory parity is not claimed there; failures retained. No general chain/contact-phase guarantee or new motor semantics.',modes={})
    for mode in ('Debug','Release'):
        oracle=build_oracle(source,mode,HERE/'RackServoOracle.cpp','rack-servo-oracle')
        silex=build_silex(mode,'RackServo.sx','rack-servo-silex',physics=True)
        outputs=dict(jolt=checked([str(oracle)]),silex=checked([str(silex)]))
        self_test(outputs)
        parsed={}
        for name,output in outputs.items():
            (BUILD/f'rack-servo-{name}-{mode.lower()}.txt').write_text(output)
            parsed[name]=parse(output);mechanics(parsed[name])
        cases={}
        for rate in (60,120):
            for case in range(3):
                full='passes'
                try: compare(parsed['silex'],parsed['jolt'],rate,case)
                except ValueError as error: full=str(error)
                if (rate,case) in ALL_STEP_PARITY and full!='passes': fail(full)
                legacy={name:max(abs(row['phase']) for key,row in rows.items() if key[:2]==(rate,case)) for name,rows in parsed.items()}
                for name,value in legacy.items():
                    if ((value>=0.002) != ((rate,case) in LEGACY_PHASE_FAILURES)): fail('legacy phase counterproof changed; reassess fixture')
                cases[f'{rate}/{case}']=dict(full_trajectory_comparison=full,legacy_all_step_phase_maxima=legacy,
                    settled_maximum_errors=compare(parsed['silex'],parsed['jolt'],rate,case,True))
        record['modes'][mode]=dict(observations=len(CASES),cases=cases,independent_mechanics=True)
        print(f'rack servo {mode}: {len(CASES)} observations; preserved transient failures; settled mechanics and bounded parity green',flush=True)
    (BUILD/'rack-servo-qualification.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__': main()
