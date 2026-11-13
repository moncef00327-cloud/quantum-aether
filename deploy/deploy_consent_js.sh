#!/usr/bin/env bash
# Deploy commit 7bcd54f (checkout: missing consent scrolls to and highlights the checkbox). Static files only, no restart.
set -euo pipefail
B=/root/backups/consent-js-$(date -u +%Y%m%d%H%M%S); mkdir -p "$B"
for f in crypto.js checkout.js pack-checkout.js; do
  cp -p "/var/www/quantum_saas/static/$f" "$B/"
  install -m 644 -o root -g root "/root/quantum-aether/static/$f" "/var/www/quantum_saas/static/$f"
  n=$(curl -s "https://ather-quantum.com/static/$f" | grep -c showConsent || true)
  echo "$f live (showConsent: $n)"
  if [ "$n" -lt 1 ]; then cp -p "$B/$f" "/var/www/quantum_saas/static/$f"; echo "ROLLED BACK $f"; exit 1; fi
done
echo "backup: $B"
echo "DEPLOYED OK"
