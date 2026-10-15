#!/usr/bin/env python3
"""Qualify wheel steering and service/hand brakes against pinned Jolt."""
import argparse,hashlib,json,math
from pathlib import Path
from Run import BUILD,GROUP,HERE,REFERENCE,build_oracle,build_silex,checked,fail,verified_source
from LoadedSwingTwistRun import rotate
from RagdollHierarchyRun import rotation_error
from VehicleTiresRun import cross,dot,add,scale,norm,curve

DURATION={k:2 if k==7 else 4 for k in range(8)}
KEYS={(k,r,s) for k,d in DURATION.items() for r in (60,120) for s in range(r*d+1)}
TOLERANCES=dict(position=.05,velocity=.1,rotation=.02,angular_velocity=.15,wheel_speed=.25,wheel_angle=.1,steering=.00001,slip=.05,slip_phase_mean=.02,slip_definition=.002,impulse_balance=.1,brake_torque=.01)
TOLERANCES.update(slip_velocity=TOLERANCES['velocity'],conditioning_speed=TOLERANCES['velocity'])
def inputs(kind,time):
    steering=(.2 if kind in (4,6) else -.2 if kind==5 else 0) if .5<=time<2.5 else 0
    brake=1 if kind==7 or kind<=2 and 1<=time<3 else .3 if kind==6 and 2<=time<3 else 0
    return steering,brake,1 if kind==3 and 1<=time<3 else 0

def parse(raw):
    rows={}
    for line in raw.splitlines():
        f=line.split()
        if len(f)!=61 or f[0]!='controls':fail('invalid wheel controls row')
        key=tuple(map(int,f[1:4]));v=tuple(map(float,f[4:]))
        if key not in KEYS or key in rows or not all(map(math.isfinite,v)):fail('invalid wheel controls key or value')
        rows[key]=v
    if set(rows)!=KEYS:fail('incomplete wheel controls witness')
    return rows

def qualify(rows):
    worst=[0.,0.,0.]
    for (kind,rate,step),v in sorted(rows.items()):
        if abs(dot(v[6:10],v[6:10])-1)>.0001 or v[1]<.5 or norm(v[:3])>20 or norm(v[3:6])>10 or norm(v[10:13])>5:fail('unbounded controlled chassis')
        old=rows.get((kind,rate,step-1));dt=1/rate;linear=[0.,0.,0.];torque=[0.,0.,0.]
        steering,brake,hand=inputs(kind,(step-1)/rate) if step else (0,0,0)
        for i,(x,z) in enumerate(((-.6,-1),(-.6,1),(.6,-1),(.6,1))):
            length,n,omega,angle,slip,lateral,f_long,f_lat,contact,turn,braking=v[13+11*i:24+11*i]
            if not 0<=length<=.60001 or not 0<=n<10000 or abs(omega)>100 or abs(angle)>2*math.pi+.0001 or slip<0 or not 0<=lateral<=math.pi/2+.0001 or contact not in (0,1):fail('invalid controlled wheel state')
            expected_turn=-steering*.5 if z>0 else 0
            if abs(turn-expected_turn)>.00001:fail('steering sign or wheel selection differs')
            budget=brake*(1.5 if kind==0 else 0 if kind==3 else .9 if kind==7 else 1500)+hand*(20 if z<0 else 0)
            if abs(braking)>budget+.01:fail('brake torque exceeds input budget')
            if abs(f_long)>math.sqrt(curve(slip))*n+.05 or abs(f_lat)>math.sqrt(curve(lateral,True))*n+.05:fail('controlled tire force exceeds friction')
            if contact==0 and (n!=0 or f_long!=0 or f_lat!=0 or abs(length-.6)>.00001):fail('unsupported controlled wheel applied force')
            if not step:
                initial=10*(i+1) if kind==7 else -10 if kind==2 else 10
                if abs(omega-initial)>.00001 or angle!=0 or turn!=0 or braking!=0:fail('wrong initial wheel controls state')
                continue
            q=(0,math.sin(turn/2),0,math.cos(turn/2));right=rotate(old[6:10],rotate(q,(-1,0,0)))
            long=cross((0,1,0),right);long=scale(long,1/norm(long));lat=cross(long,(0,1,0))
            force=add(add((0,n,0),scale(long,f_long)),scale(lat,f_lat));linear=add(linear,scale(force,dt))
            radius=rotate(old[6:10],(x,-length-.3,z));torque=add(torque,scale(cross(radius,force),dt))
            previous=old[15+11*i];expected_angle=math.fmod(old[16+11*i]+previous*dt,2*math.pi)
            if abs(math.atan2(math.sin(angle-expected_angle),math.cos(angle-expected_angle)))>.0001:fail('controlled angle did not advance once before braking')
            slowed=math.copysign(max(0,abs(previous)-budget*dt/.9),previous)
            locked=budget>abs(previous)*.9/dt
            expected_omega=0 if locked else slowed-f_long*.3*dt/.9
            if abs(omega-expected_omega)>.0001:fail('wheel braking or locking rule differs')
            e=abs(.9*(omega-previous)+(f_long*.3-braking)*dt);worst[2]=max(worst[2],e)
            if e>.1:fail('controlled wheel angular balance')
            if locked and abs(f_long)*dt>max(0,budget-abs(previous)*.9/dt)*dt/.3+.0001:fail('locked contact exceeds remaining brake budget')
            if contact:
                pv=add(old[3:6],cross(old[10:13],radius));pv[1]=0;speed=dot(pv,long);magnitude=norm(pv)
                expected_slip=abs(previous*.3-speed)/max(.001,abs(speed))
                expected_lateral=0 if magnitude<.001 else math.acos(max(0,min(1,abs(speed)/magnitude)))
                if abs(slip-expected_slip)>.002 or abs(lateral-expected_lateral)>.002:fail('controlled tire slip definition')
        if not step:
            if abs(v[1]-(3 if kind==7 else .875475))>.00001:fail('wrong initial controls height')
            continue
        external=(0,0 if kind==7 else -981*dt,0)
        errors=[norm(add(scale([x-y for x,y in zip(v[3:6],old[3:6])],100),scale(add(linear,external),-1))),norm(add(scale([x-y for x,y in zip(v[10:13],old[10:13])],100),scale(torque,-1)))]
        worst[:2]=[max(x,y) for x,y in zip(worst[:2],errors)]
        if max(errors)>.1:fail('controlled chassis impulse balance')
    for rate in (60,120):
        weak=rows[0,rate,4*rate]
        if abs(weak[5]-(3-40/140))>.02:fail('weak braking failed analytic momentum coupling')
        for kind in (1,2):
            if norm(rows[kind,rate,4*rate][3:6])>.01:fail('service brakes failed to stop')
        if rows[3,rate,4*rate][5]>2.5:fail('rear handbrake failed to slow')
        left=rows[5,rate,4*rate];right=rows[4,rate,4*rate]
        if right[0]>-.2 or left[0]<.2 or abs(right[0]+left[0])>.03 or abs(right[2]-left[2])>.03:fail('steering direction or symmetry')
        for step in range(2*rate+1):
            v=rows[7,rate,step];t=step/rate
            if norm(v[3:6])>.0001 or abs(v[1]-3)>.0001:fail('free braking moved chassis')
            for i in range(4):
                if abs(v[15+11*i]-(10*(i+1)-t))>.002:fail('free brake angular velocity differs from analytic solution')
                angle=math.fmod(10*(i+1)*t-.5*(t*t-t/rate),2*math.pi)
                if abs(math.atan2(math.sin(v[16+11*i]-angle),math.cos(v[16+11*i]-angle)))>.002:fail('free brake rotation differs from analytic solution')
    return dict(zip(('linear_impulse','angular_impulse','wheel_impulse'),worst))

def contact_velocity(rows,key,index):
    kind,rate,step=key;v=rows[key];old=rows[kind,rate,step-1]
    turn=v[22+11*index];q=(0,math.sin(turn/2),0,math.cos(turn/2))
    right=rotate(old[6:10],rotate(q,(-1,0,0)));long=cross((0,1,0),right);long=scale(long,1/norm(long));lat=cross(long,(0,1,0))
    radius=rotate(old[6:10],((-.6,.6)[index//2],-v[13+11*index]-.3,(-1,1)[index%2]))
    velocity=add(old[3:6],cross(old[10:13],radius));velocity[1]=0
    speed=dot(velocity,long)
    return old[15+11*index]*.3-speed,dot(velocity,lat),abs(speed),norm(velocity)

def compare(a,b):
    worst=[0.]*6;rolling=[0,0];low_speed=[0,0];eligible=set();worst_slip_velocity=0.0
    for key in KEYS:
        x,y=a[key],b[key]
        errors=[max(abs(p-q) for p,q in zip(x[:3],y[:3])),max(abs(p-q) for p,q in zip(x[3:6],y[3:6])),rotation_error(x[6:10],y[6:10]),max(abs(p-q) for p,q in zip(x[10:13],y[10:13])),max(abs(x[15+11*i]-y[15+11*i]) for i in range(4)),max(abs(math.atan2(math.sin(x[16+11*i]-y[16+11*i]),math.cos(x[16+11*i]-y[16+11*i]))) for i in range(4))]
        if any(e>t for e,t in zip(errors,(.05,.1,.02,.15,.25,.1))):fail(f'controlled wheel trajectory differs {key}: {errors}')
        for i in range(4):
            if abs(x[13+11*i]-y[13+11*i])>.02 or abs(x[22+11*i]-y[22+11*i])>.00001:fail('controlled wheel geometry differs')
            if key[2]>0 and x[21+11*i]==y[21+11*i]==1:
                first=contact_velocity(a,key,i);second=contact_velocity(b,key,i)
                velocity_error=max(abs(first[j]-second[j]) for j in (0,1));worst_slip_velocity=max(worst_slip_velocity,velocity_error)
                if velocity_error>TOLERANCES['velocity']:fail(f'tire slip velocity differs {key}')
                for j,c in enumerate((17,18)):
                    if min(first[j+2],second[j+2])>TOLERANCES['velocity']:
                        rolling[j]+=1;eligible.add((key,i,c))
                        if min(x[c+11*i],y[c+11*i])>.1 and abs(x[c+11*i]-y[c+11*i])>.05:fail(f'large rolling tire slip differs {key}')
                    else:low_speed[j]+=1
        worst=[max(p,q) for p,q in zip(worst,errors)]
    for kind,seconds in DURATION.items():
        for rate in (60,120):
            for start,end in ((0,.5),(.5,1),(1,2),(2,3),(3,seconds)):
                if start>=seconds:continue
                steps=range(math.ceil(start*rate),math.floor(min(end,seconds)*rate)+1)
                for i in range(4):
                    for c in (17,18):
                        paired=[s for s in steps if ((kind,rate,s),i,c) in eligible]
                        first=[a[kind,rate,s][c+11*i] for s in paired]
                        second=[b[kind,rate,s][c+11*i] for s in paired]
                        if first and second and abs(sum(first)/len(first)-sum(second)/len(second))>.02:fail(f'controlled mean slip differs {(kind,rate,start,i,c)}')
    if min(rolling)==0:fail('no meaningful rolling slip observations')
    return dict(trajectory=worst,slip_velocity=worst_slip_velocity,rolling_slip_samples=rolling,low_speed_samples=low_speed,conditioning_speed=TOLERANCES['velocity'])

def self_test(raw,rows):
    def reject(action):
        try:action()
        except (ValueError,OverflowError):return
        fail('corrupt controls witness accepted')
    lines=raw.splitlines();reject(lambda:parse('\n'.join(lines[1:])));reject(lambda:parse(raw+'\n'+lines[0]))
    f=lines[0].split();f[4]='nan';reject(lambda:parse(' '.join(f)+'\n'+'\n'.join(lines[1:])))
    for index in range(57):
        altered=dict(rows);v=list(altered[4,60,60]);v[index]+=1000 if index in [13+11*i+c for i in range(4) for c in (1,6,7)] else 1;altered[4,60,60]=tuple(v)
        def check():qualify(altered);compare(altered,rows)
        reject(check)
    return 60

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from group root: {GROUP}')
    source,digest=verified_source(args.archive);record=dict(schema=1,fixture='wheel-controls-v1',oracle_revision=REFERENCE,archive_sha256=digest,tolerances=TOLERANCES,iterations=[12,4],workers=1,jolt_brake_torque='inferred from rotor balance',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'VehicleControlsOracle.cpp','vehicle-controls-oracle');binary=build_silex(mode,'VehicleControls.sx','vehicle-controls-silex',True)
        rows={};evidence={}
        for name,exe in (('silex',binary),('jolt',oracle)):
            raw=checked([str(exe)]);(BUILD/f'vehicle-controls-{name}-{mode.lower()}.txt').write_text(raw);rows[name]=parse(raw)
            evidence[name]=dict(observations=len(rows[name]),balances=qualify(rows[name]),guards=self_test(raw,rows[name]),sha256=hashlib.sha256(raw.encode()).hexdigest())
        evidence['parity']=compare(rows['silex'],rows['jolt']);record['modes'][mode]=evidence
        (BUILD/'vehicle-controls-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(mode,'wheel controls qualification green',flush=True)
if __name__=='__main__':main()
