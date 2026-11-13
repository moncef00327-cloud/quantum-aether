#!/usr/bin/env bash
# Deploy commit 899413c (asset discovery): back up files + DB, copy, restart (ExecStartPre migrates the DB),
# smoke-test, roll back the files on failure. New table/columns stay on rollback (old code ignores them).
set -euo pipefail
SRC=/root/quantum-aether
DST=/var/www/quantum_saas
FILES=(assets.py discovery.py sales_db.py monitor_db.py monitor.py monitor_job.py quantum_saas_app.py i18n.py
       analytics_db.py agent_discovery.py templates/monitor_dashboard.html templates/llms.txt)
B=/root/backups/assets-$(date -u +%Y%m%d%H%M%S)
mkdir -p "$B"
for f in "${FILES[@]}"; do
  if [ -e "$DST/$f" ]; then mkdir -p "$B/$(dirname "$f")"; cp -p "$DST/$f" "$B/$f"; fi
done
cp -p /var/lib/quantum_saas/quantum_saas.db "$B/quantum_saas.db"
echo "backup: $B"

rollback() {
  echo "SMOKE TEST FAILED - rolling back"
  for f in "${FILES[@]}"; do
    if [ -e "$B/$f" ]; then install -m 644 -o root -g root "$B/$f" "$DST/$f"; else rm -f "$DST/$f"; fi
  done
  systemctl restart quantum_saas
  exit 1
}

for f in "${FILES[@]}"; do install -D -m 644 -o root -g root "$SRC/$f" "$DST/$f"; done
systemctl restart quantum_saas
sleep 3
systemctl is-active --quiet quantum_saas || rollback
URL=https://ather-quantum.com
for u in / /monitoring /site/google.com /llms.txt /.well-known/agent-service.json; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL$u")
  echo "$u $code"
  [ "$code" = 200 ] || rollback
done
curl -s "$URL/monitoring?lang=en" | grep -q "Asset discovery" || rollback
curl -s "$URL/llms.txt" | grep -q "Asset discovery" || rollback
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$URL/monitor/not-a-token/seeds"); echo "seeds (bad token) $code"; [ "$code" = 404 ] || rollback
/var/www/quantum_saas/.venv312/bin/python3 -B -c "
import sqlite3; c = sqlite3.connect('file:/var/lib/quantum_saas/quantum_saas.db?mode=ro', uri=True)
assert c.execute(\"SELECT 1 FROM sqlite_master WHERE name='monitor_seeds'\").fetchone()
cols = {r[1] for r in c.execute('PRAGMA table_info(monitor_domains)')}; assert {'source', 'fail_streak'} <= cols, cols
print('db schema ok')" || rollback
# the daily job imports cleanly with the new module (it runs at 05:00 UTC from the timer)
/var/www/quantum_saas/.venv312/bin/python3 -B -c "import sys; sys.path.insert(0, '/var/www/quantum_saas'); import monitor_job, assets; print('monitor_job imports ok')" || rollback
echo "DEPLOYED OK"
python3 - <<'PY' || echo "IndexNow ping failed (deploy is fine)"
import json, urllib.request
key = open("/var/www/quantum_saas/data/indexnow.key").read().strip()
urls = [f"https://ather-quantum.com/monitoring?lang={l}" for l in ("en", "ar", "de")] + ["https://ather-quantum.com/llms.txt"]
body = json.dumps({"host": "ather-quantum.com", "key": key, "keyLocation": f"https://ather-quantum.com/{key}.txt", "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                             headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "QuantumAether-IndexNow/1.0"})
print("IndexNow:", urllib.request.urlopen(req, timeout=30).status)
PY
