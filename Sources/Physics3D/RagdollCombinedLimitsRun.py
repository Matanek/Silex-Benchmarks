#!/usr/bin/env python3
"""Qualify free ragdoll combined limits under oblique angular impulses."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD,GROUP,HERE,REFERENCE,build_oracle,build_silex,checked,fail,verified_source
from RagdollLimitsRun import base_rotation,conjugate,product
from RagdollContactRun import decomposition
from SpatialHingesRun import add,sub,mul,norm,dot,cross,rotate

CONFIGS=[(rate,side,frame) for rate in (60,120) for side in (-1,1) for frame in (0,1)]
KEYS={(tag,*config,step,part) for config in CONFIGS for tag in ('state','before')
      for step in (range(config[0]*4+1) if tag=='state' else (0,config[0]*2)) for part in range(3)}
BOUNDS=dict(anchor=.01,angular_excess=.08,observable=.00002,linear=.0001,angular=.02,
            center=.001,energy_step=.001,energy_phase=.005,speed=40)
PARITY=dict(center=.001,linear=.0001,angular=.02,energy=.05)


def parse(raw):
    rows={}
    for line in raw.splitlines():
        fields=line.split()
        if len(fields)!=23 or fields[0] not in ('ragdollcombined','ragdollcombinedimpulse'):
            fail('invalid combined ragdoll limit row')
        try:
            key=('state' if fields[0]=='ragdollcombined' else 'before',*map(int,fields[1:6]))
            values=tuple(map(float,fields[6:]))
        except (ValueError,OverflowError):fail('invalid combined ragdoll number')
        if key not in KEYS or key in rows or not all(map(math.isfinite,values)):
            fail('unknown, duplicate or nonfinite combined ragdoll state')
        rows[key]=values
    if set(rows)!=KEYS:fail('missing combined ragdoll limit states')
    return rows


def totals(members):
    linear=(0,0,0);angular=(0,0,0);center=(0,0,0);energy=0.0
    for row in members:
        p,v,w=row[:3],row[7:10],row[10:13]
        linear=add(linear,mul(v,2));angular=add(angular,add(mul(cross(p,v),2),mul(w,.2)))
        center=add(center,mul(p,1/3));energy+=dot(v,v)+.1*dot(w,w)
    return dict(linear=linear,angular=angular,center=center,energy=energy)


def cone_excess(swing):
    radius=math.hypot(swing[1],swing[2])
    if radius<1e-10:return 0,0
    ellipse=math.sqrt((swing[1]/math.sin(.15))**2+(swing[2]/math.sin(.225))**2)
    allowed=radius/ellipse
    return max(0,2*math.asin(min(1,radius))-2*math.asin(min(1,allowed))),ellipse


def qualify(rows):
    worst=dict.fromkeys(BOUNDS,0);activation={part:dict(swing_y=0,swing_z=0,cone=0,twist_min=0,twist_max=0) for part in (1,2)}
    for config in CONFIGS:
        rate,side,frame=config;base=base_rotation(frame)
        impulse=rotate(base,mul((.2,.3,-.2),side));expected_center=add((0,3,0),rotate(base,(1,0,0)))
        prior_energy=0;phase_energy=0
        for step in range(rate*4+1):
            members=[rows['state',*config,step,part] for part in range(3)];all_values=totals(members)
            for part,row in enumerate(members):
                p,q,v,w=row[:3],row[3:7],row[7:10],row[10:13];twist,sy,sz,anchor=row[13:]
                error=abs(norm(q)-1)
                if norm(p)>10:fail('unbounded combined ragdoll position')
                if step==0:
                    expected_position=add((0,3,0),rotate(base,(part,0,0)))
                    if norm(sub(p,expected_position))>.000001 or abs(dot(q,base)-1)>.00001 or norm(v)>.00001:fail('initial combined ragdoll transform or velocity differs')
                values=dict(speed=max(norm(v),norm(w)),observable=error)
                if part:
                    parent=members[part-1];relative=product(conjugate(parent[3:7]),q)
                    swing,angle=decomposition(relative);excess,ellipse=cone_excess(swing)
                    first=add(parent[:3],rotate(parent[3:7],(.5,0,0)));second=add(p,rotate(q,(-.5,0,0)))
                    error=max(error,abs(angle-twist),abs(2*math.atan2(swing[1],swing[3])-sy),
                        abs(2*math.atan2(swing[2],swing[3])-sz),abs(norm(sub(second,first))-anchor))
                    values.update(anchor=anchor,angular_excess=max(excess,-.2-angle,angle-.35,0),observable=error)
                    if anchor<0:fail('negative anchor error')
                    observed=activation[part];observed['swing_y']=max(observed['swing_y'],abs(sy));observed['swing_z']=max(observed['swing_z'],abs(sz))
                    observed['cone']=max(observed['cone'],ellipse);observed['twist_min']=min(observed['twist_min'],twist);observed['twist_max']=max(observed['twist_max'],twist)
                elif max(map(abs,row[13:]))!=0:fail('root has a parent observation')
                for name,value in values.items():
                    worst[name]=max(worst[name],value)
                    if value>=BOUNDS[name]:fail(f'combined {name} bound exceeded: {value} at {config}/{step}/{part}')
            expected_angular=impulse if step<rate*2 else (0,0,0)
            values=dict(linear=norm(all_values['linear']),angular=norm(sub(all_values['angular'],expected_angular)),
                center=norm(sub(all_values['center'],expected_center)))
            energy=all_values['energy']
            if step in (0,rate*2):
                before=[rows['before',*config,step,part] for part in range(3)];previous=totals(before)
                if step==0 and max(max(norm(row[7:10]),norm(row[10:13])) for row in before)>.00001:fail('initial pre-impulse state is moving')
                jump=mul(impulse,5 if step==0 else -5)
                for part,(a,b) in enumerate(zip(before,members)):
                    expected=jump if part==2 else (0,0,0)
                    if norm(sub(sub(b[10:13],a[10:13]),expected))>.00002:fail('oblique angular impulse differs or affects another member')
                    if max(abs(a[i]-b[i]) for i in (*range(10),*range(13,17)))>.000001:fail('impulse placed a body or changed constraint geometry')
                injected=.2*dot(before[2][10:13],jump)+.1*dot(jump,jump)
                if abs(energy-previous['energy']-injected)>.00002:fail('angular impulse energy increment differs')
                phase_energy=energy
            else:
                values.update(energy_step=max(0,energy-prior_energy),energy_phase=max(0,energy-phase_energy))
            for name,value in values.items():
                worst[name]=max(worst[name],value)
                if value>=BOUNDS[name]:fail(f'combined {name} bound exceeded: {value} at {config}/{step}')
            prior_energy=energy
    for part,observed in activation.items():
        if min(observed['swing_y'],observed['swing_z'])<.02 or observed['cone']<.95:
            fail(f'combined swing directions or cone were not exercised on member {part}')
        if observed['twist_min']>-.17 or observed['twist_max']<.32:
            fail(f'both twist stops were not exercised on member {part}')
    return dict(worst=worst,activation=activation)


def compare(first,second):
    worst=dict.fromkeys(PARITY,0)
    for config in CONFIGS:
        rate,side,frame=config
        for start,end in ((int(rate*1.5),rate*2),(int(rate*3.5),rate*4+1)):
            interval=range(start,end);energies=[0,0]
            for step in interval:
                a=totals([first['state',*config,step,p] for p in range(3)]);b=totals([second['state',*config,step,p] for p in range(3)])
                for name in ('center','linear','angular'):
                    error=norm(sub(a[name],b[name]));worst[name]=max(worst[name],error)
                    if error>=PARITY[name]:fail(f'combined {name} parity differs: {error}')
                energies[0]+=a['energy'];energies[1]+=b['energy']
            error=abs(energies[0]-energies[1])/len(interval);worst['energy']=max(worst['energy'],error)
            if error>=PARITY['energy']:fail(f'combined mean energy parity differs: {error}')
    return worst


def rejected(action):
    try:action()
    except ValueError:return
    fail('combined ragdoll guard accepted corrupt evidence')


def self_test(raw,rows):
    lines=raw.splitlines();count=0
    for changed in (raw+'\n'+lines[0],'\n'.join(lines[1:]),raw.replace('ragdollcombinedimpulse 60 -1','ragdollcombinedimpulse 61 -1',1),raw.replace(lines[0],lines[0]+' 0',1)):
        rejected(lambda changed=changed:parse(changed));count+=1
    fields=lines[0].split();fields[6]='nan';changed=lines.copy();changed[0]=' '.join(fields)
    rejected(lambda:parse('\n'.join(changed)));count+=1
    for component in range(17):
        altered=rows.copy();key=('state',60,1,1,90,2);values=list(altered[key]);values[component]+=2
        altered[key]=tuple(values);rejected(lambda:qualify(altered));count+=1
    for component in (0,10):
        altered=rows.copy();key=('before',60,1,0,120,2);values=list(altered[key]);values[component]+=.1
        altered[key]=tuple(values);rejected(lambda:qualify(altered));count+=1
    altered=rows.copy()
    for part,jump in ((1,2),(2,-2)):
        key=('state',60,1,0,90,part);values=list(altered[key]);values[10]+=jump;altered[key]=tuple(values)
    rejected(lambda:qualify(altered));count+=1
    altered=rows.copy();key=('state',60,1,0,90,0);values=list(altered[key]);values[13]=.1;altered[key]=tuple(values)
    rejected(lambda:qualify(altered));count+=1
    for name in PARITY:
        altered=rows.copy()
        for step in range(90,120):
            key=('state',60,1,0,step,0);values=list(altered[key])
            if name=='center':values[0]+=.006
            if name=='linear':values[7]+=.0001
            if name=='angular':values[10]+=.11
            if name=='energy':
                for part,jump in ((1,3),(2,-3)):
                    k=('state',60,1,0,step,part);v=list(altered[k]);v[10]+=jump;altered[k]=tuple(v)
            altered[key]=tuple(values)
        rejected(lambda:compare(rows,altered));count+=1
    return count


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both')
    parser.add_argument('--archive',type=Path);parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from workspace or Spec group root: {GROUP}')
    source,digest=verified_source(args.archive)
    record=dict(schema=1,fixture='ragdoll-free-combined-stops-v1',oracle_revision=REFERENCE,archive_sha256=digest,bounds=BOUNDS,parity_bounds=PARITY,
        scope='Three free spheres with combined swing/twist limits, opposed oblique angular impulses, no gravity or contact. Global invariants and window-mean energy, not individual impact trajectories.',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        if not args.check_only:
            oracle=build_oracle(source,mode,HERE/'RagdollCombinedLimitsOracle.cpp','ragdoll-combined-oracle')
            binary=build_silex(mode,'RagdollCombinedLimits.sx','ragdoll-combined-silex',True)
            for name,exe in (('silex',binary),('jolt',oracle)):
                (BUILD/f'ragdoll-combined-{name}-{mode.lower()}.txt').write_text(checked([str(exe)]))
        evidence={};all_rows={}
        for name in ('silex','jolt'):
            raw=(BUILD/f'ragdoll-combined-{name}-{mode.lower()}.txt').read_text();rows=parse(raw);all_rows[name]=rows
            evidence[name]=dict(observations=len(rows),qualification=qualify(rows),corrupt_witnesses_rejected=self_test(raw,rows),output_sha256=hashlib.sha256(raw.encode()).hexdigest())
        evidence['invariant_parity']=compare(all_rows['silex'],all_rows['jolt']);record['modes'][mode]=evidence
        (BUILD/'ragdoll-combined-qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        print(f'{mode}: free combined ragdoll limits, global invariants and mean energy green',flush=True)

if __name__=='__main__':main()
