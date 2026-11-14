"""Isolated local QA only: render fixtures or serve them on loopback. Never deploys."""
import argparse
import base64
import copy
import datetime as dt
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import adoption
import countries
import free_alerts
import monitor_db
import packs
import quantum_saas_app
import quantum_vuln_scanner
import sales_db
from tests.test_app import RESULT
from werkzeug.security import generate_password_hash


def fixture_scan(raw):
    domain = quantum_vuln_scanner.normalize_domain(raw)
    if not domain.endswith('.example'):
        raise quantum_vuln_scanner.ScanError('invalid_domain', 'Local QA accepts reserved .example fixtures only')
    if domain == 'timeout.example':
        raise quantum_vuln_scanner.ScanError('tls_failure', 'Local QA timeout fixture')
    time.sleep(.15)  # Observable request waiting, not a fabricated production progress stage.
    result = copy.deepcopy(RESULT)
    result.update(domain=domain, scanned_at=dt.datetime.now(dt.timezone.utc).isoformat())
    if domain == 'pq.example':
        result['key_exchange'].update(pq=True, group='X25519MLKEM768')
    if domain == 'retry.example':
        result['key_exchange'].update(pq=False, hrr=True, group='secp256r1')
    result.update(quantum_vuln_scanner.assess(result['key_exchange'], result['certificate']))
    return result


def make_app(directory, port):
    app = quantum_saas_app.create_app({
        'TESTING': True, 'DATA_DIR': directory, 'PUBLIC_URL': f'http://127.0.0.1:{port}',
        'PAYPAL_CLIENT_ID': '', 'PAYPAL_CLIENT_SECRET': '', 'RESEND_API_KEY': '',
        'USDT_POLYGON_ADDR': '', 'USDC_ARBITRUM_ADDR': '',
        'OWNER_EMAIL': '', 'HASH_SALT': 'local-qa-fixture-only', 'TRUSTED_PROXIES': 0,
        'ADMIN_PASSWORD_HASH': generate_password_hash('local-qa-fixture'),
        'SCANS_PER_HOUR': 1000, 'GLOBAL_SCANS_PER_HOUR': 2000,
    }, scanner=fixture_scan)
    conn = sales_db.connect(str(Path(directory) / 'quantum_saas.db'))
    adoption.seed_from_study(conn)
    for name, domain in [('classical', 'fixture.example'), ('pq', 'pq.example'), ('retry', 'retry.example')]:
        sales_db.create_scan(conn, 'qa-' + name, 'qa-private-' + name, fixture_scan(domain), 'qa', is_test=True)
    sales_db.create_order(conn, 'qa-paid', 'qa-classical', '49.00', 'USD', is_test=True)
    sales_db.update_order(conn, 'qa-paid', 'COMPLETED')
    account, account_token = monitor_db.create_account(conn, 'qa@example.test', 'starter', 'en')
    monitor_db.set_status(conn, account, 'ACTIVE')
    domain_id = monitor_db.add_domain(conn, account, 'fixture.example')
    monitor_db.save_check(conn, domain_id, fixture_scan('fixture.example'))
    packs.create(conn, 'qa-pack', 'qa-pack-order', 10, '199.00', 'USD', 'en', 'local-qa', True)
    pack_token = packs.mark(conn, 'qa-pack', 'COMPLETED')
    alert_token, _ = free_alerts.subscribe(conn, 'qa@example.test', 'fixture.example', 'en', 'qa')
    board = countries.leaderboard(conn)
    country = board['entries'][0]['code'] if board and board['entries'] else None
    conn.close()
    routes = [('/', 'home'), ('/gravity', 'gravity'), ('/adoption', 'adoption'),
              ('/adoption/countries', 'countries'), ('/monitoring', 'monitoring'),
              ('/guides', 'guides'), ('/research', 'research'),
              ('/study/top-1000-post-quantum-tls', 'study'), ('/compare', 'compare'),
              ('/compare?a=fixture.example&b=pq.example', 'comparison-fixture'),
              ('/agency', 'agency'), ('/sample-report', 'sample-report'),
              ('/guides/enable-x25519mlkem768-nginx', 'guide'), ('/scanning', 'scanning'),
              ('/impressum', 'legal'), ('/datenschutz', 'privacy'), ('/agb', 'terms'),
              ('/deadlines', 'deadlines'), ('/site/github.com', 'domain'),
              ('/scan/qa-classical', 'scan-classical-fixture'), ('/scan/qa-pq', 'scan-pq-fixture'),
              ('/scan/qa-retry', 'scan-retry-fixture'), ('/report/qa-private-classical', 'paid-report-fixture'),
              ('/verify/fixture.example', 'badge-fixture'), ('/verify/unknown.example', 'badge-empty'),
              ('/monitor/' + account_token, 'monitor-fixture'), ('/pack/' + pack_token, 'pack-fixture'),
              ('/alerts/confirm/' + alert_token, 'alerts-fixture'), ('/missing-page', 'not-found'),
              ('/admin', 'admin-fixture')]
    if country:
        routes.append(('/adoption/countries/' + country, 'country'))
    return app, routes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/platform2/after')
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    args.output = args.output.resolve()
    with tempfile.TemporaryDirectory(prefix='aether-local-qa-') as directory:
        app, routes = make_app(directory, args.port)
        if args.serve:
            print('LOCAL QA ONLY: reserved .example fixtures; temporary database; payments and email disabled.', flush=True)
            app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False)
            return
        args.output.mkdir(parents=True, exist_ok=True)
        assets = args.output / 'assets'
        assets.mkdir(exist_ok=True)
        for path in (ROOT / 'static').iterdir():
            if path.suffix in ('.css', '.js'):
                shutil.copyfile(path, assets / path.name)
        manifest = []
        with app.test_client() as client:
            for route, name in routes:
                for lang in ('en', 'ar', 'de'):
                    headers = {'Authorization': 'Basic ' + base64.b64encode(b'admin:local-qa-fixture').decode()} if name == 'admin-fixture' else {}
                    response = client.get(route + ('&' if '?' in route else '?') + 'lang=' + lang, headers=headers)
                    expected = 404 if name == 'not-found' else 200
                    if response.status_code != expected:
                        raise RuntimeError(f'{route} {lang}: {response.status_code}, expected {expected}')
                    html = response.get_data(as_text=True).replace('"/static/', '"' + assets.as_uri() + '/')
                    if 'fixture' in name:
                        html = html.replace('<main ', '<aside style="padding:4px 12px;font:12px/1.5 monospace;color:#eaffee;background:#204430">LOCAL QA · SYNTHETIC FIXTURE · NOT A PRODUCTION RESULT</aside><main ', 1)
                    filename = name + '-' + lang + '.html'
                    (args.output / filename).write_text(html, encoding='utf-8')
                    manifest.append(dict(route=route, name=name, lang=lang, file=filename))
        (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        print(f'Rendered {len(manifest)} localized QA pages in {args.output}')


if __name__ == '__main__':
    main()
