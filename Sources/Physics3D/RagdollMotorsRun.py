#!/usr/bin/env python3
"""Qualify offset ragdoll pose motors under gravity and passive release."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from SpatialHingesRun import add, sub, mul, norm
from LoadedSwingTwistRun import product, conjugate, axis_angle, distance, rotate

KEYS = {(rate, side, step, part) for rate in (60, 120) for side in (-1, 1)
        for step in range(rate * 13 + 1) for part in (1, 2)}
BOUNDS = dict(anchor=.02, pose_error=.08, final_speed=.15,
              motor_torque=120.001, reconstruction=.0001, release_motion=.03)
PARITY = dict(orientation=.03, position=.05, speed=.05)
BASE = axis_angle((1, 2, -1), .6)
REST = {1: axis_angle((0, 0, 1), .4), 2: axis_angle((0, 1, 0), -.3)}
OFFSETS = {1: (0, -.4, 0), 2: (0, -.3, 0)}
OFFSET_ROTATIONS = {1: axis_angle((1, 0, 0), .3), 2: axis_angle((0, 0, 1), -.2)}
LOCAL_POSITIONS = {1: (0, -.5, 0), 2: (0, -.8, 0)}


def target(direction, part):
    result = product(axis_angle((0, 0, 1), .25 * direction),
                     axis_angle((1, 0, 0), .2 * direction))
    return result if part == 1 else conjugate(result)


def parse(raw):
    rows = {}
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 31 or fields[0] != 'ragdollmotor':
            fail('invalid ragdoll motor row')
        try:
            key = tuple(map(int, fields[1:5]))
            values = tuple(map(float, fields[5:]))
        except (ValueError, OverflowError):
            fail('invalid ragdoll motor number')
        if key not in KEYS or key in rows or not all(map(math.isfinite, values)):
            fail('invalid, duplicate or nonfinite ragdoll motor row')
        rows[key] = values
    if set(rows) != KEYS:
        fail('missing ragdoll motor observations')
    return rows


def qualify(rows):
    worst = dict(anchor=0, pose_error=0, final_speed=0, motor_torque=0, reconstruction=0)
    for rate in (60, 120):
        for side in (-1, 1):
            for step in range(rate * 13 + 1):
                joint_positions = {0: (0, 3, 0)}
                joint_rotations = {0: BASE}
                angular = {0: (0, 0, 0)}
                for part in (1, 2):
                    row = rows[rate, side, step, part]
                    p, q, v, w, o, a, m, e = (row[:3], row[3:7], row[7:10], row[10:13],
                                              row[13:17], row[17:20], row[20:23], row[23:26])
                    if max(abs(norm(q)-1), abs(norm(o)-1)) > .00001:
                        fail('ragdoll motor rotation is not unit')
                    if max(norm(v), norm(w)) >= 40:
                        fail('ragdoll motor motion is unbounded')
                    joint_rotations[part] = product(q, conjugate(OFFSET_ROTATIONS[part]))
                    joint_positions[part] = sub(p, rotate(joint_rotations[part], OFFSETS[part]))
                    angular[part] = w
                    reconstructed = product(conjugate(REST[part]),
                        product(conjugate(joint_rotations[part-1]), joint_rotations[part]))
                    anchor = sub(joint_positions[part], add(joint_positions[part-1],
                                 rotate(joint_rotations[part-1], LOCAL_POSITIONS[part])))
                    speed = rotate(conjugate(joint_rotations[part]), sub(w, angular[part-1]))
                    error = max(distance(reconstructed, o), norm(sub(anchor, e)), norm(sub(speed, a)))
                    worst['reconstruction'] = max(worst['reconstruction'], error)
                    if error >= BOUNDS['reconstruction']:
                        fail('ragdoll body/joint pose, offset, speed or anchor convention differs')
                    worst['anchor'] = max(worst['anchor'], norm(e))
                    worst['motor_torque'] = max(worst['motor_torque'], max(map(abs, m)))
                    if norm(e) >= BOUNDS['anchor'] or max(map(abs, m)) >= BOUNDS['motor_torque']:
                        fail('ragdoll motor anchor or torque exceeds bound')
                    if step >= rate*12 and norm(m) > .00001:
                        fail('ragdoll motors still exert torque after release')
                    if step == 0:
                        if distance(o, (0, 0, 0, 1)) > .00001 or norm(v)+norm(w)+norm(m) > .00001:
                            fail('initial motor command moved bodies or injected velocity')
                    for phase in range(3):
                        if rate*(phase*4+3.5) <= step < rate*(phase+1)*4:
                            direction = side if phase == 0 else -side if phase == 1 else 0
                            pose_error = distance(o, target(direction, part))
                            final_speed = max(norm(v), norm(a))
                            worst['pose_error'] = max(worst['pose_error'], pose_error)
                            worst['final_speed'] = max(worst['final_speed'], final_speed)
                            if pose_error >= BOUNDS['pose_error'] or final_speed >= BOUNDS['final_speed']:
                                fail(f'ragdoll target does not settle: {rate}/{side}/{step}/{part}, error {pose_error}, speed {final_speed}')
                if step == rate*13:
                    motion = distance(rows[rate,side,rate*12,2][13:17], rows[rate,side,step,2][13:17])
                    if motion <= BOUNDS['release_motion']:
                        fail('ragdoll did not resume passive motion under gravity')
    return worst


def compare(first, second):
    worst = dict.fromkeys(PARITY, 0)
    for rate in (60, 120):
        for side in (-1, 1):
            for phase in range(3):
                for step in range(int(rate*(phase*4+3.5)), rate*(phase+1)*4):
                    for part in (1, 2):
                        a, b = first[rate,side,step,part], second[rate,side,step,part]
                        errors = dict(orientation=distance(a[13:17],b[13:17]),
                                      position=norm(sub(a[:3],b[:3])), speed=norm(sub(a[17:20],b[17:20])))
                        for name, value in errors.items():
                            worst[name] = max(worst[name], value)
                            if value >= PARITY[name]:
                                fail(f'ragdoll settled {name} parity differs: {value}')
    return worst


def rejected(action):
    try:
        action()
    except ValueError:
        return
    fail('ragdoll motor guard accepted corrupt evidence')


def self_test(raw, rows):
    lines = raw.splitlines()
    rejected(lambda: parse(raw+'\n'+lines[0]))
    rejected(lambda: parse('\n'.join(lines[1:])))
    rejected(lambda: parse(raw.replace('ragdollmotor 60 -1 0 1','ragdollmotor 61 -1 0 1')))
    changed = lines.copy(); fields = changed[0].split(); fields[5] = 'nan'; changed[0] = ' '.join(fields)
    rejected(lambda: parse('\n'.join(changed)))
    for component in range(26):
        altered = rows.copy(); key=(60,-1,239,2); values=list(altered[key])
        values[component] += 300 if 20 <= component < 23 else 2
        altered[key]=tuple(values);rejected(lambda: qualify(altered))
    for part in (1,2):
        altered=rows.copy();key=(60,-1,780,part);values=list(altered[key]);values[20]=1
        altered[key]=tuple(values);rejected(lambda: qualify(altered))
    return 32


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--mode',choices=('Debug','Release','both'),default='both')
    args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='ragdoll-offset-pose-motors-v1',oracle_revision=REFERENCE,
                archive_sha256=digest,bounds=BOUNDS,parity_bounds=PARITY,
                scope='Fixed root and two offset sphere bodies, gravity, two opposed targets, neutral return and passive release. Geometric conventions and settled pose parity, not arbitrary impact or full trajectory parity.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'RagdollMotorsOracle.cpp','ragdoll-motors-oracle')
        binary=build_silex(mode,'RagdollMotors.sx','ragdoll-motors-silex',True)
        parsed={};evidence={}
        for name,executable in (('silex',binary),('jolt',oracle)):
            raw=checked([str(executable)]);(BUILD/f'ragdoll-motors-{name}-{mode.lower()}.txt').write_text(raw)
            rows=parse(raw);parsed[name]=rows
            evidence[name]=dict(observations=len(rows),worst=qualify(rows),corrupt_witnesses_rejected=self_test(raw,rows),
                                output_sha256=hashlib.sha256(raw.encode()).hexdigest())
        record['modes'][mode]=dict(witnesses=evidence,settled_parity=compare(parsed['silex'],parsed['jolt']))
        (BUILD/'ragdoll-motors-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: offset ragdoll motors, settled targets, bounded efforts and passive release green',flush=True)


if __name__=='__main__':
    main()
