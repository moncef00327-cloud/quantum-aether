#!/usr/bin/env bash
# Deploy OpenSEO audit fixes (2026-11-18): /analytics served in German for ?lang=de, distinct /gravity titles per language.
# Usage: bash deploy/deploy_seo_audit_fixes.sh            (deploy)
#        bash deploy/deploy_seo_audit_fixes.sh rollback   (restore the backup taken by the last deploy)
set -euo pipefail
SRC=/root/quantum-aether; LIVE=/var/www/quantum_saas; URL=https://ather-quantum.com
FILES=(quantum_saas_app.py templates/gravity.html)
LAST=/root/backups/seo-audit-fixes-last

restore() { for f in "${FILES[@]}"; do install -m 644 -o root -g root "$1/$(basename "$f")" "$LIVE/$f"; done; systemctl restart quantum_saas; }

if [ "${1:-}" = rollback ]; then B=$(cat "$LAST"); restore "$B"; echo "rolled back to $B"; exit 0; fi

# Refuse to overwrite live files that changed since the commit this deploy is based on.
for f in "${FILES[@]}"; do
  git -C "$SRC" show "HEAD~1:$f" | cmp -s - "$LIVE/$f" || { echo "live $f differs from HEAD~1 - aborting, nothing changed"; exit 1; }
done

B=/root/backups/pre-seo-audit-fixes-$(date -u +%Y%m%d%H%M%S); mkdir -p "$B"
for f in "${FILES[@]}"; do cp -p "$LIVE/$f" "$B/"; done; echo "$B" > "$LAST"; echo "backup: $B"
rollback() { echo "CHECK FAILED - rolling back"; restore "$B"; exit 1; }
for f in "${FILES[@]}"; do install -m 644 -o root -g root "$SRC/$f" "$LIVE/$f"; done
systemctl restart quantum_saas; sleep 3
systemctl is-active --quiet quantum_saas || rollback
for u in / "/analytics?lang=de" "/analytics?lang=en" "/gravity?lang=ar" "/gravity?lang=en" "/guides?lang=ar" "/site/github.com"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL$u"); echo "$u $code"; [ "$code" = 200 ] || rollback
done
curl -s "$URL/analytics?lang=de" | grep -q '<html lang="de"' || rollback
curl -s "$URL/analytics?lang=de" | grep -q 'rel="canonical" href="https://ather-quantum.com/analytics?lang=de"' || rollback
curl -s "$URL/gravity?lang=ar" | grep -q "<title>محرك اكتشاف الطلب التقني" || rollback
echo "DEPLOYED OK"
python3 - <<'PY' || echo "IndexNow ping failed (deploy is fine)"
import json, urllib.request
key = open("/var/www/quantum_saas/data/indexnow.key").read().strip()
urls = ["https://ather-quantum.com/analytics?lang=de", "https://ather-quantum.com/gravity?lang=ar", "https://ather-quantum.com/gravity?lang=en"]
body = json.dumps({"host": "ather-quantum.com", "key": key, "keyLocation": f"https://ather-quantum.com/{key}.txt", "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "QuantumAether-IndexNow/1.0"})
print("IndexNow:", urllib.request.urlopen(req, timeout=30).status)
PY
