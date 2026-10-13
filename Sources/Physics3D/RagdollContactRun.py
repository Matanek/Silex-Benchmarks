#!/usr/bin/env python3
"""Qualify bounded ragdoll target efforts against a frictionless floor."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from SpatialHingesRun import add, sub, mul, norm, cross, dot
from LoadedSwingTwistRun import product, conjugate, axis_angle, distance, rotate

CONFIGS = [(mode, rate, side, frame) for mode in (0, 1) for rate in (60, 120)
           for side in (-1, 1) for frame in (0, 1)]
KEYS = {(tag, *config, step) for config in CONFIGS for tag in ('ragdollcontact', 'ragdollbefore', 'ragdollafter')
        for step in (range(config[1]*14+1) if tag == 'ragdollcontact' else (0, config[1]*4, config[1]*8, config[1]*12))}
BOUNDS = dict(anchor=.02, penetration=.02, angular_excess=.08, torque=30.001,
              speed=40, reconstruction=.0001, linear_residual=.0002, angular_residual=.0002, settled_speed=.15)
PARITY = dict(orientation=.04, position=.05, speed=.05, force=1, normal_force=1)


def parse(raw):
    rows = {}
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 41:
            fail('invalid ragdoll contact row length')
        try:
            key = (fields[0], *map(int, fields[1:6]))
            values = tuple(map(float, fields[6:]))
        except (ValueError, OverflowError):
            fail('invalid ragdoll contact number')
        if key not in KEYS or key in rows or not all(map(math.isfinite, values)):
            fail('unknown, duplicate or nonfinite ragdoll contact row')
        rows[key] = values
    if set(rows) != KEYS:
        fail('missing ragdoll contact observations')
    return rows


def decomposition(q):
    if q[3] < 0:
        q = tuple(-x for x in q)
    length = math.hypot(q[0], q[3])
    if length < 1e-6:
        fail('singular swing/twist decomposition in nonsingular fixture')
    twist = (q[0]/length, 0, 0, q[3]/length)
    swing = product(q, conjugate(twist))
    return swing, 2*math.atan2(twist[0], twist[3])


def normal_impulse(row, rate):
    # Normal impulse inferred independently from the linear momentum balance.
    inferred = sub(sub(mul(sub(row[7:10], row[32:35]), 2), mul(row[26:29], 1/rate)), (0, -19.62/rate, 0))
    return inferred


def qualify(rows, engine):
    worst = dict.fromkeys((*BOUNDS, 'normal_force'), 0)
    for config in CONFIGS:
        mode, rate, side, frame = config
        base = axis_angle((0, 1, 0), .7*frame)
        for step in range(rate*14+1):
            row = rows['ragdollcontact', *config, step]
            p,q,v,w,o,a,m,e,f = (row[:3],row[3:7],row[7:10],row[10:13],row[13:17],row[17:20],row[20:23],row[23:26],row[26:29])
            if max(abs(norm(q)-1),abs(norm(o)-1)) > .00001 or row[30] not in (0,1) or row[31] != int(engine=='silex'):
                fail('invalid rotation, contact identity or measurement provenance')
            if not mode and row[30] != 0:
                fail('contact reported without floor')
            reconstruction = max(distance(product(conjugate(base),q),o),
                norm(sub(sub(sub(p,rotate(q,(1,0,0))),(0,.5,0)),e)), norm(sub(rotate(conjugate(q),w),a)))
            swing, twist = decomposition(o)
            inclination = 2*math.asin(min(1, math.hypot(swing[1],swing[2])))
            values = dict(anchor=norm(e),penetration=max(0,.25-p[1]) if mode else 0,
                angular_excess=max(0,inclination-.6,-.2-twist,twist-.35), torque=max(map(abs,m)),
                speed=max(norm(v),norm(w)),reconstruction=reconstruction)
            if norm(p) >= 10:
                fail('unbounded ragdoll position')
            if step > rate*12 and norm(m) > .00001:
                fail('motor torque remains after passive release')
            if step:
                before = rows['ragdollcontact', *config, step-1][7:10]
                if norm(sub(before,row[32:35])) > .00001:
                    fail('before-step velocity differs from preceding state')
                impulse = normal_impulse(row, rate)
                residual = max(abs(impulse[0]),abs(impulse[2]),max(0,-impulse[1]))
                if engine == 'silex':
                    residual = max(residual,abs(impulse[1]-row[29]))
                elif row[29] != 0:
                    fail('Jolt declared an unavailable measured contact impulse')
                if not row[30]:
                    residual = max(residual,norm(impulse),abs(row[29]))
                if row[29] < -.00001:
                    fail('negative measured contact impulse')
                values['linear_residual'] = residual
                worst['normal_force'] = max(worst['normal_force'], impulse[1]*rate)
            for phase in range(3):
                if rate*(phase*4+3.5) <= step <= rate*(phase+1)*4:
                    values['settled_speed'] = max(norm(v),norm(w))
                    expected = int(mode==1 and phase!=1)
                    if row[30] != expected:
                        fail(f'established contact phase absent or incorrect: {engine}/{config}/{step}')
                    if mode and phase != 1:
                        # The floor tilt axis is perpendicular to the lever
                        # and vertical. Twist limit torques have no component
                        # on it; the swing cone is inactive in these windows.
                        if inclination >= .55:fail('floor tilt balance includes an active swing stop')
                        previous=rows['ragdollcontact',*config,step-1]
                        lever=sub((0,.5,0),previous[:3]);axis=cross(lever,(0,1,0));axis=mul(axis,1/norm(axis))
                        torque=add(cross(lever,f),rotate(previous[3:7],m))
                        angular_change=mul(sub(w,previous[10:13]),.2)
                        values['angular_residual']=abs(dot(sub(angular_change,mul(torque,1/rate)),axis))
                    if mode and phase != 1 and abs(p[1]-.25) > BOUNDS['penetration']:
                        fail('contacting sphere does not rest on physical floor')
                    if phase == 1 and p[1] < .4:
                        fail('upward target never lifted the member clear of floor')
            for name,value in values.items():
                worst[name]=max(worst[name],value)
                if value >= BOUNDS[name]:
                    fail(f'{engine} {name} bound exceeded: {value} at {config}/{step}')
        for step in (0,rate*4,rate*8,rate*12):
            before=rows['ragdollbefore',*config,step];after=rows['ragdollafter',*config,step]
            preceding=rows['ragdollcontact',*config,step]
            if max(norm(sub(before[:3],preceding[:3])),distance(before[3:7],preceding[3:7]),
                   norm(sub(before[7:13],preceding[7:13]))) > .00001:
                fail('before-command record is not the actual current state')
            if max(norm(sub(before[:3],after[:3])),distance(before[3:7],after[3:7]),norm(sub(before[7:10],after[7:10]))) > .00001:
                fail('target or release command moved body or changed linear velocity')
            change=sub(after[10:13],before[10:13])
            expected=rotate(before[3:7],(1,0,0)) if step==rate*12 else (0,0,0)
            if norm(sub(change,expected)) > .00001:
                fail('target command injected angular speed or angular impulse differs')
            if norm(after[20:23])>.00001 or norm(sub(after[23:26],before[23:26]))>.00001:
                fail('command did not clear motor reactions or changed anchor')
    return worst


def window_mean(rows,config,interval,start,end):
    return tuple(sum(rows['ragdollcontact',*config,step][i] for step in interval)/len(interval)
                 for i in range(start,end))


def compare(first,second):
    worst=dict.fromkeys(PARITY,0)
    instantaneous=dict.fromkeys(PARITY,0)
    for config in CONFIGS:
        mode,rate,side,frame=config
        for phase in range(3):
            interval=range(int(rate*(phase*4+3.5)),rate*(phase+1)*4+1)
            for step in interval:
                a,b=first['ragdollcontact',*config,step],second['ragdollcontact',*config,step]
                errors=dict(orientation=distance(a[13:17],b[13:17]),position=norm(sub(a[:3],b[:3])),
                    speed=norm(sub(a[17:20],b[17:20])),force=norm(sub(a[26:29],b[26:29])),
                    normal_force=abs(normal_impulse(a,rate)[1]-normal_impulse(b,rate)[1])*rate)
                for name,value in errors.items():
                    instantaneous[name]=max(instantaneous[name],value)
                    if name in ('orientation','position'):
                        worst[name]=max(worst[name],value)
                        if value>=PARITY[name]:fail(f'established ragdoll {name} parity differs: {value}')
            errors=dict(speed=norm(sub(window_mean(first,config,interval,17,20),window_mean(second,config,interval,17,20))),
                force=norm(sub(window_mean(first,config,interval,26,29),window_mean(second,config,interval,26,29))),
                normal_force=abs(sum(normal_impulse(first['ragdollcontact',*config,step],rate)[1]
                    -normal_impulse(second['ragdollcontact',*config,step],rate)[1] for step in interval))*rate/len(interval))
            for name,value in errors.items():
                worst[name]=max(worst[name],value)
                if value>=PARITY[name]:fail(f'established window mean {name} parity differs: {value}')
    # Keep the failed pointwise experiment visible; passing window averages
    # never establishes equality of instantaneous velocity/force or impacts.
    return dict(qualified_geometry_and_window_means=worst,instantaneous_diagnostic=instantaneous,
                instantaneous_velocity_and_force_qualified=False)


def rejected(action):
    try:
        action()
    except ValueError:
        return
    fail('ragdoll contact guard accepted corrupted evidence')


def self_test(raw,rows,engine):
    lines=raw.splitlines();count=0
    for altered in (raw+'\n'+lines[0],'\n'.join(lines[1:]),raw.replace('ragdollcontact 0 60','ragdollcontact 2 60',1)):
        rejected(lambda altered=altered:parse(altered));count+=1
    altered=lines.copy();parts=altered[0].split();parts[6]='nan';altered[0]=' '.join(parts)
    rejected(lambda:parse('\n'.join(altered)));count+=1
    for component in range(35):
        key=('ragdollcontact',1,60,-1,0,239);altered=rows.copy();values=list(altered[key])
        values[component]+=300 if 20<=component<23 else 2
        altered[key]=tuple(values);rejected(lambda:qualify(altered,engine));count+=1
    for tag,component in (('ragdollafter',0),('ragdollafter',7),('ragdollafter',10),('ragdollbefore',0)):
        key=(tag,1,60,-1,0,240);altered=rows.copy();values=list(altered[key]);values[component]+=1
        altered[key]=tuple(values);rejected(lambda:qualify(altered,engine));count+=1
    # Comparator guards alter a full fixed window so its mean, rather than
    # only a single spike, differs. Invariants separately reject bad samples.
    config=(1,60,-1,0);interval=range(210,241)
    for name in PARITY:
        altered=rows.copy()
        for step in interval:
            key=('ragdollcontact',*config,step);values=list(altered[key])
            if name=='orientation':values[13:17]=product(axis_angle((1,0,0),.1),values[13:17])
            if name=='position':values[0]+=.1
            if name=='speed':values[17]+=1
            if name=='force':values[26]+=2
            if name=='normal_force':values[33]+=.1
            altered[key]=tuple(values)
        rejected(lambda:compare(rows,altered));count+=1
    return count


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true');parser.add_argument('--archive',type=Path);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both')
    args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='ragdoll-clamped-contact-targets-v2',oracle_revision=REFERENCE,archive_sha256=digest,
        bounds=BOUNDS,parity_bounds=PARITY,configuration=dict(radius=.25,mass=2,inertia=[.2,.2,.2],anchor=[0,.5,0],offset=[1,0,0],gravity=[0,-9.81,0],cone_half_angle=.6,twist_limits=[-.2,.35],motor=dict(torque=30,stiffness=80,damping=15),command_seconds=[0,4,8,12],duration=14,friction=0,restitution=0,allow_sleep=False,jolt=dict(velocity_steps=12,position_steps=16,penetration_slop=1e-6,warm_start=True,substeps=1,workers=1),silex=dict(position_steps=16,workers=1)),comparison_protocol=dict(windows='last half-second before each 4/8/12 s command, inclusive',geometry='every observation',speed='mean relative angular velocity vector',force='summed linear impulse divided by window duration',normal_force='summed normal impulse divided by window duration'),scope='Fixed root, one offset sphere, frictionless floor versus no floor; combined clamped targets and passive angular impulse. Established geometry and window-mean parity. Instantaneous velocity/force comparison fails and remains diagnostic; arbitrary impacts and trajectories are not qualified.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=BUILD/f'ragdoll-contact-oracle-{mode.lower()}' if args.check_only else build_oracle(source,mode,HERE/'RagdollContactOracle.cpp','ragdoll-contact-oracle')
        binary=BUILD/f'ragdoll-contact-silex-{mode.lower()}' if args.check_only else build_silex(mode,'RagdollContact.sx','ragdoll-contact-silex',True)
        parsed={};evidence={}
        for name,executable in (('silex',binary),('jolt',oracle)):
            output=BUILD/f'ragdoll-contact-{name}-{mode.lower()}.txt'
            raw=output.read_text() if args.check_only else checked([str(executable)])
            if not args.check_only:output.write_text(raw)
            rows=parse(raw);parsed[name]=rows
            evidence[name]=dict(observations=len(rows),worst=qualify(rows,name),corrupt_witnesses_rejected=self_test(raw,rows,name),
                output_sha256=hashlib.sha256(raw.encode()).hexdigest())
        record['modes'][mode]=dict(witnesses=evidence,established_parity=compare(parsed['silex'],parsed['jolt']))
        (BUILD/'ragdoll-contact-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: bounded ragdoll targets, floor reaction, release and established states green',flush=True)


if __name__=='__main__':main()
