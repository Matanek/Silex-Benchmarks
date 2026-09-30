from pathlib import Path
import subprocess, statistics, json, hashlib
root=Path.cwd(); out=root/'.silex/native-gap-class-qualified'; out.mkdir(exist_ok=True)
runs=[]
for case,baseline,candidate,col in [('AquariumFill','native-gap-lse','native-gap-class-final',14),('ColumnPeak','native-gap-lse-column','native-gap-class-final-column',1)]:
 reference=None
 for kind in ['baseline','candidate','candidate','baseline','baseline','candidate','candidate','baseline']:
  binary=root/'.silex'/(baseline if kind=='baseline' else candidate)
  name=f'{len(runs)+1:02d}-{case}-{kind}.csv'
  with (out/name).open('w') as stream:
   p=subprocess.Popen(['taskpolicy','-a',str(binary)],stdout=stream)
   try: subprocess.run(['taskpolicy','-B','-p',str(p.pid)],check=True)
   finally: status=p.wait()
  assert status==0,(name,status)
  rows=[line.split(',') for line in (out/name).read_text().splitlines()]
  observable=[r[:1]+r[2:14]+r[15:] if col==14 else r[:1]+r[2:] for r in rows]
  if reference is None: reference=observable
  assert observable==reference,('observable mismatch',name)
  times=[float(r[col]) for r in rows]
  run=dict(case=case,kind=kind,log=name,mean_ms=statistics.mean(times),late_ms=statistics.mean(times[-10:]),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
  runs.append(run); print(json.dumps(run),flush=True)
  (out/'runs.json').write_text(json.dumps(runs,indent=2)+'\n')
