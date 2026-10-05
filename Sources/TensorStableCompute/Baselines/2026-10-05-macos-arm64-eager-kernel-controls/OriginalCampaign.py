from pathlib import Path
import subprocess,os,json,hashlib,re,csv,platform,math
root=Path.cwd();artifacts=root.parent/'Memory/Artifacts';out=artifacts/'EagerKernel-Campaign';out.mkdir(exist_ok=False)
binary=artifacts/'EagerKernel-Release';compiler=root/'Silex/Toolchain/zig-out/bin/silex'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(repo,*args):return subprocess.check_output(['git',*args],cwd=root/repo,text=True).strip()
repos=['Silex','Silex-Documentation','Packages/Tensor','Packages/STD','Packages/GFX','Packages/GFX.GPU','Silex-Benchmarks']
heads={r:git(r,'rev-parse','HEAD') for r in repos}
for r in repos:assert not git(r,'status','--porcelain'),r
assert heads['Packages/Tensor']=='d6cff047bb46bfc10eff7551fbf02c91d42cf503'
source=root/'Silex-Benchmarks/Sources/TensorStableCompute/EagerResources.sx'
fingerprints={str(p.relative_to(root)):sha(p) for p in (root/'Packages/Tensor/Module').rglob('*') if p.is_file()};fingerprints[str(source.relative_to(root))]=sha(source)
protocol=artifacts.parent/'Task19-Kernel-Control-Protocol.md'
configuration=dict(heads=heads,compiler_sha256=sha(compiler),binary_sha256=sha(binary),fingerprints=fingerprints,protocol_sha256=sha(protocol),platform=platform.platform(),architecture=platform.machine(),mode='Release',metric='synchronized wall milliseconds',probe_source_sha256=sha(artifacts/'EagerKernel-Probe.sx.txt'),warmup_metadata=16,warmup_commands=4,processes=32,primary_pairs=16,control_pairs=8,build_logs=['EagerKernel-Release-Build.log','EagerKernel-Release-Verify.log'])
for name,args in [('os',['/usr/bin/sw_vers']),('chip',['/usr/sbin/sysctl','-n','machdep.cpu.brand_string'])]:
 r=subprocess.run(args,text=True,capture_output=True);configuration[name]=dict(exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)
(out/'Configuration.json').write_text(json.dumps(configuration,indent=2)+'\n');rows=[];runs=[]
def run(group,index,reverse,pair=0):
 name=f'{group}-{index:02d}';args=[str(binary),'--measure']+(['--reverse'] if reverse else [])
 result=subprocess.run(['/usr/bin/time','-l',*args],text=True,capture_output=True,timeout=300)
 (out/(name+'.log')).write_text(result.stdout);(out/(name+'.time')).write_text(result.stderr)
 if result.returncode:raise SystemExit(f'{name} failed: {result.returncode}\n'+result.stdout+result.stderr)
 parsed=[]
 for line in result.stdout.splitlines():
  if line.startswith('SILEX_TENSOR_KERNEL '):
   row=dict(item.split('=',1) for item in line.split()[1:]);row.update(group=group,index=index,pair=pair,reverse=reverse)
   assert math.isfinite(float(row['elapsed_ms'])) and float(row['elapsed_ms'])>=0
   assert int(row['operations'])==64 and int(row['passes'])==64 and row['uploads']=='0' and row['downloads']=='0'
   parsed.append(row)
 assert len(parsed)==4
 assert len({(p['phase'],p['mode']) for p in parsed})==4
 rows.extend(parsed);runs.append(dict(name=name,args=args,exit_code=result.returncode,stdout_sha256=sha(out/(name+'.log')),stderr_sha256=sha(out/(name+'.time'))))
 (out/'Rows.json').write_text(json.dumps(rows,indent=2)+'\n');(out/'Runs.json').write_text(json.dumps(runs,indent=2)+'\n')
 print(name,'PASS',len(parsed),'rows',flush=True)
for i in range(1,17):run('main',i,i%2==0)
for pair in range(1,9):
 for arm in range(2):run('control',2*pair-1+arm,pair%2==0,pair)
for f,h in fingerprints.items():assert sha(root/f)==h,f
for r,h in heads.items():assert git(r,'rev-parse','HEAD')==h and not git(r,'status','--porcelain'),r
assert sha(binary)==configuration['binary_sha256'] and sha(compiler)==configuration['compiler_sha256'] and sha(protocol)==configuration['protocol_sha256']
assert len(rows)==128 and len(runs)==32
fields=sorted({k for r in rows for k in r})
with (out/'Measurements.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
print('VERIFIED 32 processes, 128 rows, unchanged exact sources and binaries',flush=True)
