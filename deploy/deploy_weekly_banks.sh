#!/usr/bin/env bash
# Deploy the weekly bank post-quantum tracker (/banks/weekly, ar/en/de) + its LinkedIn texts in the Monday scorecard email.
# Usage: bash deploy/deploy_weekly_banks.sh            (deploy)
#        bash deploy/deploy_weekly_banks.sh check      (only verify live files are unchanged since BASE)
#        bash deploy/deploy_weekly_banks.sh rollback   (restore the backup taken by the last deploy)
set -euo pipefail
SRC=/root/quantum-aether; LIVE=/var/www/quantum_saas; URL=https://ather-quantum.com
BASE=8e399fc
CHANGED=(quantum_saas_app.py scorecard_job.py)
NEW=(weekly_banks.py templates/weekly_banks.html tests/test_weekly_banks.py)
LAST=/root/backups/weekly-banks-last

restore() {
  for f in "${CHANGED[@]}"; do install -m 644 -o root -g root "$1/$(basename "$f")" "$LIVE/$f"; done
  for f in "${NEW[@]}"; do rm -f "$LIVE/$f"; done
  systemctl restart quantum_saas
}
if [ "${1:-}" = rollback ]; then B=$(cat "$LAST"); restore "$B"; echo "rolled back to $B"; exit 0; fi

for f in "${CHANGED[@]}"; do
  git -C "$SRC" show "$BASE:$f" | cmp -s - "$LIVE/$f" || { echo "live $f differs from $BASE - aborting, nothing changed"; exit 1; }
done
for f in "${NEW[@]}"; do [ ! -e "$LIVE/$f" ] || { echo "live $f already exists - aborting"; exit 1; }; done
echo "live files match $BASE"
[ "${1:-}" = check ] && exit 0

B=/root/backups/pre-weekly-banks-$(date -u +%Y%m%d%H%M%S); mkdir -p "$B"
for f in "${CHANGED[@]}"; do cp -p "$LIVE/$f" "$B/"; done; echo "$B" > "$LAST"; echo "backup: $B"
rollback() { echo "CHECK FAILED - rolling back"; restore "$B"; exit 1; }
for f in "${CHANGED[@]}" "${NEW[@]}"; do install -m 644 -o root -g root "$SRC/$f" "$LIVE/$f"; done
systemctl restart quantum_saas; sleep 3
systemctl is-active --quiet quantum_saas || rollback
for u in / "/banks/weekly?lang=ar" "/banks/weekly?lang=en" "/banks/weekly?lang=de" "/banks/weekly/2026-W47.json" \
         "/banks/arab-banks-2026-11?lang=ar" "/sitemap-pages.xml" "/guides?lang=ar"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL$u"); echo "$u $code"; [ "$code" = 200 ] || rollback
done
P=$(curl -s "$URL/banks/weekly?lang=de")
grep -q '<html lang="de"' <<<"$P" || rollback
grep -q 'www.abnamro.nl' <<<"$P" || rollback
S=$(curl -s "$URL/sitemap-pages.xml"); grep -q '/banks/weekly/2026-W47' <<<"$S" || rollback
cd "$LIVE" && sudo -u quantum env QS_DATA_DIR=/var/lib/quantum_saas .venv312/bin/python -c \
  "import sales_db,weekly_banks;print(weekly_banks.as_text(weekly_banks.build(sales_db.connect('/var/lib/quantum_saas/quantum_saas.db'))).splitlines()[0])" || rollback
echo "DEPLOYED OK"
python3 - <<'PY' || echo "IndexNow ping failed (deploy is fine)"
import json, urllib.request
key = open("/var/www/quantum_saas/data/indexnow.key").read().strip()
urls = [f"https://ather-quantum.com/banks/weekly{p}?lang={l}" for p in ("", "/2026-W47", "/2026-W46") for l in ("en", "ar", "de")]
body = json.dumps({"host": "ather-quantum.com", "key": key, "keyLocation": f"https://ather-quantum.com/{key}.txt", "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "QuantumAether-IndexNow/1.0"})
print("IndexNow:", urllib.request.urlopen(req, timeout=30).status)
PY
