#!/usr/bin/env python3
"""Qualifier la réaction réciproque d'un support de masse finie."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from TrackedGroundRun import wheel, force, sub, PARITY
from TrackedVehicleRun import near, rejected
from VehicleTiresRun import add, cross, dot, norm, scale
from VehicleInclineRun import rotation_error
from MotorcycleReferenceRun import rotate

TOTAL = 6
CASES = range(6)
RATES = (60, 120)
KEYS = {(case, rate, step) for case in CASES for rate in RATES for step in range(TOTAL * rate + 1)}


def parse(raw):
    rows = {}
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 131 or fields[0] != 'tracked-dynamic-platform':
            fail('invalid dynamic platform row')
        key = tuple(map(int, fields[1:4]))
        values = tuple(struct.unpack('f', struct.pack('f', float(value)))[0] for value in fields[4:])
        if key not in KEYS or key in rows or not all(map(math.isfinite, values)):
            fail('invalid dynamic platform key/value')
        rows[key] = values
    if set(rows) != KEYS:
        fail('incomplete dynamic platform witness')
    return rows


def mass_for(case):
    return 200.0 if case >= 4 else 1000.0


def impulse(case, step, rate):
    strength = 2 * mass_for(case) if step == 2 * rate else -2 * mass_for(case) if step == 4 * rate else 0.0
    if case == 0:
        strength = 0.0
    return (strength, 0.0, 0.0) if case == 1 else (0.0, 0.0, strength)


def horizontal(value):
    return value[0], 0.0, value[2]


def inverse_rotate(quaternion, value):
    return rotate((-quaternion[0], -quaternion[1], -quaternion[2], quaternion[3]), value)


def qualify_case(rows, engine, case, rate):
    mass = mass_for(case)
    free = case in (3, 5)
    axis = 0 if case == 1 else 2
    worst = dict(linear=0.0, angular=0.0, reciprocal=0.0, momentum=0.0, center_of_mass=0.0, belt=0.0, angle=0.0, free_momentum=0.0)
    initial = rows[case, rate, 0]
    for value, target in zip(initial[:18], (0, 1.15, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1000, 0, 1, 0, 0)):
        near(value, target, 1e-5, 'initial neutral chassis')
    for value, target in zip(initial[114:127], (0, -.2, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0)):
        near(value, target, 1e-5, 'initial resting dynamic support')
    initial_center = scale(add(scale(initial[:3], 100.0), scale(initial[114:117], mass)), 1 / (100 + mass))
    center_integral = initial_center
    external_momentum = (0.0, 0.0, 0.0)
    carried = []
    carrier = []
    minimum_supports = 6
    peak = 0.0
    for step in range(TOTAL * rate + 1):
        row = rows[case, rate, step]
        old = rows[case, rate, step - 1] if step else row
        if not .3 < row[1] < 4 or norm(row[:3]) > 100 or norm(row[3:6]) > 25 or norm(row[10:13]) > 5:
            fail('unbounded dynamic-platform chassis')
        if norm(row[114:117]) > 100 or norm(row[117:120]) > 25 or norm(row[124:127]) > 5:
            fail('unbounded dynamic support')
        for quaternion in (row[6:10], row[120:124]):
            near(dot(quaternion, quaternion), 1.0, 1e-4, 'unit body rotation')
            if rotate(quaternion, (0, 1, 0))[1] < .8:
                fail('overturned body or support')
        near(row[13], 1000.0, .02, 'idle neutral engine')
        near(row[14], 0.0, 0.0, 'neutral gearbox')
        near(row[15], 1.0, 1e-5, 'engaged neutral clutch')
        loads = (0.0, 0.0, 0.0)
        torque = (0.0, 0.0, 0.0)
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
        peak = max(peak, norm(row[3:6]))
        if step > rate:
            minimum_supports = min(minimum_supports, contacts)
        if step:
            applied = impulse(case, step - 1, rate)
            external_momentum = add(external_momentum, applied)
            worst['linear'] = max(worst['linear'], near(norm(sub(scale(sub(row[3:6], old[3:6]), 100.0), scale(add(loads, (0, -981, 0)), 1 / rate))), 0.0, .1, 'chassis linear impulse'))
            worst['angular'] = max(worst['angular'], near(norm(sub(scale(sub(row[10:13], old[10:13]), 100.0), scale(torque, 1 / rate))), 0.0, .1, 'chassis angular impulse'))
            reaction = sub(add(scale(sub(row[117:120], old[117:120]), mass), scale(loads, 1 / rate)), applied)
            worst['reciprocal'] = max(worst['reciprocal'], near(norm(horizontal(reaction)), 0.0, .1, 'opposite support impulse'))
            velocity_center = scale(add(scale(row[3:6], 100.0), scale(row[117:120], mass)), 1 / (100 + mass))
            center_integral = add(center_integral, scale(velocity_center, 1 / rate))
            if free:
                spin = 2 * (sum(row[16:18]) - sum(old[16:18])) + .3 * longitudinal / rate
                worst['free_momentum'] = max(worst['free_momentum'], near(spin, 0.0, .002, 'free track angular momentum'))
        momentum = add(scale(row[3:6], 100.0), scale(row[117:120], mass))
        worst['momentum'] = max(worst['momentum'], near(norm(horizontal(sub(momentum, external_momentum))), 0.0, .1, 'total horizontal momentum'))
        center = scale(add(scale(row[:3], 100.0), scale(row[114:117], mass)), 1 / (100 + mass))
        worst['center_of_mass'] = max(worst['center_of_mass'], near(norm(horizontal(sub(center, center_integral))), 0.0, .001, 'center of mass integration'))
        if 3 * rate <= step <= int(3.75 * rate):
            expected_support = 0.0 if case == 0 else 2 * mass / (mass + 100.0)
            expected_body = expected_support
            if free:
                inertia = 4.0 / .3 ** 2
                expected_support = 2 * mass / (mass + 100.0 * inertia / (100.0 + inertia))
                expected_body = inertia * expected_support / (100.0 + inertia)
            near(row[117 + axis], expected_support, .03, 'finite-mass support speed')
            near(row[3 + axis], expected_body, .03, 'carried or free rolling speed')
            carried.append(row[3 + axis])
            carrier.append(row[117 + axis])
        if step > (TOTAL - 1) * rate:
            if contacts != 6:
                fail('six final dynamic-platform supports missing')
            near(row[1] - row[115] - .2, .88365, .003, 'final relative chassis height')
            near(sum(wheel(row, index)[1] for index in range(6)), 981.0, 2.0, 'final supported weight')
            if any(norm(value) > .05 for value in (row[3:6], row[10:13], row[117:120], row[124:127])):
                fail('vehicle and dynamic support failed to stop')
    end = rows[case, rate, TOTAL * rate]
    center = scale(add(scale(end[:3], 100.0), scale(end[114:117], mass)), 1 / (100 + mass))
    expected_distance = 0.0 if case == 0 else 4 * mass / (mass + 100.0)
    expected = (expected_distance, 0.0, 0.0) if case == 1 else (0.0, 0.0, expected_distance)
    near(norm(horizontal(sub(sub(center, initial_center), expected))), 0.0, .001, 'final center of mass displacement')
    return dict(worst=worst, end_position=end[:3], platform_position=end[114:117], mean_vehicle_speed=sum(carried) / len(carried), mean_support_speed=sum(carrier) / len(carrier), peak_speed=peak, minimum_supports=minimum_supports)


def qualify(rows, engine):
    return {f'{case}/{rate}': qualify_case(rows, engine, case, rate) for case in CASES for rate in RATES}


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
    for index, value in ((0, 'other'), (1, '6'), (2, '61'), (4, 'nan'), (4, 'inf')):
        fields = lines[0].split()
        fields[index] = value
        rejected(lambda: parse(' '.join(fields) + '\n' + '\n'.join(lines[1:])))
    keys = [((2, 60, 180), range(127))]
    keys += [((case, rate, 3 * rate), (3, 5, 16, 114, 117, 119)) for case, rate in ((3, 120), (4, 60), (5, 120))]
    count = 7
    for key, channels in keys:
        for channel in channels:
            altered = dict(rows)
            row = list(rows[key])
            row[channel] += 100.0
            altered[key] = tuple(row)
            rejected(lambda: qualify_case(altered, engine, key[0], key[1]))
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--mode', choices=('Debug', 'Release', 'both'), default='both')
    args = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f'run from group root {GROUP}')
    source, digest = verified_source(args.archive)
    report = dict(schema=1, fixture='tracked-dynamic-platform-v1', velocity_iterations=48, position_iterations=4, oracle_revision=REFERENCE, archive_sha256=digest, body_tolerances=PARITY, support_tolerances=PARITY, modes={})
    for mode in ('Debug', 'Release') if args.mode == 'both' else (args.mode,):
        oracle = build_oracle(source, mode, HERE / 'TrackedDynamicPlatformOracle.cpp', 'tracked-dynamic-platform-oracle')
        silex = build_silex(mode, 'TrackedDynamicPlatform.sx', 'tracked-dynamic-platform-silex', True)
        parsed = {}
        evidence = {}
        for engine, binary in (('jolt', oracle), ('silex', silex)):
            raw = checked([str(binary)])
            (BUILD / f'tracked-dynamic-platform-{engine}-{mode.lower()}.txt').write_text(raw)
            rows = parse(raw)
            evidence[engine] = dict(states=len(rows), qualification=qualify(rows, engine), guards=self_test(raw, rows, engine), sha256=hashlib.sha256(raw.encode()).hexdigest())
            parsed[engine] = rows
            print(mode, engine, 'qualified', flush=True)
        evidence['parity'] = compare(parsed['silex'], parsed['jolt'])
        report['modes'][mode] = evidence
        (BUILD / 'tracked-dynamic-platform-qualification.json').write_text(json.dumps(report, indent=2) + '\n')
        print(mode, 'tracked dynamic platform parity green', flush=True)
    if args.mode == 'both':
        for engine in ('jolt', 'silex'):
            if (BUILD / f'tracked-dynamic-platform-{engine}-debug.txt').read_bytes() != (BUILD / f'tracked-dynamic-platform-{engine}-release.txt').read_bytes():
                fail(f'{engine} Debug/Release differ')
        report['debug_release_identical'] = True
        (BUILD / 'tracked-dynamic-platform-qualification.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
