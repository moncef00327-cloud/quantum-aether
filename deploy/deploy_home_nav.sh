#!/usr/bin/env bash
# Home + sidebar (2026-11-14):
#  - home keeps ONE input above the fold: the scanner. The hero trial form (0 trial starts from 220 home visitors
#    since 11-09) is removed; the sample result card (github/amazon/cloudflare) no longer offers to monitor a
#    domain the visitor does not own - it sends them to the scanner. The real trial card stays on /scan/<domain>.
#  - sidebar: collapsible group "For business & agencies" = Business & pricing, Agency pack · €199,
#    Full-domain audit · €490. ProofLab stays a top-level item. shell.js keeps each group's own saved state.
# Refuses if any copied file changed on live since BASE; bumps ?v= of app.css/app.js/shell.js.
# Rollback: bash deploy/deploy_home_nav.sh rollback
set -euo pipefail
LIVE=/var/www/quantum_saas
REPO="$(cd "$(dirname "$0")/.." && pwd)"
BASE=00e55ac
STAMP=/root/backups/home-nav.last
COPY=(static/command/app.css static/command/app.js static/command/shell.js templates/command/ar.html templates/command/en.html
      templates/command/sidebar-ar.html templates/command/sidebar-en.html)
VERSIONED=(templates/base.html templates/command_home.html)

smoke() {
  for p in "/?lang=ar" "/?lang=en" "/audit?lang=ar" "/agency?lang=en" "/pricing?lang=ar" "/scan/example.com" \
           "/static/command/app.js" "/static/command/shell.js"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: ather-quantum.com" -H "X-Forwarded-Proto: https" \
      -A "Mozilla/5.0 QA-deploy-smoke" "http://127.0.0.1:8000$p")
    echo "smoke $p $code"; [[ "$code" == 200 ]] || return 1
  done
  page=$(curl -s -H "Host: ather-quantum.com" -H "X-Forwarded-Proto: https" -A "Mozilla/5.0 QA-deploy-smoke" "http://127.0.0.1:8000/?lang=ar")
  a=$(printf '%s' "$page" | grep -o 'href="/audit?lang=ar"' | wc -l); g=$(printf '%s' "$page" | grep -o 'href="/agency?lang=ar"' | wc -l)
  t=$(printf '%s' "$page" | grep -o 'id="home-result-trial"' | wc -l)
  echo "home: audit links $a, agency links $g, sample trial forms $t"; [[ $a -ge 1 && $g -ge 1 && $t -eq 0 ]]
}

if [[ "${1:-}" == "rollback" ]]; then
  B="$(cat "$STAMP")"
  for f in "${COPY[@]}" "${VERSIONED[@]}"; do cp -a "$B/$f" "$LIVE/$f"; done
  systemctl restart quantum_saas; sleep 4; smoke || true; echo "ROLLED BACK from $B"; exit 0
fi

for f in "${COPY[@]}"; do
  git -C "$REPO" show "$BASE:$f" | cmp -s - "$LIVE/$f" || { echo "live $f changed since $BASE - stop"; exit 1; }
done
grep -qF 'command/app.css?v=20261114-ui1"' "$LIVE/templates/base.html" || { echo "base.html: unexpected app.css version - stop"; exit 1; }
grep -qF 'command/shell.js?v=20261114-b2"' "$LIVE/templates/base.html" || { echo "base.html: unexpected shell.js version - stop"; exit 1; }
grep -qF 'command/app.js?v=20261114-ui2"' "$LIVE/templates/command_home.html" || { echo "command_home.html: unexpected app.js version - stop"; exit 1; }

B="/root/backups/pre-home-nav-$(date -u +%Y%m%d%H%M%S)"
for f in "${COPY[@]}" "${VERSIONED[@]}"; do mkdir -p "$B/$(dirname "$f")"; cp -a "$LIVE/$f" "$B/$f"; done
echo "$B" > "$STAMP"; echo "backup: $B"

for f in "${COPY[@]}"; do cp "$REPO/$f" "$LIVE/$f"; done
sed -i -e 's/command\/app\.css?v=20261114-ui1"/command\/app.css?v=20261114-ui3"/' \
       -e 's/command\/app\.js?v=20261114-ui2"/command\/app.js?v=20261114-ui3"/' \
       -e 's/command\/shell\.js?v=20261114-b2"/command\/shell.js?v=20261114-ui3"/' "${VERSIONED[@]/#/$LIVE/}"
grep -hoE 'command/(app\.css|app\.js|shell\.js)\?v=[^"]+' "${VERSIONED[@]/#/$LIVE/}" | sort | uniq -c

systemctl restart quantum_saas; sleep 4
smoke || { echo "SMOKE FAILED - rolling back"; bash "$0" rollback; exit 1; }
echo "DONE"
