#!/usr/bin/env python3
"""Qualify powered wheels against the pinned, real Jolt controller."""
import argparse,hashlib,json,math,struct
from collections import defaultdict
from pathlib import Path
from Run import BUILD,GROUP,HERE,REFERENCE,build_oracle,build_silex,checked,fail,verified_source
from LoadedSwingTwistRun import rotate
from VehicleTiresRun import cross,dot,add,scale,norm,curve
DURATION={k:2 if k<3 or k in (6,7) else 8 if k in (8,9) else 5 for k in range(11)}
KEYS={(k,r,s) for k,d in DURATION.items() for r in (60,120) for s in range(r*d+1)}
TOLERANCES=dict(position=.05,velocity=.1,rotation=.02,angular_velocity=.15,wheel_speed=.25,wheel_angle=.1,rpm=5,clutch=.0001,slip=.05,slip_phase_mean=.02,slip_definition=.002,slip_velocity=.1,conditioning_speed=.1,impulse_balance=.1,discrete_steps=1)
TOLERANCES["angle_conditioning_speed"]=math.sqrt(2)*TOLERANCES["velocity"]/math.sin(TOLERANCES["slip"])
CONVERSION=60/(2*math.pi)

def inputs(kind,time):
    throttle=.5 if kind==10 else .7 if kind==5 else 1
    steering=.2 if kind==5 and 1<=time<3 or kind==10 and .5<=time<2.5 else 0
    brake=0
    if (3<=kind<=5 or kind==10) and time>=3 or kind==8 and time>=4 or kind==9 and time>=6:throttle=0;brake=1
    elif kind==9 and time>=3:throttle=-1
    return throttle,steering,brake

def parse(raw):
    rows={}
    for line in raw.splitlines():
        f=line.split()
        if len(f)!=62 or f[0]!='powertrain':fail('invalid powertrain row')
        key=tuple(map(int,f[1:4]));v=tuple(map(float,f[4:]))
        if key not in KEYS or key in rows or not all(map(math.isfinite,v)):fail('invalid powertrain key or value')
        rows[key]=v
    if set(rows)!=KEYS:fail('incomplete powertrain witness')
    return rows

def dense_solve(a,b):
    n=len(b);a=[list(row)+[value] for row,value in zip(a,b)]
    for i in range(n):
        pivot=max(range(i,n),key=lambda j:abs(a[j][i]));a[i],a[pivot]=a[pivot],a[i]
        divisor=a[i][i]
        if abs(divisor)<1e-15:fail('singular powertrain witness')
        a[i]=[x/divisor for x in a[i]]
        for j in range(n):
            if i!=j:
                factor=a[j][i];a[j]=[x-factor*y for x,y in zip(a[j],a[i])]
    return [row[-1] for row in a]

def distribution(kind,old):
    ratios=[3.,3.,3.,3.];fractions=[.25]*4
    if kind not in (6,7):return ratios,fractions
    ratios=[3.,2.,3.,2.];fractions=[.35,.225,.35,.075]
    if kind==7:return ratios,fractions
    speeds=[old[15+10*i] for i in range(4)]
    differentials=[(1,3,2.,.3,.25),(0,2,3.,.7,.5)]
    omegas=[abs((speeds[l]+speeds[r])*ratio/2) for l,r,ratio,share,split in differentials]
    low=min(omegas);high=max(omegas);alpha=min(1,(max(.001,high)/max(.001,low)-1)/.4)
    factors=[0 if high==low else (high-w)/(high-low) for w in omegas];total=sum(factors)
    for j,(l,r,ratio,share,split) in enumerate(differentials):
        if total:share=share*(1-alpha)+alpha*factors[j]/total
        a=max(.001,abs(speeds[l]));b=max(.001,abs(speeds[r]));weight=min(1,(max(a,b)/min(a,b)-1)/.4)
        right=split*(1-weight)+(weight if a>=b else 0)
        fractions[l]=share*(1-right);fractions[r]=share*right
    return ratios,fractions

def expected_rotors(kind,rate,step,old,current):
    dt=1/rate;throttle,steering,brake=inputs(kind,(step-1)/rate)
    ratios,fractions=distribution(kind,old);ratios=[x*(1 if old[54]==1 else .5 if old[54]==2 else -1 if old[54]==-1 else 0) for x in ratios]
    strength=old[55]*10 if old[54] else 0
    a=[[float(i==j) for j in range(5)] for i in range(5)];b=[0.]*5;estimates=[]
    for i in range(4):
        omega=old[15+10*i];sign=-1 if omega<0 or omega==0 and old[54]<0 else 1
        impulse=sign*1500*brake*dt
        if current[21+10*i]:impulse+=old[19+10*i]*dt*.3
        estimates.append(impulse)
        for j in range(4):a[i][j]+=dt*strength*ratios[i]*fractions[i]*ratios[j]/(4*.9)
        a[i][4]=-dt*strength*ratios[i]*fractions[i]/.9
        b[i]=omega-impulse/.9;a[4][i]=-dt*strength*ratios[i]/(4*.5)
    a[4][4]+=dt*strength/.5
    expected_torque=12*abs(throttle)*(old[55] if kind in (8,9) else 1)
    if abs(current[57]-expected_torque)>.0001:fail('engine torque does not follow input and prior clutch')
    b[4]=old[53]/CONVERSION+dt*expected_torque/.5
    result=dense_solve(a,b);error=abs(current[53]/CONVERSION-max(0,min(6000/CONVERSION,result[4])))*.5
    for i in range(4):
        before=result[i]+estimates[i]/.9
        locked=1500*brake>abs(before)*.9/dt
        expected=0 if locked else math.copysign(max(0,abs(before)-1500*brake*dt/.9),before)-current[19+10*i]*dt*.3/.9
        error=max(error,.9*abs(current[15+10*i]-expected))
    if error>.1:fail('powertrain dense coupling / braking / rotor impulse residual')
    return error

def f32(value):return struct.unpack("f",struct.pack("f",value))[0]

def transmission(state,dt,rpm,input,can_shift):
    dt=f32(dt)
    gear,clutch,switch,release,latency=state;old=gear
    if gear==0 or input*gear<0:gear=1 if input>0 else -1 if input<0 else 0
    elif latency==0:
        if can_shift and rpm>100:gear=min(2,gear+1) if gear>0 else max(-1,gear-1)
        elif rpm<50:gear=max(1 if input else 0,gear-1) if gear>0 else min(-1 if input else 0,gear+1)
    if old!=gear:switch=.5 if old else 0;release=f32(.3);latency=.5;clutch=0
    elif switch>0:switch=max(0,f32(switch-dt));clutch=0
    elif release>0:release=max(0,f32(release-dt));clutch=f32(1-f32(release/f32(.3)))
    else:clutch=1;latency=max(0,f32(latency-dt))
    return gear,clutch,switch,release,latency

def qualify(rows):
    worst=[0.,0.,0.];states={};seen=defaultdict(set)
    for (kind,rate,step),v in sorted(rows.items()):
        air=kind<3 or kind in (6,7);dt=1/rate;old=rows.get((kind,rate,step-1));linear=[0.]*3;angular=[0.]*3
        if abs(dot(v[6:10],v[6:10])-1)>.0001 or v[1]<.5 or norm(v[:3])>40 or norm(v[3:6])>10 or norm(v[10:13])>5:fail('unbounded powered chassis')
        if not 0<=v[53]<=6000.001 or v[54] not in (-1,0,1,2) or not 0<=v[55]<=1.000001 or v[56] not in (0,1) or not 0<=v[57]<=12.00001:fail('invalid engine or transmission state')
        seen[kind,rate].add(v[54]);throttle,steering,brake=inputs(kind,(step-1)/rate) if step else (0,0,0)
        for i,(x,z) in enumerate(((-.6,-1),(-.6,1),(.6,-1),(.6,1))):
            length,n,omega,angle,slip,lateral,fl,ft,contact,turn=v[13+10*i:23+10*i]
            if not 0<=length<=.60001 or not 0<=n<10000 or abs(omega)>100 or abs(angle)>2*math.pi+.0001 or slip<0 or not 0<=lateral<=math.pi/2+.0001 or contact not in (0,1):fail('invalid powered wheel state')
            if abs(turn-(-steering*.5 if z>0 else 0))>.00001:fail('powered steering differs')
            if abs(fl)>math.sqrt(curve(slip))*n+.05 or abs(ft)>math.sqrt(curve(lateral,True))*n+.05:fail('powered tire exceeds friction')
            if not contact and (n!=0 or fl!=0 or ft!=0 or abs(length-.6)>.00001):fail('unsupported powered tire applied force')
            if not step:
                expected=(3,21,9,37)[i] if kind in (6,7) else 15 if kind==10 else 0
                if abs(omega-expected)>.00001 or angle!=0:fail('wrong initial powered wheel state')
                continue
            q=(0,math.sin(turn/2),0,math.cos(turn/2));right=rotate(old[6:10],rotate(q,(-1,0,0)))
            long=cross((0,1,0),right);long=scale(long,1/norm(long));lat=cross(long,(0,1,0));radius=rotate(old[6:10],(x,-length-.3,z))
            force=add(add((0,n,0),scale(long,fl)),scale(lat,ft));linear=add(linear,scale(force,dt));angular=add(angular,scale(cross(radius,force),dt))
            change=angle-old[16+10*i]-old[15+10*i]*dt
            if abs(math.atan2(math.sin(change),math.cos(change)))>.0001:fail('powered angle did not advance once before torque')
            if contact:
                velocity=add(old[3:6],cross(old[10:13],radius));velocity[1]=0;speed=dot(velocity,long);magnitude=norm(velocity)
                if abs(slip-abs(old[15+10*i]*.3-speed)/max(.001,abs(speed)))>.002 or abs(lateral-(0 if magnitude<.001 else math.acos(max(0,min(1,abs(speed)/magnitude)))))>.002:fail('powered slip definition differs')
        if not step:
            gear=0 if kind in (8,9) or kind==1 else -1 if kind==4 else 1;clutch=0 if kind==2 else 1
            if v[53:]!=(0.,gear,clutch,0.,0.) or abs(v[1]-(3 if air else .875475))>.00001:fail('wrong initial powertrain')
            states[kind,rate]=(gear,clutch,0.,0.,0.);continue
        external=(0,0 if air else -981*dt,0)
        errors=[norm(add(scale([x-y for x,y in zip(v[3:6],old[3:6])],100),scale(add(linear,external),-1))),norm(add(scale([x-y for x,y in zip(v[10:13],old[10:13])],100),scale(angular,-1))),expected_rotors(kind,rate,step,old,v)]
        worst=[max(x,y) for x,y in zip(worst,errors)]
        if max(errors)>.1:fail('powered chassis impulse balance')
        if kind in (8,9):
            slipping=any(not v[21+10*i] or v[17+10*i]>.1 for i in range(4))
            states[kind,rate]=transmission(states[kind,rate],dt,v[53],throttle,not slipping and v[53]>=old[53])
            gear,clutch,switch,release,latency=states[kind,rate]
            if v[54]!=gear or abs(v[55]-clutch)>.0001 or v[56]!=int(switch>0):fail('automatic state machine differs')
        elif v[54]!=old[54] or v[55]!=old[55] or v[56]!=0:fail('manual transmission changed without input')
        if kind in (0,1,2):
            if kind==0:
                a=1/.5+9/(4*.9);difference=12/(.5*10*a)*(1-(1/(1+10*dt*a))**step)
                expected=(12*step*dt+4*.9/9*difference)/(.5+4*.9/9)
                if abs(v[53]/CONVERSION-expected)*.5>.1:fail('analytic free engine differs')
                if max(abs(v[15+10*i]-(expected-difference)/3)*.9 for i in range(4))>.1:fail('analytic free wheels differ')
            elif abs(v[53]/CONVERSION-24*step*dt)*.5>.1 or any(v[15+10*i]!=0 for i in range(4)):fail('disengaged engine is not isolated')
    for rate in (60,120):
        for kind in (3,4,5,8,9,10):
            if norm(rows[kind,rate,DURATION[kind]*rate][3:6])>.03:fail('powered vehicle failed to stop')
        if rows[3,rate,3*rate][2]<.1 or rows[4,rate,3*rate][2]>-.1:fail('powered forward/reverse travel missing')
        if 2 not in seen[8,rate] or -1 not in seen[9,rate]:fail('automatic shifting or reversal missing')
        if max(abs(rows[6,rate,2*rate][15+10*i]-rows[7,rate,2*rate][15+10*i]) for i in range(4))<.5:fail('limited slip distinction missing')
    return worst

def contact_velocity(rows,key,index):
    kind,rate,step=key;v=rows[key];old=rows[kind,rate,step-1];length=v[13+10*index];turn=v[22+10*index]
    x,z=((-0.6,-1),(-0.6,1),(0.6,-1),(0.6,1))[index];q=(0,math.sin(turn/2),0,math.cos(turn/2))
    long=cross((0,1,0),rotate(old[6:10],rotate(q,(-1,0,0))));long=scale(long,1/norm(long));lat=cross(long,(0,1,0))
    velocity=add(old[3:6],cross(old[10:13],rotate(old[6:10],(x,-length-.3,z))));velocity[1]=0
    return dot(velocity,long),dot(velocity,lat),norm(velocity)

def compare(a,b):
    worst=dict(position=0.,velocity=0.,rotation=0.,angular_velocity=0.,wheel_speed=0.,wheel_angle=0.,rpm=0.,clutch=0.,slip_velocity=0.)
    velocity_phases=defaultdict(lambda:[0.,0.,0]);all_velocity_max=0.0;velocity_low=0
    phases=defaultdict(lambda:[0.,0.,0]);counts=dict(ratio_conditioned=0,ratio_low_speed=0,angle_conditioned=0,angle_low_speed=0);discrete=0
    for key,v in a.items():
        other=b[key];kind,rate,step=key
        for name,left,right in [('position',v[:3],other[:3]),('velocity',v[3:6],other[3:6]),('angular_velocity',v[10:13],other[10:13])]:worst[name]=max(worst[name],max(abs(x-y) for x,y in zip(left,right)))
        worst['rotation']=max(worst['rotation'],min(max(abs(x-y) for x,y in zip(v[6:10],other[6:10])),max(abs(x+y) for x,y in zip(v[6:10],other[6:10]))))
        worst['rpm']=max(worst['rpm'],abs(v[53]-other[53]));worst['clutch']=max(worst['clutch'],abs(v[55]-other[55]))
        if v[54]!=other[54] or v[56]!=other[56]:
            discrete+=1
            if not any((kind,rate,j) in b and v[54]==b[kind,rate,j][54] and v[56]==b[kind,rate,j][56] for j in (step-1,step+1)):fail('powertrain discrete state differs beyond one step')
        for i in range(4):
            worst['wheel_speed']=max(worst['wheel_speed'],abs(v[15+10*i]-other[15+10*i]));change=v[16+10*i]-other[16+10*i]
            worst['wheel_angle']=max(worst['wheel_angle'],abs(math.atan2(math.sin(change),math.cos(change))))
            if step and v[21+10*i] and other[21+10*i]:
                av=contact_velocity(a,key,i);bv=contact_velocity(b,key,i)
                error=max(abs(av[0]-bv[0]),abs(av[1]-bv[1]));all_velocity_max=max(all_velocity_max,error)
                if min(av[2],bv[2])>TOLERANCES['conditioning_speed']:worst['slip_velocity']=max(worst['slip_velocity'],error)
                else:velocity_low+=1
                for component in (0,1):
                    entry=velocity_phases[kind,rate,i,component,int(step/rate)];entry[0]+=av[component];entry[1]+=bv[component];entry[2]+=1
                for channel,denominator in ((17,0),(18,2)):
                    label='ratio' if channel==17 else 'angle'
                    threshold=.1 if channel==17 else TOLERANCES['angle_conditioning_speed']
                    if min(abs(av[denominator]),abs(bv[denominator]))>threshold:
                        counts[label+'_conditioned']+=1;left=v[channel+10*i];right=other[channel+10*i]
                        if abs(left-right)>.05:fail('conditioned powered slip differs')
                        entry=phases[kind,rate,i,channel,int(step/rate)];entry[0]+=left;entry[1]+=right;entry[2]+=1
                    else:counts[label+'_low_speed']+=1
    for name,value in worst.items():
        if value>TOLERANCES[name]:fail(f'powertrain parity {name}: {value} > {TOLERANCES[name]}')
    if any(abs(x-y)/n>.02 for x,y,n in phases.values()):fail('conditioned powered slip phase differs')
    if any(abs(x-y)/n>TOLERANCES['slip_velocity'] for x,y,n in velocity_phases.values()):fail('powered contact velocity phase differs')
    if counts['angle_conditioned']==0:fail('no conditioned powered angle samples')
    return dict(maxima=worst,contact_velocity_all_samples_maximum=all_velocity_max,contact_velocity_low_speed_samples=velocity_low,contact_velocity_phase_maximum=max(abs(x-y)/n for x,y,n in velocity_phases.values()),slip_counts=counts,discrete_near_threshold=discrete)

def self_test(raw,rows):
    def reject(action):
        try:action()
        except (ValueError,OverflowError):return
        fail('corrupt powertrain witness accepted')
    lines=raw.splitlines();reject(lambda:parse('\n'.join(lines[1:])));reject(lambda:parse(raw+'\n'+lines[0]))
    f=lines[0].split();f[4]='nan';reject(lambda:parse(' '.join(f)+'\n'+'\n'.join(lines[1:])))
    for index in range(58):
        altered=dict(rows);v=list(altered[5,60,120]);v[index]+=1000;altered[5,60,120]=tuple(v)
        def check():qualify(altered);compare(altered,rows)
        reject(check)
    return 61

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path);parser.add_argument('--mode',choices=('Debug','Release','both'),default='both');args=parser.parse_args()
    if Path.cwd().resolve()!=GROUP:fail(f'run from group root: {GROUP}')
    source,digest=verified_source(args.archive);record=dict(schema=1,fixture='vehicle-powertrain-v2',oracle_revision=REFERENCE,archive_sha256=digest,tolerances=TOLERANCES,iterations=[12,4],workers=1,wheel_torques='not directly observed in Jolt; independent dense rotor residual and Silex consumer balances',modes={})
    for mode in ('Debug','Release') if args.mode=='both' else (args.mode,):
        oracle=build_oracle(source,mode,HERE/'VehiclePowertrainOracle.cpp','vehicle-powertrain-oracle');binary=build_silex(mode,'VehiclePowertrain.sx','vehicle-powertrain-silex',True)
        rows={};evidence={}
        for name,exe in (('silex',binary),('jolt',oracle)):
            raw=checked([str(exe)]);(BUILD/f'vehicle-powertrain-{name}-{mode.lower()}.txt').write_text(raw);rows[name]=parse(raw)
            evidence[name]=dict(observations=len(rows[name]),balances=qualify(rows[name]),guards=self_test(raw,rows[name]),sha256=hashlib.sha256(raw.encode()).hexdigest())
        evidence['parity']=compare(rows['silex'],rows['jolt']);record['modes'][mode]=evidence
        (BUILD/'vehicle-powertrain-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(mode,'vehicle powertrain qualification green',flush=True)
if __name__=='__main__':main()
