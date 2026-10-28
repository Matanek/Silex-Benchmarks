#!/usr/bin/env python3
"""Qualify wheel contacts and bounded terrain compositions for all vehicle families."""
import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from VehicleTiresRun import add, cross, norm, scale
from VehicleInclineRun import rotation_error, sub
from LoadedSwingTwistRun import rotate
from TrackedVehicleRun import rejected

CURVES={(f,d,t,r,m) for f in range(3) for d in range(3) for t in range(6) for r in (60,120) for m in (0,1) if m==0 or t!=2}
KEYS={(*curve,step) for curve in CURVES for step in range((1 if curve[4]==0 else 6*curve[3])+1)}
def count(family):return 2 if family==2 else 4
WKEYS={(*key,i) for key in KEYS for i in range(count(key[0]))}
BUDGETS=(.05,.1,.02,.15)


def parse(raw):
    bodies={};wheels={}
    for line in raw.splitlines():
        fields=line.split()
        if not fields:fail('empty terrain record')
        if fields[0]=='terrain-body' and len(fields)==33:
            key=tuple(map(int,fields[1:7]));values=tuple(map(float,fields[7:]));target=bodies;expected=KEYS
        elif fields[0]=='terrain-wheel' and len(fields)==17:
            key=tuple(map(int,fields[1:8]));values=tuple(map(float,fields[8:]));target=wheels;expected=WKEYS
        else:fail('invalid terrain record schema')
        if key not in expected or key in target or not all(map(math.isfinite,values)):fail('invalid terrain record key or number')
        target[key]=values
    if set(bodies)!=KEYS or set(wheels)!=WKEYS:fail('incomplete terrain witness')
    return bodies,wheels


def inverse_rotate(q,v):return rotate((-q[0],-q[1],-q[2],q[3]),v)


def qualify(data,curves=CURVES,*,reference=False):
    bodies,wheels=data;worst={name:0. for name in ('linear','angular','pair_linear','pair_angular','unqualified_cumulative_pair_angular','height','surface','wheel_boundary','unqualified_reference_wheel_boundary')}
    worst['unqualified_reference_wheel_boundary_violations']=0
    for curve in sorted(curves):
        family,detector,terrain,rate,motion=curve;n=count(family);initial=bodies[*curve,0]
        normal=rotate(initial[6:10],(0,1,0));last=1 if motion==0 else 6*rate
        supported=False;crossed=False;rest_loads=[]
        for step in range(last+1):
            key=(*curve,step);body=bodies[key];p=body[:3];v=body[3:6];q=body[6:10];omega=body[10:13]
            if norm(p)>40 or norm(v)>15 or norm(omega)>5:fail('unbounded terrain chassis')
            for start in (6,19):
                if abs(sum(x*x for x in body[start:start+4])-1)>1e-4:fail('nonunit terrain body rotation')
            if terrain!=5 and body[13:]!=initial[13:]:fail('fixed terrain moved')
            force=(0.,0.,0.);torque=(0.,0.,0.);ground_torque=(0.,0.,0.);contacts=0
            old=bodies[*curve,max(0,step-1)]
            for i in range(n):
                length,load,hit,*geometry=wheels[*key,i];point=geometry[:3];axis=geometry[3:]
                if not 0<=length<=.60001 or not 0<=load<1e6 or hit not in (0.,1.):fail('invalid terrain wheel state')
                if step==0:
                    if load!=0 or hit!=0:fail('terrain initial contact/load')
                    continue
                if not hit:
                    if load!=0 or abs(length-.6)>1e-5 or norm(geometry)!=0:fail('unsupported terrain wheel has response')
                    continue
                contacts+=1
                if abs(norm(axis)-1)>1e-4:fail('nonunit terrain contact normal')
                local=inverse_rotate(old[19:23],sub(point,old[13:16]));surface=abs(local[1]-(.5 if terrain in (0,1,2,5) else 0.))
                worst['surface']=max(worst['surface'],surface)
                if surface>.003:fail(f'terrain point off support {key}/{i}: {surface}')
                anchor=(0.,0.,1. if i==0 else -1.) if family==2 else (-.6 if i<2 else .6,0.,-1. if i%2==0 else 1.)
                center=add(old[:3],rotate(old[6:10],add(anchor,(0.,-length,0.))))
                offset=sub(point,center)
                if detector==2:
                    axle=rotate(old[6:10],(-1.,0.,0.));axial=sum(a*b for a,b in zip(offset,axle));radial=norm(sub(offset,scale(axle,axial)))
                    boundary=max(abs(axial)-.2,radial-.3,min(abs(abs(axial)-.2),abs(radial-.3)))
                    channel='unqualified_reference_wheel_boundary' if reference and motion==1 else 'wheel_boundary'
                    worst[channel]=max(worst[channel],boundary)
                    if boundary>.003:
                        if reference and motion==1:worst['unqualified_reference_wheel_boundary_violations']+=1
                        else:fail(f'terrain point off wheel boundary {key}/{i}')
                elif abs(norm(offset)-.3)>.003:fail('terrain spherical/ray point off wheel boundary')
                if terrain==2 and local[0]>10.253:fail('edge contact lies beyond box')
                if terrain!=2 and (not reference or detector!=2 or motion==0) and norm(sub(axis,rotate(old[19:23],(0,1,0))))>.003:fail('planar terrain normal differs')
                reaction=scale(axis,load);force=add(force,reaction);torque=add(torque,cross(sub(point,old[:3]),reaction));ground_torque=add(ground_torque,cross(sub(point,old[13:16]),scale(reaction,-1)))
                if motion==0:
                    outside=terrain==2 and (family==2 or i>=2)
                    if outside and detector==0:fail('central ray reached beyond the edge')
                    expected=.8-math.sqrt(.08) if outside and detector==1 else .5
                    if abs(length-expected)>.003:fail(f'analytic terrain length differs {key}/{i}: {length}/{expected}')
            if not step:continue
            if motion==0:
                expected_contacts=(0 if family==2 else 2) if terrain==2 and detector==0 else n
                if contacts!=expected_contacts:fail('terrain detector support coverage differs')
            if motion==1:
                gravity=(0.,0.,0.) if terrain==5 else (0.,-9.81,0.)
                linear=norm(sub(scale(sub(v,old[3:6]),100),scale(add(force,scale(gravity,100)),1/rate)));worst['linear']=max(worst['linear'],linear)
                angular=norm(sub(scale(sub(omega,old[10:13]),100),scale(torque,1/rate)));worst['angular']=max(worst['angular'],angular)
                if linear>.1 or angular>.1:fail(f'terrain chassis balance {key}: {linear}/{angular}')
                if terrain==5:
                    momentum=add(scale(v,100),scale(body[16:19],1000));expected_momentum=add(scale(initial[3:6],100),scale(initial[16:19],1000));error=norm(sub(momentum,expected_momentum));worst['pair_linear']=max(worst['pair_linear'],error)
                    total=add(add(scale(omega,100),scale(body[23:26],10000)),add(cross(p,scale(v,100)),cross(body[13:16],scale(body[16:19],1000))))
                    first=add(add(scale(initial[10:13],100),scale(initial[23:26],10000)),add(cross(initial[:3],scale(initial[3:6],100)),cross(initial[13:16],scale(initial[16:19],1000))))
                    previous=add(add(scale(old[10:13],100),scale(old[23:26],10000)),add(cross(old[:3],scale(old[3:6],100)),cross(old[13:16],scale(old[16:19],1000))))
                    angular_error=norm(sub(total,previous));worst['pair_angular']=max(worst['pair_angular'],angular_error)
                    worst['unqualified_cumulative_pair_angular']=max(worst['unqualified_cumulative_pair_angular'],norm(sub(total,first)))
                    if error>.002 or angular_error>.002:fail('free terrain pair momentum differs')
                    center=scale(add(scale(p,100),scale(body[13:16],1000)),1/1100);first_center=scale(add(scale(initial[:3],100),scale(initial[13:16],1000)),1/1100)
                    if norm(sub(center,add(first_center,scale(expected_momentum,step/(rate*1100)))))>.002:fail('free terrain center of mass differs')
                    if norm(sub(scale(sub(body[23:26],old[23:26]),10000),scale(ground_torque,1/rate)))>.1:fail('terrain reaction angular balance')
                else:
                    if contacts==n:supported=True
                    if terrain in (3,4) and p[2]>1.5 and contacts==n:crossed=True
                    if step>5*rate:
                        expected=.9-981*normal[1]/(n*10000);height=sum(a*b for a,b in zip(p,normal));error=abs(height-expected);worst['height']=max(worst['height'],error)
                        if error>.003 or contacts!=n or abs(sum(a*b for a,b in zip(v,normal)))>.05:fail('analytic terrain equilibrium differs')
                        rest_loads.append(norm(force))
        if rest_loads and abs(sum(rest_loads)/len(rest_loads)-981*normal[1])>2:fail('analytic terrain mean normal load differs')
        if motion==1 and terrain!=5 and not supported:fail('terrain suspension never supported')
        if motion==1 and terrain in (3,4) and not crossed:fail('terrain seam traversal missing')
    return worst


def compare(first,second,*,allow_reference_limits=False):
    a,wa=first;b,wb=second;worst=[0.]*4;length_error=0.;window_error=0.;instant_angular=0.;mean_angular=0.;unqualified_grid_motorcycle_angular=0.
    for key in sorted(KEYS):
        for start in (0,13):
            x=a[key][start:start+13];y=b[key][start:start+13];errors=(norm(sub(x[:3],y[:3])),norm(sub(x[3:6],y[3:6])),rotation_error(x[6:10],y[6:10]),norm(sub(x[10:13],y[10:13])))
            for i,(error,budget) in enumerate(zip(errors,BUDGETS)):
                worst[i]=max(worst[i],error)
                if i==3 and key[1]==2 and key[4]==1:
                    instant_angular=max(instant_angular,error)
                elif error>budget:fail(f'terrain body parity {key}/{start}/{i}: {error}')
        for i in range(count(key[0])):
            error=abs(wa[*key,i][0]-wb[*key,i][0]);length_error=max(length_error,error)
            if error>.003:fail(f'terrain length parity {key}/{i}: {error}')
    for curve in CURVES:
        if curve[4]==0:continue
        rate=curve[3]
        if curve[1]==2:
            for quarter in range(24):
                steps=range(quarter*rate//4+1,(quarter+1)*rate//4+1)
                for start in (0,13):
                    difference=[sum(a[*curve,step][start+channel]-b[*curve,step][start+channel] for step in steps)/len(steps) for channel in range(10,13)]
                    error=norm(difference)
                    # The unassisted two-wheel cylinder/grid reference is sensitive
                    # beyond this budget even to a common 0.1 mm world translation.
                    # Keep its angular channel measured and explicitly unqualified;
                    # position, velocity, orientation, lengths and balances stay strict.
                    if allow_reference_limits and curve[0]==2 and curve[2]==4:
                        unqualified_grid_motorcycle_angular=max(unqualified_grid_motorcycle_angular,error)
                    else:
                        mean_angular=max(mean_angular,error)
                        if error>.05:fail(f'terrain cylinder mean angular response differs {curve}/{quarter}/{start}: {error}')
        for second in range(6):
            delta=abs(sum(sum(wa[*curve,step,i][1]-wb[*curve,step,i][1] for i in range(count(curve[0]))) for step in range(second*rate+1,(second+1)*rate+1)))/rate;window_error=max(window_error,delta)
            if delta>20:fail('terrain mean force parity')
    return {'body':worst,'length':length_error,'window_force':window_error,'cylinder_quarter_second_angular':mean_angular,'unqualified_cylinder_instantaneous_angular':instant_angular,'unqualified_grid_motorcycle_mean_angular':unqualified_grid_motorcycle_angular,'full_angular_parity':not allow_reference_limits}


def self_test(raw,data,*,reference=False):
    lines=raw.splitlines();rejected(lambda:parse('\n'.join(lines[1:])));rejected(lambda:parse(raw+lines[0]+'\n'))
    for index,value in ((0,'unknown'),(1,'3'),(2,'3'),(3,'6'),(4,'61'),(7,'nan'),(7,'inf')):
        fields=lines[0].split();fields[index]=value;rejected(lambda:parse(' '.join(fields)+'\n'+'\n'.join(lines[1:])))
    bodies,wheels=data
    for family in range(3):
        for detector in range(3):
            curve=(family,detector,0,120,1);key=(*curve,360)
            qualify(data,(curve,),reference=reference)
            for channel in range(26):
                altered=dict(bodies);row=list(altered[key]);row[channel]+=1000;altered[key]=tuple(row);rejected(lambda:qualify((altered,wheels),(curve,),reference=reference))
            for channel in range(9):
                altered=dict(wheels);wk=(*key,0);row=list(altered[wk]);row[channel]+=1000;altered[wk]=tuple(row);rejected(lambda:qualify((bodies,altered),(curve,),reference=reference))
    return 324



def comparison_scope_guards(data):
    compare(data,data,allow_reference_limits=True)
    bodies,wheels=data;curve=(2,2,4,120,1);key=(*curve,360)
    for channel,delta in ((0,.06),(3,.11),(6,1.)):
        altered=dict(bodies);row=list(altered[key]);row[channel]+=delta;altered[key]=tuple(row)
        rejected(lambda:compare(data,(altered,wheels),allow_reference_limits=True))
    altered=dict(wheels);wk=(*key,0);row=list(altered[wk]);row[0]+=.004;altered[wk]=tuple(row)
    rejected(lambda:compare(data,(bodies,altered),allow_reference_limits=True))
    def angular_change(selected):
        altered=dict(bodies)
        for step in range(1,31):
            k=(*selected,step);row=list(altered[k]);row[10]+=.06;altered[k]=tuple(row)
        return altered,wheels
    rejected(lambda:compare(data,angular_change((0,2,0,120,1)),allow_reference_limits=True))
    unqualified=angular_change(curve)
    rejected(lambda:compare(data,unqualified))
    result=compare(data,unqualified,allow_reference_limits=True)
    if result['unqualified_grid_motorcycle_mean_angular']<.059 or result['full_angular_parity']:
        fail('reference angular limit was hidden or claimed qualified')
    return {'rejected':6,'unqualified_channel_reported':1}


def source_fingerprint():
    paths=[HERE/name for name in ('VehicleTerrains.sx','VehicleTerrainsOracle.cpp',
        'VehicleTerrainsRun.py','Run.py','VehicleTiresRun.py','VehicleInclineRun.py',
        'LoadedSwingTwistRun.py','TrackedVehicleRun.py')]
    root=GROUP/'Packages/GFX.Physics'
    paths.extend((root/'Module').rglob('*.sx'));paths.append(root/'Package.json')
    return {str(path.relative_to(GROUP)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail('run from group root')
    source,digest=verified_source(args.archive);pins=source_fingerprint();compiler=Path(shutil.which('silex') or 'silex').resolve();compiler_sha=hashlib.sha256(compiler.read_bytes()).hexdigest();report={'schema':1,'compiler':{'path':str(compiler),'sha256':compiler_sha},'source_sha256':pins,'fixture':'vehicle-terrain-composition-v1','oracle_revision':REFERENCE,'archive_sha256':digest,'solver':[12,4],'body_budgets':BUDGETS,'moving_cylinder_angular_policy':{'window_seconds':.25,'mean_budget':.05,'pointwise_qualified':False},'free_support_angular_policy':{'per_step_budget':.002,'cumulative_qualified':False},'reference_limits':{'moving_cylinder_wheel_boundary_qualified':False,'unassisted_grid_motorcycle_angular_qualified':False,'strict_target_geometry':True},'modes':{}}
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'VehicleTerrainsOracle.cpp','vehicle-terrains-oracle');binary=build_silex(mode,'VehicleTerrains.sx','vehicle-terrains-silex',True);result={};parsed={}
        for engine,exe in [('silex',binary),('jolt',oracle)]:
            raw=checked([str(exe)]);(BUILD/f'vehicle-terrains-{engine}-{mode.lower()}.txt').write_text(raw);data=parse(raw);result[engine]={'body_states':len(data[0]),'wheel_states':len(data[1]),'qualification':qualify(data,reference=engine=='jolt'),'guards':self_test(raw,data,reference=engine=='jolt'),'comparison_scope_guards':comparison_scope_guards(data),'sha256':hashlib.sha256(raw.encode()).hexdigest()};parsed[engine]=data;print(mode,engine,'terrains qualified',flush=True)
        result['parity']=compare(parsed['silex'],parsed['jolt'],allow_reference_limits=True);report['modes'][mode]=result;(BUILD/'vehicle-terrains-qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(mode,'terrain comparison qualified within declared scope; reference limits retained',flush=True)
    if args.mode=='both':
        for engine in ('silex','jolt'):
            if (BUILD/f'vehicle-terrains-{engine}-debug.txt').read_bytes()!=(BUILD/f'vehicle-terrains-{engine}-release.txt').read_bytes():fail('terrain Debug/Release differ')
        report['debug_release_identical']=True;(BUILD/'vehicle-terrains-qualification.json').write_text(json.dumps(report,indent=2)+'\n')

    if source_fingerprint()!=pins or hashlib.sha256(compiler.read_bytes()).hexdigest()!=compiler_sha:fail('terrain qualification inputs changed during execution')
    report['inputs_unchanged']=True
    (BUILD/'vehicle-terrains-qualification.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
