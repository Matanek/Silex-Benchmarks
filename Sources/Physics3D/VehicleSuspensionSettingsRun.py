#!/usr/bin/env python3
"""Qualify suspension preload, alternative spring units and local force points."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from VehicleTiresRun import add, cross, norm, scale
from LoadedSwingTwistRun import rotate
from VehicleInclineRun import rotation_error, sub
from TrackedVehicleRun import rejected

CASES=range(9)
RATES=(60,120)
KEYS={(case,rate,step) for case in CASES for rate in RATES for step in range(6*rate+1)}
PARITY=(.05,.1,.02,.15)


def parse(raw):
    rows={}
    for line in raw.splitlines():
        fields=line.split()
        if len(fields)!=29 or fields[0]!='suspension-settings':fail('invalid suspension settings row')
        key=tuple(map(int,fields[1:4]));values=tuple(map(float,fields[4:]))
        if key not in KEYS or key in rows or not all(map(math.isfinite,values)):fail('invalid suspension settings key/value')
        rows[key]=values
    if set(rows)!=KEYS:fail('incomplete suspension settings witness')
    return rows


def load(row):return sum(row[14+3*i] for i in range(4))


def equilibrium(case):
    mass=200. if case==3 else 100.
    preload=.01 if case in (1,7) else 0.
    stiffness=10000.
    if case in (2,3,7):stiffness=mass/2.36*(2*math.pi*3)**2
    elif case==4:stiffness=mass/2.36*400
    if case==5:return .9*math.cos(.12)+.6*math.sin(.12)-981*math.cos(.12)**2/20000
    if case==8:return .5
    return .9+preload-mass*9.81/(4*stiffness)


def qualify(rows):
    worst={'linear':0.,'angular':0.,'position_integral':0.,'height':0.};outcomes={}
    for case in CASES:
        mass=200. if case==3 else 100.;extra=20000. if case==8 else 0.
        expected_rotation=(0.,0.,math.sin(.06),math.cos(.06)) if case in (5,6) else (0.,0.,0.,1.)
        for rate in RATES:
            initial=rows[case,rate,0];expected_height=.7 if case==8 else 1.4
            if norm(sub(initial[:3],(0.,expected_height,0.)))>1e-5 or norm(initial[3:6])+norm(initial[10:13])>1e-5 or rotation_error(initial[6:10],expected_rotation)>1e-5:fail('initial settings pose differs')
            lost=False;recovered=False
            for step in range(6*rate+1):
                row=rows[case,rate,step]
                if not .3<row[1]<4 or norm(row[:3])>10 or norm(row[3:6])>15 or norm(row[10:13])>5:fail('unbounded suspension settings body')
                if abs(sum(v*v for v in row[6:10])-1)>1e-4:fail('nonunit suspension rotation')
                contacts=0
                for i in range(4):
                    length,force,touch=row[13+3*i:16+3*i]
                    if not 0<=length<=.60001 or not 0<=force<1e6 or touch not in (0.,1.):fail('invalid suspension geometry or load')
                    if not touch and (force!=0 or abs(length-.6)>1e-5):fail('unsupported suspension response')
                    contacts+=int(touch)
                if not step:
                    if load(row)!=0:fail('initial suspension load')
                    continue
                old=rows[case,rate,step-1];impulse=(0.,500.,0.) if case==0 and step==2*rate+1 else (0.,0.,0.)
                expected=add(scale((0.,load(row)-mass*9.81-extra,0.),1/rate),impulse)
                linear=norm(sub(scale(sub(row[3:6],old[3:6]),mass),expected));worst['linear']=max(worst['linear'],linear)
                if linear>.1:fail(f'settings linear impulse balance {case}/{rate}/{step}: {linear}')
                torque=(0.,0.,0.)
                for i,(x,z) in enumerate(((-.6,-1.),(-.6,1.),(.6,-1.),(.6,1.))):
                    arm=(0.,0.,0.) if case in (5,8) else rotate(old[6:10],(x,-row[13+3*i]-.3,z))
                    torque=add(torque,cross(arm,(0.,row[14+3*i],0.)))
                angular=norm(sub(scale(sub(row[10:13],old[10:13]),mass),scale(torque,1/rate)));worst['angular']=max(worst['angular'],angular)
                if angular>.1:fail(f'settings angular impulse balance {case}/{rate}/{step}: {angular}')
                if case!=8:
                    integral=norm(sub(sub(row[:3],old[:3]),scale(row[3:6],1/rate)));worst['position_integral']=max(worst['position_integral'],integral)
                    if integral>1e-4:fail('suspension position integration differs')
                if case==0 and step>2*rate:
                    if contacts==0:lost=True
                    if lost and contacts==4:recovered=True
                if case in (5,8) and norm(row[10:13])>1e-4:fail('central force point generated angular momentum')
                if case==5 and rotation_error(row[6:10],expected_rotation)>1e-4:fail('central force point changed initial roll')
                if step>5*rate:
                    error=abs(row[1]-equilibrium(case));worst['height']=max(worst['height'],error)
                    if error>.003 or norm(row[3:6])>.05 or norm(row[10:13])>.05:fail(f'analytic settings rest differs {case}/{rate}: {error}')
                    if abs(load(row)-mass*9.81-extra)>2:fail('analytic settings supported load differs')
                    if contacts!=(2 if case==5 else 4):fail('rest contacts differ')
                    if case!=5 and rotation_error(row[6:10],(0,0,0,1))>.01:fail('ordinary suspension did not level the chassis')
            if case==0 and not(lost and recovered):fail('default jump/recovery missing')
            final=rows[case,rate,6*rate];outcomes[f'{case}/{rate}']={'height':final[1],'load':load(final),'rotation':final[6:10]}
    for rate in RATES:
        if abs(rows[1,rate,6*rate][1]-rows[0,rate,6*rate][1]-.01)>.003:fail('preload response missing')
        if abs(rows[2,rate,6*rate][1]-rows[3,rate,6*rate][1])>.003:fail('frequency response changes with scaled chassis mass')
    return {'worst':worst,'outcomes':outcomes}


def compare(a,b):
    worst=[0.]*4;wheel_error=0.;force_error=0.
    for key in sorted(KEYS):
        x,y=a[key],b[key];errors=(norm(sub(x[:3],y[:3])),norm(sub(x[3:6],y[3:6])),rotation_error(x[6:10],y[6:10]),norm(sub(x[10:13],y[10:13])))
        for i,(error,budget) in enumerate(zip(errors,PARITY)):
            worst[i]=max(worst[i],error)
            if error>budget:fail(f'settings body parity {key}/{i}: {error} > {budget}')
        for i in range(4):
            error=abs(x[13+3*i]-y[13+3*i]);wheel_error=max(wheel_error,error)
            if error>.003:fail(f'settings wheel parity {key}/{i}: {error}')
    for case in CASES:
        for rate in RATES:
            for second in range(6):
                delta=abs(sum(load(a[case,rate,t])-load(b[case,rate,t]) for t in range(second*rate+1,(second+1)*rate+1))/rate);force_error=max(force_error,delta)
                if delta>20:fail('settings mean force parity')
    return {'body':worst,'wheel_length':wheel_error,'window_force':force_error}


def self_test(raw,rows):
    lines=raw.splitlines();rejected(lambda:parse('\n'.join(lines[1:])));rejected(lambda:parse(raw+lines[0]+'\n'))
    for index,value in ((0,'other'),(1,'9'),(2,'61'),(4,'nan'),(4,'inf')):
        fields=lines[0].split();fields[index]=value;rejected(lambda:parse(' '.join(fields)+'\n'+'\n'.join(lines[1:])))
    for case in CASES:
        key=(case,120,360)
        for channel in range(25):
            altered=dict(rows);row=list(altered[key]);row[channel]+=1000.;altered[key]=tuple(row);rejected(lambda:qualify(altered))
    return 232


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail('run from the workspace or Spec group root')
    source,digest=verified_source(args.archive);report={'schema':1,'fixture':'vehicle-suspension-settings-v1','oracle_revision':REFERENCE,'archive_sha256':digest,'solver':[12,4],'parity':PARITY,'modes':{}}
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'VehicleSuspensionSettingsOracle.cpp','vehicle-suspension-settings-oracle');binary=build_silex(mode,'VehicleSuspensionSettings.sx','vehicle-suspension-settings-silex',True);parsed={};result={}
        for engine,exe in [('silex',binary),('jolt',oracle)]:
            raw=checked([str(exe)]);(BUILD/f'vehicle-suspension-settings-{engine}-{mode.lower()}.txt').write_text(raw);rows=parse(raw);result[engine]={'states':len(rows),'qualification':qualify(rows),'guards':self_test(raw,rows),'sha256':hashlib.sha256(raw.encode()).hexdigest()};parsed[engine]=rows;print(mode,engine,'settings qualified',flush=True)
        result['parity']=compare(parsed['silex'],parsed['jolt']);report['modes'][mode]=result;(BUILD/'vehicle-suspension-settings-qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(mode,'suspension settings parity green',flush=True)
    if args.mode=='both':
        for engine in ('silex','jolt'):
            if (BUILD/f'vehicle-suspension-settings-{engine}-debug.txt').read_bytes()!=(BUILD/f'vehicle-suspension-settings-{engine}-release.txt').read_bytes():fail('settings Debug/Release differ')
        report['debug_release_identical']=True;(BUILD/'vehicle-suspension-settings-qualification.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
