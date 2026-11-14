#!/usr/bin/env bash
# Deploy the trial card on unprotected scan results: backup, copy, restart, check, rollback.
set -euo pipefail
SRC=/root/quantum-aether; DST=/var/www/quantum_saas
FILES=(templates/scan.html i18n.py)
B=/root/backups/scan-trial-$(date -u +%Y%m%d%H%M%S); mkdir -p "$B/templates"
for f in "${FILES[@]}"; do cp -p "$DST/$f" "$B/$f"; done
echo "backup: $B"
rollback() { echo "CHECK FAILED - rolling back"; for f in "${FILES[@]}"; do install -m 644 -o root -g root "$B/$f" "$DST/$f"; done; systemctl restart quantum_saas; exit 1; }
for f in "${FILES[@]}"; do install -m 644 -o root -g root "$SRC/$f" "$DST/$f"; done
systemctl restart quantum_saas; sleep 3
systemctl is-active --quiet quantum_saas || rollback
URL=https://ather-quantum.com
for u in / /monitoring /site/google.com; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL$u"); echo "$u $code"; [ "$code" = 200 ] || rollback
done
# a recent real classical scan page must show the card (no new scan is created)
/var/www/quantum_saas/.venv312/bin/python3 -B - <<'PY' || rollback
import sqlite3, urllib.request
c = sqlite3.connect("file:/var/lib/quantum_saas/quantum_saas.db?mode=ro", uri=True)
row = c.execute("SELECT id FROM scans WHERE grade IN ('B','C') AND is_test = 0 ORDER BY created_at DESC LIMIT 1").fetchone()
html = urllib.request.urlopen(f"https://ather-quantum.com/scan/{row[0]}?lang=ar", timeout=30).read().decode()
assert 'id="scan-trial"' in html and 'action="/monitoring/trial' in html, "trial card missing"
print("scan page trial card ok")
PY
echo "DEPLOYED OK"
