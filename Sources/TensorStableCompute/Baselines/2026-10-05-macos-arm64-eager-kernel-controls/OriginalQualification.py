from pathlib import Path
import subprocess,os,json,hashlib
root=Path.cwd();a=root.parent/'Memory/Artifacts';cli=root/'Silex/Toolchain/zig-out/bin/silex';probe=root/'Packages/Tensor/Module/@EagerKernel.sx'
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(root/'.silex/zig-global'))
try:
 for mode in ['Debug','Release']:
  binary=a/('EagerKernel-'+mode)
  args=[str(cli),'compile','Packages/Tensor/Module/@EagerKernel.sx','--'+mode.lower(),'--output',str(binary)]
  result=subprocess.run(args,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
  (a/('EagerKernel-'+mode+'-Build.log')).write_text(result.stdout)
  if result.returncode:raise SystemExit(result.stdout)
  result=subprocess.run([str(binary),'--verify'],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
  (a/('EagerKernel-'+mode+'-Verify.log')).write_text(result.stdout)
  if result.returncode or 'SILEX_TENSOR_KERNEL_VERIFY status=pass' not in result.stdout:raise SystemExit(result.stdout)
  print(mode,'VERIFIED',flush=True)
finally:
 probe.unlink()
 print('Temporary owning-namespace probe removed; original production Module restored',flush=True)
config=json.loads((a/'EagerResources-Campaign/Configuration.json').read_text())
for f,h in config['fingerprints'].items():assert hashlib.sha256((root/f).read_bytes()).hexdigest()==h,f
assert subprocess.check_output(['git','status','--porcelain'],cwd=root/'Packages/Tensor',text=True)==''
