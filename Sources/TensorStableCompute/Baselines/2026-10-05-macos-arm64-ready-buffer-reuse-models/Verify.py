from pathlib import Path
import argparse,json,statistics as st,re,hashlib
args=argparse.Namespace(harness='models')
p=Path(__file__).resolve().parent
for f,h in json.loads((p/'Checksums.json').read_text()).items():assert hashlib.sha256((p/f).read_bytes()).hexdigest()==h,f
rows=json.loads((p/'Rows.json').read_text());runs=json.loads((p/'Runs.json').read_text());config=json.loads((p/'Configuration.json').read_text())
assert json.loads((p/'Verified.json').read_text())['unchanged']
assert len(runs)==64 and len(rows)==(1280 if args.harness=='micro' else 384)
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
for run in runs:
 assert run['exit_code']==0 and sha(p/(run['name']+'.log'))==run['stdout_sha256'] and sha(p/(run['name']+'.time'))==run['stderr_sha256']
def stats(v):
 m=st.median(v);return dict(median=m,mad=st.median([abs(x-m) for x in v]),minimum=min(v),maximum=max(v))
def key(r):return (r['phase'],r['mode'],str(r['size'])) if args.harness=='micro' else (r['family'],)
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
 assert len(values)==16;rss[variant]=stats(values)
resources=[]
for k in keys:
 selected=[r for r in rows if key(r)==k and r['group']=='main']
 fields=[f for f in ['allocations','releases','peak_bytes','peak_delta_bytes'] if f in selected[0]]
 if fields:resources.append(dict(case=k,**{v:{f:stats([int(r[f]) for r in selected if r['variant']==v]) for f in fields} for v in ['before','after']}))
summary=dict(harness=args.harness,cases=analysis('elapsed_ms'),cold_cases=analysis('cold_ms'),resources=resources,processes=64,rows=len(rows),rss_process_bytes=rss,full_observations_checked=args.harness=='models',source_fingerprints=config['fingerprints'],compiler_sha256=config['compiler_sha256'],binary_sha256=config['binary_sha256'])
assert json.loads(json.dumps(summary))==json.loads((p/'Summary.json').read_text())
for metric in ['cases','cold_cases']:
 for r in summary[metric]:print(metric,'/'.join(r['case']),f"{r['before']['median']:.6f} -> {r['after']['median']:.6f} ms",r['verdict'],f"delta={r['paired'].get('median')} MAD={r['paired'].get('mad')}",['invalid A/A '+v for v,c in r['controls'].items() if not c['valid']])
print('RSS',rss,flush=True)

assert hashlib.sha256((p/"Source.sx.txt").read_bytes()).hexdigest()==config["fingerprints"]["Silex-Benchmarks/Sources/TensorStableCompute/ResidentSteps.sx"]
assert hashlib.sha256((p/"Protocol.md").read_bytes()).hexdigest()==config["protocol_sha256"]

reference={};total=0
for run in runs:
    observations={}
    for line in (p/(run['name']+'.log')).read_text().splitlines():
        if line.startswith('SILEX_TENSOR_RESIDENT_VALUE '):
            r=dict(item.split('=',1) for item in line.split()[1:]);values=observations.setdefault(r['family'],[])
            assert int(r['index'])==len(values);value=float(r['value']);assert __import__('math').isfinite(value);values.append(value)
    for family,count in {'mlp':92,'cnn':116,'rnn':108,'gru':288,'lstm':372,'transformer':724}.items():
        values=observations[family];assert len(values)==count;total+=count
        expected=reference.setdefault(family,values)
        assert all(abs(x-y)<=0.00002*(1+abs(y)) for x,y in zip(values,expected)),(run['name'],family)
assert total==108800
for variant in ['before','after']:
    for mode in ['debug','release']:
        text=(p/f'Qualification-{variant}-{mode}.log').read_text()
        assert 'SILEX_TENSOR_RESIDENT_VERIFY status=pass families=6 full_state=pass' in text
        observed={r['family']:int(r['observations']) for line in text.splitlines() if line.startswith('SILEX_TENSOR_RESIDENT_VERIFY_FAMILY ') for r in [dict(item.split('=',1) for item in line.split()[1:])]}
        assert observed=={'mlp':92,'cnn':116,'rnn':108,'gru':288,'lstm':372,'transformer':724}
print('VERIFIED 108800 complete scalar observations',flush=True)

assert config["compiler_sha256"]["before"]==config["compiler_sha256"]["after"]
print("VERIFIED raw data, fixed admission, source/protocol and same compiler",flush=True)

record=json.loads((p/'Candidate-Source.json').read_text())
for f,h in record['candidate_module'].items():assert config['fingerprints'][f]==h,f
for filename in ['@Storage.sx','@Profile.sx']:
    assert sha(p/('Candidate-'+filename+'.txt'))==config['fingerprints']['Packages/Tensor/Module/'+filename]
with (p/'Measurements.csv').open(newline='') as f:csv_rows=list(__import__('csv').DictReader(f))
assert csv_rows==[{k:str(r.get(k,'')) for k in csv_rows[0]} for r in rows]
print('VERIFIED committed Tensor source mapping and CSV/JSON parity',flush=True)
