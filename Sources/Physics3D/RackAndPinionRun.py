#!/usr/bin/env python3
"""Qualify rack/pinion projections, travel and reactions without rendering."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
FIELDS=('angle','travel','pinion_speed','rack_speed','pinion_torque','rack_force')
BOUNDS=dict(zip(FIELDS,(0.002,0.002,0.0003,0.0003,0.002,0.002)))
CASES={(case,step) for case in range(7) for step in (1,*range(15,361,15))}
def parse(output):
    rows={}
    for line in output.splitlines():
        v=line.split()
        if len(v)!=9 or v[0]!='rack': fail('invalid rack row')
        try: key=tuple(map(int,v[1:3]));data=list(map(float,v[3:]))
        except ValueError: fail('invalid numeric rack row')
        if key not in CASES or key in rows or not all(map(math.isfinite,data)): fail('invalid rack observation')
        rows[key]=dict(zip(FIELDS,data))
    if set(rows)!=CASES: fail('missing rack observations')
    return rows

def wrapped(angle):
    return angle-2*math.pi*math.floor((angle+math.pi)/(2*math.pi))

def mechanics(rows):
    ratios=(1,2,-2,.5,2,2,2);dt=1/60
    for (case,step),row in rows.items():
        ratio=ratios[case];mass=8 if case==4 else 2
        inverse_mass=5+ratio*ratio/mass;initial_lambda=ratio/inverse_mass
        w=5*initial_lambda;v=1-ratio*initial_lambda/mass
        torque=initial_lambda/dt if step==1 else 0;force=-ratio*torque
        angle=w*step*dt;travel=v*step*dt
        if case==6:
            angular_acceleration=5*ratio*.1/(mass*inverse_mass)
            linear_acceleration=5*.1/(mass*inverse_mass)
            angle+=angular_acceleration*dt*dt*step*(step+1)/2
            travel+=linear_acceleration*dt*dt*step*(step+1)/2
            w+=angular_acceleration*step*dt;v+=linear_acceleration*step*dt
            torque+=ratio*.1/(mass*inverse_mass);force-=ratio*ratio*.1/(mass*inverse_mass)
        expected=(wrapped(angle),travel,w,v,torque,force)
        for name,value in zip(FIELDS,expected):
            error=row[name]-value
            if name=='angle': error=wrapped(error)
            if abs(error)>BOUNDS[name]: fail(f'rack lost independent projection/load {(case,step)} {name} {row[name]} vs {value}')
def compare(actual,reference):
    errors=dict.fromkeys(FIELDS,0.0)
    for key in CASES:
        for name in FIELDS:
            e=actual[key][name]-reference[key][name]
            e=abs(wrapped(e) if name=='angle' else e);errors[name]=max(errors[name],e)
            if e>BOUNDS[name]: fail(f'rack {key} {name}: {e} > {BOUNDS[name]}')
    return errors

def self_test():
    rows={key:dict.fromkeys(FIELDS,0.) for key in CASES}
    output='\n'.join('rack '+' '.join(map(str,(*key,*(r[n] for n in FIELDS)))) for key,r in sorted(rows.items()))
    compare(parse(output),rows)
    for bad in (output+'\n'+output.splitlines()[0],'\n'.join(output.splitlines()[1:]),output.replace('rack 0 1 0.0','rack 0 1 nan',1)):
        try: parse(bad)
        except ValueError: continue
        fail('rack parser accepted corrupt evidence')
    try: mechanics(rows)
    except ValueError: pass
    else: fail('rack mechanics accepted inert fixtures')
    changed={k:r.copy() for k,r in rows.items()};changed[0,1]['pinion_torque']=1
    try: compare(changed,rows)
    except ValueError: pass
    else: fail('rack comparison accepted an altered reaction')
    print('rack qualification guard self-test: ok')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path);p.add_argument('--self-test',action='store_true');o=p.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from Spec group: {GROUP}')
    self_test()
    if o.self_test: return
    source,digest=verified_source(o.archive)
    record=dict(schema=1,fixture='rack-signed-ratios-seven-cases-360-steps',oracle_revision=REFERENCE,archive_sha256=digest,host=platform.platform(),bounds=BOUNDS,
        sources_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ('RackAndPinion.sx','RackAndPinionOracle.cpp','RackAndPinionRun.py','Run.py')},
        scope='signed/fractional rotation-travel ratios, unequal rack mass, rotated frame and sustained load, independent projection and travel; no freely rotating rack or general spatial-chain parity claim',modes={})
    for mode in ('Debug','Release'):
        oracle=build_oracle(source,mode,HERE/'RackAndPinionOracle.cpp','rack-oracle');silex=build_silex(mode,'RackAndPinion.sx','rack-silex',physics=True)
        outputs=dict(jolt=checked([str(oracle)]),silex=checked([str(silex)]));parsed={}
        for name,output in outputs.items():
            (BUILD/f'rack-{name}-{mode.lower()}.txt').write_text(output);parsed[name]=parse(output);mechanics(parsed[name])
        errors=compare(parsed['silex'],parsed['jolt']);record['modes'][mode]=dict(observations=len(CASES),maximum_errors=errors,independent_mechanics=True)
        print(f'rack {mode}: {len(CASES)} observations, errors {errors}',flush=True)
    (BUILD/'rack-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print('physics3d rack qualification: ok')
if __name__=='__main__': main()
