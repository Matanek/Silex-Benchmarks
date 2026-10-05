from pathlib import Path
import subprocess,os,json,hashlib
w=Path.cwd();a=w.parent/'Memory/Artifacts';cli=w/'Silex/Toolchain/zig-out/bin/silex';source='Silex-Benchmarks/Sources/TensorStableCompute/EagerResources.sx'
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(w/'.silex/zig-global'));results=[]
before=json.loads((a/'EagerResources-Campaign/Configuration.json').read_text())
for f,h in before['fingerprints'].items():assert hashlib.sha256((w/f).read_bytes()).hexdigest()==h,f
assert hashlib.sha256((a/'EagerResources-Release').read_bytes()).hexdigest()==before['binary_sha256']
for label,mode in [('After-Debug','debug'),('After-Release','release')]:
    binary=a/('EagerResources-'+label)
    x=subprocess.run([str(cli),'compile',source,'--'+mode,'--output',str(binary)],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    (a/('EagerResources-'+label+'-Build.log')).write_text(x.stdout)
    if x.returncode:raise SystemExit(x.stdout)
    x=subprocess.run([str(binary),'--verify'],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    (a/('EagerResources-'+label+'-Verify.log')).write_text(x.stdout)
    ok=x.returncode==0 and 'SILEX_TENSOR_RESOURCE_VERIFY status=pass' in x.stdout
    results.append(dict(label=label,status='pass' if ok else 'fail',exit_code=x.returncode,compiler_sha256=hashlib.sha256(cli.read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),source_sha256=hashlib.sha256((w/source).read_bytes()).hexdigest()))
    (a/'EagerResources-Constructor-Qualification.json').write_text(json.dumps(results,indent=2)+'\n');print(label,'PASS' if ok else 'FAIL',flush=True)
    if not ok:raise SystemExit(x.stdout)
x=subprocess.run([str(a/'EagerResources-Release'),'--verify'],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
(a/'EagerResources-Before-Verify-Recheck.log').write_text(x.stdout)
assert x.returncode==0 and 'SILEX_TENSOR_RESOURCE_VERIFY status=pass' in x.stdout,x.stdout
print('VERIFIED identical micro source Debug/Release candidate and exact baseline binary',flush=True)
