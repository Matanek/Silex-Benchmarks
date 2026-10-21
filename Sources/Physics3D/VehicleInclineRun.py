#!/usr/bin/env python3
"""Qualify powered incline motion, braking and zero grip against pinned Jolt."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from VehicleTiresRun import add, cross, dot, norm, scale
from VehiclePowertrainRun import dense_solve

KEYS = {(s, c, g, r, i) for s in (-1, 1) for c in range(3) for g in (0, 1)
        for r in (60, 120) for i in range(8*r+1)}
PARITY = (.05, .1, .02, .15, .25, .1)
IMPULSE = .1
ANALYTIC_VELOCITY = .002
ANALYTIC_POSITION = .005


def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def mean(values):
    return sum(values)/len(values)


def rotation_error(first, second):
    a = norm(first)
    b = norm(second)
    if min(a, b) < 1e-20:
        fail('invalid quaternion for angular distance')
    first = scale(first, 1/a)
    second = scale(second, 1/b)
    distance = min(norm(sub(first, second)), norm(add(first, second)))
    return 4*math.asin(min(1, distance/2))


def basis(sign):
    angle = .2*sign
    return (0, math.cos(angle), -math.sin(angle)), (0, math.sin(angle), math.cos(angle))


def wheel(row, index):
    return row[13+16*index:29+16*index]


def parse(raw, soft=False):
    rows = {}
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 86 or fields[0] != ('incline-soft' if soft else 'incline'):
            fail('invalid incline row')
        key = tuple(map(int, fields[1:6]))
        values = tuple(map(float, fields[6:]))
        if key not in KEYS or key in rows or not all(map(math.isfinite, values)):
            fail('invalid incline key or value')
        rows[key] = values
    if set(rows) != KEYS:
        fail('incomplete incline witness')
    return rows


def rotor_balance(old, row, sign, rate, step):
    dt = 1/rate
    driving = 2*rate <= step-1 < 5*rate
    brake = 0 if driving else 1500
    ratio = 3*sign
    conversion = 60/(2*math.pi)
    matrix = [[float(i == j) for j in range(5)] for i in range(5)]
    rhs = [0.]*5
    estimates = []
    for i in range(4):
        previous = wheel(old, i)
        direction = -1 if previous[2] < 0 or previous[2] == 0 and sign < 0 else 1
        impulse = direction*brake*dt
        if wheel(row, i)[6]:
            impulse += previous[4]*dt*.3
        estimates.append(impulse)
        for j in range(4):
            matrix[i][j] += dt*10*ratio*.25*ratio/(4*.9)
        matrix[i][4] = -dt*10*ratio*.25/.9
        rhs[i] = previous[2]-impulse/.9
        matrix[4][i] = -dt*10*ratio/(4*.5)
    matrix[4][4] += dt*10/.5
    rhs[4] = old[77]/conversion+dt*(32 if driving else 0)/.5
    result = dense_solve(matrix, rhs)
    residual = .5*abs(row[77]/conversion-max(0, min(6000/conversion, result[4])))
    for i in range(4):
        before = result[i]+estimates[i]/.9
        if brake > abs(before)*.9/dt:
            expected = 0
        else:
            expected = math.copysign(max(0, abs(before)-brake*dt/.9), before)-wheel(row, i)[4]*dt*.3/.9
        residual = max(residual, .9*abs(wheel(row, i)[2]-expected))
    if residual > IMPULSE:
        fail(f'incline independent dense rotor balance {(sign, rate, step)}: {residual}')
    return residual


def qualify(rows, soft=False):
    maximum = .77985 if soft else .6
    stiffness = 1200 if soft else 10000
    worst = dict(linear_impulse=0., angular_impulse=0., rotor_impulse=0., wheel_rotation_step=0., free_velocity=0., free_position=0.)
    summaries = {}
    for key, row in sorted(rows.items()):
        sign, contact, grip, rate, step = key
        normal, forward = basis(sign)
        if step == 0:
            expected_position = scale(normal, 1.15)
            expected_rotation = (-math.sin(.1*sign), 0, 0, math.cos(.1*sign))
            if norm(sub(row[:3], expected_position)) > .00001 or rotation_error(row[6:10], expected_rotation) > .00001 or norm(row[3:6])+norm(row[10:13]) > .00001 or abs(row[77]) > .00001:
                fail(f'incline initial calibration differs {key}')
            if any(abs(wheel(row, i)[0]-maximum) > .00001 or any(abs(value) > .00001 for value in wheel(row, i)[1:]) for i in range(4)):
                fail(f'incline initial wheel calibration differs {key}')
        if abs(dot(row[6:10], row[6:10])-1) > .0001 or not .5 < dot(row[:3], normal) < 2:
            fail(f'invalid incline pose {key}')
        if norm(row[:3]) > 150 or norm(row[3:6]) > 25 or norm(row[10:13]) > 8:
            fail(f'unbounded incline body {key}')
        if not 0 <= row[77] <= 6000.001 or row[78] != sign or abs(row[79]-1) > .00001:
            fail(f'invalid incline powertrain {key}')
        old = rows.get((sign, contact, grip, rate, step-1))
        linear = (0, -981/rate, 0)
        angular = (0, 0, 0)
        for index in range(4):
            values = wheel(row, index)
            length, force, omega, angle, longitudinal, lateral, touching = values[:7]
            point, n, f = values[7:10], values[10:13], values[13:16]
            if not 0 <= length <= maximum+.00001 or not 0 <= force < 20000 or abs(omega) > 200 or abs(angle) > 2*math.pi+.0001 or touching not in (0, 1):
                fail(f'invalid incline wheel {key} {index}')
            if touching:
                if norm(sub(n, normal)) > .0002 or abs(dot(point, normal)) > .0002:
                    fail(f'incline contact differs from plane {key} {index}')
                if abs(norm(f)-1) > .0001 or abs(dot(f, n)) > .0001 or dot(f, forward) < .98:
                    fail(f'invalid incline tangent {key} {index}')
            elif any(abs(x) > .00001 for x in (force, longitudinal, lateral, *point, *n, *f)):
                fail('absent incline contact retains force or geometry')
            capacity = force if grip else 0
            if max(abs(longitudinal), abs(lateral)) > capacity+.05:
                fail(f'incline force exceeds friction {key} {index}')
            if old:
                rotation_step = angle-wheel(old, index)[3]-wheel(old, index)[2]/rate
                rotation_error_step = abs(math.atan2(math.sin(rotation_step), math.cos(rotation_step)))
                worst['wheel_rotation_step'] = max(worst['wheel_rotation_step'], rotation_error_step)
                if rotation_error_step > .0001:
                    fail(f'incline wheel rotation integration {key} {index}')
                force_vector = add(scale(n, force), add(scale(f, longitudinal), scale(cross(f, n), lateral)))
                linear = add(linear, scale(force_vector, 1/rate))
                angular = add(angular, scale(cross(sub(point, old[:3]), force_vector), 1/rate))
        if old:
            worst['rotor_impulse'] = max(worst['rotor_impulse'], rotor_balance(old, row, sign, rate, step))
            e_linear = norm(sub(scale(sub(row[3:6], old[3:6]), 100), linear))
            e_angular = norm(sub(scale(sub(row[10:13], old[10:13]), 100), angular))
            worst['linear_impulse'] = max(worst['linear_impulse'], e_linear)
            worst['angular_impulse'] = max(worst['angular_impulse'], e_angular)
            if max(e_linear, e_angular) > IMPULSE:
                fail(f'incline impulse balance {key}: {e_linear}, {e_angular}')
        if not grip:
            acceleration = -9.81*math.sin(.2*sign)
            e_velocity = abs(dot(row[3:6], forward)-acceleration*step/rate)
            e_position = abs(dot(row[:3], forward)-acceleration*step*(step+1)/(2*rate*rate))
            worst['free_velocity'] = max(worst['free_velocity'], e_velocity)
            worst['free_position'] = max(worst['free_position'], e_position)
            if e_velocity > ANALYTIC_VELOCITY or e_position > ANALYTIC_POSITION:
                fail(f'zero-grip incline differs from gravity {key}: {e_velocity}, {e_position}')
    for sign in (-1, 1):
        normal, forward = basis(sign)
        for contact in range(3):
            for rate in (60, 120):
                final = rows[sign, contact, 1, rate, 8*rate]
                launch = rows[sign, contact, 1, rate, 2*rate]
                braking = rows[sign, contact, 1, rate, 5*rate]
                last = rows[sign, contact, 1, rate, 7*rate]
                progress = sign*dot(sub(braking[:3], launch[:3]), forward)
                if progress < 1 or norm(final[3:6]) > .05 or norm(sub(final[:3], last[:3])) > .1:
                    fail(f'incline did not climb and stop {(sign, contact, rate)}')
                weights = []
                for step in range(7*rate+1, 8*rate+1):
                    row = rows[sign, contact, 1, rate, step]
                    if any(wheel(row, i)[6] != 1 for i in range(4)):
                        fail('incline recovery lacks four supports')
                    if abs(dot(row[:3], normal)-(.3+maximum-981*math.cos(.2)/(4*stiffness))) > .003:
                        fail('incline did not recover suspension height')
                    weights.append(sum(wheel(row, i)[1] for i in range(4)))
                if abs(mean(weights)-981*math.cos(.2)) > 2:
                    fail('incline recovered weight differs from gravity projection')
                summaries[str((sign, contact, rate))] = dict(uphill_distance=progress, stopped_speed=norm(final[3:6]), mean_normal_force=mean(weights))
    return dict(worst=worst, cases=summaries)


def errors(x, y):
    return (norm(sub(x[:3], y[:3])), norm(sub(x[3:6], y[3:6])), rotation_error(x[6:10], y[6:10]),
            norm(sub(x[10:13], y[10:13])), max(abs(wheel(x, i)[2]-wheel(y, i)[2]) for i in range(4)),
            max(abs(math.atan2(math.sin(wheel(x, i)[3]-wheel(y, i)[3]), math.cos(wheel(x, i)[3]-wheel(y, i)[3]))) for i in range(4)))


def increment(rows, prefix, rate, start, index):
    return sum(math.atan2(math.sin(wheel(rows[prefix+(rate, step)], index)[3]-wheel(rows[prefix+(rate, step-1)], index)[3]),
                          math.cos(wheel(rows[prefix+(rate, step)], index)[3]-wheel(rows[prefix+(rate, step-1)], index)[3]))
               for step in range(start*rate+1, (start+1)*rate+1))


def compare(first, second):
    raw_worst = [0.]*6
    free_worst = [0.]*6
    phase_worst = [0.]*6
    for key, x in first.items():
        differences = errors(x, second[key])
        raw_worst = [max(a, b) for a, b in zip(raw_worst, differences)]
        if key[2] == 0:
            free_worst = [max(a, b) for a, b in zip(free_worst, differences)]
            if any(error > tolerance for index, (error, tolerance) in enumerate(zip(differences, PARITY)) if not (key[1] == 2 and index == 3)):
                fail(f'zero-grip incline parity {key}: {differences}')
        elif differences[2] > PARITY[2]:
            fail(f'incline orientation parity {key}: {differences[2]}')
    cylinder_angular = 0.
    for sign in (-1, 1):
        for rate in (60, 120):
            for window in range(32):
                groups = [[rows[sign, 2, 0, rate, step] for step in range(window*rate//4+1, (window+1)*rate//4+1)] for rows in (first, second)]
                averages = [tuple(mean([row[channel] for row in group]) for channel in range(10, 13)) for group in groups]
                error = norm(sub(averages[0], averages[1]))
                cylinder_angular = max(cylinder_angular, error)
                if error > .05:
                    fail(f'zero-grip cylindrical quarter-second angular parity {(sign, rate, window)}: {error}')
    for sign in (-1, 1):
        for contact in range(3):
            prefix = (sign, contact, 1)
            for rate in (60, 120):
                for start in range(8):
                    groups = [[rows[prefix+(rate, step)] for step in range(start*rate+1, (start+1)*rate+1)] for rows in (first, second)]
                    displacements = [sub(rows[prefix+(rate, (start+1)*rate)][:3], rows[prefix+(rate, start*rate)][:3]) for rows in (first, second)]
                    vector_errors = []
                    for channels in (range(3, 6), range(10, 13)):
                        averages = [tuple(mean([row[channel] for row in group]) for channel in channels) for group in groups]
                        vector_errors.append(norm(sub(averages[0], averages[1])))
                    rotor_error = max(abs(mean([wheel(row, i)[2] for row in groups[0]])-mean([wheel(row, i)[2] for row in groups[1]])) for i in range(4))
                    angle_error = max(abs(increment(first, prefix, rate, start, i)-increment(second, prefix, rate, start, i)) for i in range(4))
                    phase = (norm(sub(*displacements)), vector_errors[0], 0., vector_errors[1], rotor_error, angle_error)
                    phase_worst = [max(a, b) for a, b in zip(phase_worst, phase)]
                    if any(error > tolerance for error, tolerance in zip(phase, PARITY)):
                        fail(f'incline one-second parity {(prefix, rate, start)}: {phase}')
    return dict(zero_grip_pointwise_except_cylinder_angular=free_worst, cylinder_angular_quarter_second=cylinder_angular,
                grip_one_second=phase_worst, raw_pointwise_not_claimed_for_grip=raw_worst)


def mirror(rows):
    result = {}
    for (sign, contact, grip, rate, step), source in rows.items():
        values = list(source)
        for index in (2, 5, 6, 7, 10, 11, 78):
            values[index] = -values[index]
        for index in range(4):
            reflected = list(wheel(source, index ^ 1))
            for channel in (2, 3, 4, 9, 12, 13, 14):
                reflected[channel] = -reflected[channel]
            values[13+16*index:29+16*index] = reflected
        result[-sign, contact, grip, rate, step] = tuple(values)
    return result


def rejected(action):
    try:
        action()
    except (ValueError, OverflowError):
        return
    fail('corrupt incline witness accepted')


def self_test(raw, rows, soft=False):
    lines = raw.splitlines()
    rejected(lambda: parse('\n'.join(lines[1:]), soft))
    rejected(lambda: parse(raw.rstrip('\n')+'\n'+lines[0], soft))
    rejected(lambda: parse(raw.replace('incline-soft', 'incline') if soft else raw.replace('incline ', 'incline-soft '), soft))
    for channel, value in ((0, 'other'), (1, '0'), (4, '61'), (6, 'nan'), (6, 'inf')):
        fields = lines[0].split()
        fields[channel] = value
        rejected(lambda: parse(' '.join(fields)+'\n'+'\n'.join(lines[1:]), soft))
    key = (1, 0, 1, 120, 600)
    for channel in (0, 1, 3, 6, 10, 13, 14, 15, 17, 18, 19, 20, 23, 26, 77, 78, 79):
        changed = dict(rows)
        values = list(changed[key])
        values[channel] += 1 if channel in (3, 10) else 100 if channel == 14 else 1000
        changed[key] = tuple(values)
        rejected(lambda: qualify(changed, soft))
    translated = {}
    for key, source in rows.items():
        values = list(source)
        values[0] += 1
        for i in range(4):
            if wheel(source, i)[6]:
                values[20+16*i] += 1
        translated[key] = tuple(values)
    rejected(lambda: qualify(translated, soft))
    return 26


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--mode', choices=('Debug', 'Release', 'both'), default='both')
    args = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f'run from workspace or Spec group root: {GROUP}')
    source, digest = verified_source(args.archive)
    record = dict(schema=1, fixture='vehicle-incline-coulomb-v1', oracle_revision=REFERENCE, archive_sha256=digest,
                  tolerances=dict(parity=PARITY, per_step_impulse=IMPULSE, cylinder_angular_quarter_second=.05, analytic_velocity=ANALYTIC_VELOCITY, analytic_position=ANALYTIC_POSITION),
                  scope='Constant tire coefficient 1 versus 0, world-normal plane, mirrored grades 0.2 rad. No grip: pointwise and gravity analytic, except cylindrical angular means over 0.25 s. Grip: pointwise orientation and one-second displacement/velocity/rotor increments. Per-step physical balances throughout. Variable friction curves and strict instantaneous braking parity are not qualified.', modes={})
    for mode in ('Debug', 'Release') if args.mode == 'both' else (args.mode,):
        oracle = build_oracle(source, mode, HERE/'VehicleInclineOracle.cpp', 'vehicle-incline-oracle')
        binary = build_silex(mode, 'VehicleIncline.sx', 'vehicle-incline-silex', True)
        evidence = {}
        for preset in ('firm', 'soft'):
            soft = preset == 'soft'
            rows = {}
            result = {}
            for name, exe in (('silex', binary), ('jolt', oracle)):
                raw = checked([str(exe)]+(['--soft'] if soft else []))
                (BUILD/f'vehicle-incline-{preset}-{name}-{mode.lower()}.txt').write_text(raw)
                rows[name] = parse(raw, soft)
                result[name] = dict(observations=len(rows[name]), qualification=qualify(rows[name], soft),
                                    mirrored=compare(rows[name], mirror(rows[name])), guards=self_test(raw, rows[name], soft), sha256=hashlib.sha256(raw.encode()).hexdigest())
            result['parity'] = compare(rows['silex'], rows['jolt'])
            evidence[preset] = result
            print(f'{mode} {preset}: incline gravity, uphill propulsion and braking green', flush=True)
        record['modes'][mode] = evidence
        (BUILD/'vehicle-incline-qualification.json').write_text(json.dumps(record, indent=2)+'\n')
        print(f'{mode}: incline gravity, uphill propulsion, braking and conditioned parity green', flush=True)


if __name__ == '__main__':
    main()
