"""Publish the reviewed agent discovery and remote MCP update with rollback."""
from pathlib import Path
import json, os, shutil, subprocess, tempfile, time, urllib.request

ROOT=Path('/root/quantum-aether')
TARGET=Path('/var/www/quantum_saas').resolve()
BASE='https://ather-quatum.cloud'
FILES=[
 'quantum_saas_app.py','agent_discovery.py','openapi.yaml','templates/base.html',
 'templates/command_home.html','templates/llms.txt','templates/agents.html',
 'templates/command/ar.html','templates/command/en.html',
 'templates/command/sidebar-ar.html','templates/command/sidebar-en.html',
 'static/command/app.js',
]
assert all((ROOT/p).is_file() for p in FILES)
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
import tempfile, quantum_saas_app
with tempfile.TemporaryDirectory() as data:
 app=quantum_saas_app.create_app({'TESTING':True,'DATA_DIR':data,'PAYPAL_CLIENT_ID':'','PAYPAL_CLIENT_SECRET':''})
 with app.test_client() as c:
  for path in ['/agents','/.well-known/agent-service.json','/api/v1/agent/methodology','/api/v1/agent/example','/api/v1/agent/mcp-server.json','/openapi.yaml','/llms.txt']:
   r=c.get(path);assert r.status_code==200,(path,r.status_code)
'''
 subprocess.run([str(TARGET/'.venv/bin/python'),'-c',check],cwd=TARGET,check=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
 restart()
 for path in ['/agents?lang=ar','/agents?lang=en','/.well-known/agent-service.json','/api/v1/agent/methodology','/api/v1/agent/example','/api/v1/agent/mcp-server.json','/llms.txt','/openapi.yaml']:
  data=fetch(path);print('verified',path,len(data))
 manifest=json.loads(fetch('/.well-known/agent-service.json'))
 assert manifest['pricing']['x402']['enabled'] is False
 print(json.dumps({'status':'published','url':BASE,'backup':str(backup),'files':FILES},indent=2))
except BaseException:
 for name in FILES:
  dst=TARGET/name
  if name in existing:shutil.copy2(backup/name,dst)
  else:dst.unlink(missing_ok=True)
 restart()
 raise
