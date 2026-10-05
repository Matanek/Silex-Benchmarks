from pathlib import Path
import os,subprocess,json,hashlib
w=Path.cwd();a=w.parent/'Memory/Artifacts';current=w/'Silex/Toolchain/zig-out/bin/silex';before=a/'Silex-Before-Constructor-Dependencies';env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(w/'.silex/zig-global'))
results=[];source='Silex-Benchmarks/Sources/TensorStableCompute/ResidentSteps.sx'
for label,cli,mode in [('After-Debug',current,'debug'),('After-Release',current,'release'),('Before-Release',before,'release')]:
 binary=a/('ResidentSteps-'+label)
 x=subprocess.run([str(cli),'compile',source,'--'+mode,'--output',str(binary)],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
 (a/('ResidentSteps-'+label+'-Build.log')).write_text(x.stdout)
 if x.returncode:raise SystemExit(x.stdout)
 x=subprocess.run([str(binary),'--verify'],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
 (a/('ResidentSteps-'+label+'-Verify.log')).write_text(x.stdout)
 ok=x.returncode==0 and 'SILEX_TENSOR_RESIDENT_VERIFY status=pass families=6 full_state=pass' in x.stdout
 results.append(dict(label=label,status='pass' if ok else 'fail',exit_code=x.returncode,compiler_sha256=hashlib.sha256(cli.read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),source_sha256=hashlib.sha256((w/source).read_bytes()).hexdigest()))
 (a/'ResidentSteps-Qualification-Summary.json').write_text(json.dumps(results,indent=2)+'\n')
 print(label,'PASS' if ok else 'FAIL',flush=True)
 if not ok:raise SystemExit(x.stdout)
print('VERIFIED six models full CPU/Metal states, Debug/Release and baseline compiler',flush=True)
