"""Replay public measurement evidence locally; no production service or database access."""
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

import quantum_saas_app
import sales_db
import search_indexing

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/indexing-review'
rows=json.loads((OUT/'weekly-public-fixture.json').read_text())
base='https://ather-quantum.com'
ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
with tempfile.TemporaryDirectory(prefix='indexing-replay-') as tmp:
    app=quantum_saas_app.create_app({'TESTING':True,'DATA_DIR':tmp,'PUBLIC_URL':base,'PAYPAL_CLIENT_ID':'','PAYPAL_CLIENT_SECRET':''},scanner=lambda _: (_ for _ in ()).throw(AssertionError('No network scans')))
    conn=sales_db.connect(tmp+'/quantum_saas.db')
    fields=list(rows[0]);sql='INSERT INTO adoption_results ('+','.join(fields)+') VALUES ('+','.join('?' for _ in fields)+')'
    with conn:conn.executemany(sql,[[row[f] for f in fields] for row in rows])
    count_before=conn.execute('SELECT COUNT(*) FROM adoption_results').fetchone()[0]
    with app.test_request_context('/sitemap.xml'):
        with patch('search_indexing.is_excluded',return_value=False):baseline=set(d for d,_ in quantum_saas_app._sitemap_domains())
        proposed=set(d for d,_ in quantum_saas_app._sitemap_domains())
    removed=baseline-proposed
    assert removed==search_indexing.reviewed_hosts(),removed
    assert not proposed-baseline
    client=app.test_client();sitemap=client.get('/sitemap.xml');assert sitemap.status_code==200
    urls=[]
    for e in ET.fromstring(sitemap.data).findall('s:sitemap/s:loc',ns):
        if 'sitemap-sites-' not in e.text:continue
        response=client.get(urlsplit(e.text).path);assert response.status_code==200
        urls.extend(e.text for e in ET.fromstring(response.data).findall('s:url/s:loc',ns))
    assert len(urls)==len(proposed)*2
    assert len(urls)==len(set(urls))
    robots=client.get('/robots.txt').text
    assert robots==(OUT/'live-robots.txt').read_text()
    parser=RobotFileParser();parser.parse(robots.splitlines())
    page_checks=[]
    for domain in sorted(removed):
        for lang in ['en','ar']:
            path='/site/'+domain+'?lang='+lang;response=client.get(path)
            assert response.status_code==200
            assert 'noindex' in response.headers['X-Robots-Tag']
            assert '<meta name="robots" content="noindex, follow">' in response.text
            assert parser.can_fetch('Googlebot',base+path)
            assert 'href="'+base+path+'"' in response.text
            assert base+path not in urls
            page_checks.append(path)
    for path in ['/adoption?lang=en','/study/top-1000-post-quantum-tls?lang=en','/guides?lang=en','/site/github.com?lang=en','/site/onlyfans.com?lang=en','/site/erome.com?lang=en','/site/xhamster46.desi?lang=en']:
        response=client.get(path);assert response.status_code==200,path
        assert 'noindex' not in response.headers.get('X-Robots-Tag',''),path
        assert '<meta name="robots" content="noindex' not in response.text,path
        assert parser.can_fetch('Googlebot',base+path)
    assert conn.execute('SELECT COUNT(*) FROM adoption_results').fetchone()[0]==count_before
    assert all(domain in json.dumps(client.get('/adoption.json').json) for domain in removed)
    conn.close()
    result={'production_database_used':False,'public_measurement_rows_replayed':len(rows),'domain_pages_before':len(baseline),'domain_pages_after':len(proposed),'removed_domains':sorted(removed),'sitemap_urls_before':len(baseline)*2,'sitemap_urls_after':len(urls),'removed_language_urls':len(removed)*2,'excluded_pages_verified':page_checks,'robots_byte_identical':True,'datasets_preserved':True,'ordinary_pages_indexable':True,'google_index_status':'Not verified; no authenticated URL Inspection access','published':False}
    (OUT/'local-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
