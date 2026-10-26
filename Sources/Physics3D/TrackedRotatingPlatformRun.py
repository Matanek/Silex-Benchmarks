#!/usr/bin/env python3
"""Qualify offset tracked transport on a rotating support."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from TrackedBrakeOracle import build_tracked_oracle
from TrackedGroundRun import wheel, force, sub, PARITY
from TrackedVehicleRun import near, rejected
from VehicleTiresRun import add, cross, dot, norm, scale
from VehicleInclineRun import rotation_error
from MotorcycleReferenceRun import rotate

TOTAL=6
CASES=range(4)
RATES=(60,120)
KEYS={(k,r,t) for k in CASES for r in RATES for t in range(TOTAL*r+1)}


def f32(value):
    return struct.unpack('f',struct.pack('f',value))[0]


def parse(raw, combined=False):
    rows={}
    prefix='tracked-combined-platform' if combined else 'tracked-rotating-platform'
    for line in raw.splitlines():
        fields=line.split()
        if len(fields)!=131 or fields[0]!=prefix:fail(f'invalid {prefix} row')
        key=tuple(map(int,fields[1:4]));values=tuple(f32(float(x)) for x in fields[4:])
        if key not in KEYS or key in rows or not all(map(math.isfinite,values)):fail('invalid tracked-rotating-platform key/value')
        rows[key]=values
    if set(rows)!=KEYS:fail('incomplete tracked-rotating-platform witness')
    return rows


def spin_for(case, step, rate):
    return (-.25 if case == 2 else .25) if case and 2 * rate <= step < 4 * rate else 0.0


def inverse_rotate(q, value):
    return rotate((-q[0], -q[1], -q[2], q[3]), value)


def qualify_case(rows, engine, case, rate, combined=False):
    worst = dict(linear=0.0, angular=0.0, belt=0.0, angle=0.0, free_momentum=0.0, carrier=0.0)
    initial = rows[case, rate, 0]
    for value, target in zip(initial[:18], (1, 1.15, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1000, 0, 1, 0, 0)):
        near(value, target, 1e-5, 'initial offset neutral chassis')
    moving_slip = []
    free_rotors = []
    minimum_supports = 6
    for step in range(TOTAL * rate + 1):
        row = rows[case, rate, step]
        old = rows[case, rate, step - 1] if step else row
        omega = spin_for(case, step - 1, rate)
        moving = case > 0 and 2 * rate <= step - 1 < 4 * rate
        locked = case != 3 or (combined and not moving)
        direction = -1 if case == 2 else 1 if case else 0
        support_z = direction * 2 * min(max(step - 2 * rate, 0), 2 * rate) / rate if combined else 0.0
        linear = (0, 0, direction * 2 if combined and moving else 0)
        near(norm(sub(row[114:117], (0, -.2, support_z))), 0.0, 1e-4, 'integrated support center')
        near(norm(sub(row[117:120], linear)), 0.0, 1e-4, 'prescribed support linear velocity')
        near(norm(sub(row[124:127], (0, omega, 0))), 0.0, 1e-4, 'prescribed support spin')
        angle = direction * .25 * min(max(step - 2 * rate, 0), 2 * rate) / rate
        expected = (0, math.sin(angle / 2), 0, math.cos(angle / 2))
        worst['carrier'] = max(worst['carrier'], near(rotation_error(row[120:124], expected), 0.0, 1e-4, 'integrated support angle'))
        for quaternion in (row[6:10], row[120:124]):
            near(dot(quaternion, quaternion), 1.0, 1e-4, 'unit rotation')
        if not .3 < row[1] < 4 or norm(row[:3]) > 100 or norm(row[3:6]) > 25 or norm(row[10:13]) > 5:
            fail('unbounded rotating-platform chassis')
        if rotate(row[6:10], (0, 1, 0))[1] < .8:
            fail('overturned rotating-platform chassis')
        near(row[13], 1000, .02, 'idle engine')
        near(row[14], 0, 0, 'neutral gearbox')
        near(row[15], 1, 1e-5, 'engaged neutral clutch')
        loads = (0, 0, 0)
        torque = (0, 0, 0)
        contacts = 0
        longitudinal = 0.0
        for index in range(6):
            sample = wheel(row, index)
            side = index // 3
            if sample[6] not in (0.0, 1.0) or not 0 <= sample[0] <= .60001 or not 0 <= sample[1] < 100000:
                fail('invalid rotating-platform wheel domain')
            expected_speed = old[16 + side] if engine == 'jolt' and step and not sample[6] and case == 3 and not locked else 0.0 if engine == 'jolt' and step and not sample[6] else row[16 + side]
            worst['belt'] = max(worst['belt'], near(sample[2], expected_speed, 1e-4, 'common belt and wheel speed'))
            if locked:
                near(row[16 + side], 0, 1e-4, 'locked track')
            if step:
                increment = math.remainder(sample[3] - wheel(old, index)[3] - old[16 + side] / rate, 2 * math.pi)
                worst['angle'] = max(worst['angle'], near(increment, 0, 1e-4, 'wheel angle integral'))
            if sample[6]:
                contacts += 1
                normal = rotate(old[120:124], (0, 1, 0))
                near(norm(sub(sample[10:13], normal)), 0, 1e-4, 'actual rotating top normal')
                near(norm(sample[13:16]), 1, 1e-4, 'unit longitudinal direction')
                near(dot(sample[10:13], sample[13:16]), 0, 1e-4, 'orthogonal wheel frame')
                anchor = add(old[:3], rotate(old[6:10], (-.6 if index < 3 else .6, 0, index % 3 - 1)))
                direction_ray = rotate(old[6:10], (0, -1, 0))
                ray = sub(sample[7:10], anchor)
                distance = dot(ray, direction_ray)
                near(norm(sub(ray, scale(direction_ray, distance))), 0, 1e-4, 'contact on suspension ray')
                if not 0 <= distance <= .9001:
                    fail('contact outside suspension ray')
                near(sample[0], max(.2, distance - .3), 1e-4, 'suspension from geometry')
                local = inverse_rotate(old[120:124], sub(sample[7:10], old[114:117]))
                near(local[1], .2, 1e-4, 'rotating support top')
                if abs(local[0]) > 4.0001 or abs(local[2]) > 6.0001:
                    fail('contact outside rotating support')
                if abs(sample[4]) > sample[1] + .003 or abs(sample[5]) > math.sqrt(.15) * sample[1] + .003:
                    fail('rotating-platform friction capacity')
                value = force(sample)
                loads = add(loads, value)
                torque = add(torque, cross(sub(sample[7:10], old[:3]), value))
                longitudinal += sample[4]
            elif any(abs(sample[channel]) > .002 for channel in (1, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15)):
                fail('unsupported wheel has contact effort')
        if step > rate:
            minimum_supports = min(minimum_supports, contacts)
        if step:
            worst['linear'] = max(worst['linear'], near(norm(sub(scale(sub(row[3:6], old[3:6]), 100), scale(add(loads, (0, -981, 0)), 1 / rate))), 0, .1, 'chassis linear impulse'))
            worst['angular'] = max(worst['angular'], near(norm(sub(scale(sub(row[10:13], old[10:13]), 100), scale(torque, 1 / rate))), 0, .1, 'chassis angular impulse'))
            if norm(sub(row[:3], old[:3])) > (norm(row[3:6]) + norm(old[3:6])) / rate + .01:
                fail('chassis pose discontinuity')
            if case == 3 and not locked:
                spin = 2 * (sum(row[16:18]) - sum(old[16:18])) + .3 * longitudinal / rate
                worst['free_momentum'] = max(worst['free_momentum'], near(spin, 0, .002, 'free track angular momentum'))
        if int(3.25 * rate) <= step <= int(3.75 * rate):
            tangent = add(linear, cross((0, omega, 0), sub(row[:3], row[114:117])))
            slip = norm(sub(row[3:6], tangent))
            moving_slip.append(slip)
            free_rotors.append(sum(abs(value) for value in row[16:18]))
            if case != 3:
                near(slip, 0, .05, 'locked chassis follows point velocity')
                near(row[11], omega, .05, 'locked chassis follows support yaw')
        if step > 5 * rate:
            if contacts != 6:
                fail('six final rotating-platform supports missing')
            near(row[1], .88365, .003, 'final suspension height')
            near(sum(wheel(row, i)[1] for i in range(6)), 981, 2, 'final supported weight')
            if norm(row[3:6]) > .05 or norm(row[10:13]) > .05:
                fail('rotating-platform chassis failed to stop')
    mean_slip = sum(moving_slip) / len(moving_slip)
    mean_rotors = sum(free_rotors) / len(free_rotors)
    if case == 3 and (mean_slip <= .02 or mean_rotors <= .05):
        fail('free tracks not distinguished from locked support')
    end = rows[case, rate, TOTAL * rate]
    if case == 0:
        near(norm((end[0] - 1, end[2])), 0, .01, 'stationary offset control')
    return dict(worst=worst, end_position=end[:3], end_rotation=end[6:10], mean_relative_speed=mean_slip, mean_free_rotors=mean_rotors, minimum_supports=minimum_supports)


def mirror(rows):
    worst = [0.0] * 4
    for rate in RATES:
        for step in range(TOTAL * rate + 1):
            first, second = rows[1, rate, step], rows[2, rate, step]
            errors = norm(sub(first[:3], (second[0], second[1], -second[2]))), norm(sub(first[3:6], (second[3], second[4], -second[5]))), rotation_error(first[6:10], (-second[6], -second[7], second[8], second[9])), norm(sub(first[10:13], (-second[10], -second[11], second[12])))
            for index, (error, limit) in enumerate(zip(errors, (.005, .02, .005, .02))):
                worst[index] = max(worst[index], near(error, 0, limit, 'opposite rotations mirror'))
    return worst


def qualify(rows, engine, combined=False):
    return dict(outcomes={f'{case}/{rate}': qualify_case(rows, engine, case, rate, combined) for case in CASES for rate in RATES}, mirror=mirror(rows))


def compare(a,b):
    body=[0.]*4;force_error=torque_error=normal_error=angle_error=0.
    for key in KEYS:
        x,y=a[key],b[key]
        errors=norm(sub(x[:3],y[:3])),norm(sub(x[3:6],y[3:6])),rotation_error(x[6:10],y[6:10]),norm(sub(x[10:13],y[10:13]))
        for i,(error,limit) in enumerate(zip(errors,PARITY)):body[i]=max(body[i],near(error,0.,limit,f'chassis parity {key}/{i}'))
    for case in CASES:
        for rate in RATES:
            for phase in range(TOTAL):
                sums=[]
                for rows in (a,b):
                    f=(0,0,0);torque=(0,0,0);normal=[0.]*6;angles=[0.]*6
                    for t in range(phase*rate+1,(phase+1)*rate+1):
                        row,old=rows[case,rate,t],rows[case,rate,t-1]
                        for i in range(6):
                            w=wheel(row,i);value=force(w);f=add(f,scale(value,1/rate));torque=add(torque,scale(cross(sub(w[7:10],old[:3]),value),1/rate));normal[i]+=w[1]/rate;angles[i]+=math.remainder(w[3]-wheel(old,i)[3],2*math.pi)
                    sums.append((f,torque,normal,angles))
                x,y=sums
                force_error=max(force_error,near(norm(sub(x[0],y[0])),0.,20.,'window force'))
                torque_error=max(torque_error,near(norm(sub(x[1],y[1])),0.,30.,'window torque'))
                for i in range(6):
                    normal_error=max(normal_error,near(x[2][i]-y[2][i],0.,20.,'window normal'))
                    angle_error=max(angle_error,near(x[3][i]-y[3][i],0.,.1,'window rotation'))
    return dict(body=body,force_mean=force_error,torque_mean=torque_error,normal_mean=normal_error,rotation_increment=angle_error)



def static_law(rows):
    results = {}
    for case in (1, 2):
        for rate in RATES:
            load = (0, 0, 0)
            required = (0, 0, 0)
            torque = (0, 0, 0)
            slip = 0.0
            count = 0
            for step in range(math.ceil(3.25 * rate), math.floor(3.75 * rate) + 1):
                row, old = rows[case, rate, step], rows[case, rate, step - 1]
                omega = old[124:127]
                radius = sub(old[:3], old[114:117])
                required = add(required, scale(cross(omega, cross(omega, radius)), 100))
                for index in range(6):
                    sample = wheel(row, index)
                    near(sample[6], 1, 0, 'static law contact')
                    value = force(sample)
                    load = add(load, value)
                    torque = add(torque, cross(sub(sample[7:10], old[:3]), value))
                    chassis_point = add(row[3:6], cross(row[10:13], sub(sample[7:10], row[:3])))
                    support_point = add(row[117:120], cross(row[124:127], sub(sample[7:10], row[114:117])))
                    slip = max(slip, near(norm(sub(chassis_point, support_point)), 0, .05, 'static law contact slip'))
                for rotor in row[16:18]:
                    near(rotor, 0, 1e-4, 'static law locked belt')
                count += 1
            load, required, torque = scale(load, 1 / count), scale(required, 1 / count), scale(torque, 1 / count)
            error = near(norm((load[0] - required[0], 0, load[2] - required[2])), 0, 2, 'static law centripetal force')
            near(load[1], 981, 2, 'static law supported weight')
            near(norm(torque), 0, 2, 'static law mean torque')
            results[f'{case}/{rate}'] = dict(mean_force=load, analytical_force=required, horizontal_error=error,
                                           mean_torque=torque, maximum_contact_slip=slip)
    return results


def self_test(raw, rows, engine, combined=False):
    lines = raw.splitlines()
    rejected(lambda: parse('\n'.join(lines[1:]), combined))
    rejected(lambda: parse(raw + lines[0] + '\n', combined))
    for index, value in ((0, 'other'), (1, '4'), (2, '61'), (4, 'nan'), (4, 'inf')):
        fields = lines[0].split();fields[index] = value
        rejected(lambda: parse(' '.join(fields) + '\n' + '\n'.join(lines[1:]), combined))
    count = 7
    for key, channels in [((1,60,180), range(127)), ((3,120,420), (3,5,16,17,124)), ((0,60,210), (114,117,124))]:
        for channel in channels:
            altered = dict(rows);row = list(rows[key]);row[channel] += 100.0;altered[key] = tuple(row)
            rejected(lambda: qualify_case(altered, engine, key[0], key[1], combined));count += 1
    altered = dict(rows);row = list(rows[2,60,210]);row[2] += .02;altered[2,60,210] = tuple(row)
    rejected(lambda: mirror(altered));count += 1
    return count


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');parser.add_argument('--combined',action='store_true',help='Compose linear and angular support velocities; brake free tracks again after4s');parser.add_argument('--stable-brakes',action='store_true',help='Explicit symmetric accumulated brake-friction variant of pinned Jolt');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from group root {GROUP}')
    source,digest=verified_source(args.archive)
    stem='tracked-combined-platform' if args.combined else 'tracked-rotating-platform'
    output_stem=stem+('-stable-brakes' if args.stable_brakes else '')
    arguments=['--combined'] if args.combined else []
    report=dict(schema=1,fixture=stem+'-v1',oracle_revision=REFERENCE,archive_sha256=digest,velocity_iterations=12,position_iterations=4,body_tolerances=PARITY,linear_speed=2.0 if args.combined else 0.0,angular_speed=.25,free_track_schedule="free only from2s to4s, then brake" if args.combined else "free throughout case3",modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle,adapter=build_tracked_oracle(source,mode,HERE/'TrackedRotatingPlatformOracle.cpp',stem+'-oracle',stable=args.stable_brakes);silex=build_silex(mode,'TrackedRotatingPlatform.sx',stem+'-silex',True)
        parsed={};evidence={'oracle_adapter':adapter}
        for engine,binary in (('jolt',oracle),('silex',silex)):
            raw=checked([str(binary),*arguments]);(BUILD/f'{output_stem}-{engine}-{mode.lower()}.txt').write_text(raw);rows=parse(raw,args.combined)
            evidence[engine]=dict(states=len(rows),qualification=qualify(rows,engine,args.combined),guards=self_test(raw,rows,engine,args.combined),sha256=hashlib.sha256(raw.encode()).hexdigest());parsed[engine]=rows;print(mode,engine,'qualified',flush=True)
        evidence['parity']=compare(parsed['silex'],parsed['jolt']);
        if args.combined: evidence['static_law']={engine:static_law(rows) for engine,rows in parsed.items()}
        report['modes'][mode]=evidence;(BUILD/f'{output_stem}-qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(mode,'tracked platform parity green',flush=True)
    if args.mode=='both':
        for engine in ('jolt','silex'):
            if (BUILD/f'{output_stem}-{engine}-debug.txt').read_bytes()!=(BUILD/f'{output_stem}-{engine}-release.txt').read_bytes():fail(f'{engine} Debug/Release differ')
        report['debug_release_identical']=True;(BUILD/f'{output_stem}-qualification.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
