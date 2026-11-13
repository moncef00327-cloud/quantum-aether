#!/usr/bin/env bash
# Deploy commit b7c22c0 (14-day free monitoring trial): back up, copy, restart (ExecStartPre migrates the DB),
# smoke-test, roll back the files on failure. The 3 new nullable DB columns stay on rollback (old code ignores them).
set -euo pipefail
SRC=/root/quantum-aether
DST=/var/www/quantum_saas
FILES=(quantum_saas_app.py monitor.py monitor_db.py monitor_job.py i18n.py legal.py static/subscribe.js
       templates/monitoring.html templates/monitor_dashboard.html templates/admin.html templates/trial.html)
B=/root/backups/trial-$(date -u +%Y%m%d%H%M%S)
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
B_URL=https://ather-quantum.com
for u in / /monitoring /research /agb /datenschutz /site/google.com; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$B_URL$u")
  echo "$u $code"
  [ "$code" = 200 ] || rollback
done
for lang in en ar de; do
  curl -s "$B_URL/monitoring?lang=$lang&domain=acme.org" | grep -q 'action="/monitoring/trial' || rollback
  echo "/monitoring?lang=$lang trial form ok"
done
# invalid request must be refused without sending any email
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST -d 'email=bad&domain=acme.org&consent=1' "$B_URL/monitoring/trial?lang=en")
echo "POST /monitoring/trial (bad email) $code"
[ "$code" = 400 ] || rollback
/var/www/quantum_saas/.venv312/bin/python3 -B -c "
import sqlite3; c=sqlite3.connect('file:/var/lib/quantum_saas/quantum_saas.db?mode=ro', uri=True)
cols={r[1] for r in c.execute('pragma table_info(monitor_accounts)')}
assert {'trial_ends_at','trial_notice','client_hash'} <= cols, cols
print('db columns ok')" || rollback
echo "DEPLOYED OK"
