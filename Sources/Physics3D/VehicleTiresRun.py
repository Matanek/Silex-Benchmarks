#!/usr/bin/env python3
"""Qualify passive tire rolling and lateral grip against pinned Jolt."""
import argparse, hashlib, json, math
from pathlib import Path
from Run import BUILD,GROUP,HERE,REFERENCE,build_oracle,build_silex,checked,fail,verified_source
from LoadedSwingTwistRun import rotate
from RagdollHierarchyRun import rotation_error

DURATION={0:3,1:3,2:3,3:1,4:4,5:3}
KEYS={(kind,rate,step) for kind,seconds in DURATION.items() for rate in (60,120) for step in range(rate*seconds+1)}
TOLERANCES=dict(position=.02,velocity=.05,rotation=.01,angular_velocity=.1,wheel_speed=.1,wheel_angle=.05,slip=.05,slip_phase_mean=.01,slip_definition=.002,impulse_balance=.1)

def parse(raw):
    rows={}
    for line in raw.splitlines():
        f=line.split()
        if len(f)!=53 or f[0]!='tires':fail('invalid tire row')
        key=tuple(map(int,f[1:4]));v=tuple(map(float,f[4:]))
        if key not in KEYS or key in rows or not all(map(math.isfinite,v)):fail('invalid tire key or value')
        rows[key]=v
    if set(rows)!=KEYS:fail('incomplete tire witness')
    return rows

def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def add(a,b):return [x+y for x,y in zip(a,b)]
def scale(a,b):return [x*b for x in a]
def norm(a):return math.sqrt(dot(a,a))
def curve(x,lateral=False):
    points=[(0,0),(math.radians(3),1.2),(math.radians(20),1)] if lateral else [(0,0),(.06,1.2),(.2,1)]
    for (a,b),(c,d) in zip(points,points[1:]):
        if x<=c:return b+(d-b)*(x-a)/(c-a)
    return 1

def qualify(rows):
    worst=[0.,0.,0.]
    for (kind,rate,step),v in sorted(rows.items()):
        if abs(dot(v[6:10],v[6:10])-1)>.0001 or v[1]<.5 or norm(v[:3])>15 or norm(v[3:6])>10 or norm(v[10:13])>5:fail('unbounded tire chassis')
        for i in range(4):
            length,n,omega,angle,slip,lateral,f_long,f_lat,contact=v[13+9*i:22+9*i]
            if not 0<=length<=.60001 or not 0<=n<10000 or abs(omega)>100 or abs(angle)>2*math.pi+.0001 or slip<0 or not 0<=lateral<=math.pi/2+.0001 or contact not in (0,1):fail('invalid tire state')
            if abs(f_long)>math.sqrt(curve(slip))*n+.05 or abs(f_lat)>math.sqrt(curve(lateral,True))*n+.05:fail('tire force exceeds friction capacity')
            if contact==0 and (n!=0 or f_long!=0 or f_lat!=0 or abs(length-.6)>.00001):fail('unsupported tire applied force')
        if step==0:
            if abs(v[1]-(3 if kind==3 else .875475))>.00001:fail('wrong initial tire chassis height')
            for i in range(4):
                if abs(v[15+9*i]-(10*(i+1) if kind==3 else 0))>.00001 or v[16+9*i]!=0:fail('wrong initial wheel rotation')
            continue
        old=rows[kind,rate,step-1];dt=1/rate;linear=[0.,0.,0.];torque=[0.,0.,0.]
        right=rotate(old[6:10],(-1,0,0));long=cross((0,1,0),right);long=scale(long,1/norm(long));lat=cross(long,(0,1,0))
        for i,(x,z) in enumerate(((-.6,-1),(-.6,1),(.6,-1),(.6,1))):
            length,n,omega,angle,slip,lateral,f_long,f_lat,contact=v[13+9*i:22+9*i]
            force=add(add((0,n,0),scale(long,f_long)),scale(lat,f_lat));linear=add(linear,scale(force,dt))
            radius=rotate(old[6:10],(x,-length-.3,z));torque=add(torque,scale(cross(radius,force),dt))
            damped=old[15+9*i]*(1-.2*dt if kind==3 else 1)
            if contact:
                point_velocity=add(old[3:6],cross(old[10:13],radius));point_velocity[1]=0
                longitudinal=dot(point_velocity,long);magnitude=norm(point_velocity)
                expected_slip=abs(damped*.3-longitudinal)/max(.001,abs(longitudinal))
                expected_lateral=0 if magnitude<.001 else math.acos(max(0,min(1,abs(longitudinal)/magnitude)))
                if abs(slip-expected_slip)>.002 or abs(lateral-expected_lateral)>.002:fail(f'tire slip definition differs {(kind,rate,step,i)}')
            error=abs(.9*(omega-damped)+f_long*.3*dt);worst[2]=max(worst[2],error)
            if error>.1:fail(f'wheel angular impulse balance {(kind,rate,step,i)}: {error}')
            expected=math.fmod(old[16+9*i]+damped*dt,2*math.pi)
            if abs(math.atan2(math.sin(angle-expected),math.cos(angle-expected)))>.0001:fail('wheel angle did not advance once before constraint solve')
        external=(0,0 if kind==3 else -981*dt,0)
        if kind==4 and step==rate+1:external=add(external,(0,500,0))
        e_linear=norm(add(scale([x-y for x,y in zip(v[3:6],old[3:6])],100),scale(add(linear,external),-1)))
        e_angular=norm(add(scale([x-y for x,y in zip(v[10:13],old[10:13])],100),scale(torque,-1)))
        worst[0]=max(worst[0],e_linear);worst[1]=max(worst[1],e_angular)
        if max(e_linear,e_angular)>.1:fail(f'chassis impulse balance {(kind,rate,step)}: {e_linear}, {e_angular}')
    for rate in (60,120):
        for kind in (0,5):
            final=rows[kind,rate,DURATION[kind]*rate];axis=3 if kind==5 else 5
            if abs(final[axis]-300/140)>.02 or abs(final[4])>.02:fail('passive rolling failed analytic momentum coupling')
            for i in range(4):
                if abs(final[15+9*i]*.3-final[axis])>.02:fail('passive wheel failed rolling condition')
        diagonal=rows[2,rate,3*rate]
        right=rotate(diagonal[6:10],(-1,0,0));forward=cross((0,1,0),right);forward=scale(forward,1/norm(forward));side=cross(forward,(0,1,0))
        if abs(dot(diagonal[3:6],side))>.01:fail('diagonal vehicle retained lateral drift')
        for i in range(4):
            if abs(diagonal[15+9*i]*.3-dot(diagonal[3:6],forward))>.02:fail('diagonal wheel failed relative rolling condition')
        final=rows[1,rate,3*rate]
        if abs(final[3])>.01 or final[0]>1:fail('lateral grip did not stop sliding')
        contacts=[sum(rows[4,rate,s][21+9*i] for i in range(4)) for s in range(rate+1,4*rate+1)]
        if 0 not in contacts or 4 not in contacts[contacts.index(0)+1:]:fail('moving tire jump did not lose and regain support')
        for step in range(rate+1):
            free=rows[3,rate,step]
            if norm(free[3:6])>.0001 or abs(free[1]-3)>.0001:fail('free wheels moved the chassis')
    return dict(zip(('linear_impulse','angular_impulse','wheel_impulse'),worst))

def compare(a,b):
    worst=[0.]*6
    for key in KEYS:
        x,y=a[key],b[key]
        errors=[max(abs(p-q) for p,q in zip(x[:3],y[:3])),max(abs(p-q) for p,q in zip(x[3:6],y[3:6])),rotation_error(x[6:10],y[6:10]),max(abs(p-q) for p,q in zip(x[10:13],y[10:13])),max(abs(x[15+9*i]-y[15+9*i]) for i in range(4)),max(abs(math.atan2(math.sin(x[16+9*i]-y[16+9*i]),math.cos(x[16+9*i]-y[16+9*i]))) for i in range(4))]
        if any(e>t for e,t in zip(errors,(.02,.05,.01,.1,.1,.05))):fail(f'tire trajectory differs from Jolt {key}: {errors}')
        for i in range(4):
            if abs(x[13+9*i]-y[13+9*i])>.02:fail('tire suspension length differs from Jolt')
            if x[21+9*i]==y[21+9*i]==1:
                for channel in (17,18):
                    if min(x[channel+9*i],y[channel+9*i])>.1 and abs(x[channel+9*i]-y[channel+9*i])>.05:fail(f'large tire slip differs from Jolt {key}')
        worst=[max(p,q) for p,q in zip(worst,errors)]
    for kind,seconds in DURATION.items():
        for rate in (60,120):
            for start,end in ((0,.25),(.25,.75),(.75,1.25),(1.25,seconds)):
                if start>=seconds:continue
                steps=range(math.ceil(start*rate),math.floor(min(end,seconds)*rate)+1)
                for i in range(4):
                    for channel in (17,18):
                        first=[a[kind,rate,s][channel+9*i] for s in steps if a[kind,rate,s][21+9*i]==1]
                        second=[b[kind,rate,s][channel+9*i] for s in steps if b[kind,rate,s][21+9*i]==1]
                        if first and second and abs(sum(first)/len(first)-sum(second)/len(second))>.01:fail(f'tire mean slip differs {(kind,rate,start,end,i,channel)}')
    return worst

def self_test(raw,rows):
    def reject(action):
        try:action()
        except (ValueError,OverflowError):return
        fail('corrupt tire witness accepted')
    lines=raw.splitlines();reject(lambda:parse('\n'.join(lines[1:])));reject(lambda:parse(raw+'\n'+lines[0]))
    fields=lines[0].split();fields[4]='nan';reject(lambda:parse(' '.join(fields)+'\n'+'\n'.join(lines[1:])))
    for index in range(49):
        changed=dict(rows);v=list(changed[0,60,30]);v[index]+=1000 if index in (14,19,20,23,28,29,32,37,38,41,46,47) else 1;changed[0,60,30]=tuple(v)
        def check():qualify(changed);compare(changed,rows)
        reject(check)
    return 52

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from group root: {GROUP}')
    source,digest=verified_source(args.archive);record=dict(schema=1,fixture='passive-tires-v1',oracle_revision=REFERENCE,archive_sha256=digest,tolerances=TOLERANCES,iterations=[12,4],workers=1,modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'VehicleTiresOracle.cpp','vehicle-tires-oracle');binary=build_silex(mode,'VehicleTires.sx','vehicle-tires-silex',True)
        rows={};evidence={}
        for name,exe in (('silex',binary),('jolt',oracle)):
            raw=checked([str(exe)]);(BUILD/f'vehicle-tires-{name}-{mode.lower()}.txt').write_text(raw);rows[name]=parse(raw)
            evidence[name]=dict(observations=len(rows[name]),balances=qualify(rows[name]),guards=self_test(raw,rows[name]),sha256=hashlib.sha256(raw.encode()).hexdigest())
        evidence['parity']=compare(rows['silex'],rows['jolt']);record['modes'][mode]=evidence
        (BUILD/'vehicle-tires-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(mode,'passive tire qualification green',flush=True)

if __name__=='__main__':main()
