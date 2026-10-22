#!/usr/bin/env python3
"""Qualify powered motorcycle ramp traversal, free flight and landing."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from MotorcycleReferenceRun import dot, norm, sub, rotate, near
from MotorcycleHandlingRun import wheel, tilt, rotors
from VehicleInclineRun import rotation_error

KEYS={(k,r,t) for k in (0,1) for r in (60,120) for t in range(16*r+1)}
PARITY=(.05,.1,.02,.15)
NORMAL=(0.,math.cos(.1),-math.sin(.1))


def parse(raw):
    rows={}
    for line in raw.splitlines():
        fields=line.split()
        if len(fields)!=63 or fields[0]!='motorcycle-ramp': fail('invalid ramp record')
        key=tuple(map(int,fields[1:4]))
        v=tuple(struct.unpack('f',struct.pack('f',float(x)))[0] for x in fields[4:])
        if key not in KEYS or key in rows or not all(map(math.isfinite,v)): fail('invalid ramp key/value')
        rows[key]=v
    if set(rows)!=KEYS: fail('incomplete ramp witness')
    return rows


def throttle(old,r,t):
    if not 2*r<=t-1<6*r: return 0.
    forward=rotate(old[6:10],(0,0,1))
    pitch=math.asin(max(-1.,min(1.,forward[1])))
    pitch_rate=-dot(old[10:13],rotate(old[6:10],(1,0,0)))
    return .4*max(0.,min(1.,(.25-pitch-.15*pitch_rate)/.15))


def qualify(rows):
    worst=dict(rotor=0.,ballistic_momentum=0.,position_step=0.,contact_point=0.)
    outcomes={}
    for k in (0,1):
        for r in (60,120):
            airborne=[];ramp_contacts=0;landing=None;peak=0.
            for t in range(16*r+1):
                v=rows[k,r,t];peak=max(peak,v[1])
                if norm(v[:3])>150 or not .5<v[1]<3 or norm(v[3:6])>30 or norm(v[10:13])>5: fail('unbounded ramp body')
                near(dot(v[6:10],v[6:10]),1.,1e-4,'unit ramp rotation')
                if tilt(v)>.4 or v[56] or v[53]!=1 or v[54]!=1 or v[55]!=0 or v[57]!=1: fail('ramp rider state differs')
                if not 0<=v[16]<=6000 or v[17]!=1: fail('invalid ramp powertrain')
                near(norm(v[13:16]),0. if t==0 else 1.,1e-4,'unit ramp target')
                contacts=0
                for i in (0,1):
                    w=wheel(v,i)
                    if w[3] not in (0.,1.) or not 0<=w[1]<=.60001 or not 0<=w[2]<100000 or abs(w[4])>100: fail('invalid ramp wheel')
                    if max(abs(w[6]),abs(w[7]))>w[2]+.003: fail('ramp friction capacity exceeded')
                    if w[0]!=0: fail('straight ramp wheel steered')
                    if not w[3]:
                        if any(w[j]!=0 for j in (2,6,7,8,9,10,11,12,13,14,15,16)): fail('unsupported wheel has contact force/geometry')
                        continue
                    contacts+=1
                    near(norm(w[11:14]),1.,1e-5,'unit ramp contact normal')
                    near(norm(w[14:17]),1.,1e-5,'unit ramp longitudinal')
                    near(dot(w[11:14],w[14:17]),0.,1e-5,'tire tangent to surface')
                    point=w[8:11]
                    if norm(sub(w[11:14],(0,1,0)))<1e-5:
                        near(point[1],0.,2e-5,'plane contact geometry')
                    else:
                        if not k: fail('flat recipe hit ramp')
                        near(norm(sub(w[11:14],NORMAL)),0.,1e-5,'ramp top normal')
                        near(dot(sub(point,(0,.1,15)),NORMAL),.2,2e-5,'ramp top plane')
                        local=rotate((math.sin(.05),0,0,math.cos(.05)),sub(point,(0,.1,15)))
                        if abs(local[0])>4.00001 or abs(local[2])>3.01501: fail('ramp contact outside finite box')
                        ramp_contacts+=1
                    if t:
                        old=rows[k,r,t-1]
                        offset=(0.,-w[1]-.3,1.25 if i==0 else -.75)
                        predicted=tuple(a+b for a,b in zip(old[:3],rotate(old[6:10],offset)))
                        worst['contact_point']=max(worst['contact_point'],near(norm(sub(point,predicted)),0.,3e-5,'suspension ray geometry at beginning of step'))
                if t>2*r and not contacts: airborne.append(t)
                if airborne and contacts and landing is None: landing=t
                if not t:
                    near(norm(sub(v[:3],(0,1.05,0))),0.,1e-5,'initial ramp position')
                    continue
                old=rows[k,r,t-1];gas=throttle(old,r,t);brake=.35 if t-1<2*r or t-1>=6*r else 0.
                near(v[58],gas,3e-6,'ramp throttle governor')
                if v[18]!=float(gas>0): fail('ramp clutch transition differs')
                worst['rotor']=max(worst['rotor'],rotors(old,v,gas,brake,r))
                expected_position=tuple(old[i]+v[3+i]/r for i in range(3))
                if not contacts:
                    worst['position_step']=max(worst['position_step'],near(norm(sub(v[:3],expected_position)),0.,3e-5,'unsupported position integration'))
                    expected_velocity=tuple((old[3+i]+(0.,-9.81,0.)[i]/r)/(1+.05/r) for i in range(3))
                    worst['ballistic_momentum']=max(worst['ballistic_momentum'],near(100*norm(sub(v[3:6],expected_velocity)),0.,.005,'unsupported gravity/damping momentum'))
            end=rows[k,r,16*r]
            if norm(end[3:6])>.05 or norm(end[10:13])>.05 or tilt(end)>.05 or end[2]<60: fail('ramp did not traverse and return to rest')
            if not wheel(end,0)[3] or not wheel(end,1)[3]: fail('ramp final supports missing')
            near(wheel(end,0)[2]+wheel(end,1)[2],981.,2.,'ramp final supported weight')
            if k:
                if ramp_contacts<r/2 or len(airborne)<r/3 or landing is None or peak<1.4: fail('ramp ascent/flight/landing missing')
                if airborne!=list(range(airborne[0],airborne[-1]+1)) or landing!=airborne[-1]+1: fail('ramp flight not contiguous')
                if not 4<airborne[0]/r<5 or not 4.5<landing/r<5.5: fail('ramp transition phase missing')
            elif ramp_contacts or airborne or peak>1.051: fail('flat control unexpectedly jumped')
            outcomes[f'{k}/{r}']=dict(ramp_contact_samples=ramp_contacts,air_steps=len(airborne),takeoff=airborne[0]/r if airborne else None,landing=landing/r if landing else None,peak_height=peak,final_position=end[:3],final_speed=norm(end[3:6]))
    return dict(worst=worst,outcomes=outcomes)


def compare(rows,reference):
    worst=[0.]*4
    for key,a in rows.items():
        b=reference[key]
        errors=(norm(sub(a[:3],b[:3])),norm(sub(a[3:6],b[3:6])),rotation_error(a[6:10],b[6:10]),norm(sub(a[10:13],b[10:13])))
        if any(x>limit for x,limit in zip(errors,PARITY)): fail(f'ramp body parity {key}: {errors}')
        worst=[max(x,y) for x,y in zip(worst,errors)]
    qa,qb=qualify(rows),qualify(reference)
    for k in (0,1):
        for r in (60,120):
            a,b=qa['outcomes'][f'{k}/{r}'],qb['outcomes'][f'{k}/{r}']
            near(a['peak_height'],b['peak_height'],.1,'ramp peak height parity')
            if k:
                for name in ('takeoff','landing'): near(a[name],b[name],.1,'ramp event time parity')
    return dict(states=len(rows),worst=worst,scope='all states including takeoff and landing; no pointwise exclusions')


def self_test(raw,rows,reference):
    lines=raw.splitlines();bad=lines[0].split();bad[4]='nan'
    for changed in (raw+'\n'+lines[0],'\n'.join(lines[1:]),raw.replace('motorcycle-ramp 0 60 0','motorcycle-ramp 99 60 0',1),' '.join(bad)+'\n'+'\n'.join(lines[1:])):
        try: parse(changed)
        except (ValueError,OverflowError): pass
        else: fail('corrupt ramp record accepted')
    fields=(0,3,6,10,13,16,17,18,19,20,21,22,23,24,25,27,30,33,53,54,55,56,57,58)
    for component in fields:
        key=(1,60,960) if component==21 else (1,60,260)
        changed=dict(rows);v=list(rows[key]);v[component]+=20000 if component==21 else 2;changed[key]=tuple(v)
        try: qualify(changed);compare(changed,reference)
        except (ValueError,OverflowError): pass
        else: fail(f'corrupt ramp observable accepted: {component}')
    return 4+len(fields)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=('Debug','Release','both'),default='both');p.add_argument('--archive',type=Path);args=p.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='motorcycle-ramp-v1',oracle_revision=REFERENCE,archive_sha256=digest,body_parity=PARITY,scope='100kg/I100,80Nm rider profile; plane and finite box ramp8x.4x6.03 at(0,.1,15), rotationX=-.1rad, ray supports. No arbitrary terrain/detector or performance claim.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        j=build_oracle(source,mode,HERE/'MotorcycleRampOracle.cpp','motorcycle-ramp-oracle');b=build_silex(mode,'MotorcycleRamp.sx','motorcycle-ramp-silex',True)
        raw_j=checked([str(j)]);raw=checked([str(b)])
        for engine,text in [('jolt',raw_j),('silex',raw)]: (BUILD/f'motorcycle-ramp-{engine}-{mode.lower()}.txt').write_text(text)
        reference=parse(raw_j);rows=parse(raw)
        record['modes'][mode]=dict(states=len(rows),jolt=qualify(reference),silex=qualify(rows),parity=compare(rows,reference),guards=self_test(raw,rows,reference),sha256=hashlib.sha256(raw.encode()).hexdigest(),jolt_sha256=hashlib.sha256(raw_j.encode()).hexdigest())
        (BUILD/'motorcycle-ramp-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(mode,'ramp, ballistic flight and landing qualified',flush=True)
    if args.mode=='both':
        for engine in ('jolt','silex'):
            if (BUILD/f'motorcycle-ramp-{engine}-debug.txt').read_bytes()!=(BUILD/f'motorcycle-ramp-{engine}-release.txt').read_bytes(): fail(f'{engine} ramp Native Debug/Release differ')
        record['debug_release_identical']=True;(BUILD/'motorcycle-ramp-qualification.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__': main()
