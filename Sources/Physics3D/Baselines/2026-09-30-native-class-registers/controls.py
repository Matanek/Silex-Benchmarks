from pathlib import Path
import subprocess, statistics, json, hashlib
root=Path.cwd(); out=root/'.silex/native-gap-class-qualified'; runs=[]
reference=[r.split(',') for r in (out/'01-AquariumFill-baseline.csv').read_text().splitlines()]
reference=[r[:1]+r[2:14]+r[15:] for r in reference]
for name in ['llvm','original','candidate','candidate','original','llvm']:
 binary=root/'.silex'/dict(llvm='levers-aquarium-llvm',original='levers-AquariumFill-candidate',candidate='native-gap-class-final')[name]
 log=f'control-{len(runs)+1:02d}-{name}.csv'
 with (out/log).open('w') as stream:
  p=subprocess.Popen(['taskpolicy','-a',str(binary)],stdout=stream)
  try: subprocess.run(['taskpolicy','-B','-p',str(p.pid)],check=True)
  finally: status=p.wait()
 assert status==0,(log,status)
 rows=[r.split(',') for r in (out/log).read_text().splitlines()]
 assert [r[:1]+r[2:14]+r[15:] for r in rows]==reference,('observables',name)
 run=dict(kind=name,log=log,mean_ms=statistics.mean(float(r[14]) for r in rows),late_ms=statistics.mean(float(r[14]) for r in rows[-10:]),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
 runs.append(run);print(json.dumps(run),flush=True)
 (out/'controls.json').write_text(json.dumps(runs,indent=2)+'\n')
