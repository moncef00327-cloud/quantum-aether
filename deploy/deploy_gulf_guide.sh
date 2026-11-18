#!/usr/bin/env bash
# Deploy guides.py with the new Gulf banks PQC requirements guide (ar/en): backup, copy, restart, check, auto-rollback; IndexNow.
# Usage: bash deploy/deploy_gulf_guide.sh            (deploy)
#        bash deploy/deploy_gulf_guide.sh rollback   (restore the backup taken by the last deploy)
set -euo pipefail
SRC=/root/quantum-aether/guides.py; DST=/var/www/quantum_saas/guides.py
LAST=/root/backups/gulf-guide-last
SLUG=gulf-banks-post-quantum-cryptography-requirements
URL=https://ather-quantum.com

if [ "${1:-}" = rollback ]; then
  B=$(cat "$LAST"); install -m 644 -o root -g root "$B/guides.py" "$DST"; systemctl restart quantum_saas
  echo "rolled back to $B"; exit 0
fi

B=/root/backups/pre-gulf-guide-$(date -u +%Y%m%d%H%M%S); mkdir -p "$B"; cp -p "$DST" "$B/"; echo "$B" > "$LAST"
echo "backup: $B"
rollback() { echo "CHECK FAILED - rolling back"; install -m 644 -o root -g root "$B/guides.py" "$DST"; systemctl restart quantum_saas; exit 1; }
install -m 644 -o root -g root "$SRC" "$DST"
systemctl restart quantum_saas; sleep 3
systemctl is-active --quiet quantum_saas || rollback
for u in / /guides "/guides/$SLUG?lang=ar" "/guides/$SLUG?lang=en" "/guides/nis2-dora-post-quantum-cryptography?lang=ar" "/banks/arab-banks-2026-11?lang=ar"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL$u"); echo "$u $code"; [ "$code" = 200 ] || rollback
done
curl -s "$URL/guides/$SLUG?lang=ar" | grep -q "482021280" || rollback
curl -s "$URL/sitemap-pages.xml" | grep -q "/guides/$SLUG?lang=ar" || rollback
echo "DEPLOYED OK"
python3 - <<'PY' || echo "IndexNow ping failed (deploy is fine)"
import json, urllib.request
key = open("/var/www/quantum_saas/data/indexnow.key").read().strip()
slug = "gulf-banks-post-quantum-cryptography-requirements"
urls = [f"https://ather-quantum.com/guides/{slug}?lang={l}" for l in ("ar", "en")] + [
    "https://ather-quantum.com/guides?lang=ar", "https://ather-quantum.com/feed.xml", "https://ather-quantum.com/llms.txt"]
body = json.dumps({"host": "ather-quantum.com", "key": key, "keyLocation": f"https://ather-quantum.com/{key}.txt", "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "QuantumAether-IndexNow/1.0"})
print("IndexNow:", urllib.request.urlopen(req, timeout=30).status)
PY
