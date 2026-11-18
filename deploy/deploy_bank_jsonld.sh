#!/bin/bash
# Deploy JSON-LD for /banks/<report>/<domain> pages. Usage: bash deploy/deploy_bank_jsonld.sh [rollback]
set -euo pipefail
SRC=/root/quantum-aether; LIVE=/var/www/quantum_saas; F=templates/bank_detail.html
BK=/root/backups/pre-bank-jsonld
if [ "${1:-}" = rollback ]; then cp "$BK/bank_detail.html" "$LIVE/$F"; systemctl restart quantum_saas; echo "rolled back"; exit 0; fi
mkdir -p "$BK"; cp "$LIVE/$F" "$BK/bank_detail.html"
cp "$SRC/$F" "$LIVE/$F"; systemctl restart quantum_saas; sleep 3
for l in ar en; do
  n=$(curl -s "https://ather-quantum.com/banks/arab-banks-2026-11/qnb.com?lang=$l" | grep -c '"@type": "Dataset"' || true)
  if [ "$n" -lt 1 ]; then echo "verify FAILED ($l) -> rollback"; cp "$BK/bank_detail.html" "$LIVE/$F"; systemctl restart quantum_saas; exit 1; fi
done
curl -s -o /dev/null -w "home %{http_code}\n" https://ather-quantum.com/
echo "DEPLOYED OK (backup $BK)"
