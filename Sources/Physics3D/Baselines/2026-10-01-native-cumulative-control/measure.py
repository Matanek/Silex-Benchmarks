from pathlib import Path
import subprocess,hashlib,json,statistics
root=Path.cwd();out=root/'.silex/native-qualified-controls';out.mkdir(exist_ok=True)
binaries={'original':'levers-AquariumFill-candidate','qualified':'deferred-boundary-aquarium','llvm':'levers-aquarium-llvm'}
runs=[];reference=None
for kind in ['llvm','original','qualified','qualified','original','llvm']:
 binary=root/'.silex'/binaries[kind];name=f'{len(runs)+1:02d}-{kind}.csv'
 with (out/name).open('w') as stream:
  p=subprocess.Popen(['taskpolicy','-a',str(binary)],stdout=stream)
  subprocess.run(['taskpolicy','-B','-p',str(p.pid)],check=True)
  status=p.wait()
 assert status==0,(name,status)
 rows=[line.split(',') for line in (out/name).read_text().splitlines()]
 observable=[r[:1]+r[2:14]+r[15:] for r in rows]
 if kind!='llvm':
  if reference is None:reference=observable
  assert observable==reference,('Native observable mismatch',name)
 run=dict(kind=kind,log=name,mean_ms=statistics.mean(float(r[14]) for r in rows),late_ms=statistics.mean(float(r[14]) for r in rows[-10:]),exit=status,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
 runs.append(run);(out/'runs.json').write_text(json.dumps(runs,indent=2)+'\n');print(json.dumps(run),flush=True)
