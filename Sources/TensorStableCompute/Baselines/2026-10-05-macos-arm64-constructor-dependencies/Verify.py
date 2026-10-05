from pathlib import Path
import argparse,json,statistics as st,hashlib,re,csv,math
args=argparse.Namespace(harness='micro')
p=Path(__file__).resolve().parent
checksums=json.loads((p/'Checksums.json').read_text())
for filename,expected in checksums.items():assert hashlib.sha256((p/filename).read_bytes()).hexdigest()==expected,filename
with (p/'Measurements.csv').open(newline='') as f:csv_rows=list(csv.DictReader(f))
json_rows=json.loads((p/'Rows.json').read_text())
assert csv_rows==[{k:str(r.get(k,'')) for k in csv_rows[0]} for r in json_rows]
assert hashlib.sha256((p/'Source.sx.txt').read_bytes()).hexdigest()==json.loads((p/'Configuration.json').read_text())['fingerprints']['Silex-Benchmarks/Sources/TensorStableCompute/'+('EagerResources' if args.harness=='micro' else 'ResidentSteps')+'.sx']
assert hashlib.sha256((p/'Protocol.md').read_bytes()).hexdigest()==json.loads((p/'Configuration.json').read_text())['protocol_sha256']
rows=json.loads((p/'Rows.json').read_text());runs=json.loads((p/'Runs.json').read_text());configuration=json.loads((p/'Configuration.json').read_text())
assert json.loads((p/'Verified.json').read_text())['unchanged']
assert len(runs)==64 and len(rows)==64*(20 if args.harness=='micro' else 6)
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
for run in runs:
    assert run['exit_code']==0
    assert sha(p/(run['name']+'.log'))==run['stdout_sha256']
    assert sha(p/(run['name']+'.time'))==run['stderr_sha256']
def median(v):return st.median(v)
def mad(v):return median([abs(x-median(v)) for x in v])
def stats(v):return dict(median=median(v),mad=mad(v),minimum=min(v),maximum=max(v))
def key(r):return (r['phase'],r['mode'],str(r['size'])) if args.harness=='micro' else (r['family'],)
keys=sorted({key(r) for r in rows});cases=[]
for k in keys:
    selected=[r for r in rows if key(r)==k]
    def arm(group,variant,number=None):
        result=sorted([r for r in selected if r['group']==group and r['variant']==variant and (number is None or r['arm']==number)],key=lambda r:r['pair'])
        assert len(result)==(16 if group=='main' else 8)
        return [float(r['elapsed_ms']) for r in result]
    before=arm('main','before');after=arm('main','after')
    delta=[100*(y/x-1) if x>0 else None for x,y in zip(before,after)]
    aa={}
    for variant in ['before','after']:
        x=arm('control',variant,0);y=arm('control',variant,1)
        differences=[100*(b/a-1) if a>0 else None for a,b in zip(x,y)]
        if None in differences:aa[variant]=dict(differences=differences,valid=False,reason='zero denominator')
        else:aa[variant]=dict(differences=differences,**stats(differences),valid=not(abs(median(differences))>=5 and abs(median(differences))>3*mad(differences)))
    if None in delta:paired=dict(differences=delta);verdict='indeterminate'
    else:
        paired=dict(differences=delta,**stats(delta),negative=sum(d<0 for d in delta),positive=sum(d>0 for d in delta))
        signal=abs(paired['median'])>=5 and abs(paired['median'])>3*paired['mad'] and max(paired['negative'],paired['positive'])>=14
        verdict=('signal_decrease' if paired['median']<0 else 'signal_increase') if signal and all(v['valid'] for v in aa.values()) else 'indeterminate'
    cases.append(dict(case=k,before=stats(before),after=stats(after),paired=paired,controls=aa,verdict=verdict))
rss={}
for variant in ['before','after']:
    values=[]
    for r in runs:
        if r['group']=='main' and r['variant']==variant:
            m=re.search(r'(\d+)\s+maximum resident set size',(p/(r['name']+'.time')).read_text());assert m;values.append(int(m[1]))
    assert len(values)==16;rss[variant]=stats(values)
summary=dict(harness=args.harness,cases=cases,processes=64,rows=len(rows),rss_process_bytes=rss,full_observations_checked=args.harness=='models',source_fingerprints=configuration['fingerprints'],compiler_sha256=configuration['compiler_sha256'],binary_sha256=configuration['binary_sha256'])
assert json.loads(json.dumps(summary))==json.loads((p/'Summary.json').read_text())
for r in cases:print('/'.join(r['case']),f"{r['before']['median']:.6f} -> {r['after']['median']:.6f} ms",r['verdict'],f"delta={r['paired'].get('median')} MAD={r['paired'].get('mad')}",['invalid A/A '+v for v,c in r['controls'].items() if not c['valid']])
print('VERIFIED raw checksums, paired medians/MAD, fixed admission rule and process RSS',flush=True)
