#!/usr/bin/env bash
# Deploy the check history (dashboard log + CSV) and the crawler/agent texts that announce it: back up, copy, restart, smoke-test, roll back on failure.
set -euo pipefail
SRC=/root/quantum-aether
DST=/var/www/quantum_saas
FILES=(monitor_db.py monitor.py monitor_job.py quantum_saas_app.py i18n.py legal.py analytics_db.py agent_discovery.py
       templates/monitor_dashboard.html templates/monitoring.html templates/llms.txt)
B=/root/backups/history-$(date -u +%Y%m%d%H%M%S)
mkdir -p "$B"
for f in "${FILES[@]}"; do
  if [ -e "$DST/$f" ]; then mkdir -p "$B/$(dirname "$f")"; cp -p "$DST/$f" "$B/$f"; fi
done
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
for u in / /monitoring /site/google.com /datenschutz /llms.txt /feed.xml /.well-known/agent-service.json; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL$u")
  echo "$u $code"
  [ "$code" = 200 ] || rollback
done
# the DB table exists (created at service start) and the CSV route answers 404 for an unknown token
/var/www/quantum_saas/.venv312/bin/python3 -B -c "
import sqlite3; c = sqlite3.connect('file:/var/lib/quantum_saas/quantum_saas.db?mode=ro', uri=True)
assert c.execute(\"SELECT 1 FROM sqlite_master WHERE name='monitor_checks'\").fetchone(); print('monitor_checks table ok')" || rollback
code=$(curl -s -o /dev/null -w '%{http_code}' "$URL/monitor/not-a-token/history.csv"); echo "history.csv (bad token) $code"; [ "$code" = 404 ] || rollback
curl -s "$URL/monitoring?lang=en" | grep -q '"@type": "Service"' || rollback
curl -s "$URL/llms.txt" | grep -q "Free trial: 14 days" || rollback
echo "crawler texts ok"
echo "DEPLOYED OK"
# tell IndexNow (Bing, Yandex, Seznam, Naver) the changed URLs; failure here does not undo the deploy
python3 - <<'PY' || echo "IndexNow ping failed (deploy is fine)"
import json, urllib.request
key = open("/var/www/quantum_saas/data/indexnow.key").read().strip()
urls = [f"https://ather-quantum.com/monitoring?lang={l}" for l in ("en", "ar", "de")] + [
    "https://ather-quantum.com/llms.txt", "https://ather-quantum.com/llms-full.txt", "https://ather-quantum.com/feed.xml"]
body = json.dumps({"host": "ather-quantum.com", "key": key, "keyLocation": f"https://ather-quantum.com/{key}.txt", "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                             headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "QuantumAether-IndexNow/1.0"})
print("IndexNow:", urllib.request.urlopen(req, timeout=30).status)
PY
