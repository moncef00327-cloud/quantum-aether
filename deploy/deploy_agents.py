"""Publish the reviewed agent discovery and remote MCP update with rollback."""
from pathlib import Path
import json, os, shutil, subprocess, tempfile, time, urllib.request

ROOT=Path('/root/quantum-aether')
TARGET=Path('/var/www/quantum_saas').resolve()
BASE='https://ather-quantum.com'
PREVIOUS_RELEASE='400fa95'
FILES=[
 'quantum_saas_app.py','agent_discovery.py','crypto_pay.py','i18n.py','openapi.yaml','templates/base.html','templates/scan.html',
 'templates/command_home.html','templates/llms.txt','templates/agents.html',
 'templates/command/ar.html','templates/command/en.html',
 'templates/command/sidebar-ar.html','templates/command/sidebar-en.html',
 'static/command/app.js','static/crypto.js',
]
assert all((ROOT/p).is_file() for p in FILES)
for name in FILES:
 baseline=subprocess.check_output(['git','show',PREVIOUS_RELEASE+':'+name],cwd=ROOT)
 assert (TARGET/name).read_bytes()==baseline,f'Production file differs from last deployed release: {name}'
backup=Path(tempfile.mkdtemp(prefix='pre-agents-',dir='/root/backups'))
existing=[]
for name in FILES:
 src=TARGET/name
 if src.exists():
  dst=backup/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);existing.append(name)
(backup/'manifest.json').write_text(json.dumps({'files':FILES,'existing':existing},indent=2))
def restart():
 subprocess.run(['systemctl','restart','quantum_saas'],check=True)
 subprocess.run(['systemctl','is-active','--quiet','quantum_saas'],check=True)
def fetch(path):
 for i in range(8):
  try:
   with urllib.request.urlopen(BASE+path,timeout=25) as r:
    assert r.status==200,path
    return r.read()
  except Exception:
   if i==7: raise
   time.sleep(2)
try:
 for name in FILES:
  dst=TARGET/name;dst.parent.mkdir(parents=True,exist_ok=True)
  tmp=dst.with_name(dst.name+'.agents-new');shutil.copyfile(ROOT/name,tmp);os.chmod(tmp,0o644);os.replace(tmp,dst)
 check='''
import tempfile, json, quantum_saas_app, sales_db
with tempfile.TemporaryDirectory() as data:
 app=quantum_saas_app.create_app({'TESTING':True,'DATA_DIR':data,'PAYPAL_CLIENT_ID':'','PAYPAL_CLIENT_SECRET':'','USDC_BASE_ADDR':'0x3855475de54c955b6d0785b6d02f57291addb064'})
 with app.test_client() as c:
  for path in ['/agents','/.well-known/agent-service.json','/api/v1/agent/methodology','/api/v1/agent/example','/api/v1/agent/mcp-server.json','/openapi.yaml','/llms.txt']:
   r=c.get(path);assert r.status_code==200,(path,r.status_code)
  conn=sales_db.connect(data+'/quantum_saas.db')
  conn.executescript(sales_db.SCHEMA)
  sales_db.create_scan(conn,'x402-smoke','smoke-token',{'domain':'example.test','grade':'A','tls_version':'TLS 1.3','key_exchange_group':'X25519MLKEM768','post_quantum_key_exchange':True},'smoke-client',is_test=True)
  conn.close()
  direct=c.post('/api/v1/crypto/orders',json={'scan_id':'x402-smoke','network':'base-usdc','consent_immediate_delivery':True})
  assert direct.status_code==201 and direct.json['network']=='base-usdc' and direct.json['pay_to'].lower()=='0x3855475de54c955b6d0785b6d02f57291addb064',direct.json
  r=c.post('/api/v1/agent/report/x402-smoke',json={});assert r.status_code==402
  challenge=json.loads(__import__('base64').b64decode(r.headers['PAYMENT-REQUIRED']))
  accepted=challenge['accepts'][0]
  assert accepted['network']=='eip155:8453' and accepted['asset'].lower()=='0x833589fcd6edb6e08f4c7c32d4f71b54bda02913' and accepted['payTo'].lower()=='0x3855475de54c955b6d0785b6d02f57291addb064'
  tools=c.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/list'}).json['result']['tools']
  assert 'get_full_report' in {tool['name'] for tool in tools}
  mcp_challenge=c.post('/mcp',json={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'get_full_report','arguments':{'scan_id':'x402-smoke'}}}).json['result']
  assert mcp_challenge['isError'] and mcp_challenge['structuredContent']['accepts'][0]['network']=='eip155:8453'
'''
 subprocess.run([str(TARGET/'.venv/bin/python'),'-c',check],cwd=TARGET,check=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
 restart()
 for path in ['/agents?lang=ar','/agents?lang=en','/.well-known/agent-service.json','/api/v1/agent/methodology','/api/v1/agent/example','/api/v1/agent/mcp-server.json','/llms.txt','/openapi.yaml']:
  data=fetch(path);print('verified',path,len(data))
 manifest=json.loads(fetch('/.well-known/agent-service.json'))
 assert manifest['pricing']['x402']['enabled'] is True
 assert manifest['pricing']['x402']['network']=='eip155:8453'
 print(json.dumps({'status':'published','url':BASE,'backup':str(backup),'files':FILES},indent=2))
except BaseException:
 for name in FILES:
  dst=TARGET/name
  if name in existing:shutil.copy2(backup/name,dst)
  else:dst.unlink(missing_ok=True)
 restart()
 raise
