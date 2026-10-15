#!/usr/bin/env python3
"""Qualify four wheel suspensions against analytic balances and pinned Jolt."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from LoadedSwingTwistRun import rotate
from RagdollHierarchyRun import rotation_error

KEYS={(kind,rate,step) for kind in (0,1) for rate in (60,120)
      for step in range(rate*(6 if kind==0 else 3)+1)}
POSITION=.01
VELOCITY=.05
BALANCE=.05
HEIGHT=.875475

def parse(raw):
    rows={}
    for line in raw.splitlines():
        fields=line.split()
        if len(fields)!=29 or fields[0]!='suspension': fail('invalid vehicle suspension row')
        key=tuple(map(int,fields[1:4]));values=tuple(map(float,fields[4:]))
        if key not in KEYS or key in rows or not all(map(math.isfinite,values)): fail('invalid suspension key or value')
        rows[key]=values
    if set(rows)!=KEYS: fail('incomplete suspension witness')
    return rows

def forces(row): return [row[14+3*i] for i in range(4)]
def mean(values): return sum(values)/len(values)
def window(rows,kind,rate,start,end):
    return [rows[kind,rate,step] for step in range(math.ceil(start*rate),math.floor(end*rate)+1)]

def qualify(rows):
    worst_linear=0.0;worst_angular=0.0
    for (kind,rate,step),value in sorted(rows.items()):
        if abs(sum(x*x for x in value[6:10])-1)>.0001: fail('non-unit vehicle quaternion')
        if value[1]<.48 or max(abs(x) for x in value[:3])>10 or max(abs(x) for x in value[3:6])>15: fail('unbounded vehicle pose or velocity')
        if max(abs(value[i]) for i in (0,2,3,5))>.0001: fail('symmetric suspension gained horizontal motion')
        for i in range(4):
            length,force,contact=value[13+3*i:16+3*i]
            if not 0<=length<=.60001 or not 0<=force<100000 or contact not in (0,1): fail('invalid wheel length, force or contact flag')
            if contact==0 and (force!=0 or abs(length-.6)>.00001): fail('unsupported suspension applied force or retained compression')
        if step==0:
            initial=1.4 if kind==0 else .7
            if abs(value[1]-initial)>.00001 or max(abs(x) for x in value[3:6]+value[10:13])>.00001 or sum(forces(value))!=0: fail('incorrect initial vehicle state')
            continue
        previous=rows[kind,rate,step-1];dt=1/rate
        extra=20000 if kind==1 else 0
        impulse=500 if kind==0 and step==2*rate+1 else 0
        linear=abs(100*(value[4]-previous[4])-(sum(forces(value))-981-extra)*dt-impulse)
        worst_linear=max(worst_linear,linear)
        if linear>BALANCE: fail(f'vertical suspension balance {(kind,rate,step)}: {linear}')
        torque=[0.0,0.0,0.0]
        for i,(x,z) in enumerate(((-.6,-1),(-.6,1),(.6,-1),(.6,1))):
            radius=rotate(previous[6:10],(x,-value[13+3*i]-.3,z));force=value[14+3*i]
            torque[0]-=radius[2]*force;torque[2]+=radius[0]*force
        angular=max(abs(100*(value[10+i]-previous[10+i])-torque[i]*dt) for i in range(3))
        worst_angular=max(worst_angular,angular)
        if angular>BALANCE: fail(f'angular suspension balance {(kind,rate,step)}: {angular}')
    for rate in (60,120):
        for start,end in ((1.5,1.9),(5.5,6)):
            rest=window(rows,0,rate,start,end)
            if max(abs(r[1]-HEIGHT) for r in rest)>.002 or max(abs(r[4]) for r in rest)>.02: fail('suspension did not reach analytic height and rest speed')
            if abs(mean([sum(forces(r)) for r in rest])-981)>1: fail('suspension mean weight support differs')
            if any(r[15+3*i]!=1 or abs(r[13+3*i]-(HEIGHT-.3))>.002 for r in rest for i in range(4)): fail('rest wheel geometry or contact differs')
        contacts=[sum(r[15+3*i] for i in range(4)) for r in window(rows,0,rate,2.1,4.5)]
        if 0 not in contacts or not any(x==4 for x in contacts[contacts.index(0)+1:]): fail('jump did not lose and regain wheel support')
        loaded=window(rows,1,rate,2,3)
        if abs(mean([sum(forces(r)) for r in loaded])-20981)>20: fail('mean hard stop support differs from applied load')
        if max(r[1] for r in loaded)>.51 or any(r[15+3*i]!=1 for r in loaded for i in range(4)): fail('hard stop geometry or contact differs')
    return dict(linear_balance=worst_linear,angular_balance=worst_angular)

def compare(a,b):
    worst=[0.0]*4
    for key in KEYS:
        if key[0]!=0: continue
        first,second=a[key],b[key]
        error=[max(abs(x-y) for x,y in zip(first[:3],second[:3])),max(abs(x-y) for x,y in zip(first[3:6],second[3:6])),rotation_error(first[6:10],second[6:10]),max(abs(x-y) for x,y in zip(first[10:13],second[10:13]))]
        if any(e>t for e,t in zip(error,(POSITION,VELOCITY,.005,.05))): fail(f'vehicle suspension oracle mismatch {key}: {error}')
        if max(abs(first[13+3*i]-second[13+3*i]) for i in range(4))>.01: fail(f'wheel length oracle mismatch {key}')
        worst=[max(x,y) for x,y in zip(worst,error)]
    for kind in (0,1):
        for rate in (60,120):
            for start,end in (((1.5,1.9),(5.5,6)) if kind==0 else ((2,3),)):
                first=window(a,kind,rate,start,end);second=window(b,kind,rate,start,end)
                if abs(mean([sum(forces(r)) for r in first])-mean([sum(forces(r)) for r in second]))>(1 if kind==0 else 20): fail('mean suspension force differs from Jolt')
                if abs(mean([r[1] for r in first])-mean([r[1] for r in second]))>(.002 if kind==0 else .01): fail('mean suspension height differs from Jolt')
    return worst

def rejected(action):
    try: action()
    except (ValueError,OverflowError): return
    fail('corrupt suspension witness accepted')

def self_test(raw,rows):
    lines=raw.splitlines()
    rejected(lambda:parse(raw+'\n'+lines[0]));rejected(lambda:parse('\n'.join(lines[1:])))
    rejected(lambda:parse(raw.replace('suspension 0 60 0','suspension 8 60 0')))
    fields=lines[0].split();fields[4]='nan';rejected(lambda:parse(' '.join(fields)+'\n'+'\n'.join(lines[1:])))
    key=(0,60,100)
    for component in range(25):
        changed=dict(rows);value=list(changed[key]);value[component]+=1000 if component in (14,17,20,23) else 1
        changed[key]=tuple(value);rejected(lambda:qualify(changed))
    changed=dict(rows);value=list(changed[key]);value[1]+=.1;changed[key]=tuple(value);rejected(lambda:compare(changed,rows))
    return 30

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path)
    parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='four-wheel-suspension-v1',oracle_revision=REFERENCE,archive_sha256=digest,
                settings=dict(mass=100,stiffness_per_wheel=10000,damping_per_wheel=1000,lengths=[.2,.6],radius=.3,silex_iterations=[12,4],jolt_iterations=[12,4],jolt_workers=1),
                tolerances=dict(position=POSITION,velocity=VELOCITY,linear_angular_impulse_balance=BALANCE,rest_height=.002,rest_mean_force=1,hard_stop_mean_force=20),
                scope='Ray support only. Soft suspension trajectory; loaded hard stop uses geometry and phase mean reactions. No tire friction or propulsion.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'VehicleSuspensionOracle.cpp','vehicle-suspension-oracle')
        binary=build_silex(mode,'VehicleSuspension.sx','vehicle-suspension-silex',True);rows={};evidence={}
        for name,exe in (('silex',binary),('jolt',oracle)):
            raw=checked([str(exe)]);(BUILD/f'vehicle-suspension-{name}-{mode.lower()}.txt').write_text(raw)
            rows[name]=parse(raw);evidence[name]=dict(observations=len(rows[name]),worst=qualify(rows[name]),guards=self_test(raw,rows[name]),sha256=hashlib.sha256(raw.encode()).hexdigest())
        evidence['parity']=compare(rows['silex'],rows['jolt']);record['modes'][mode]=evidence
        (BUILD/'vehicle-suspension-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: suspension, hard stop, jump and independent balances green',flush=True)

if __name__=='__main__': main()
