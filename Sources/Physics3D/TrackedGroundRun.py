#!/usr/bin/env python3
"""Qualify tracked driving, skid steering, pivoting and braking on a plane."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from VehicleInclineRun import rotation_error
from TrackedVehicleRun import near, rejected
from VehicleTiresRun import add, cross, dot, norm, scale

KEYS = {(case, rate, step) for case in range(6) for rate in (60, 120)
        for step in range(8*rate+1)}
PARITY = (.05, .1, .02, .15)
IMPULSE = .1
FORCE_MEAN = 20.
TORQUE_MEAN = 30.
ROTATION_INCREMENT = .1


def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def parse(raw):
    rows = {}
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 118 or fields[0] != 'tracked-ground':
            fail('invalid tracked-ground row')
        key = tuple(map(int, fields[1:4]))
        values = tuple(struct.unpack('f', struct.pack('f', float(x)))[0] for x in fields[4:])
        if key not in KEYS or key in rows or not all(map(math.isfinite, values)):
            fail('invalid tracked-ground key or value')
        rows[key] = values
    if set(rows) != KEYS:
        fail('incomplete tracked-ground witness')
    return rows


def wheel(row, index):
    return row[18+16*index:34+16*index]


def force(w):
    lateral = cross(w[13:16], w[10:13])
    return add(scale(w[10:13], w[1]), add(scale(w[13:16], w[4]), scale(lateral, w[5])))


def yaw(row):
    x, y, z, w = row[6:10]
    return math.atan2(2*(x*z+y*w), 1-2*(x*x+y*y))


def post_collision_speeds(old, case, step, rate):
    ratio = (-1. if case == 4 else .5 if case == 2 else 1., .5 if case == 3 else 1.)
    gear = -1 if case == 1 else 1
    driving = 2*rate <= step < 4*rate
    omega = list(old[16:18])
    rpm = min(6000., max(1000., (min if gear < 0 else max)(omega)*6*gear*60/(2*math.pi)))
    torque = gear*15*(.8 if driving else 0.)
    for i in range(2):
        maximum = rpm/(gear*6*ratio[i]*60/(2*math.pi))*1.001
        if omega[i]*maximum < 0 or abs(omega[i]) < abs(maximum):
            omega[i] += 6*ratio[i]*torque/rate/2
    difference = ratio[0]*omega[1]-ratio[1]*omega[0]
    if ratio[0]*ratio[1] > 0:
        correction = difference/(2*ratio[0]+2*ratio[1])
        omega[0] += 2*correction
        omega[1] -= 2*correction
    else:
        correction = difference/(2*ratio[1]-2*ratio[0])
        omega[0] += 2*correction
        omega[1] += 2*correction
    if not driving:
        omega = [math.copysign(max(0., abs(x)-1500/rate/2), x) for x in omega]
    return omega


def qualify(rows, engine='jolt'):
    residuals = dict(linear_impulse=0., angular_impulse=0., wheel_angle=0., belt=0., rpm=0.)
    for case in range(6):
        for rate in (60, 120):
            initial = rows[case, rate, 0]
            near(norm(sub(initial[:3], (0., 1.15, 0.))), 0, 1e-5, 'initial chassis')
            for i in list(range(3, 9))+list(range(10, 13))+list(range(16, 18)):
                near(initial[i], 0, 1e-5, 'initial body or tracks')
            near(initial[9], 1, 1e-5, 'initial quaternion')
            total_load = 0.
            for step in range(8*rate+1):
                row = rows[case, rate, step]
                if norm(row[:3]) > 100 or not .4 < row[1] < 2 or norm(row[3:6]) > 25 or norm(row[10:13]) > 25:
                    fail('tracked body outside fixture bounds')
                near(dot(row[6:10], row[6:10]), 1, 1e-4, 'unit body quaternion')
                if not 1000 <= row[13] <= 6000 or row[14] != (-1 if case == 1 else 1) or row[15] != 1:
                    fail('manual tracked powertrain outside fixture domain')
                total_force = (0., -981., 0.)
                torque = (0., 0., 0.)
                old = rows[case, rate, step-1] if step else row
                for index in range(6):
                    w = wheel(row, index)
                    if not 0 <= w[0] <= .60001 or not 0 <= w[1] < 100000 or w[6] not in (0., 1.):
                        fail('invalid tracked suspension or support')
                    expected_speed = row[16+index//3]
                    if engine == 'jolt' and step and not w[6]:
                        expected_speed = post_collision_speeds(old, case, step-1, rate)[index//3]
                    residuals['belt'] = max(residuals['belt'], near(w[2], expected_speed, 1e-4, 'belt angular velocity at reported observation boundary'))
                    if w[6]:
                        near(w[8], 0., 1e-5, 'ground contact plane')
                        near(norm(w[10:13]), 1, 1e-4, 'unit contact normal')
                        near(norm(w[13:16]), 1, 1e-4, 'unit contact longitudinal')
                        near(dot(w[10:13], w[13:16]), 0, 1e-4, 'orthogonal contact basis')
                        grip = 0. if case == 5 else 1.
                        if abs(w[4]) > grip*w[1]+.002 or abs(w[5]) > math.sqrt(.15)*grip*w[1]+.002:
                            fail('track force exceeds Coulomb capacity')
                        value = force(w)
                        total_force = add(total_force, value)
                        torque = add(torque, cross(sub(w[7:10], old[:3]), value))
                    elif any(abs(x) > .002 for x in (w[1], w[4], w[5])):
                        fail('unsupported track wheel applies force')
                    if step:
                        before = wheel(old, index)
                        angle = math.remainder(w[3]-before[3]-old[16+index//3]/rate, 2*math.pi)
                        residuals['wheel_angle'] = max(residuals['wheel_angle'], near(angle, 0, 1e-4, 'wheel angle before torque'))
                if step:
                    momentum = sub(scale(sub(row[3:6], old[3:6]), 100.), scale(total_force, 1/rate))
                    angular = sub(scale(sub(row[10:13], old[10:13]), 100.), scale(torque, 1/rate))
                    residuals['linear_impulse'] = max(residuals['linear_impulse'], near(norm(momentum), 0., IMPULSE, f'body impulse {case} {rate} {step}'))
                    residuals['angular_impulse'] = max(residuals['angular_impulse'], near(norm(angular), 0., IMPULSE, f'body angular impulse {case} {rate} {step}'))
                    if norm(sub(row[:3], old[:3])) > (norm(row[3:6])+norm(old[3:6]))/rate+.01:
                        fail('unphysical tracked position jump')
                    rpm = (min if case == 1 else max)(old[16], old[17])*6*row[14]*60/(2*math.pi)
                    residuals['rpm'] = max(residuals['rpm'], near(row[13], min(6000, max(1000, rpm)), .02, 'connected tracked engine RPM'))
                if step > 7*rate:
                    if any(wheel(row, i)[6] != 1. for i in range(6)):
                        fail('tracked recovery missing a support')
                    near(row[1], .88365, .003, 'recovered tracked height')
                    for i in range(6):
                        near(wheel(row, i)[1], 163.5, 2., 'recovered wheel load')
                    total_load += sum(wheel(row, i)[1] for i in range(6))
            near(total_load/rate, 981, 2, 'recovered normal load')
            end = rows[case, rate, 8*rate]
            if norm(end[3:6]) >= .05 or norm(end[10:13]) >= .05:
                fail('tracked braking did not settle')
            driven = rows[case, rate, 4*rate]
            if case in (0, 1) and driven[2]*(1 if case == 0 else -1) <= 1:
                fail('tracked drive missing forward/reverse progress')
            if case in (2, 3) and yaw(driven)*(-1 if case == 2 else 1) <= .1:
                fail('tracked curve missing the requested turn')
            if case == 4 and yaw(driven) >= -.1:
                fail('tracked pivot missing counter-rotation')
            if case == 5:
                for step in range(8*rate+1):
                    row = rows[case, rate, step]
                    near(norm((row[0], row[2], row[3], row[5])), 0, 1e-4, 'zero-grip chassis translation')
                if min(abs(driven[16]), abs(driven[17])) <= .1:
                    fail('zero-grip powered tracks did not spin')
    return residuals


def compare(first, second, conditioned_velocity=False):
    maxima = [0.]*4
    for key in KEYS:
        a, b = first[key], second[key]
        errors = norm(sub(a[:3], b[:3])), norm(sub(a[3:6], b[3:6])), rotation_error(a[6:10], b[6:10]), norm(sub(a[10:13], b[10:13]))
        for i, (error, limit) in enumerate(zip(errors, PARITY)):
            maxima[i] = max(maxima[i], error)
            if not conditioned_velocity or i in (0, 2):
                near(error, 0., limit, f'tracked parity {key} channel {i}')
    velocity_mean = angular_mean = 0.
    if conditioned_velocity:
        for case in range(6):
            for rate in (60, 120):
                for phase in range(8):
                    for start, tolerance in ((3, PARITY[1]), (10, PARITY[3])):
                        means = []
                        for rows in (first, second):
                            value = (0., 0., 0.)
                            for step in range(phase*rate+1, (phase+1)*rate+1):
                                value = add(value, scale(rows[case, rate, step][start:start+3], 1/rate))
                            means.append(value)
                        error = near(norm(sub(*means)), 0, tolerance, 'one-second mirrored body velocity')
                        if start == 3:
                            velocity_mean = max(velocity_mean, error)
                        else:
                            angular_mean = max(angular_mean, error)
    force_max = torque_max = normal_max = rotation_max = 0.
    for case in range(6):
        for rate in (60, 120):
            for phase in range(8):
                forces, torques, normals, angles = [], [], [], []
                for rows in (first, second):
                    accumulated_force = (0., 0., 0.)
                    accumulated_torque = (0., 0., 0.)
                    loads = [0.]*6
                    rotations = [0.]*6
                    for step in range(phase*rate+1, (phase+1)*rate+1):
                        row, old = rows[case, rate, step], rows[case, rate, step-1]
                        for index in range(6):
                            w, before = wheel(row, index), wheel(old, index)
                            value = force(w)
                            accumulated_force = add(accumulated_force, scale(value, 1/rate))
                            accumulated_torque = add(accumulated_torque, scale(cross(sub(w[7:10], old[:3]), value), 1/rate))
                            loads[index] += w[1]/rate
                            rotations[index] += math.remainder(w[3]-before[3], 2*math.pi)
                    forces.append(accumulated_force)
                    torques.append(accumulated_torque)
                    normals.append(loads)
                    angles.append(rotations)
                force_max = max(force_max, near(norm(sub(*forces)), 0, FORCE_MEAN, 'one-second resultant force mean'))
                torque_max = max(torque_max, near(norm(sub(*torques)), 0, TORQUE_MEAN, 'one-second resultant torque mean'))
                for index in range(6):
                    normal_max = max(normal_max, near(normals[0][index]-normals[1][index], 0, FORCE_MEAN, 'one-second wheel normal force mean'))
                    rotation_max = max(rotation_max, near(angles[0][index]-angles[1][index], 0, ROTATION_INCREMENT, 'one-second wheel rotation increment'))
    return dict(body=maxima, conditioned_velocity=conditioned_velocity, velocity_mean=velocity_mean, angular_mean=angular_mean, force_mean=force_max, torque_mean=torque_max, normal_force_mean=normal_max, rotation_increment=rotation_max)


def mirror_curves(rows):
    result = dict(rows)
    for (case, rate, step), row in rows.items():
        if case not in (2, 3):
            continue
        values = list(row)
        for index in (0, 3, 7, 8, 11, 12):
            values[index] = -values[index]
        values[16], values[17] = row[17], row[16]
        for index in range(6):
            target = 18+16*index
            w = list(wheel(row, (index+3) % 6))
            for component in (5, 7, 10, 13):
                w[component] = -w[component]
            values[target:target+16] = w
        result[5-case, rate, step] = tuple(values)
    return result


def self_test(raw, rows, engine):
    lines = raw.splitlines()
    rejected(lambda: parse('\n'.join(lines[1:])))
    rejected(lambda: parse(raw.rstrip('\n')+'\n'+lines[0]))
    for channel, value in ((0, 'other'), (1, '6'), (2, '61'), (4, 'nan'), (4, 'inf')):
        values = lines[0].split()
        values[channel] = value
        rejected(lambda: parse(' '.join(values)+'\n'+'\n'.join(lines[1:])))
    for channel in range(114):
        altered = dict(rows)
        values = list(rows[2, 120, 900])
        values[channel] += 100.
        altered[2, 120, 900] = tuple(values)
        rejected(lambda: qualify(altered, engine))
    return 121


def compare_air(first, second):
    maxima = [0.]*30
    for key, row in first.items():
        for index, (a, b) in enumerate(zip(row, second[key])):
            difference = math.remainder(a-b, 2*math.pi) if index in (19, 21, 23, 25, 27, 29) else a-b
            tolerance = .02 if index == 13 else 1e-5 if index <= 15 else 1e-4
            maxima[index] = max(maxima[index], near(abs(difference), 0., tolerance, f'tracked air parity {key} channel {index}'))
    return maxima


def main():
    import TrackedVehicleRun as air
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--mode', choices=('Debug', 'Release', 'both'), default='both')
    args = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f'run from workspace or Spec group root: {GROUP}')
    source, digest = verified_source(args.archive)
    report = dict(schema=1, fixture='tracked-driving-ray-v1', oracle_revision=REFERENCE, archive_sha256=digest,
                  recipe=dict(units='SI', mass=100, inertia=[100]*3, chassis=[1.4, .4, 2.4],
                              wheel_positions=[[x, 0, z] for x in (-.6, .6) for z in (-1, 0, 1)],
                              radius=.3, travel=[.2, .6], stiffness=10000, damping=1000,
                              track_inertia=2, track_damping=0, differential=6, brake_torque=1500,
                              engine_torque=15, rpm=[1000, 6000], engine_damping=0, constant_torque_curve=1,
                              manual_ratios=[-1, 1], throttle=.8, tire_friction=[1, .15],
                              plane_friction=1, contact='ray', phases_seconds=[2, 2, 4], gravity=[0, -9.81, 0],
                              velocity_iterations=12, position_iterations=4, substeps=1, workers=1),
                  tolerances=dict(body_pointwise=PARITY, impulse=IMPULSE, wheel_angle_step=1e-4, belt_angular=1e-4,
                                  rpm=.02, resultant_force_mean=FORCE_MEAN, resultant_torque_mean=TORQUE_MEAN,
                                  wheel_normal_force_mean=FORCE_MEAN, rotation_increment=ROTATION_INCREMENT),
                  scope='Air: 16 reference cases at 60/120 Hz with float32 reconstruction and per-step checks. Ground: 6 ray-plane cases at 60/120 Hz, pointwise body parity and physical balances. Contact resultants, normal loads and rotation increments compared on command-aligned one-second windows; individual tangential contact sharing is not qualified. Jolt unsupported wheel angular observations are checked at their post-collision cache boundary; Silex exposes final belt speed. Mirror pose is pointwise, mirror velocities are one-second means, same thresholds. No volumetric track contact, general terrain or rendered scene qualified here.', modes={})
    modes = ('Debug', 'Release') if args.mode == 'both' else (args.mode,)
    parsed = {}
    for mode in modes:
        air_oracle = build_oracle(source, mode, HERE/'TrackedVehicleOracle.cpp', 'tracked-vehicle-oracle')
        ground_oracle = build_oracle(source, mode, HERE/'TrackedGroundOracle.cpp', 'tracked-ground-oracle')
        binaries = dict(air=build_silex(mode, 'TrackedAir.sx', 'tracked-air-silex', True),
                        ground=build_silex(mode, 'TrackedGround.sx', 'tracked-ground-silex', True))
        evidence = {}
        for label, oracle in (('air', air_oracle), ('ground', ground_oracle)):
            rows = {}
            proofs = {}
            for engine, binary in (('jolt', oracle), ('silex', binaries[label])):
                raw = checked([str(binary)])
                (BUILD/f'tracked-{label}-{engine}-{mode.lower()}.txt').write_text(raw)
                values = air.parse(raw) if label == 'air' else parse(raw)
                validation = air.qualify(values) if label == 'air' else qualify(values, engine)
                guards = air.self_test(raw, values) if label == 'air' else self_test(raw, values, engine)
                rows[engine] = values
                proofs[engine] = dict(observations=len(values), qualification=validation, guards=guards,
                                      sha256=hashlib.sha256(raw.encode()).hexdigest())
                if label == 'ground':
                    proofs[engine]['mirror'] = compare(values, mirror_curves(values), conditioned_velocity=True)
                print(f'{mode} {label} {engine}: {len(values)} states, {guards} guards green', flush=True)
            proofs['parity'] = compare_air(rows['silex'], rows['jolt']) if label == 'air' else compare(rows['silex'], rows['jolt'])
            evidence[label] = proofs
            parsed[mode, label] = rows
        perturbed_raw = checked([str(ground_oracle), '--perturb'])
        (BUILD/f'tracked-ground-jolt-perturbed-{mode.lower()}.txt').write_text(perturbed_raw)
        perturbed = parse(perturbed_raw)
        evidence['jolt_height_perturbation'] = dict(qualification=qualify(perturbed, 'jolt'), parity=compare(parsed[mode, 'ground']['jolt'], perturbed),
                                                   sha256=hashlib.sha256(perturbed_raw.encode()).hexdigest())
        report['modes'][mode] = evidence
        (BUILD/'tracked-driving-qualification.json').write_text(json.dumps(report, indent=2)+'\n')
        print(f'{mode}: tracked air and ground qualification green', flush=True)
    if len(modes) == 2:
        cross_mode = {}
        for label in ('air', 'ground'):
            for engine in ('jolt', 'silex'):
                first, second = parsed['Debug', label][engine], parsed['Release', label][engine]
                raw_a = (BUILD/f'tracked-{label}-{engine}-debug.txt').read_bytes()
                raw_b = (BUILD/f'tracked-{label}-{engine}-release.txt').read_bytes()
                cross_mode[label+'-'+engine] = dict(byte_identical=raw_a == raw_b,
                                                     comparison=compare_air(first, second) if label == 'air' else compare(first, second))
        report['cross_mode'] = cross_mode
        (BUILD/'tracked-driving-qualification.json').write_text(json.dumps(report, indent=2)+'\n')
        print('Tracked driving Debug/Release comparison green', flush=True)


if __name__ == '__main__':
    main()
