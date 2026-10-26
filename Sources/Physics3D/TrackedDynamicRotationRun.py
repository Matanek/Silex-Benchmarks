#!/usr/bin/env python3
"""Qualify tracked angular momentum exchange on a finite-mass rotating support."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_silex, checked, fail, verified_source
from TrackedBrakeOracle import build_tracked_oracle
from TrackedGroundRun import wheel, force, sub, PARITY
from TrackedVehicleRun import near, rejected
from VehicleTiresRun import add, cross, dot, norm, scale
from VehicleInclineRun import rotation_error
from MotorcycleReferenceRun import rotate
from TrackedDynamicPlatformRun import horizontal, inverse_rotate

TOTAL = 6
CASES = range(7)
RATES = (60, 120)
KEYS = {(case, rate, step) for case in CASES for rate in RATES for step in range(TOTAL * rate + 1)}


def parse(raw):
    rows = {}
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 131 or fields[0] != 'tracked-dynamic-rotation':
            fail('invalid dynamic rotation row')
        key = tuple(map(int, fields[1:4]))
        values = tuple(struct.unpack('f', struct.pack('f', float(value)))[0] for value in fields[4:])
        if key not in KEYS or key in rows or not all(map(math.isfinite, values)):
            fail('invalid dynamic rotation key/value')
        rows[key] = values
    if set(rows) != KEYS:
        fail('incomplete dynamic rotation witness')
    return rows


def mass_for(case):
    return 200.0 if 3 <= case <= 5 else 1000.0


def inertia_for(case):
    mass = mass_for(case)
    return mass * 144.16 / 12, mass * 208 / 12, mass * 64.16 / 12


def angular_impulse(case, step, rate):
    if case in (0, 6) or step not in (2 * rate, 4 * rate):
        return 0.0
    sign = -1 if case in (2, 4) else 1
    return sign * inertia_for(case)[1] * .5 * (-1 if step == 4 * rate else 1)


def angular_momentum(row, case):
    local = inverse_rotate(row[120:124], row[124:127])
    inertia = inertia_for(case)
    return rotate(row[120:124], tuple(a * b for a, b in zip(local, inertia)))


def qualify_case(rows, engine, case, rate):
    mass = mass_for(case)
    initial = rows[case, rate, 0]
    for value, target in zip(initial[:18], (2.5, 1.15, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1000, 0, 1, 0, 0)):
        near(value, target, 1e-5, 'initial offset neutral chassis')
    for value, target in zip(initial[114:127], (0, -.2, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0)):
        near(value, target, 1e-5, 'initial resting support')
    center_initial = scale(add(scale(initial[:3], 100), scale(initial[114:117], mass)), 1 / (100 + mass))
    external_spin = 0.0
    worst = dict(linear=0.0, angular=0.0, reciprocal=0.0, reciprocal_spin=0.0, momentum=0.0,
                 spin=0.0, center=0.0, belt=0.0, angle=0.0, free_momentum=0.0)
    slips, spins, rotors = [], [], []
    for step in range(TOTAL * rate + 1):
        row = rows[case, rate, step]
        old = rows[case, rate, step - 1] if step else row
        moving = 2 * rate <= step - 1 < 4 * rate
        free = case == 5 and moving
        if not .3 < row[1] < 4 or any(norm(v) > limit for v, limit in ((row[:3], 100), (row[3:6], 25), (row[10:13], 5), (row[114:117], 100), (row[117:120], 25), (row[124:127], 5))):
            fail('unbounded dynamic rotation')
        for q in (row[6:10], row[120:124]):
            near(dot(q, q), 1, 1e-4, 'unit rotation')
            if rotate(q, (0, 1, 0))[1] < .8:
                fail('overturned rotating support or vehicle')
        near(row[13], 1000, .02, 'idle engine')
        near(row[14], 0, 0, 'neutral gear')
        near(row[15], 1, 1e-5, 'engaged clutch')
        if case == 6:
            near(norm(sub(row[114:117], (0, -.2, 0))), 0, 1e-4, 'kinematic center')
            near(norm(row[117:120]), 0, 1e-4, 'kinematic translation')
            near(norm(sub(row[124:127], (0, .5 if moving else 0, 0))), 0, 1e-4, 'kinematic spin')
            angle = .5 * min(max(step - 2 * rate, 0), 2 * rate) / rate
            near(rotation_error(row[120:124], (0, math.sin(angle / 2), 0, math.cos(angle / 2))), 0, 1e-4, 'kinematic angle')
        loads = (0, 0, 0)
        torque = (0, 0, 0)
        contacts = 0
        longitudinal = 0.0
        for index in range(6):
            sample = wheel(row, index)
            side = index // 3
            if sample[6] not in (0.0, 1.0) or not 0 <= sample[0] <= .60001 or not 0 <= sample[1] < 100000:
                fail('invalid dynamic-platform wheel domain')
            expected = old[16 + side] if engine == 'jolt' and step and not sample[6] and free else 0.0 if engine == 'jolt' and step and not sample[6] else row[16 + side]
            worst['belt'] = max(worst['belt'], near(sample[2], expected, 1e-4, 'common belt and wheel speed'))
            if not free:
                near(row[16 + side], 0.0, 1e-4, 'locked track')
            if step:
                increment = math.remainder(sample[3] - wheel(old, index)[3] - old[16 + side] / rate, 2 * math.pi)
                worst['angle'] = max(worst['angle'], near(increment, 0.0, 1e-4, 'wheel angle integral'))
            if sample[6]:
                contacts += 1
                normal = rotate(old[120:124], (0, 1, 0))
                near(norm(sub(sample[10:13], normal)), 0.0, 1e-4, 'actual support top normal')
                near(norm(sample[13:16]), 1.0, 1e-4, 'unit longitudinal direction')
                near(dot(sample[10:13], sample[13:16]), 0.0, 1e-4, 'orthogonal wheel frame')
                anchor = add(old[:3], rotate(old[6:10], (-.6 if index < 3 else .6, 0, index % 3 - 1)))
                direction = rotate(old[6:10], (0, -1, 0))
                ray = sub(sample[7:10], anchor)
                distance = dot(ray, direction)
                near(norm(sub(ray, scale(direction, distance))), 0.0, 1e-4, 'contact lies on suspension ray')
                if not 0 <= distance <= .9001:
                    fail('contact outside suspension ray')
                near(sample[0], max(.2, distance - .3), 1e-4, 'suspension from geometry')
                local = inverse_rotate(old[120:124], sub(sample[7:10], old[114:117]))
                near(local[1], .2, 1e-4, 'finite dynamic support top')
                if abs(local[0]) > 4.0001 or abs(local[2]) > 6.0001:
                    fail('contact outside finite dynamic support')
                if abs(sample[4]) > sample[1] + .003 or abs(sample[5]) > math.sqrt(.15) * sample[1] + .003:
                    fail('dynamic-platform friction capacity exceeded')
                value = force(sample)
                loads = add(loads, value)
                torque = add(torque, cross(sub(sample[7:10], old[:3]), value))
                longitudinal += sample[4]
            elif any(abs(sample[channel]) > .002 for channel in (1, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15)):
                fail('unsupported wheel has contact effort')
        if step:
            worst['linear'] = max(worst['linear'], near(norm(sub(scale(sub(row[3:6], old[3:6]), 100), scale(add(loads, (0, -981, 0)), 1 / rate))), 0, .1, 'chassis linear impulse'))
            worst['angular'] = max(worst['angular'], near(norm(sub(scale(sub(row[10:13], old[10:13]), 100), scale(torque, 1 / rate))), 0, .1, 'chassis angular impulse'))
            if case != 6:
                applied = angular_impulse(case, step - 1, rate)
                external_spin += applied
                worst['reciprocal'] = max(worst['reciprocal'], near(norm(horizontal(add(scale(sub(row[117:120], old[117:120]), mass), scale(loads, 1 / rate)))), 0, .1, 'opposite support impulse'))
                reaction = (0, 0, 0)
                for index in range(6):
                    sample = wheel(row, index)
                    reaction = sub(reaction, cross(sub(sample[7:10], old[114:117]), force(sample)))
                delta = angular_momentum(row, case)[1] - angular_momentum(old, case)[1]
                worst['reciprocal_spin'] = max(worst['reciprocal_spin'], near(delta - applied - reaction[1] / rate, 0, .1, 'opposite support angular impulse'))
            if free:
                value = 2 * (sum(row[16:18]) - sum(old[16:18])) + .3 * longitudinal / rate
                worst['free_momentum'] = max(worst['free_momentum'], near(value, 0, .002, 'free belt momentum'))
        if case != 6:
            momentum = add(scale(row[3:6], 100), scale(row[117:120], mass))
            worst['momentum'] = max(worst['momentum'], near(norm(horizontal(momentum)), 0, .1, 'total horizontal momentum'))
            spin = 100 * row[11] + angular_momentum(row, case)[1]
            spin += cross(row[:3], scale(row[3:6], 100))[1] + cross(row[114:117], scale(row[117:120], mass))[1]
            worst['spin'] = max(worst['spin'], near(spin, external_spin, .5, 'total spin and orbital momentum Y'))
            center = scale(add(scale(row[:3], 100), scale(row[114:117], mass)), 1 / (100 + mass))
            worst['center'] = max(worst['center'], near(norm(horizontal(sub(center, center_initial))), 0, .001, 'fixed horizontal center of mass'))
        if math.ceil(3.25 * rate) <= step <= math.floor(3.75 * rate):
            point = add(row[117:120], cross(row[124:127], sub(row[:3], row[114:117])))
            slip = norm(sub(row[3:6], point))
            slips.append(slip);spins.append(abs(row[125]));rotors.append(sum(abs(v) for v in row[16:18]))
            if case != 5:
                near(slip, 0, .05, 'locked point transport')
                near(row[11], row[125], .05, 'locked common spin')
                if case not in (0, 6):
                    mu = 100 * mass / (100 + mass)
                    expected = inertia_for(case)[1] * .5 / (inertia_for(case)[1] + 100 + mu * 2.5 ** 2)
                    near(abs(row[125]), expected, .03, 'shared rotational inertia')
        if step > 5 * rate:
            if contacts != 6:
                fail('six final supports missing')
            near(row[1] - row[115] - .2, .88365, .003, 'final relative height')
            near(sum(wheel(row, i)[1] for i in range(6)), 981, 2, 'final supported weight')
            if any(norm(v) > .05 for v in (row[3:6], row[10:13], row[117:120], row[124:127])):
                fail('dynamic rotation failed to stop')
    if case == 0:
        near(norm(horizontal(sub(rows[case, rate, TOTAL * rate][:3], (2.5, 0, 0)))), 0, .01, 'stationary control')
    slip = sum(slips) / len(slips)
    rotor = sum(rotors) / len(rotors)
    if case == 5 and (slip <= .02 or rotor <= .05):
        fail('free tracks not distinguished')
    return dict(worst=worst, mean_relative_speed=slip, mean_support_spin=sum(spins) / len(spins), mean_rotors=rotor,
                end_position=rows[case, rate, TOTAL * rate][:3])


def mirror(rows):
    worst = [0.0] * 4
    for first_case, second_case in ((1, 2), (3, 4)):
        for rate in RATES:
            for step in range(TOTAL * rate + 1):
                a, b = rows[first_case, rate, step], rows[second_case, rate, step]
                for pos, vel, rot, spin in ((0, 3, 6, 10), (114, 117, 120, 124)):
                    errors = norm(sub(a[pos:pos+3], (b[pos], b[pos+1], -b[pos+2]))), norm(sub(a[vel:vel+3], (b[vel], b[vel+1], -b[vel+2]))), rotation_error(a[rot:rot+4], (-b[rot], -b[rot+1], b[rot+2], b[rot+3])), norm(sub(a[spin:spin+3], (-b[spin], -b[spin+1], b[spin+2])))
                    for index, (error, limit) in enumerate(zip(errors, (.005, .02, .005, .02))):
                        worst[index] = max(worst[index], near(error, 0, limit, 'dynamic rotation mirror'))
    return worst


def qualify(rows, engine):
    outcomes = {f'{case}/{rate}': qualify_case(rows, engine, case, rate) for case in CASES for rate in RATES}
    for rate in RATES:
        heavy, light, imposed = (outcomes[f'{case}/{rate}']['mean_support_spin'] for case in (1, 3, 6))
        if not imposed - heavy > .005 or not heavy - light > .02:
            fail('finite rotational inertia response not distinguished')
    return dict(outcomes=outcomes, mirror=mirror(rows))


def compare(first, second):
    body = [0.0] * 4
    support = [0.0] * 4
    force_error = torque_error = normal_error = angle_error = 0.0
    for key in KEYS:
        x, y = first[key], second[key]
        for result, position, velocity, rotation, spin in ((body, 0, 3, 6, 10), (support, 114, 117, 120, 124)):
            errors = norm(sub(x[position:position + 3], y[position:position + 3])), norm(sub(x[velocity:velocity + 3], y[velocity:velocity + 3])), rotation_error(x[rotation:rotation + 4], y[rotation:rotation + 4]), norm(sub(x[spin:spin + 3], y[spin:spin + 3]))
            for index, (error, limit) in enumerate(zip(errors, PARITY)):
                result[index] = max(result[index], near(error, 0.0, limit, f'body/support parity {key}/{position}/{index}'))
    for case in CASES:
        for rate in RATES:
            for phase in range(TOTAL):
                sums = []
                for rows in (first, second):
                    load = (0.0, 0.0, 0.0)
                    torque = (0.0, 0.0, 0.0)
                    normal = [0.0] * 6
                    angles = [0.0] * 6
                    for step in range(phase * rate + 1, (phase + 1) * rate + 1):
                        row, old = rows[case, rate, step], rows[case, rate, step - 1]
                        for index in range(6):
                            sample = wheel(row, index)
                            value = force(sample)
                            load = add(load, scale(value, 1 / rate))
                            torque = add(torque, scale(cross(sub(sample[7:10], old[:3]), value), 1 / rate))
                            normal[index] += sample[1] / rate
                            angles[index] += math.remainder(sample[3] - wheel(old, index)[3], 2 * math.pi)
                    sums.append((load, torque, normal, angles))
                x, y = sums
                force_error = max(force_error, near(norm(sub(x[0], y[0])), 0.0, 20.0, 'window force'))
                torque_error = max(torque_error, near(norm(sub(x[1], y[1])), 0.0, 30.0, 'window torque'))
                for index in range(6):
                    normal_error = max(normal_error, near(x[2][index] - y[2][index], 0.0, 20.0, 'window normal'))
                    angle_error = max(angle_error, near(x[3][index] - y[3][index], 0.0, .1, 'window rotation'))
    return dict(body=body, support=support, force_mean=force_error, torque_mean=torque_error, normal_mean=normal_error, rotation_increment=angle_error)


def self_test(raw, rows, engine):
    lines = raw.splitlines()
    rejected(lambda: parse('\n'.join(lines[1:])))
    rejected(lambda: parse(raw + lines[0] + '\n'))
    for index, value in ((0, 'other'), (1, '7'), (2, '61'), (4, 'nan'), (4, 'inf')):
        fields = lines[0].split();fields[index] = value
        rejected(lambda: parse(' '.join(fields) + '\n' + '\n'.join(lines[1:])))
    count = 7
    for key, channels in [((1, 60, 180), range(127)), ((5, 120, 420), (3, 5, 16, 17, 125)), ((6, 60, 210), (114, 117, 119, 124, 125, 126))]:
        for channel in channels:
            altered = dict(rows);row = list(rows[key]);row[channel] += 100;altered[key] = tuple(row)
            rejected(lambda: qualify_case(altered, engine, key[0], key[1]));count += 1
    altered = dict(rows);row = list(rows[4,60,210]);row[2] += .02;altered[4,60,210] = tuple(row)
    rejected(lambda: mirror(altered))
    return count + 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--mode', choices=('Debug', 'Release', 'both'), default='both')
    parser.add_argument('--stable-brakes', action='store_true', required=True)
    args = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f'run from group root {GROUP}')
    source, digest = verified_source(args.archive)
    stem = 'tracked-dynamic-rotation-stable-brakes'
    report = dict(schema=1, fixture='tracked-dynamic-rotation-v1', oracle_revision=REFERENCE, archive_sha256=digest,
                  profiles=dict(dynamic=[48, 4], kinematic=[12, 4]), initial_offset=2.5, initial_spin=.5, modes={})
    for mode in ('Debug', 'Release') if args.mode == 'both' else (args.mode,):
        oracle, adapter = build_tracked_oracle(source, mode, HERE/'TrackedDynamicRotationOracle.cpp', 'tracked-dynamic-rotation-oracle', stable=True)
        silex = build_silex(mode, 'TrackedDynamicRotation.sx', 'tracked-dynamic-rotation-silex', True)
        parsed = {};evidence = dict(oracle_adapter=adapter)
        for engine, binary in (('jolt', oracle), ('silex', silex)):
            raw = checked([str(binary)]);(BUILD/f'{stem}-{engine}-{mode.lower()}.txt').write_text(raw);rows = parse(raw)
            evidence[engine] = dict(states=len(rows), qualification=qualify(rows, engine), guards=self_test(raw, rows, engine), sha256=hashlib.sha256(raw.encode()).hexdigest());parsed[engine] = rows
            print(mode, engine, 'qualified', flush=True)
        evidence['parity'] = compare(parsed['silex'], parsed['jolt']);report['modes'][mode] = evidence
        (BUILD/f'{stem}-qualification.json').write_text(json.dumps(report, indent=2)+'\n');print(mode, 'dynamic rotation parity green', flush=True)
    if args.mode == 'both':
        for engine in ('jolt', 'silex'):
            if (BUILD/f'{stem}-{engine}-debug.txt').read_bytes() != (BUILD/f'{stem}-{engine}-release.txt').read_bytes():
                fail(f'{engine} Debug/Release differ')
        report['debug_release_identical'] = True
        (BUILD/f'{stem}-qualification.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
