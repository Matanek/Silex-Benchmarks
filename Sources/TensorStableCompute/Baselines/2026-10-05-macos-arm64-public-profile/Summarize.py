from pathlib import Path
import json,csv,sys,statistics as st
base=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
variants=['reference','off','on','control-a','control-b']
data={};counters={}; profiles={}
for v in variants:
 vals={};cmd={};ps={}
 for log in sorted((base/v).glob('*.log')):
  rep=int(log.stem.split('-')[-1]); count=0
  for line in log.read_text().splitlines():
   if line.startswith('SILEX_TENSOR_NEURAL '):
    fields=dict(f.split('=',1) for f in line.split()[1:]);key=tuple(fields[k] for k in ['phase','family','backend','batch']);value=float(fields['per_iteration_ms']);vals.setdefault(key,{})[rep]=value
    cmd[(key,rep)]=tuple(int(fields[k]) for k in ['uploads','downloads','compute_passes']);count+=1
   if line.startswith('SILEX_TENSOR_PROFILE '):
    fields=dict(f.split('=',1) for f in line.split()[1:]);ints={k:int(value) for k,value in fields.items() if k!='family'}
    assert ints['passes']==ints['bindings']==ints['dispatches']
    assert ints['submissions']==ints['fences']
    assert ints['allocations']>=ints['releases'] and ints['active_bytes']<=ints['peak_bytes']
    batch=fields['batch'];pkey=(fields['family'],batch,rep)
    ps.setdefault(pkey,[]).append(fields)
  assert count==54,(v,log,count)
  assert 'SILEX_TENSOR_NEURAL_VERIFY status=pass uploads=0 hidden_downloads=0' in log.read_text()
 assert len(vals)==162 and all(len(reps)==5 for reps in vals.values()),(v,len(vals))
 if v=='on':
  assert len(ps)==45 and all(len(p)==2 for p in ps.values())
  for (family,batch,rep),p in ps.items():
   end=p[1]
   expected=cmd[(('step_end_to_end',family,'gpu',batch),rep)]
   assert tuple(int(end[k]) for k in ['uploads','downloads','passes'])==expected
 else:assert not ps
 data[v]=vals;counters[v]=cmd;profiles[v]=ps
assert all(counters[v]==counters['reference'] for v in variants)
def metrics(values):
 med=st.median(values);return med,min(values),max(values),st.median(abs(x-med) for x in values)*100/med if med>0 else None
rows=[]
for a,b,label in [('reference','off','disabled'),('off','on','enabled'),('control-a','control-b','A/A')]:
 for key in sorted(data[a]):
  left=[data[a][key][i] for i in range(1,6)];right=[data[b][key][i] for i in range(1,6)]
  ratios=[(y/x-1)*100 for x,y in zip(left,right) if x>0];lm=metrics(left);rm=metrics(right)
  delta=(rm[0]/lm[0]-1)*100 if lm[0]>0 else None
  rows.append(dict(comparison=label,phase=key[0],family=key[1],backend=key[2],batch=key[3],a_median_ms=lm[0],a_min_ms=lm[1],a_max_ms=lm[2],a_relative_mad=lm[3],b_median_ms=rm[0],b_min_ms=rm[1],b_max_ms=rm[2],b_relative_mad=rm[3],median_change_pct=delta,paired_median_pct=st.median(ratios) if ratios else None,paired_min_pct=min(ratios) if ratios else None,paired_max_pct=max(ratios) if ratios else None,slower_pairs=sum(r>0 for r in ratios),candidate_signal=delta is not None and lm[3] is not None and rm[3] is not None and delta>=5 and delta>lm[3] and delta>rm[3] and sum(r>0 for r in ratios)>=4))
with (base/'Comparisons.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
print('validated 4050 timings; identical transfers and compute commands; 90 public snapshots')
for phase in ['step_adam','step_resident','step_end_to_end']:
 for comp in ['disabled','enabled','A/A']:
  picked=[r for r in rows if r['comparison']==comp and r['backend']=='gpu' and r['phase']==phase]
  print(phase,comp,'median changes',', '.join(f"{r['family']}/{r['batch']}:{r['median_change_pct']:.2f}%" for r in picked))
print('Signals:')
for row in rows:
 if row['candidate_signal']:print(row['comparison'],row['phase'],row['family'],row['backend'],row['batch'],round(row['median_change_pct'],2))
print('global summary',json.dumps({label:{'min':min(r['median_change_pct'] for r in rows if r['comparison']==label and r['median_change_pct'] is not None),'max':max(r['median_change_pct'] for r in rows if r['comparison']==label and r['median_change_pct'] is not None),'signals':sum(r['candidate_signal'] for r in rows if r['comparison']==label and r['median_change_pct'] is not None)} for label in ['disabled','enabled','A/A']},indent=2))
