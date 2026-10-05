from pathlib import Path
import json,statistics as st,csv
p=Path(__file__).resolve().parent;rows=json.loads((p/'Rows.json').read_text());runs=json.loads((p/'Runs.json').read_text());assert len(rows)==640 and len(runs)==32
for run in runs:assert run['exit_code']==0
sizes=[1,256,4096,65536]
def median(v):return st.median(v)
def mad(v):return median([abs(x-median(v)) for x in v])
def selected(group,phase,mode,size):return sorted([r for r in rows if r['group']==group and r['phase']==phase and r['mode']==mode and int(r['size'])==size],key=lambda r:r['index'])
def times(rs):return [float(r['elapsed_ms']) for r in rs]
def stats(v):return dict(median=median(v),mad=mad(v),minimum=min(v),maximum=max(v))
result=[]
for size in sizes:
 for phase,a,b in [('resident','replace','retain'),('buffer_control','create_release','existing')]:
  left=times(selected('main',phase,a,size));right=times(selected('main',phase,b,size));assert len(left)==len(right)==16
  delta=[100*(y/x-1) if x else None for x,y in zip(left,right)]
  aa={}
  for mode in [a,b]:
   v=times(selected('control',phase,mode,size));assert len(v)==16
   d=[100*(v[i+1]/v[i]-1) if v[i] else None for i in range(0,16,2)]
   if None in d:aa[mode]=dict(differences=d,valid=False,reason='zero denominator')
   else:aa[mode]=dict(differences=d,**stats(d),valid=not(abs(median(d))>=5 and abs(median(d))>3*mad(d)))
  if None in delta:verdict='indeterminate';ds=dict(differences=delta)
  else:
   ds=dict(differences=delta,**stats(delta),negative=sum(d<0 for d in delta),positive=sum(d>0 for d in delta))
   direction=max(ds['negative'],ds['positive'])
   signal=abs(ds['median'])>=5 and abs(ds['median'])>3*ds['mad'] and direction>=14
   verdict=('signal_decrease' if ds['median']<0 else 'signal_increase') if signal and all(v['valid'] for v in aa.values()) else 'indeterminate'
  result.append(dict(size=size,phase=phase,reference=a,variation=b,left=stats(left),right=stats(right),paired=ds,controls=aa,verdict=verdict))
summary=dict(cases=result,dependent={str(size):stats(times(selected('main','resident','dependent',size))) for size in sizes},rows=640,processes=32)
(p/'Summary.json').write_text(json.dumps(summary,indent=2)+'\n')
for r in result:print(r['size'],r['phase'],f"{r['left']['median']:.4f} -> {r['right']['median']:.4f} ms",r['verdict'],f"delta={r['paired'].get('median')} MAD={r['paired'].get('mad')}",['control invalid '+k for k,v in r['controls'].items() if not v['valid']])
