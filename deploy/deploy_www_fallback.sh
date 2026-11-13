#!/usr/bin/env bash
# Deploy commit e6ca4f1 (apex <-> www fallback): back up, copy two files, restart, smoke-test, roll back on failure.
set -euo pipefail
SRC=/root/quantum-aether
DST=/var/www/quantum_saas
FILES=(quantum_saas_app.py badge_evidence.py)
B=/root/backups/www-fallback-$(date -u +%Y%m%d%H%M%S)
mkdir -p "$B"
for f in "${FILES[@]}"; do cp -p "$DST/$f" "$B/"; done
echo "backup: $B"

rollback() {
  echo "SMOKE TEST FAILED - rolling back"
  for f in "${FILES[@]}"; do install -m 644 -o root -g root "$B/$f" "$DST/$f"; done
  systemctl restart quantum_saas
  exit 1
}

for f in "${FILES[@]}"; do install -m 644 -o root -g root "$SRC/$f" "$DST/$f"; done
systemctl restart quantum_saas
sleep 3
systemctl is-active --quiet quantum_saas || rollback
for u in / /monitoring /research /site/google.com /site/www.google.com; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "https://ather-quantum.com$u")
  echo "$u $code"
  [ "$code" = 200 ] || rollback
done
echo "DEPLOYED OK"
