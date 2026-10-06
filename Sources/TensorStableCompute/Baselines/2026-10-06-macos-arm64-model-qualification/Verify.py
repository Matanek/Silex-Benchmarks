from pathlib import Path
import json,hashlib,re,math
p=Path(__file__).resolve().parent
checks=json.loads((p/'Checksums.json').read_text())
for f,h in checks.items():assert hashlib.sha256((p/f).read_bytes()).hexdigest()==h,f
config=json.loads((p/'Config.json').read_text());assert config['status']=='qualified' and config['gpu_tolerance']==0.0 and config['cpu_absolute_tolerance']==0.00002
for name,item in config['sources'].items():assert hashlib.sha256((p/item['file']).read_bytes()).hexdigest()==item['sha256'],name
current=json.loads((p/'Task18-Models-Qualification.json').read_text());control=json.loads((p/'Task18-Unfused-Qualification.json').read_text());global_proof=json.loads((p/'Task16-Tensor-Summary.json').read_text())
assert len(current['rows'])==8 and len(control['rows'])==4 and control['restored']
for proof in [current,control]:
 assert proof['compiler_sha256']==config['compiler_sha256']
 assert all(r['status']=='pass' and r['exit_code']==0 for r in proof['rows'])
assert global_proof['compiler_sha256']==config['compiler_sha256']
assert len(global_proof['results'])==112 and sum(r['tests'] for r in global_proof['results'])==470
assert all(r['status']=='pass' and r['exit_code']==0 for r in global_proof['results'])
for name,item in config['sources'].items():
 if name.startswith('Packages/Tensor/Module/'):assert global_proof['fingerprints'][name]==item['sha256']==control['original_fingerprints'][name]
original=(p/'Task18-Neural-Original.sx.txt').read_bytes();variant=(p/'Task18-Neural-Unfused.sx.txt').read_bytes()
needle=b'        if self.is_gpu() { return centered.divide(variance.shifted_square_root(epsilon)) }\n'
assert original.count(needle)==1 and original.replace(needle,b'')==variant
assert hashlib.sha256(variant).hexdigest()==control['variant_sha256']
assert original==(p/config['sources']['Packages/Tensor/Module/@Neural.sx']['file']).read_bytes()
expected=config['observations_per_arm'];parameters={'mlp':4,'cnn':4,'rnn':5,'gru':6,'lstm':6,'transformer':18}
passes={'mlp':252,'cnn':258,'rnn':405,'gru':819,'lstm':831,'transformer':1278}
submissions={'mlp':252,'cnn':258,'rnn':405,'gru':927,'lstm':903,'transformer':1290}
def fields(line):return dict(re.findall(r'(\w+)=([^ ]+)',line))
def read(mode,unfused=False):
 text=(p/f'Task18-{"Unfused" if unfused else "Models"}-{mode}-Run.log').read_text()
 assert 'Metal API Validation Enabled' in text and f'MODEL_QUALIFICATION status=pass families=6 eager_only={str(unfused).lower()}' in text
 values={};runs={};steps={};preparations={};verified=[]
 for line in text.splitlines():
  if not line.startswith('MODEL_'):continue
  f=fields(line)
  if line.startswith('MODEL_VALUE '):
   key=(f['family'],f['arm']);v=values.setdefault(key,[]);assert int(f['index'])==len(v)
   x=float(f['value']);assert math.isfinite(x);v.append(x)
  elif line.startswith('MODEL_RUN '):
   key=(f['family'],f['arm']);assert key not in runs;runs[key]=f;assert f['status']=='pass'
  elif line.startswith('MODEL_STEP '):
   key=(f['family'],f['arm']);s=steps.setdefault(key,[]);assert int(f['iteration'])==len(s);s.append(f)
   assert int(f['parameters'])==parameters[f['family']] and f['training']=='true' and f['trainable']=='true' and f['hyperparameters']=='pass'
   assert (int(f['state_values'])+5)*5==expected[f['family']]
  elif line.startswith('MODEL_PREPARATION '):
   key=(f['family'],f['arm']);assert key not in preparations;preparations[key]=f
   assert f['state_preserved']=='true' and f['prepared']==str(f['family']=='mlp').lower()
  elif line.startswith('MODEL_VERIFY '):assert f['status']=='pass' and f['resources_released']=='true';verified.append(f['family'])
 assert verified==list(expected)
 arms=['cpu','eager'] if unfused else ['cpu','eager','repeat','forward','training']
 assert len(values)==len(runs)==len(steps)==6*len(arms)
 assert len(preparations)==(0 if unfused else 12)
 for family,count in expected.items():
  cpu=values[(family,'cpu')];eager=values[(family,'eager')]
  assert all(abs(a-b)<=config['cpu_absolute_tolerance'] for a,b in zip(cpu,eager))
  for arm in arms:
   key=(family,arm);r=runs[key];assert len(values[key])==int(r['observations'])==count and len(steps[key])==5
   if arm=='cpu':assert int(r['passes'])==int(r['submissions'])==0;continue
   assert values[key]==eager
   delta=6 if unfused and family=='transformer' else 0
   assert int(r['passes'])==passes[family]+delta
   expected_submissions=submissions[family]+delta
   if family=='mlp' and arm=='forward':expected_submissions=240
   if family=='mlp' and arm=='training':expected_submissions=57
   assert int(r['submissions'])==expected_submissions
 return values
candidate={mode:read(mode) for mode in ['debug','release']}
unfused={mode:read(mode,True) for mode in ['debug','release']}
assert candidate['debug']==candidate['release'] and unfused['debug']==unfused['release']
for mode in candidate:
 for family in expected:assert candidate[mode][(family,'eager')]==unfused[mode][(family,'eager')]
for mode in ['debug','release']:
 text=(p/f'Task18-Resident-{mode}-Run.log').read_text();assert 'SILEX_TENSOR_RESIDENT_VERIFY status=pass families=6 full_state=pass' in text
composition=json.loads((p/'Task16-Composition-Summary.json').read_text());assert len(composition['results'])==6 and all(r['status']=='pass' for r in composition['results'])
for name,item in config['sources'].items():
 if name.startswith('Packages/Tensor/Module/'):assert composition['fingerprints'][name]==item['sha256']
assert 'error:' not in (p/'Task18-Package-Check.log').read_text()
count=sum(len(v) for x in [*candidate.values(),*unfused.values()] for v in x.values())
assert count==119420
print(f'VERIFIED six families, {count} scalar observations, exact GPU paths and determinism, CPU 2e-5, state-preserving rejections, fusion counts, resource release, Debug/Release; unchanged 470-test and six-target proofs; no new timing claim')
