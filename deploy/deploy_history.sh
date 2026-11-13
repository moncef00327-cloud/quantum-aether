#!/usr/bin/env bash
# Deploy the check history (dashboard log + CSV): back up, copy, restart, smoke-test, roll back on failure.
set -euo pipefail
SRC=/root/quantum-aether
DST=/var/www/quantum_saas
FILES=(monitor_db.py monitor.py monitor_job.py quantum_saas_app.py i18n.py legal.py analytics_db.py
       templates/monitor_dashboard.html)
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
for u in / /monitoring /site/google.com /datenschutz; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL$u")
  echo "$u $code"
  [ "$code" = 200 ] || rollback
done
# the DB table exists (created at service start) and the CSV route answers 404 for an unknown token
/var/www/quantum_saas/.venv312/bin/python3 -B -c "
import sqlite3; c = sqlite3.connect('file:/var/lib/quantum_saas/quantum_saas.db?mode=ro', uri=True)
assert c.execute(\"SELECT 1 FROM sqlite_master WHERE name='monitor_checks'\").fetchone(); print('monitor_checks table ok')" || rollback
code=$(curl -s -o /dev/null -w '%{http_code}' "$URL/monitor/not-a-token/history.csv"); echo "history.csv (bad token) $code"; [ "$code" = 404 ] || rollback
echo "DEPLOYED OK"
