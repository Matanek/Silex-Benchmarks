from pathlib import Path
import argparse, subprocess, os, json, hashlib, platform, math, csv

parser=argparse.ArgumentParser();parser.add_argument('harness',choices=['micro','models']);args=parser.parse_args()
w=Path.cwd();a=w.parent/'Memory/Artifacts';harness=args.harness
out=a/('Constructor-'+harness+'-Campaign');out.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(repo,*args):return subprocess.check_output(['git',*args],cwd=w/repo,text=True).strip()
repos=['Silex','Silex-Documentation','Packages/Tensor','Packages/STD','Packages/GFX','Packages/GFX.GPU','Silex-Benchmarks']
heads={r:git(r,'rev-parse','HEAD') for r in repos}
for r in repos:assert not git(r,'status','--porcelain'),r
compilers={'before':a/'Silex-Before-Constructor-Dependencies','after':w/'Silex/Toolchain/zig-out/bin/silex'}
if harness=='micro':
    binaries={'before':a/'EagerResources-Release','after':a/'EagerResources-After-Release'}
    source=w/'Silex-Benchmarks/Sources/TensorStableCompute/EagerResources.sx'
else:
    binaries={'before':a/'ResidentSteps-Before-Release','after':a/'ResidentSteps-After-Release'}
    source=w/'Silex-Benchmarks/Sources/TensorStableCompute/ResidentSteps.sx'
protocol=a.parent/('Task19-Constructor-Protocol.md' if harness=='micro' else 'Task19-Resident-Protocol.md')
fingerprints={str(p.relative_to(w)):sha(p) for p in (w/'Packages/Tensor/Module').rglob('*') if p.is_file()}
fingerprints[str(source.relative_to(w))]=sha(source)
configuration=dict(heads=heads,compiler_sha256={k:sha(p) for k,p in compilers.items()},binary_sha256={k:sha(p) for k,p in binaries.items()},fingerprints=fingerprints,protocol_sha256=sha(protocol),platform=platform.platform(),architecture=platform.machine(),mode='Release',metric='synchronized wall milliseconds',primary_pairs=16,control_pairs_per_binary=8,total_processes=64,harness=harness,observation_tolerance=0.00002,baseline_compiler_commit='9ba34c2415b1e1cd33bc9b3c69c16c3247d92957',after_compiler_commit=heads['Silex'])
if harness=='models':configuration.update(optimizer='AdamW',learning_rate=0.01,epsilon=0.0001,warmup_steps=2,timed_steps=3,observations_per_process=1700)
for name,command in [('os',['/usr/bin/sw_vers']),('chip',['/usr/sbin/sysctl','-n','machdep.cpu.brand_string'])]:
    x=subprocess.run(command,text=True,capture_output=True);configuration[name]=dict(exit_code=x.returncode,stdout=x.stdout,stderr=x.stderr)
(out/'Configuration.json').write_text(json.dumps(configuration,indent=2)+'\n')
rows=[];runs=[];reference={}
def parse(stdout):
    prefix='SILEX_TENSOR_RESOURCE ' if harness=='micro' else 'SILEX_TENSOR_RESIDENT '
    parsed=[dict(item.split('=',1) for item in line.split()[1:]) for line in stdout.splitlines() if line.startswith(prefix)]
    assert len(parsed)==(20 if harness=='micro' else 6)
    observations={}
    if harness=='models':
        for line in stdout.splitlines():
            if line.startswith('SILEX_TENSOR_RESIDENT_VALUE '):
                value=dict(item.split('=',1) for item in line.split()[1:]);family=value['family'];values=observations.setdefault(family,[])
                assert int(value['index'])==len(values);v=float(value['value']);assert math.isfinite(v);values.append(v)
    for r in parsed:
        assert math.isfinite(float(r['elapsed_ms'])) and float(r['elapsed_ms'])>=0
        if harness=='micro':
            size=int(r['size']);assert size in [1,256,4096,65536]
            if r['phase']=='resident':
                assert all(int(r[k])==64 for k in ['operations','allocations','submissions'])
                assert r['uploads']=='0' and r['downloads']=='0'
                assert int(r['peak_delta_bytes'])<=64*size*4
            else:assert int(r['operations'])==4096 and int(r['checksum'])==4096*size*4
        else:
            assert r['backend']=='gpu' and r['iterations']=='3' and r['uploads']=='0' and r['downloads']=='0'
            assert int(r['passes'])>0 and int(r['allocations'])>0
            family=r['family'];values=observations[family]
            cardinalities={'mlp':92,'cnn':116,'rnn':108,'gru':288,'lstm':372,'transformer':724}
            assert len(values)==int(r['observations'])==cardinalities[family] and math.isfinite(float(r['loss']))
            if family not in reference:reference[family]=dict(values=values,loss=float(r['loss']),passes=r['passes'],submissions=r['submissions'],allocations=r['allocations'])
            expected=reference[family]
            assert len(values)==len(expected['values']) and r['passes']==expected['passes'] and r['submissions']==expected['submissions'] and r['allocations']==expected['allocations']
            assert abs(float(r['loss'])-expected['loss'])<=0.00002
            assert all(abs(x-y)<=0.00002*(1+abs(y)) for x,y in zip(values,expected['values'])),family
    keys=[(r['phase'],r['mode'],r['size']) if harness=='micro' else r['family'] for r in parsed]
    assert len(set(keys))==len(parsed)
    return parsed
def run(group,pair,arm,variant,reverse):
    name=f'{group}-{pair:02d}-{arm}-{variant}';command=[str(binaries[variant]),'--measure']+(['--reverse'] if reverse else [])
    x=subprocess.run(['/usr/bin/time','-l',*command],text=True,capture_output=True,timeout=300)
    log=out/(name+'.log');timer=out/(name+'.time');log.write_text(x.stdout);timer.write_text(x.stderr)
    assert x.returncode==0,(name,x.returncode,x.stdout,x.stderr)
    parsed=parse(x.stdout)
    for r in parsed:r.update(group=group,pair=pair,arm=arm,variant=variant,reverse=reverse,run=name)
    rows.extend(parsed);runs.append(dict(name=name,args=command,group=group,pair=pair,arm=arm,variant=variant,reverse=reverse,exit_code=x.returncode,stdout_sha256=sha(log),stderr_sha256=sha(timer)))
    (out/'Rows.json').write_text(json.dumps(rows,indent=2)+'\n');(out/'Runs.json').write_text(json.dumps(runs,indent=2)+'\n')
    print(name,'PASS',len(parsed),'rows',flush=True)
for pair in range(1,17):
    order=['before','after'] if pair%2 else ['after','before']
    for arm,variant in enumerate(order):run('main',pair,arm,variant,pair%2==0)
for pair in range(1,9):
    order=['before','after'] if pair%2 else ['after','before']
    for variant in order:
        for arm in range(2):run('control',pair,arm,variant,pair%2==0)
for f,h in fingerprints.items():assert sha(w/f)==h,f
for r,h in heads.items():assert git(r,'rev-parse','HEAD')==h and not git(r,'status','--porcelain'),r
for k,p in binaries.items():assert sha(p)==configuration['binary_sha256'][k]
for k,p in compilers.items():assert sha(p)==configuration['compiler_sha256'][k]
assert sha(protocol)==configuration['protocol_sha256']
assert len(runs)==64 and len(rows)==64*(20 if harness=='micro' else 6)
fields=sorted({k for r in rows for k in r})
with (out/'Measurements.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)
(out/'Verified.json').write_text(json.dumps(dict(processes=len(runs),rows=len(rows),unchanged=True,full_observations_checked=harness=='models'),indent=2)+'\n')
print('VERIFIED',len(runs),'processes',len(rows),'rows, exact binaries and sources unchanged',flush=True)
