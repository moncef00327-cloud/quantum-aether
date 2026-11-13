#!/usr/bin/env bash
# Deploy commit cadf5ff (probe every public address): back up, copy, restart, smoke-test, roll back on failure.
set -euo pipefail
SRC=/root/quantum-aether
DST=/var/www/quantum_saas
FILES=(adoption_job.py i18n.py monitor.py openapi.yaml quantum_saas_app.py quantum_vuln_scanner.py scan_experience.py
       templates/llms.txt templates/report.html templates/scan.html templates/_endpoints.html)
B=/root/backups/endpoints-$(date -u +%Y%m%d%H%M%S)
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
for u in / /monitoring /research /site/google.com /openapi.yaml /llms.txt; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL$u")
  echo "$u $code"
  [ "$code" = 200 ] || rollback
done
# a real multi-address scan through the site API must return endpoint_summary
out=$(curl -s -X POST -H 'Content-Type: application/json' -d '{"domain":"cloudflare.com"}' "$URL/api/scan")
echo "$out" | grep -q '"endpoint_summary": *{' || { echo "api: ${out:0:300}"; rollback; }
echo "api endpoint_summary ok"
echo "DEPLOYED OK"
