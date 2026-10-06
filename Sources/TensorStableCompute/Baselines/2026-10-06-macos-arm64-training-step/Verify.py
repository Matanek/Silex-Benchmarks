from pathlib import Path
import json,hashlib,re,csv,statistics
p=Path(__file__).resolve().parent
for f,h in json.loads((p/'Checksums.json').read_text()).items():assert hashlib.sha256((p/f).read_bytes()).hexdigest()==h,f
config=json.loads((p/'Config.json').read_text());rows=json.loads((p/'Samples.json').read_text());assert len(rows)==192
pattern=re.compile(r'TRAINING_PLAN_MEASURE status=pass case=(\d+) planned=(true|false) iterations=(\d+) elapsed_ms=([\d.eE+-]+) preparation_ms=([\d.eE+-]+) passes=(\d+) observations=(\d+)')
for case in range(3):
 for series,n in [('AB',16),('AA-eager',8),('AA-grouped',8)]:
  selected=[r for r in rows if r['case']==case and r['series']==series];assert len(selected)==2*n
  for pair in range(n):assert {r['arm'] for r in selected if r['pair']==pair}=={'A','B'}
values={}
for r in rows:
 text=(p/r['log']).read_text();m=pattern.search(text);assert m
 c,g,n,t,cold,passes,obs=m.groups()
 assert int(c)==r['case'] and (g=='true')==r['planned'] and int(n)==r['iterations'] and float(t)==r['elapsed_ms'] and float(cold)==r['preparation_ms']
 assert int(passes)==r['passes']==int(n)*(147 if int(c)==2 else 84) and int(obs)==r['observations']
 assert int(n)==[128,64,64][int(c)] and int(obs)==[93,3361,129][int(c)]
 observed=[line for line in text.splitlines() if line.startswith('TRAINING_VALUE ')];assert len(observed)==int(obs)
 if c in values:assert observed==values[c]
 else:values[c]=observed
 rss=int(re.search(r'(\d+)\s+maximum resident set size',(p/r['log'].replace('.log','.time')).read_text()).group(1));assert rss==r['maximum_resident_bytes']
with (p/'Samples.csv').open(newline='') as f:csv_rows=list(csv.DictReader(f))
assert csv_rows==[{k:str(v) for k,v in r.items()} for r in rows]
def paired(case,series):
    selected=[r for r in rows if r['case']==case and r['series']==series]
    deltas=[]
    for pair in sorted({r['pair'] for r in selected}):
        values={r['arm']:r['elapsed_ms'] for r in selected if r['pair']==pair}
        deltas.append(100*(values['B']/values['A']-1))
    median=statistics.median(deltas);mad=statistics.median(abs(d-median) for d in deltas)
    return dict(median_percent=median,mad_percent=mad,favourable=sum(d<0 for d in deltas),deltas_percent=deltas,
                a_median_ms=statistics.median(r['elapsed_ms'] for r in selected if r['arm']=='A'),b_median_ms=statistics.median(r['elapsed_ms'] for r in selected if r['arm']=='B'))
results=[]
for case in range(3):
    ab=paired(case,'AB');aa=[paired(case,s) for s in ('AA-eager','AA-grouped')]
    valid=all(not(abs(r['median_percent'])>=5 and abs(r['median_percent'])>3*r['mad_percent']) for r in aa)
    signal=valid and ab['median_percent']<=-5 and -ab['median_percent']>3*ab['mad_percent'] and ab['favourable']>=14
    results.append(dict(case=case,local_signal='gain' if signal else 'regression' if valid and ab['median_percent']>=5 and ab['median_percent']>3*ab['mad_percent'] and ab['favourable']<=2 else 'indeterminate',identical_controls_valid=valid,ab=ab,aa=aa))
summary=dict(status='pass',samples=len(rows),observations=sum(r['observations'] for r in rows),results=results,scope=config['scope'])
assert json.loads(json.dumps(summary))==json.loads((p/'Summary.json').read_text())
manifest=json.loads((p/'Candidate-Source.json').read_text());proof=json.loads((p/'Tensor-Qualification.json').read_text())
assert proof['compiler_sha256']==config['compiler_sha256']==manifest['compiler_sha256']
assert all(r['status']=='pass' for r in proof['results']) and len(proof['results'])>=112
for name,item in manifest['snapshots'].items():
 assert hashlib.sha256((p/item['file']).read_bytes()).hexdigest()==item['sha256']
 if name in config['source_sha256']:assert item['sha256']==config['source_sha256'][name]
 assert proof['fingerprints']['Packages/Tensor/'+name]==item['sha256']
assert hashlib.sha256((p/'Source.sx.txt').read_bytes()).hexdigest()==config['benchmark_sha256']
diagnostics=json.loads((p/'Diagnostics.json').read_text());assert len(diagnostics)==57 and all(r['rejection_observed'] for r in diagnostics)
composition_proof=json.loads((p/'Composition.json').read_text())
for name,item in manifest['snapshots'].items():assert composition_proof['fingerprints']['Packages/Tensor/'+name]==item['sha256']
composition=composition_proof['results'];assert len(composition)==6 and all(r['status']=='pass' and r['compiler_sha256']==config['compiler_sha256'] for r in composition)
for mode in ['Debug','Release']:
 text=(p/f'Qualification-{mode}.log').read_text()
 for marker in ['TRAINING_PLAN_GUARDS status=pass','TRAINING_STEP_GRAPH_GUARDS status=pass','TRAINING_STEP_NONFINITE status=pass','TRAINING_STEP_RESOURCES status=pass']:assert marker in text
 assert text.count('TRAINING_PLAN_REPLAY status=pass')==2 and text.count('TRAINING_PLAN_PROBE_STATE status=pass')==2
assert summary['observations']==229312 and summary['results'][0]['local_signal']=='gain' and summary['results'][1]['local_signal']=='regression' and summary['results'][2]['local_signal']=='gain'
print('VERIFIED raw logs, complete GPU state, CPU oracle, admission, regression, source snapshots, corpus and six linked targets')
