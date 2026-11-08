"""Publish reviewed indexing and Dataset changes with a guarded backup and rollback."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT=Path('/root/quantum-aether')
TARGET=Path('/var/www/quantum_saas').resolve()
OUT=ROOT/'artifacts/latest-publish'
FILES=['data/indexing_exclusions.json','search_indexing.py','templates/country.html',
       'templates/adoption.html','templates/site_page.html','quantum_saas_app.py']
EXPECTED={
 'quantum_saas_app.py':'8d3457dbe26b298b0c3618ee85385761420b28bbc818e53d3c7700ac0f055c1b',
 'search_indexing.py':None,'data/indexing_exclusions.json':None,
 'templates/country.html':'eed3b95f917892b0ed7f2519b84248f4085f7c45e98a281196e291f2699a1307',
 'templates/adoption.html':'5f9c00aa13c9ccc9db8a8be81a1b700bdc87708cf4863877ea96d7da35eb0b43',
 'templates/site_page.html':'d48b7ece4cd1a84e07bd48c675673a99720ed2ecda3cd8a4a403db920a7087d5',
}
BASE='https://ather-quantum.com'
NS={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
HOSTS={r['domain'] for r in json.loads((ROOT/'data/indexing_exclusions.json').read_text())['domains']}

class Metadata(HTMLParser):
 def __init__(self):
  super().__init__();self.active=False;self.parts=[];self.docs=[];self.robots=[];self.canonical=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='script' and a.get('type')=='application/ld+json':self.active=True;self.parts=[]
  if tag=='meta' and a.get('name')=='robots':self.robots.append(a.get('content',''))
  if tag=='link' and a.get('rel')=='canonical':self.canonical.append(a.get('href'))
 def handle_data(self,text):
  if self.active:self.parts.append(text)
 def handle_endtag(self,tag):
  if tag=='script' and self.active:self.docs.append(json.loads(''.join(self.parts)));self.active=False

def objects(value):
 if isinstance(value,dict):
  yield value
  for child in value.values():yield from objects(child)
 elif isinstance(value,list):
  for child in value:yield from objects(child)

def fetch(path):
 for attempt in range(6):
  try:
   with urllib.request.urlopen(BASE+path,timeout=30) as r:
    assert r.status==200,path
    return r.headers,r.read()
  except Exception:
   if attempt==5:raise
   time.sleep(1)

def domain_urls():
 _,index=fetch('/sitemap.xml');result=set()
 for loc in ET.fromstring(index).findall('s:sitemap/s:loc',NS):
  if 'sitemap-sites-' not in loc.text:continue
  _,data=fetch(urllib.parse.urlsplit(loc.text).path)
  result.update(e.text for e in ET.fromstring(data).findall('s:url/s:loc',NS))
 return result

def restart():
 subprocess.run(['systemctl','restart','quantum_saas'],check=True)
 subprocess.run(['systemctl','is-active','--quiet','quantum_saas'],check=True)

for name in FILES:
 current=TARGET/name
 digest=hashlib.sha256(current.read_bytes()).hexdigest() if current.is_file() else None
 assert digest==EXPECTED[name], 'Production changed since review: '+name
 assert (ROOT/name).is_file(),name
_,robots_before=fetch('/robots.txt')
urls_before=domain_urls()
BACKUP=Path(tempfile.mkdtemp(prefix='pre-indexing-dataset-',dir='/root/backups'))
existing=[]
for name in FILES:
 if (TARGET/name).exists():
  saved=BACKUP/name;saved.parent.mkdir(parents=True,exist_ok=True)
  shutil.copy2(TARGET/name,saved);existing.append(name)
(BACKUP/'manifest.json').write_text(json.dumps({'files':FILES,'existing':existing},indent=2))
try:
 for name in FILES:
  target=TARGET/name;target.parent.mkdir(parents=True,exist_ok=True)
  temporary=target.with_name(target.name+'.latest-new')
  shutil.copyfile(ROOT/name,temporary);os.chmod(temporary,0o644);os.replace(temporary,target)
 check='''
import tempfile,json
from pathlib import Path
import quantum_saas_app,sales_db
from tests.test_countries import seed
with tempfile.TemporaryDirectory() as tmp:
 app=quantum_saas_app.create_app({'TESTING':True,'DATA_DIR':tmp,'PUBLIC_URL':'https://ather-quantum.com','PAYPAL_CLIENT_ID':'','PAYPAL_CLIENT_SECRET':''},scanner=lambda _: (_ for _ in ()).throw(AssertionError('No live scanning')))
 conn=sales_db.connect(tmp+'/quantum_saas.db');seed(conn);conn.close()
 with app.test_client() as c:
  for path in ['/site/github.com?lang=en','/adoption','/adoption/countries','/study/top-1000-post-quantum-tls','/sample-report','/business','/pricing']:
   r=c.get(path);assert r.status_code==200,path
   assert b'noindex' not in r.headers.get('X-Robots-Tag','').encode(),path
  for lang in ['ar','en']:
   r=c.get('/site/pornhub.com?lang='+lang)
   assert r.status_code==200
   assert 'noindex' in r.headers['X-Robots-Tag']
   assert b'https://creativecommons.org/licenses/by/4.0/' in r.data
print('Candidate production integration checks passed')
'''
 subprocess.run([str(TARGET/'.venv/bin/python'),'-c',check],cwd=TARGET,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),check=True)
 restart()
 for host in sorted(HOSTS|{'github.com'}):
  for lang in ['en','ar']:
   path='/site/'+host+'?lang='+lang;headers,data=fetch(path)
   meta=Metadata();meta.feed(data.decode())
   assert meta.canonical==[BASE+path],path
   excluded=host in HOSTS
   assert ('noindex' in headers.get('X-Robots-Tag',''))==excluded,path
   assert any('noindex' in rule for rule in meta.robots)==excluded,path
   datasets=[o for doc in meta.docs for o in objects(doc) if o.get('@type')=='Dataset']
   assert datasets,path
   for dataset in datasets:
    assert len(dataset.get('description',''))>=50,path
    assert dataset['license']=='https://creativecommons.org/licenses/by/4.0/'
    assert dataset['creator']['@type']=='Organization' and dataset['creator']['name']=='Quantum Aether'
   print('Verified metadata/indexing: '+path)
 for path in ['/?lang=en','/?lang=ar','/adoption?lang=en','/adoption/countries?lang=en','/study/top-1000-post-quantum-tls?lang=en','/guides?lang=en','/sample-report?lang=en','/business?lang=ar','/pricing?lang=en','/llms.txt']:
  headers,data=fetch(path);assert 'noindex' not in headers.get('X-Robots-Tag',''),path
  meta=Metadata();meta.feed(data.decode())
  assert not any('noindex' in rule for rule in meta.robots),path
  for dataset in [o for doc in meta.docs for o in objects(doc) if o.get('@type')=='Dataset']:
   assert dataset.get('description') and dataset.get('license') and dataset.get('creator'),path
  print('Verified ordinary page: '+path)
 _,robots_after=fetch('/robots.txt');assert robots_after==robots_before,'robots.txt changed'
 urls_after=domain_urls()
 removed={BASE+'/site/'+host+'?lang='+lang for host in HOSTS for lang in ['en','ar']}
 assert removed<=urls_before,'Reviewed pages were missing from baseline sitemap'
 assert urls_after==urls_before-removed,'Unexpected sitemap changes'
 for name in FILES:assert (TARGET/name).read_bytes()==(ROOT/name).read_bytes(),name
 receipt={'url':BASE,'backup':str(BACKUP),'files':FILES,'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'robots_unchanged':True,'sitemap_urls_before':len(urls_before),'sitemap_urls_after':len(urls_after),'excluded_domains':sorted(HOSTS),'dataset_metadata_verified':True,'gsc_validation_started':False,'status':'succeeded'}
 OUT.mkdir(exist_ok=True,parents=True);(OUT/'deployment.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt,indent=2))
except BaseException:
 for name in FILES:
  if name in existing:shutil.copy2(BACKUP/name,TARGET/name)
  else:(TARGET/name).unlink(missing_ok=True)
 restart()
 raise
