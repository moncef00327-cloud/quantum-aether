"""Read-only production indexing audit; never imports the application or writes production data."""
import concurrent.futures
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT=Path('/root/quantum-aether')
PROD=Path('/var/www/quantum_saas').resolve()
OUT=ROOT/'artifacts/indexing-review'
OUT.mkdir(parents=True,exist_ok=True)
CONFIRMED=['pornhub.com','stripchat.com','xvideos.com','xnxx.com','xhamster.com','chaturbate.com','eporner.com','fapello.com']
REVIEW_ONLY=['erome.com','onlyfans.com','xhamster46.desi']
class Metadata(HTMLParser):
    def __init__(self):super().__init__();self.robots=[];self.canonical=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='meta' and a.get('name','').lower() in ['robots','googlebot']:self.robots.append(a.get('content',''))
        if tag=='link' and a.get('rel')=='canonical':self.canonical.append(a.get('href'))
        if tag=='a' and a.get('href'):self.links.append(a['href'])

def fetch(path):
    url='https://ather-quantum.com'+path
    try:r=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Quantum-Aether-Indexing-Audit/1.0'}),timeout=30)
    except urllib.error.HTTPError as exc:r=exc
    except Exception as exc:return {'url':url,'error':str(exc)}
    with r:
        data=r.read().decode('utf-8','replace');parser=Metadata();parser.feed(data)
        return {'url':url,'status':r.status,'final_url':r.url,'x_robots_tag':r.headers.get('X-Robots-Tag'),'canonical':parser.canonical,'robots':parser.robots,'content_type':r.headers.get('Content-Type'),'body_sha256':hashlib.sha256(data.encode()).hexdigest(),'body':data,'links':parser.links}

settings={}
for line in Path('/etc/quantum_saas.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key,value=line.split('=',1)
        if key in ['QS_DATA_DIR','QS_PUBLIC_URL']:settings[key]=value.strip().strip('\"\'')
p=Path(settings.get('QS_DATA_DIR','/var/www/quantum_saas/instance'))/'quantum_saas.db'
conn=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True);conn.row_factory=sqlite3.Row;conn.execute('PRAGMA query_only=ON')
study=json.loads((PROD/'data/pq_study_top1000.json').read_text());study_domains={s['domain'] for s in study['sites']}
weeks=[r[0] for r in conn.execute('SELECT DISTINCT week FROM adoption_results ORDER BY week')]
latest_week=weeks[-1] if weeks else None
all_weekly={r['domain']:dict(r) for r in conn.execute('SELECT domain,week,rank,ok,scanned_at FROM adoption_results ORDER BY week')}
latest_ok={r['domain']:dict(r) for r in conn.execute('SELECT domain,week,rank,ok,scanned_at FROM adoption_results WHERE ok=1 ORDER BY week')}
scan_rows=[dict(r) for r in conn.execute('SELECT domain,created_at,source,is_test FROM scans ORDER BY created_at')]
since=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
latest_scan={r['domain']:r for r in scan_rows if r['created_at']>=since}
domains=[]
for domain in CONFIRMED+REVIEW_ONLY:
    weekly=latest_ok.get(domain);scan=latest_scan.get(domain)
    domains.append({'domain':domain,'classification':'confirmed_source_candidate' if domain in CONFIRMED else 'unconfirmed_no_policy_change','in_study':domain in study_domains,'weekly':all_weekly.get(domain),'latest_successful_weekly':weekly,'visitor_scan':scan,'effective_source':'scan' if scan else 'weekly' if weekly else 'study' if domain in study_domains else None,'google_index_status':'UNVERIFIED: authenticated URL Inspection not available'})
counts={'study_reachable_domains':len(study_domains),'weekly_rows':conn.execute('SELECT COUNT(*) FROM adoption_results').fetchone()[0],'weekly_unique_domains':len(all_weekly),'scan_rows':len(scan_rows),'scan_unique_domains':len({r['domain'] for r in scan_rows}),'latest_week':latest_week}
conn.close()
paths=['/robots.txt','/sitemap.xml','/sitemap-pages.xml','/?lang=en','/adoption?lang=en','/study/top-1000-post-quantum-tls?lang=en','/guides?lang=en','/guides/enable-x25519mlkem768-nginx?lang=en','/site/github.com?lang=en','/site/not-a-record.example?lang=en']
paths += ['/site/'+d+'?lang='+lang for d in CONFIRMED+REVIEW_ONLY for lang in ['en','ar']]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:responses=list(pool.map(fetch,paths))
ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
index=next(r for r in responses if r['url'].endswith('/sitemap.xml'))
sitemaps=[urllib.parse.urlsplit(e.text).path for e in ET.fromstring(index['body']).findall('s:sitemap/s:loc',ns) if 'sitemap-sites-' in e.text]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:responses.extend(pool.map(fetch,sitemaps))
for row in domains:
    row['live_sitemap_urls']=[e.text for res in responses if '/sitemap-sites-' in res['url'] for e in ET.fromstring(res['body']).findall('s:url/s:loc',ns) if urllib.parse.urlsplit(e.text).path=='/site/'+row['domain']]
for res in responses:
    path=urllib.parse.urlsplit(res['url']).path
    if path.startswith('/sitemap') or path=='/robots.txt':
        (OUT/('live-'+path.lstrip('/'))).write_text(res['body'])
    res['links_to_reviewed_domains']=[href for href in res.pop('links',[]) if any('/site/'+d in href for d in CONFIRMED)]
    res.pop('body',None)
tracked=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
differences=[];production_hashes={}
for name in tracked:
    a=ROOT/name;b=PROD/name
    if b.is_file() and (name.endswith(('.py','.html','.js','.css')) or name.startswith('data/')):
        production_hashes[name]=hashlib.sha256(b.read_bytes()).hexdigest()
        if a.is_file() and a.read_bytes()!=b.read_bytes():differences.append(name)
prod_only=[]
for folder in ['templates','static']:
    for file in (PROD/folder).rglob('*'):
        if file.is_file() and not (ROOT/file.relative_to(PROD)).exists():prod_only.append(str(file.relative_to(PROD)))
verification={}
for f in [PROD/'templates/base.html',PROD/'templates/command_home.html']:
    verification[str(f.relative_to(PROD))]=re.findall(r'<meta name="google-site-verification" content="([^"]+)"',f.read_text())
log_summary={'source':'journalctl quantum_saas: most recent 10000 lines','unverified_user_agents':True}
try:
    result=subprocess.run(['journalctl','-u','quantum_saas','-n','10000','--no-pager','-o','cat'],capture_output=True,text=True,timeout=20)
    paths_seen={}
    for line in result.stdout.splitlines():
        m=re.search(r'"(GET|HEAD) ([^ ]+) HTTP/[^\"]+" (\d{3})',line)
        if m:
            path=urllib.parse.urlsplit(m[2]).path
            if path.startswith(('/site/','/sitemap','/robots','/.well-known','/wp-','/google')):
                key=path+' '+m[3];paths_seen[key]=paths_seen.get(key,0)+1
    log_summary.update(returncode=result.returncode,paths=paths_seen)
except Exception as exc:log_summary['error']=str(exc)
report={'observed_at':dt.datetime.now(dt.timezone.utc).isoformat(),'read_only':True,'production_root':str(PROD),'public_runtime_config':settings,'counts':counts,'domains':domains,'public_responses':responses,'tracked_source_production_differences':differences,'production_only_template_static_files':prod_only,'verification_tokens':verification,'production_file_hashes':production_hashes,'log_summary':log_summary,'search_console':{'performance':'not accessible','url_inspection':'not accessible','owners_permissions':'not accessible','sitemaps_submitted_in_gsc':'not accessible','manual_actions_security_issues':'not accessible'}}
(OUT/'production-audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'counts':counts,'domains':domains,'tracked_source_production_differences':differences,'production_only_template_static_files':prod_only,'responses':[{k:v for k,v in r.items() if k in ['url','status','canonical','robots','x_robots_tag']} for r in responses],'evidence':str(OUT/'production-audit.json')},indent=2))
