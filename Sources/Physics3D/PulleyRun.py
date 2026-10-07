#!/usr/bin/env python3
"""Qualify pulley geometry, weighted lengths and reactions without rendering."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
FIELDS=('first_y','second_y','first_vy','second_vy','first_wz','second_wz','first_angle','second_angle','length','first_fx','first_fy','second_fx','second_fy','first_tz','second_tz','energy')
BOUNDS=dict(zip(FIELDS,(0.005,0.005,0.003,0.003,0.003,0.003,0.005,0.005,0.005,0.05,0.05,0.05,0.05,0.02,0.02,0.05)))
CASES={(case,step) for case in range(10) for step in (1,*range(15,361,15))}
def parse(output):
    rows={}
    for line in output.splitlines():
        v=line.split()
        if len(v)!=len(FIELDS)+3 or v[0]!='pulley': fail('invalid pulley row')
        try: key=tuple(map(int,v[1:3]));data=list(map(float,v[3:]))
        except ValueError: fail('invalid numeric pulley row')
        if key not in CASES or key in rows or not all(map(math.isfinite,data)): fail('invalid pulley observation')
        rows[key]=dict(zip(FIELDS,data))
    if set(rows)!=CASES: fail('missing pulley observations')
    return rows

def wrapped(angle):
    return angle-2*math.pi*math.floor((angle+math.pi)/(2*math.pi))

def mechanics(rows):
    ratios=(1,2,.5,1,2,1,1,1,1,1);dt=1/60
    for (case,step),r in rows.items():
        ratio=ratios[case];mass=8 if case in (1,8) else (4 if case==4 else 2)
        t=step*dt;expected={}
        if case in (0,1,2,9):
            impulse=-ratio/(.5+ratio*ratio/mass)
            a=-impulse/2;b=-1-ratio*impulse/mass
            expected=dict(first_y=a*t,second_y=b*t,first_vy=a,second_vy=b,first_fy=-impulse/dt if step==1 else 0,second_fy=-ratio*impulse/dt if step==1 else 0,length=10*(1+ratio),energy=a*a+.5*mass*b*b)
        if case in (3,4):
            expected=dict(first_y=0,second_y=0,first_vy=0,second_vy=0,first_fy=19.62,second_fy=ratio*19.62,length=10*(1+ratio),energy=0)
        if case==5:
            expected=dict(first_y=0,second_y=-t,first_vy=0,second_vy=-1,first_fy=0,second_fy=0,length=20+t,energy=1)
        if case==6:
            y=0 if step<=180 else 1
            expected=dict(first_y=y,second_y=y,first_vy=0,second_vy=0,first_fy=0,second_fy=0,length=20-2*y,energy=0)
        if case==8:
            acceleration=5.886;y=acceleration*dt*dt*step*(step+1)/2;v=acceleration*t
            expected=dict(first_y=y,second_y=-y,first_vy=v,second_vy=-v,first_fy=31.392,second_fy=31.392,length=400,energy=5*v*v)
        if case==7:
            if r['length']>20.005 or r['energy']>1.0001: fail('pulley offset cable stretched or created energy')
            if step==1:
                impulse=-1/3.5
                expected=dict(first_vy=-impulse/2,second_vy=-1-impulse/2,first_wz=-2.5*impulse,second_wz=-2.5*impulse,first_fy=-impulse/dt,second_fy=-impulse/dt,first_tz=-.5*impulse/dt,second_tz=-.5*impulse/dt)
        else:
            expected.update(first_fx=0,second_fx=0,first_tz=0,second_tz=0,first_wz=0,second_wz=0,first_angle=0,second_angle=0)
        for name,value in expected.items():
            limit=BOUNDS[name]
            if case==8 and name=='energy':
                limit+=(2*abs(expected['first_vy'])+8*abs(expected['second_vy']))*BOUNDS['first_vy']+5*BOUNDS['first_vy']**2
                measured=r['first_vy']**2+4*r['second_vy']**2
                if abs(r['energy']-measured)>BOUNDS['energy']: fail('pulley Atwood energy disagrees with its measured velocities')
            if abs(r[name]-value)>limit: fail(f'pulley lost independent mechanics {(case,step)} {name} {r[name]} vs {value}')
def compare(actual,reference):
    errors=dict.fromkeys(FIELDS,0.0)
    for key in CASES:
        for name in FIELDS:
            e=actual[key][name]-reference[key][name]
            e=abs(wrapped(e) if name in ('first_angle','second_angle') else e);errors[name]=max(errors[name],e)
            if e>BOUNDS[name]: fail(f'pulley {key} {name}: {e} > {BOUNDS[name]}')
    return errors

def self_test():
    rows={key:dict.fromkeys(FIELDS,0.) for key in CASES}
    output='\n'.join('pulley '+' '.join(map(str,(*key,*(r[n] for n in FIELDS)))) for key,r in sorted(rows.items()))
    compare(parse(output),rows)
    for bad in (output+'\n'+output.splitlines()[0],'\n'.join(output.splitlines()[1:]),output.replace('pulley 0 1 0.0','pulley 0 1 nan',1)):
        try: parse(bad)
        except ValueError: continue
        fail('pulley parser accepted corrupt evidence')
    try: mechanics(rows)
    except ValueError: pass
    else: fail('pulley mechanics accepted inert fixtures')
    changed={k:r.copy() for k,r in rows.items()};changed[0,1]['first_tz']=1
    try: compare(changed,rows)
    except ValueError: pass
    else: fail('pulley comparison accepted an altered reaction')
    print('pulley qualification guard self-test: ok')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path);p.add_argument('--self-test',action='store_true');o=p.parse_args()
    if Path.cwd().resolve()!=GROUP: fail(f'run from Spec group: {GROUP}')
    self_test()
    if o.self_test: return
    source,digest=verified_source(o.archive)
    record=dict(schema=1,fixture='pulley-ten-cases-360-steps',oracle_revision=REFERENCE,archive_sha256=digest,host=platform.platform(),bounds=BOUNDS,
        analytic_energy_scope="Atwood analytic energy propagates the predeclared velocity error; measured energy must match reported velocities within 0.05 J; pairwise oracle energy bound remains 0.05 J",
        sources_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ('Pulley.sx','PulleyOracle.cpp','PulleyRun.py','Run.py')},
        scope='taut/slack cable, block/tackle ratios, unequal masses, balanced load, length mutation, offset anchors, Atwood load and rotated frame; independent projection, force, travel and energy; no general spatial-chain or exact impact-step parity claim',modes={})
    for mode in ('Debug','Release'):
        oracle=build_oracle(source,mode,HERE/'PulleyOracle.cpp','pulley-oracle');silex=build_silex(mode,'Pulley.sx','pulley-silex',physics=True)
        outputs=dict(jolt=checked([str(oracle)]),silex=checked([str(silex)]));parsed={}
        for name,output in outputs.items():
            (BUILD/f'pulley-{name}-{mode.lower()}.txt').write_text(output);parsed[name]=parse(output);mechanics(parsed[name])
        errors=compare(parsed['silex'],parsed['jolt']);record['modes'][mode]=dict(observations=len(CASES),maximum_errors=errors,independent_mechanics=True)
        print(f'pulley {mode}: {len(CASES)} observations, errors {errors}',flush=True)
    (BUILD/'pulley-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print('physics3d pulley qualification: ok')
if __name__=='__main__': main()
