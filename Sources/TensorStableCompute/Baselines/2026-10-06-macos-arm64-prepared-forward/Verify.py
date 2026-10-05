from pathlib import Path
import csv,hashlib,json,re,statistics
p=Path(__file__).resolve().parent
for file,h in json.loads((p/'Checksums.json').read_text()).items():assert hashlib.sha256((p/file).read_bytes()).hexdigest()==h,file
config=json.loads((p/'Config.json').read_text());rows=json.loads((p/'Samples.json').read_text());out=p
assert len(rows)==256
pattern=re.compile(r'FORWARD_PLAN_MEASURE status=pass case=(\d+) planned=(true|false) profiled=(true|false) iterations=(\d+) elapsed_ms=([\d.eE+-]+) preparation_ms=([\d.eE+-]+) passes=(\d+) observations=(\d+)')
for case in range(4):
 for series,pairs in [('AB',16),('AA-A',8),('AA-B',8)]:
  selected=[r for r in rows if r['case']==case and r['series']==series]
  assert len(selected)==2*pairs
  for pair in range(pairs):assert {r['arm'] for r in selected if r['pair']==pair}=={'A','B'}
for row in rows:
 m=pattern.search((p/row['log']).read_text());assert m is not None,row['log']
 case,planned,profiled,n,t,cold,passes,observations=m.groups()
 assert int(case)==row['case'] and (planned=='true')==row['planned'] and (profiled=='true')==row['profiled']
 assert int(n)==row['iterations'] and float(t)==row['elapsed_ms'] and float(cold)==row['preparation_ms']
 assert int(passes)==row['passes']==int(n)*5 and int(observations)==row['observations']
 assert row['iterations']==[512,256,128,512][row['case']] and row['observations']==[4,128,512,4][row['case']]
with (p/'Samples.csv').open(newline='') as f: csv_rows=list(csv.DictReader(f))
assert len(csv_rows)==len(rows)
for recorded,raw in zip(csv_rows,rows):assert recorded=={k:str(v) for k,v in raw.items()}
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
for case in range(4):
    ab=paired(case,'AB');aa=[paired(case,s) for s in ('AA-A','AA-B')]
    valid=all(not(abs(r['median_percent'])>=5 and abs(r['median_percent'])>3*r['mad_percent']) for r in aa)
    signal=valid and ab['median_percent']<=-5 and -ab['median_percent']>3*ab['mad_percent'] and ab['favourable']>=14
    results.append(dict(case=case,kind='profile overhead' if case==3 else 'forward hot', local_signal=('gain' if signal else 'indeterminate') if case<3 else ('overhead' if valid and ab['median_percent']>=5 and ab['median_percent']>3*ab['mad_percent'] and ab['favourable']<=2 else 'indeterminate'),identical_controls_valid=valid,ab=ab,aa=aa))
summary=dict(status='pass',samples=len(rows),observations=sum(r['observations'] for r in rows),results=results,scope=config['scope'])
assert json.loads(json.dumps(summary))==json.loads((p/'Summary.json').read_text())
print(json.dumps(summary,indent=2),flush=True)

manifest=json.loads((p/'Candidate-Source.json').read_text());proof=json.loads((p/'Tensor-Qualification.json').read_text())
assert proof['compiler_sha256']==config['compiler_sha256']==manifest['compiler_sha256']
assert len(proof['results'])==110 and sum(r['tests'] for r in proof['results'])==464 and all(r['status']=='pass' for r in proof['results'])
assert hashlib.sha256((p/'Source.sx.txt').read_bytes()).hexdigest()==config['source_sha256']['Tests/Consumer/Qualification/ForwardPlanMeasure.sx']
for key,data in manifest['snapshots'].items():
 assert hashlib.sha256((p/data['file']).read_bytes()).hexdigest()==data['sha256']==config['source_sha256'][key]
 if key.startswith('Module/') or key=='Tests/Consumer/Tests/ForwardPlans.sx':assert proof['fingerprints']['Packages/Tensor/'+key]==data['sha256']
assert len(json.loads((p/'Diagnostics.json').read_text()))==3
composition=json.loads((p/'Composition.json').read_text())['results'];assert len(composition)==6 and all(r['status']=='pass' and r['compiler_sha256']==config['compiler_sha256'] for r in composition)
for mode in ['Debug','Release']:
 text=(p/f'Qualification-{mode}.log').read_text()
 for marker in ['PLAN_CLOSED_REJECTIONS status=pass','PLAN_CAPACITY status=pass','PLAN_GUARDS status=pass','PLAN_SHARED_VIEW status=pass','PLAN_NORMALIZATION status=pass','FORWARD_PLAN_RESOURCES status=pass']:assert marker in text
 assert text.count('PLAN_REPLAY status=pass')==2
 assert 'PLAN_ACTIVATIONS status=pass' in (p/f'Activations-{mode}.log').read_text()
assert summary['observations']==41472 and all(r['local_signal']=='gain' and r['identical_controls_valid'] for r in summary['results'][:3])
print('VERIFIED raw logs, paired admission, A/A controls, source snapshots, 464 tests and six linked targets')
