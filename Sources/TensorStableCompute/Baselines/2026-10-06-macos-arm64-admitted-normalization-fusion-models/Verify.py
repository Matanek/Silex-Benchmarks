from pathlib import Path
import argparse,json,statistics as st,re,hashlib
args=argparse.Namespace(harness='models')
p=Path(__file__).resolve().parent
for f,h in json.loads((p/'Checksums.json').read_text()).items():assert hashlib.sha256((p/f).read_bytes()).hexdigest()==h,f
rows=json.loads((p/'Rows.json').read_text());runs=json.loads((p/'Runs.json').read_text());config=json.loads((p/'Configuration.json').read_text())
assert json.loads((p/'Verified.json').read_text())['unchanged']
assert len(runs)==(384 if args.harness=='micro' else 64) and len(rows)==384
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
for run in runs:
 assert run['exit_code']==0 and sha(p/(run['name']+'.log'))==run['stdout_sha256'] and sha(p/(run['name']+'.time'))==run['stderr_sha256']
def stats(v):
 m=st.median(v);return dict(median=m,mad=st.median([abs(x-m) for x in v]),minimum=min(v),maximum=max(v))
def key(r):return (r['case'],str(r['size'])) if args.harness=='micro' else (r['family'],)
keys=sorted({key(r) for r in rows})
def analysis(metric):
 cases=[]
 for k in keys:
  selected=[r for r in rows if key(r)==k]
  if metric not in selected[0]:continue
  def arm(group,variant,number=None):
   result=sorted([r for r in selected if r['group']==group and r['variant']==variant and (number is None or r['arm']==number)],key=lambda r:r['pair'])
   assert len(result)==(16 if group=='main' else 8)
   return [float(r[metric]) for r in result]
  before=arm('main','before');after=arm('main','after')
  delta=[100*(y/x-1) if x>0 else None for x,y in zip(before,after)];aa={}
  for variant in ['before','after']:
   x=arm('control',variant,0);y=arm('control',variant,1)
   dif=[100*(b/a-1) if a>0 else None for a,b in zip(x,y)]
   aa[variant]=dict(differences=dif,valid=False,reason='zero denominator') if None in dif else dict(differences=dif,**stats(dif),valid=not(abs(st.median(dif))>=5 and abs(st.median(dif))>3*stats(dif)['mad']))
  if None in delta:paired=dict(differences=delta);verdict='indeterminate'
  else:
   paired=dict(differences=delta,**stats(delta),negative=sum(d<0 for d in delta),positive=sum(d>0 for d in delta))
   signal=abs(paired['median'])>=5 and abs(paired['median'])>3*paired['mad'] and max(paired['negative'],paired['positive'])>=14
   verdict=('signal_decrease' if paired['median']<0 else 'signal_increase') if signal and all(c['valid'] for c in aa.values()) else 'indeterminate'
  cases.append(dict(case=k,before=stats(before),after=stats(after),paired=paired,controls=aa,verdict=verdict))
 return cases
rss={}
for variant in ['before','after']:
 values=[]
 for r in runs:
  if r['group']=='main' and r['variant']==variant:
   m=re.search(r'(\d+)\s+maximum resident set size',(p/(r['name']+'.time')).read_text());assert m;values.append(int(m[1]))
 assert len(values)==(96 if args.harness=='micro' else 16);rss[variant]=stats(values)
resources=[]
for k in keys:
 selected=[r for r in rows if key(r)==k and r['group']=='main']
 fields=[f for f in ['passes','submissions','allocations','reuses','releases','peak_bytes','peak_allocated_bytes','cached_bytes'] if f in selected[0]]
 if fields:resources.append(dict(case=k,**{v:{f:stats([int(r[f]) for r in selected if r['variant']==v]) for f in fields} for v in ['before','after']}))
summary=dict(harness=args.harness,cases=analysis('elapsed_ms'),cold_cases=analysis('cold_ms'),resources=resources,processes=len(runs),rows=len(rows),rss_process_bytes=rss,full_observations_checked=args.harness=='models',source_fingerprints=config['fingerprints'],compiler_sha256=config['compiler_sha256'],binary_sha256=config['binary_sha256'])
assert json.loads(json.dumps(summary))==json.loads((p/'Summary.json').read_text())
for metric in ['cases','cold_cases']:
 for r in summary[metric]:print(metric,'/'.join(r['case']),f"{r['before']['median']:.6f} -> {r['after']['median']:.6f} ms",r['verdict'],f"delta={r['paired'].get('median')} MAD={r['paired'].get('mad')}",['invalid A/A '+v for v,c in r['controls'].items() if not c['valid']])
print('RSS',rss,flush=True)

assert hashlib.sha256((p/"Source.sx.txt").read_bytes()).hexdigest()==config["fingerprints"]["Silex-Benchmarks/Sources/TensorStableCompute/ResidentSteps.sx"]
assert hashlib.sha256((p/"Protocol.md").read_bytes()).hexdigest()==config["protocol_sha256"]

import csv,math
with (p/'Measurements.csv').open(newline='') as stream:csv_rows=list(csv.DictReader(stream))
assert len(csv_rows)==len(rows)
for recorded,raw in zip(csv_rows,rows):assert recorded=={k:str(v) for k,v in raw.items()}
manifest=json.loads((p/'Binary-Qualification.json').read_text())
assert len(manifest['results'])==8 and all(r['status']=='pass' for r in manifest['results'])
assert config['compiler_sha256']['before']==config['compiler_sha256']['after']
for file in ['@Storage.sx','@Tensor.sx','@Neural.sx','@Autograd.sx','Elementwise.hlsl']:
 key='Packages/Tensor/Module/'+('Shaders/' if file=='Elementwise.hlsl' else '')+file
 assert hashlib.sha256((p/('Prototype-'+file+'.txt')).read_bytes()).hexdigest()==config['fingerprints'][key]==manifest['candidate_fingerprints'][key]
assert json.loads((p/'Targeted-Release-Qualification.json').read_text())['status']=='pass'
proof=json.loads((p/'Tensor-Qualification.json').read_text());assert len(proof['results'])==108 and sum(r['tests'] for r in proof['results'])==457 and all(r['status']=='pass' for r in proof['results'])
for file,h in config['fingerprints'].items():
 if file.startswith('Packages/Tensor/Module/'):assert h==proof['fingerprints'][file]
composition=json.loads((p/'Composition-Qualification.json').read_text());assert len(composition['results'])==6 and all(r['status']=='pass' for r in composition['results'])
for file,h in config['fingerprints'].items():
 if file.startswith('Packages/Tensor/Module/'):assert h==composition['fingerprints'][file]
providers=json.loads((p/'Provider-Artifacts.json').read_text());assert len(providers)==6 and all(r['status']=='pass' for r in providers)
assert json.loads((p/'Legacy-Normalization-Bias.json').read_text())['restored']

reference={};total=0
for run in runs:
 observations={}
 for line in (p/(run['name']+'.log')).read_text().splitlines():
  if line.startswith('SILEX_TENSOR_RESIDENT_VALUE '):
   r=dict(item.split('=',1) for item in line.split()[1:]);values=observations.setdefault(r['family'],[])
   assert int(r['index'])==len(values);value=float(r['value']);assert math.isfinite(value);values.append(value)
 for family,count in {'mlp':92,'cnn':116,'rnn':108,'gru':288,'lstm':372,'transformer':724}.items():
  values=observations[family];assert len(values)==count;total+=count;expected=reference.setdefault(family,values)
  assert all(abs(x-y)<=0.00002*(1+abs(y)) for x,y in zip(values,expected)),(run['name'],family)
assert total==108800
for family in ['mlp','cnn','rnn','gru','lstm','transformer']:
 before=[r for r in rows if r['family']==family and r['variant']=='before'];after=[r for r in rows if r['family']==family and r['variant']=='after']
 assert len(before)==len(after)==32
 assert all(int(y['passes'])==int(x['passes'])-(6 if family=='transformer' else 0) for x,y in zip(before,after))
print('VERIFIED 108800 full scalar observations')

print("VERIFIED normalization experiment: raw data, fixed admission, complete qualifications and source provenance")
