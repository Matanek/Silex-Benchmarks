#!/usr/bin/env python3
"""Qualify gears and preserve the pinned Jolt ratio defect without rendering."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
FIELDS=('first_speed','second_speed','first_torque')
BOUNDS=dict(zip(FIELDS,(0.0003,0.0003,0.002)))
CASES={(case,step) for case in range(6) for step in (1,*range(15,361,15))}
def parse(output):
    rows={}
    for line in output.splitlines():
        v=line.split()
        if len(v)!=6 or v[0]!='gear': fail('invalid gear row')
        try: key=tuple(map(int,v[1:3]));data=list(map(float,v[3:]))
        except ValueError: fail('invalid numeric gear row')
        if key not in CASES or key in rows or not all(map(math.isfinite,data)): fail('invalid gear observation')
        rows[key]=dict(zip(FIELDS,data))
    if set(rows)!=CASES: fail('missing gear observations')
    return rows

def mechanics(rows):
    for (case,step),row in rows.items():
        inertia=0.8 if case==1 else 0.2;speed=0.25 if case==4 else 0
        initial_lambda=-(speed+1)/(5+1/inertia)
        first=speed+5*initial_lambda;second=1+initial_lambda/inertia
        torque=initial_lambda*60 if step==1 else 0
        if case==5: first-=step*0.1/(0.4*60);second+=step*0.1/(0.4*60);torque-=0.05
        if any(abs(row[n]-e)>BOUNDS[n] for n,e in zip(FIELDS,(first,second,torque))): fail(f'gear lost independent projection/load {(case,step)} {row}')
def compare(actual,reference):
    errors=dict.fromkeys(FIELDS,0.0)
    for key in CASES:
        for name in FIELDS:
            e=abs(actual[key][name]-reference[key][name]);errors[name]=max(errors[name],e)
            if e>BOUNDS[name]: fail(f'gear {key} {name}: {e} > {BOUNDS[name]}')
    return errors

def known_reference_defect(output):
    rows={}
    for line in output.splitlines():
        v=line.split()
        if len(v)!=5 or v[0]!='gear-probe': fail('invalid native defect probe')
        ratio=float(v[1]);data=list(map(float,v[2:]))
        if ratio in rows or not all(map(math.isfinite,data)): fail('invalid duplicate defect probe')
        rows[ratio]=data
    native={1:(-.5,.5,-.1),2:(-2/3,1/3,-2/15),-1:(12,13,2.4)}
    if set(rows)!=set(native): fail('missing native defect ratios')
    result={}
    for ratio,actual in rows.items():
        if any(abs(a-b)>0.00001 for a,b in zip(actual,native[ratio])): fail('pinned native defect changed; reassess reference')
        impulse=-ratio/(5+5*ratio*ratio);expected=(5*impulse,1+5*ratio*impulse,impulse)
        error=max(abs(a-b) for a,b in zip(actual,expected))
        if (ratio==1 and error>0.00001) or (ratio!=1 and error<0.1): fail('defect witness did not discriminate ratios')
        result[str(ratio)]=dict(native=actual,mechanical=list(expected),maximum_error=error)
    return result

def self_test():
    rows={key:dict.fromkeys(FIELDS,0.) for key in CASES}
    output='\n'.join('gear '+' '.join(map(str,(*key,*(r[n] for n in FIELDS)))) for key,r in sorted(rows.items()))
    compare(parse(output),rows)
    for bad in (output+'\n'+output.splitlines()[0],'\n'.join(output.splitlines()[1:]),output.replace('gear 0 1 0.0','gear 0 1 nan',1)):
        try: parse(bad)
        except ValueError: continue
        fail('gear parser accepted corrupt evidence')
    try: mechanics(rows)
    except ValueError: pass
    else: fail('gear mechanics accepted inert fixtures')
    changed={k:r.copy() for k,r in rows.items()};changed[0,1]['first_torque']=1
    try: compare(changed,rows)
    except ValueError: pass
    else: fail('gear comparison accepted an altered reaction')
    print('gear qualification guard self-test: ok')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path);p.add_argument('--self-test',action='store_true');o=p.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from Spec group: {GROUP}')
    self_test()
    if o.self_test: return
    source,digest=verified_source(o.archive)
    record=dict(schema=1,fixture='gear-unit-ratio-six-cases-360-steps',oracle_revision=REFERENCE,archive_sha256=digest,host=platform.platform(),bounds=BOUNDS,
        sources_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ('Gear.sx','GearOracle.cpp','GearProbe.cpp','GearRun.py','Run.py')},
        scope='native unit-ratio speeds/reactions, unequal inertia, rotated and separate axes, initial speeds and sustained load; signed/nonunit ratios qualified analytically by consumer tests, pinned native defect preserved; no general spatial-chain or exact impact-step parity claim',modes={})
    for mode in ('Debug','Release'):
        probe=build_oracle(source,mode,HERE/'GearProbe.cpp','gear-probe')
        output=checked([str(probe)]);(BUILD/f'gear-defect-{mode.lower()}.txt').write_text(output);defect=known_reference_defect(output)
        oracle=build_oracle(source,mode,HERE/'GearOracle.cpp','gear-oracle');silex=build_silex(mode,'Gear.sx','gear-silex',physics=True)
        outputs=dict(jolt=checked([str(oracle)]),silex=checked([str(silex)]));parsed={}
        for name,output in outputs.items():
            (BUILD/f'gear-{name}-{mode.lower()}.txt').write_text(output);parsed[name]=parse(output);mechanics(parsed[name])
        errors=compare(parsed['silex'],parsed['jolt']);record['modes'][mode]=dict(observations=len(CASES),maximum_errors=errors,known_reference_defect=defect)
        print(f'gear {mode}: {len(CASES)} observations, errors {errors}; pinned nonunit/signed defect reproduced',flush=True)
    (BUILD/'gear-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print('physics3d gear qualification: ok')
if __name__=='__main__': main()
