from pathlib import Path
import json,hashlib,re,struct
p=Path(__file__).resolve().parent
for f,h in json.loads((p/'Checksums.json').read_text()).items():assert hashlib.sha256((p/f).read_bytes()).hexdigest()==h,f
config=json.loads((p/'Config.json').read_text());assert config['status']=='indeterminate' and not config['api_added']
for name,item in config['sources'].items():assert hashlib.sha256((p/item['file']).read_bytes()).hexdigest()==item['sha256']
oracle=json.loads((p/'Task17-Conversion-Oracle.json').read_text());assert len(oracle)==15
for r in oracle:
 value=struct.unpack('>f',struct.pack('>I',r['input_bits']))[0]
 try:half=struct.pack('>e',value)
 except OverflowError:half=struct.pack('>H',0x7c00 if value>0 else 0xfc00)
 assert struct.unpack('>H',half)[0]==r['half_bits']
 assert struct.unpack('>I',struct.pack('>f',struct.unpack('>e',half)[0]))[0]==r['roundtrip_bits']
rows=json.loads((p/'Task17-Canonical-Qualification.json').read_text());assert len(rows)==8 and all(r['status']=='pass' and r['exit_code']==0 for r in rows)
for r in rows:
 if r['phase']!='Run':continue
 text=(p/r['log']).read_text();assert 'Metal API Validation Enabled' in text
 values=[line for line in text.splitlines() if '_VALUE index=' in line];assert len(values)==15
 for line,expected in zip(values,oracle):
  observed={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)}
  assert observed['input_bits']==expected['input_bits']
  if observed['index']==14:
   assert observed['packed']&0x7c00==0x7c00 and observed['packed']&0x3ff
   assert observed['roundtrip_bits']&0x7f800000==0x7f800000 and observed['roundtrip_bits']&0x7fffff
  else:
   assert observed['packed']==expected['half_bits'] and observed['roundtrip_bits']==expected['roundtrip_bits']
   actual=expected['input_bits'] if r['name']=='Float16Gate' else expected['roundtrip_bits']
   assert observed['half_bits']==actual and observed.get('min16_bits',observed.get('control_bits'))==actual
 arithmetic=next(line for line in text.splitlines() if '_ARITHMETIC ' in line)
 observed={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',arithmetic)}
 assert observed['float_bits']==0x447a1000
 actual=0x447a1000 if r['name']=='Float16Gate' else 0x447a0000
 assert observed['half_bits']==actual and observed.get('min16_bits',observed.get('control_bits'))==actual
 assert 'conversions=true' in text
composition=json.loads((p/'Task17-Float16-Composition-Summary.json').read_text());assert len(composition['results'])==6
assert all(r['status']=='pass' and r['compiler_sha256']==config['compiler_sha256'] for r in composition['results'])
for name in ['Float16Gate.sx','Shaders/Float16Gate.hlsl']:assert composition['fingerprints']['Silex-Benchmarks/Sources/TensorStableCompute/'+name]==config['sources'][name]['sha256']
assert "unknown type name 'float16_t'" in (p/'Task17-Explicit16-Compiler.log').read_text()
msl=(p/'Task17-Conversion-Dynamic-Default.msl.txt').read_text();assert ' + 1000.25' in msl and 'half2' in msl
print('VERIFIED 15 independent bit cases, HLSL float32 promotion, native Metal half control, Debug/Release, explicit-type rejection, six linked targets; no mixed-precision admission')
