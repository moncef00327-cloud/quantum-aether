#!/usr/bin/env bash
# Home UI fixes (2026-11-14):
#  1) phones (<=600px): stats card and grade card (with the 14-day trial form) each take the full row,
#     so the form no longer wraps one word per line;
#  2) ProofLab link restored in the home-page menu (it was only hand-added to the sidebar of other pages;
#     now it comes from frontend/command/App.tsx, so future builds keep it).
# Copies the built frontend files and bumps ?v= of app.css/app.js in base.html and command_home.html
# (other live edits in those two templates are kept). Refuses to run if any copied file changed on live
# since base commit 79bef0c.
# Rollback: bash deploy/deploy_mobile_cards.sh rollback
set -euo pipefail
LIVE=/var/www/quantum_saas
REPO="$(cd "$(dirname "$0")/.." && pwd)"
BASE=79bef0c
STAMP=/root/backups/mobile-cards.last
COPY=(static/command/app.css static/command/app.js templates/command/ar.html templates/command/en.html
      templates/command/sidebar-ar.html templates/command/sidebar-en.html)
VERSIONED=(templates/base.html templates/command_home.html)

smoke() {
  for p in "/?lang=ar" "/?lang=en" "/monitoring?lang=ar" "/prooflab?lang=ar" "/guides?lang=en" "/static/command/app.css" "/static/command/app.js"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: ather-quantum.com" -H "X-Forwarded-Proto: https" \
      -A "Mozilla/5.0 QA-deploy-smoke" "http://127.0.0.1:8000$p")
    echo "smoke $p $code"; [[ "$code" == 200 ]] || return 1
  done
  n=$(curl -s -H "Host: ather-quantum.com" -H "X-Forwarded-Proto: https" -A "Mozilla/5.0 QA-deploy-smoke" \
      "http://127.0.0.1:8000/?lang=ar" | grep -o 'href="/prooflab?lang=ar"' | wc -l)
  echo "home ProofLab links: $n (1 before this fix)"; [[ "$n" -ge 2 ]]
}

if [[ "${1:-}" == "rollback" ]]; then
  B="$(cat "$STAMP")"
  for f in "${COPY[@]}" "${VERSIONED[@]}"; do cp -a "$B/$f" "$LIVE/$f"; done
  systemctl restart quantum_saas; sleep 4; smoke || true; echo "ROLLED BACK from $B"; exit 0
fi

for f in "${COPY[@]}"; do
  git -C "$REPO" show "$BASE:$f" | cmp -s - "$LIVE/$f" || { echo "live $f changed since $BASE - stop, rebuild first"; exit 1; }
done
for f in "${VERSIONED[@]}"; do
  grep -qE 'command/app\.(css|js)\?v=20261114-t4"' "$LIVE/$f" || { echo "$f has no t4 asset version - stop, check by hand"; exit 1; }
done

B="/root/backups/pre-mobile-cards-$(date -u +%Y%m%d%H%M%S)"
for f in "${COPY[@]}" "${VERSIONED[@]}"; do mkdir -p "$B/$(dirname "$f")"; cp -a "$LIVE/$f" "$B/$f"; done
echo "$B" > "$STAMP"; echo "backup: $B"

for f in "${COPY[@]}"; do cp "$REPO/$f" "$LIVE/$f"; done
sed -i -E 's/(command\/app\.(css|js))\?v=20261114-t4"/\1?v=20261114-ui1"/g' "${VERSIONED[@]/#/$LIVE/}"
grep -hoE 'command/app\.(css|js)\?v=[^"]+' "${VERSIONED[@]/#/$LIVE/}" | sort | uniq -c

systemctl restart quantum_saas; sleep 4
smoke || { echo "SMOKE FAILED - rolling back"; bash "$0" rollback; exit 1; }
echo "DONE"
