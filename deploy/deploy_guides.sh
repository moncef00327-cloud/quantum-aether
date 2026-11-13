#!/usr/bin/env bash
# Deploy guides.py (Ubuntu 26.04 section + nginx won't-start troubleshooting): backup, copy, restart, check, rollback; IndexNow.
set -euo pipefail
SRC=/root/quantum-aether/guides.py; DST=/var/www/quantum_saas/guides.py
B=/root/backups/guides-$(date -u +%Y%m%d%H%M%S); mkdir -p "$B"; cp -p "$DST" "$B/"
echo "backup: $B"
rollback() { echo "CHECK FAILED - rolling back"; install -m 644 -o root -g root "$B/guides.py" "$DST"; systemctl restart quantum_saas; exit 1; }
install -m 644 -o root -g root "$SRC" "$DST"
systemctl restart quantum_saas; sleep 3
systemctl is-active --quiet quantum_saas || rollback
URL=https://ather-quantum.com
for u in / /guides "/guides/ubuntu-openssl-3-0-post-quantum-tls?lang=en" "/guides/ubuntu-openssl-3-0-post-quantum-tls?lang=ar" \
         "/guides/enable-x25519mlkem768-nginx?lang=en" "/guides/enable-x25519mlkem768-nginx?lang=ar"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL$u"); echo "$u $code"; [ "$code" = 200 ] || rollback
done
curl -s "$URL/guides/ubuntu-openssl-3-0-post-quantum-tls?lang=en" | grep -q "26.04 LTS: already on by default" || rollback
curl -s "$URL/guides/enable-x25519mlkem768-nginx?lang=en" | grep -q "nginx won&#39;t start\|nginx won't start" || rollback
echo "DEPLOYED OK"
python3 - <<'PY' || echo "IndexNow ping failed (deploy is fine)"
import json, urllib.request
key = open("/var/www/quantum_saas/data/indexnow.key").read().strip()
urls = [f"https://ather-quantum.com/guides/{s}?lang={l}" for s in ("ubuntu-openssl-3-0-post-quantum-tls", "enable-x25519mlkem768-nginx") for l in ("en", "ar")] + ["https://ather-quantum.com/feed.xml"]
body = json.dumps({"host": "ather-quantum.com", "key": key, "keyLocation": f"https://ather-quantum.com/{key}.txt", "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "QuantumAether-IndexNow/1.0"})
print("IndexNow:", urllib.request.urlopen(req, timeout=30).status)
PY
