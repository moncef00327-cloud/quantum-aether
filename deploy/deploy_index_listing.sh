#!/usr/bin/env bash
# Deploy commit "Discovery: Atom feed and llms.txt list every published section" onto the LIVE tree.
# Applies only this commit's diff with patch(1), so other edits already live in the same files are kept.
# Steps: dry-run on a copy -> full tests on the patched copy -> backup -> apply -> restart -> smoke -> IndexNow (new pages only).
# Rollback: bash deploy/deploy_index_listing.sh rollback
set -euo pipefail
LIVE=/var/www/quantum_saas
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$LIVE/.venv312/bin/python"
STAMP_FILE=/root/backups/index-listing.last
FILES=(quantum_saas_app.py templates/llms.txt)

if [[ "${1:-}" == "rollback" ]]; then
  B="$(cat "$STAMP_FILE")"
  for f in "${FILES[@]}"; do cp -a "$B/$f" "$LIVE/$f"; done
  rm -f "$LIVE/tests/test_index_listing.py"
  systemctl restart quantum_saas; sleep 3
  curl -fsS -o /dev/null -w "rollback: feed %{http_code}\n" -H "Host: ather-quantum.com" http://127.0.0.1:8000/feed.xml
  exit 0
fi

PATCH="$(mktemp)"; git -C "$REPO" diff 8ec2261~1 8ec2261 -- "${FILES[@]}" > "$PATCH"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK" "$PATCH"' EXIT
rsync -a --exclude .venv --exclude .venv312 --exclude __pycache__ --exclude node_modules "$LIVE/" "$WORK/"
(cd "$WORK" && patch -p1 --quiet < "$PATCH")
cp "$REPO/tests/test_index_listing.py" "$WORK/tests/"
echo "== full tests on patched copy of live"
(cd "$WORK" && PYTHONPATH=.:tests "$PY" -m unittest discover -s tests -t . 2>&1 | grep -E "^(Ran|OK|FAILED)")
(cd "$WORK" && PYTHONPATH=.:tests "$PY" -m unittest discover -s tests -t . >/dev/null 2>&1) || { echo "TESTS FAILED - nothing deployed"; exit 1; }

B="/root/backups/pre-index-listing-$(date -u +%Y%m%d%H%M%S)"; mkdir -p "$B/templates"
for f in "${FILES[@]}"; do cp -a "$LIVE/$f" "$B/$f"; done; echo "$B" > "$STAMP_FILE"; echo "backup: $B"
(cd "$LIVE" && patch -p1 --quiet < "$PATCH")
cp "$REPO/tests/test_index_listing.py" "$LIVE/tests/"
systemctl restart quantum_saas; sleep 4

H=(-H "Host: ather-quantum.com" -H "X-Forwarded-Proto: https" -A "Mozilla/5.0 QA-deploy-smoke")
for p in / /feed.xml /llms.txt /sitemap.xml /prooflab /banks/arab-banks-2026-11; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "${H[@]}" "http://127.0.0.1:8000$p"); echo "smoke $p $code"
  [[ "$code" == 200 ]] || { echo "SMOKE FAILED - rolling back"; bash "$0" rollback; exit 1; }
done
n=$(curl -s "${H[@]}" http://127.0.0.1:8000/feed.xml | grep -c "<entry>"); echo "feed entries: $n"

echo "== IndexNow (new/changed URLs only)"
KEY="$(cat "$LIVE/data/indexnow.key")"
"$PY" - "$KEY" <<'EOF'
import json, re, sys, urllib.error, urllib.request
key = sys.argv[1]; base = "https://ather-quantum.com"
paths = {"/prooflab", "/banks/arab-banks-2026-11", "/adoption/dach-hosting", "/exposure", "/tools/pq-tls-config",
         "/audit", "/press", "/guides"}
sm = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8000/sitemap-pages.xml", headers={
    "Host": "ather-quantum.com", "X-Forwarded-Proto": "https", "User-Agent": "Mozilla/5.0 QA-deploy-smoke"}), timeout=30).read().decode()
locs = [u.replace("&amp;", "&") for u in re.findall(r"<loc>([^<]+)</loc>", sm)]
urls = [base + "/feed.xml", base + "/llms.txt"] + [u for u in locs if u.split("?")[0][len(base):] in paths]
body = json.dumps({"host": "ather-quantum.com", "key": key, "keyLocation": f"{base}/{key}.txt", "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                             headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "QuantumAether-IndexNow/1.1"})
try:
    print("IndexNow", urllib.request.urlopen(req, timeout=30).status, len(urls), "URLs")
except urllib.error.HTTPError as e:
    print("IndexNow HTTP", e.code)
EOF
echo "DONE"
