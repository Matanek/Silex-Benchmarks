from pathlib import Path
import json,hashlib,statistics as s,csv
p=Path(__file__).resolve().parent
checks=json.loads((p/'Checksums.json').read_text())
for name,h in checks.items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==h,name
config=json.loads((p/'Configuration.json').read_text());rows=json.loads((p/'Rows.json').read_text());runs=json.loads((p/'Runs.json').read_text())
assert len(rows)==128 and len(runs)==32
assert hashlib.sha256((p/'Probe.sx.txt').read_bytes()).hexdigest()==config['probe_source_sha256']
assert hashlib.sha256((p/'Protocol.md').read_bytes()).hexdigest()==config['protocol_sha256']
for run in runs:
 assert run['exit_code']==0
 for suffix,key in [('log','stdout_sha256'),('time','stderr_sha256')]:assert hashlib.sha256((p/(run['name']+'.'+suffix)).read_bytes()).hexdigest()==run[key]
assert len(list(csv.DictReader((p/'Measurements.csv').open())))==128
summary=json.loads((p/'Summary.json').read_text())
def select(group,arm):return [float(r['elapsed_ms']) for r in sorted(rows,key=lambda r:r['index']) if r['group']==group and (r['phase'],r['mode'])==tuple(arm)]
def medmad(v):
 m=s.median(v);return m,s.median(abs(x-m) for x in v)
def control(arm):
 v=select('control',arm);d=[100*(v[i+1]/v[i]-1) for i in range(0,16,2)];m,mad=medmad(d)
 return not(abs(m)>=5 and abs(m)>3*mad)
if isinstance(summary,list):
 cases=[(c,(c['phase'],'generate' if c['phase']=='metadata' else 'wait_each'),(c['phase'],'existing' if c['phase']=='metadata' else 'wait_final')) for c in summary]
else:cases=[(c,c['reference'],c['variation']) for c in summary['cases']]
for case,a,b in cases:
 l=select('main',a);r=select('main',b);assert len(l)==len(r)==16
 d=[100*(y/x-1) for x,y in zip(l,r)];m,mad=medmad(d)
 signal=abs(m)>=5 and abs(m)>3*mad and max(sum(x<0 for x in d),sum(x>0 for x in d))>=14 and control(a) and control(b)
 verdict=('signal_decrease' if m<0 else 'signal_increase') if signal else 'indeterminate'
 assert case['verdict']==verdict
 if 'paired' in case:assert case['paired']['median']==m and case['paired']['mad']==mad
 else:assert case['paired_median']==m and case['paired_mad']==mad
print('VERIFIED checksums, 32 runs, 128 rows and all statistical verdicts')
