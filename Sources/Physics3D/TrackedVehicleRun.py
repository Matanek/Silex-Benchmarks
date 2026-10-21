#!/usr/bin/env python3
"""Qualify pinned Jolt track coupling in flight before the Silex implementation."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, checked, fail, verified_source

KEYS = {(case, rate, step) for case in range(16) for rate in (60, 120)
        for step in range(2*rate+1)}
TOLERANCES = dict(body=1e-5, angular_step=1e-4, wheel_angle_step=1e-4,
                  engine_rpm=.02, clutch=1e-5, mode_angular=1e-4)


def near(a, b, tolerance, label):
    error = abs(a-b)
    if not math.isfinite(error) or error > tolerance:
        fail(f'{label}: {a} versus {b}, error {error}, tolerance {tolerance}')
    return error


def parse(raw):
    rows = {}
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 34 or fields[0] != 'tracked-air':
            fail('invalid tracked-air row')
        key = tuple(map(int, fields[1:4]))
        values = tuple(struct.unpack('f', struct.pack('f', float(value)))[0] for value in fields[4:])
        if key not in KEYS or key in rows or not all(map(math.isfinite, values)):
            fail('invalid tracked-air key or value')
        rows[key] = values
    if set(rows) != KEYS:
        fail('incomplete tracked-air witness')
    return rows


def command(case, step, rate):
    throttle, left, right, brake = .5, 1., 1., 0.
    if case == 1:
        left = .5
    if case == 2:
        left = -1
    if case == 3:
        left, right = -.5, -1
    if case in (4, 13):
        throttle = -.5
    if case in (7, 8, 15):
        throttle, brake = 0., .25 if case == 7 else 1.
    if case == 14 and step >= rate:
        left = -1
    return throttle, left, right, brake


def initial(case):
    omega = [0., 0.]
    if case in (5, 6, 7, 8, 15):
        omega = [20., 40.]
    if case == 9:
        omega = [1000., 1000.]
    gear = -1 if case == 4 else 0 if case in (5, 12, 13) else 1
    return [0., 3., 0., 0., 0., 0., 0., 0., 0., 1., 0., 0., 0.,
            0. if case == 10 else 1000., float(gear), 0. if case == 6 else 1.,
            *omega, *([0.]*12)]


def radius(case, index):
    return .2 + .1*(index % 3) if case == 11 else .3


def step_reference(old, case, step, rate, clutch_left):
    dt = 1/rate
    throttle, left, right, brake = command(case, step, rate)
    ratios = left, right
    omegas = [old[16+i]*(1-.5*dt) for i in range(2)]
    angles = [math.fmod(old[19+2*i] + omegas[i//3]*radius(case, 3*(i//3))/radius(case, i)*dt,
                        2*math.pi) for i in range(6)]
    minimum = 0. if case == 10 else 1000.
    rpm, gear, clutch = old[13:16]
    if gear != 0 and clutch > .001:
        fastest = (max if gear > 0 else min)(omegas[0]*3, omegas[1]*4)
        rpm = min(6000., max(minimum, fastest*gear*60/(2*math.pi)))
    else:
        rpm = min(6000., max(minimum, rpm*(1-.2*dt)))
        if case not in (12, 13):
            rpm = min(6000., max(minimum, rpm + 60/(2*math.pi)*12*abs(throttle)*dt/.5))
    if case in (12, 13):
        requested = 1. if throttle > 0 else -1. if throttle < 0 else 0.
        if gear == 0 or throttle*gear < 0:
            gear = requested
            clutch = 0.
            clutch_left = .3
        elif clutch_left > 0:
            clutch_left = max(0., clutch_left-dt)
            clutch = 1-clutch_left/.3
        else:
            clutch = 1.
    transmission_torque = clutch*gear*12*abs(throttle)
    for i, (inertia, differential, ratio) in enumerate(zip((10., 20.), (3., 4.), ratios)):
        if transmission_torque != 0:
            maximum = rpm/(gear*differential*ratio*60/(2*math.pi))*1.001
            if omegas[i]*maximum < 0 or abs(omegas[i]) < abs(maximum):
                omegas[i] += differential*ratio*transmission_torque*dt/inertia
    numerator = left*omegas[1]-right*omegas[0]
    if left*right > 0:
        correction = numerator/(left*20+right*10)
        omegas[0] += correction*10
        omegas[1] -= correction*20
    else:
        correction = numerator/(right*10-left*20)
        omegas[0] += correction*10
        omegas[1] += correction*20
    for i, inertia in enumerate((10., 20.)):
        torque = 5000. if case == 8 else 1000. if case == 15 and i == 1 else 50.
        decrement = brake*torque*dt/inertia
        omegas[i] = math.copysign(max(0., abs(omegas[i])-decrement), omegas[i])
    wheels = []
    for i in range(6):
        wheels.extend([omegas[i//3]*radius(case, 3*(i//3))/radius(case, i), angles[i]])
    return [*old[:13], rpm, gear, clutch, *omegas, *wheels], clutch_left


def qualify(rows):
    errors = dict(angular=0., angle=0., rpm=0., clutch=0., belt=0.)
    for case in range(16):
        for rate in (60, 120):
            first = rows[case, rate, 0]
            for a, b in zip(first, initial(case)):
                near(a, b, 1e-5, f'initial case {case}')
            clutch_left = 0.
            for step in range(1, 2*rate+1):
                old, row = rows[case, rate, step-1], rows[case, rate, step]
                expected, clutch_left = step_reference(old, case, step-1, rate, clutch_left)
                for i, value in enumerate(initial(case)[:13]):
                    near(row[i], value, TOLERANCES['body'], f'body {case} {rate} {step} {i}')
                errors['rpm'] = max(errors['rpm'], near(row[13], expected[13], TOLERANCES['engine_rpm'], 'engine RPM'))
                near(row[14], expected[14], 0, 'gear')
                errors['clutch'] = max(errors['clutch'], near(row[15], expected[15], TOLERANCES['clutch'], 'clutch'))
                for i in (16, 17, 18, 20, 22, 24, 26, 28):
                    errors['angular'] = max(errors['angular'], near(row[i], expected[i], TOLERANCES['angular_step'], f'angular step {case} {rate} {step} {i}'))
                for i in range(6):
                    offset = 18+2*i
                    difference = math.remainder(row[offset+1]-expected[offset+1], 2*math.pi)
                    errors['angle'] = max(errors['angle'], near(difference, 0., TOLERANCES['wheel_angle_step'], f'wheel angle {case} {rate} {step} {i}'))
                    belt = row[offset]*radius(case, i)
                    driven = row[16+i//3]*radius(case, 3*(i//3))
                    errors['belt'] = max(errors['belt'], near(belt, driven, 1e-4, 'common belt speed'))
                if not 0 <= row[13] <= 6000 or not 0 <= row[15] <= 1:
                    fail('engine or clutch outside domain')
                if (case == 10 or case == 8 and step >= math.ceil(40*20/5000*rate)) and row[16:18] != (0., 0.):
                    fail('zero-idle startup moved or finite-torque stop bound exceeded')
                if case in (12, 13) and abs(row[14]) != 1:
                    fail('airborne automatic gearbox unexpectedly shifted up')
    return errors


def rejected(action):
    try:
        action()
    except (ValueError, OverflowError):
        return
    fail('corrupt tracked witness accepted')


def self_test(raw, rows):
    lines = raw.splitlines()
    rejected(lambda: parse('\n'.join(lines[1:])))
    rejected(lambda: parse(raw.rstrip('\n')+'\n'+lines[0]))
    for index, value in ((0, 'other'), (1, '16'), (2, '61'), (4, 'nan'), (4, 'inf')):
        values = lines[0].split()
        values[index] = value
        rejected(lambda: parse(' '.join(values)+'\n'+'\n'.join(lines[1:])))
    for channel in range(30):
        altered = dict(rows)
        row = list(rows[1, 120, 90])
        row[channel] += 100.
        altered[1, 120, 90] = tuple(row)
        rejected(lambda: qualify(altered))
    return 37


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--mode', choices=('Debug', 'Release', 'both'), default='both')
    args = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f'run from workspace or Spec group root: {GROUP}')
    source, digest = verified_source(args.archive)
    report = dict(schema=1, fixture='tracked-air-coupling-v1', oracle_revision=REFERENCE,
                  archive_sha256=digest, tolerances=TOLERANCES,
                  scope='Reference Jolt only. Six wheels, two tracks in flight, 16 cases at 60/120 Hz. Per-step independent scalar checks, no ground or Silex capability qualified.', modes={})
    parsed = {}
    for mode in ('Debug', 'Release') if args.mode == 'both' else (args.mode,):
        oracle = build_oracle(source, mode, HERE/'TrackedVehicleOracle.cpp', 'tracked-vehicle-oracle')
        raw = checked([str(oracle)])
        (BUILD/f'tracked-air-jolt-{mode.lower()}.txt').write_text(raw)
        rows = parse(raw)
        errors = qualify(rows)
        guards = self_test(raw, rows)
        parsed[mode] = rows
        report['modes'][mode] = dict(observations=len(rows), errors=errors, guards=guards,
                                   sha256=hashlib.sha256(raw.encode()).hexdigest())
        print(f'{mode}: {len(rows)} Jolt track observations, {guards} corruptions rejected', flush=True)
        (BUILD/'tracked-air-reference.json').write_text(json.dumps(report, indent=2)+'\n')
    if len(parsed) == 2:
        maxima = []
        for key in KEYS:
            for i, (a, b) in enumerate(zip(parsed['Debug'][key], parsed['Release'][key])):
                maxima.append(near(a, b, .02 if i == 13 else 1e-4, 'Debug/Release reference parity'))
        report['cross_mode_maximum'] = max(maxima)
        (BUILD/'tracked-air-reference.json').write_text(json.dumps(report, indent=2)+'\n')
        print('Debug/Release reference parity green', flush=True)


if __name__ == '__main__':
    main()
