#!/usr/bin/env python3
"""Qualify hinge stop impulse and motion while reporting distinct activation phases."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source

FIELDS = ('before_angle', 'before_speed', 'angle', 'speed', 'limit_impulse', 'motor_impulse', 'anchor', 'axis')
CASES = {(recipe, rate, sign, step) for recipe in range(7) for rate in (60,120)
         for sign in (-1,1) for step in range(1,rate*(6 if recipe >= 5 else 1)+1)}
PARITY = dict(angle=0.0001, speed=0.0001)


def parse(output):
    rows = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) != 13 or fields[0] != 'impact': fail('invalid impact row')
        try:
            numbers = list(map(float, fields[1:5]))
            if not all(math.isfinite(number) and number.is_integer() for number in numbers): fail('invalid impact key')
            key = tuple(map(int, numbers)); values = list(map(float, fields[5:]))
        except ValueError: fail('invalid impact number')
        if key not in CASES or key in rows or not all(map(math.isfinite,values)): fail('invalid impact observation')
        rows[key] = dict(zip(FIELDS,values))
    if set(rows) != CASES: fail('missing impact observations')
    return rows


def mechanics(rows):
    worst_balance = 0
    for key in sorted(CASES):
        recipe, rate, sign, step = key; row = rows[key]
        a, w, angle, speed, limit, motor, anchor, axis = (row[name] for name in FIELDS)
        if step > 1:
            previous = rows[recipe,rate,sign,step-1]
            if abs(a-previous['angle']) > 0.000002 or abs(w-previous['speed']) > 0.000002: fail('impact state discontinuity')
        else:
            initial_angle = sign*(0.283 if recipe == 1 else 0.3 if recipe in (2,3) else 0)
            initial_speed = 0 if recipe >= 5 else -sign if recipe == 3 else sign
            if abs(a-initial_angle) > 0.000002 or abs(w-initial_speed) > 0.000002: fail('wrong impact initial state')
        balance = abs(0.1*(speed-w)-limit-motor); worst_balance = max(worst_balance,balance)
        if balance > 0.000002: fail('impact impulse balance')
        work = limit*(w+speed)/2
        if work > 0.000001: fail('stop supplied positive kinetic work')
        if 0.05*(speed*speed-w*w)-motor*(w+speed)/2 > 0.000001: fail('unpowered energy increase')
        if anchor > 0.00001 or axis > 0.00001 or anchor < 0 or axis < 0: fail('impact frame drift')
        if recipe < 5 and motor != 0: fail('motor in passive impact')
        if abs(motor) > 10/rate+0.000002: fail('impact motor budget')
        if recipe not in (4,5):
            advance = max(max(0,abs(a)-0.3),abs(w)/rate+100/(rate*rate))
            if abs(angle) > 0.3+advance+0.00001: fail('stop exceeded free advance')
        elif limit != 0: fail('stop impulse on free axis')
        if recipe == 4 and (abs(speed-sign)>0.00001 or abs(angle-sign*step/rate)>0.00001): fail('free axis changed motion')
        if recipe == 2 and step == 1 and abs(speed)>0.00001: fail('active stop did not brake')
        if recipe == 3 and step == 1 and (abs(speed+sign)>0.00001 or abs(angle)>=0.3): fail('stop did not release')
        if recipe < 4 and step == rate:
            destination = -sign if recipe == 3 else sign
            if abs(speed)>0.00001 or abs(angle-destination*0.3)>0.00001: fail('passive stop did not settle')
    return worst_balance


def compare_motor_only(actual,reference):
    worst = dict.fromkeys(PARITY,0.0)
    for key in sorted(CASES):
        if key[0] != 5: continue
        for field, bound in PARITY.items():
            error = abs(actual[key][field]-reference[key][field]); worst[field] = max(worst[field],error)
            if error > bound: fail('motor-only parity '+field)
    return worst


def summary(rows):
    cases = []
    for recipe in range(7):
        for rate in (60,120):
            for sign in (-1,1):
                samples = [(key,row) for key,row in sorted(rows.items()) if key[:3] == (recipe,rate,sign)]
                first = next(((key,row) for key,row in samples if abs(row['limit_impulse'])>0.00001),None)
                last = samples[-1][1]
                cases.append(dict(recipe=recipe,rate=rate,sign=sign,first_limit=None if first is None else dict(step=first[0][3],**first[1]),
                                  final_angle=last['angle'],final_speed=last['speed'],
                                  strict_driven_rest_1e5=None if recipe != 6 else abs(last['speed'])<=0.00001))
    return cases


def rejected(action):
    try: action()
    except ValueError: return
    fail('impact guard accepted corrupt witness')


def self_test(raw,rows):
    rejected(lambda:parse(raw+'\n'+raw.splitlines()[0]))
    rejected(lambda:parse('\n'.join(raw.splitlines()[1:])))
    def altered_raw(index,value):
        lines = raw.splitlines(); fields = lines[0].split(); fields[index] = value
        lines[0] = ' '.join(fields); return '\n'.join(lines)
    rejected(lambda:parse(altered_raw(1,'9')))
    rejected(lambda:parse(altered_raw(5,'nan')))
    for field,value in [('limit_impulse',1),('motor_impulse',1),('speed',5),('angle',2),('anchor',1),('axis',1)]:
        altered = {key:row.copy() for key,row in rows.items()}; altered[1,60,1,1][field] = value
        rejected(lambda:mechanics(altered))
    altered = {key:row.copy() for key,row in rows.items()}; altered[5,60,1,1]['angle'] += 0.01
    rejected(lambda:compare_motor_only(altered,rows))
    return 11


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--archive',type=Path)
    options = parser.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest = verified_source(options.archive)
    record = dict(schema=1,fixture='hinge-impact-seven-cases-two-rates-v1',oracle_revision=REFERENCE,
                  archive_sha256=digest,host=platform.platform(),observations_per_engine=len(CASES),
                  phase_parity=False,strict_driven_rest_qualified=False,modes={})
    for mode in ('Debug','Release'):
        oracle = build_oracle(source,mode,HERE/'HingeImpactOracle.cpp','hinge-impact-oracle')
        silex = build_silex(mode,'HingeImpact.sx','hinge-impact',True)
        outputs = {engine:checked([str(binary)]) for engine,binary in [('silex',silex),('jolt',oracle)]}
        rows = {engine:parse(output) for engine,output in outputs.items()}
        evidence = dict(balance={engine:mechanics(data) for engine,data in rows.items()},
                        motor_only_parity=compare_motor_only(rows['silex'],rows['jolt']),
                        corrupt_witnesses_rejected=self_test(outputs['silex'],rows['silex']),
                        cases={engine:summary(data) for engine,data in rows.items()})
        for engine,output in outputs.items():
            path = BUILD/f'hinge-impact-{engine}-{mode.lower()}.txt'; path.write_text(output)
            evidence[engine+'_output_sha256'] = hashlib.sha256(output.encode()).hexdigest()
        record['modes'][mode] = evidence
        (BUILD/'hinge-impact-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: {len(CASES)} observations per engine, impulse/work/motion/release green; 11 corrupt witnesses rejected',flush=True)


if __name__ == '__main__': main()
