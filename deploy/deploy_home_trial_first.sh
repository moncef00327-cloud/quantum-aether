#!/usr/bin/env bash
# Home (2026-11-15, owner request): trial email form FIRST, scanner second, in the same top card.
# ("scan" and "monitor" together at the top); the example list moved below it. The domain field is shared with
# the scanner, so a domain typed once is used by both. Trial events keep data-trial-source="home".
# Copies 4 built files, bumps app.css/app.js ?v= to 20261114-ui5. Refuses if live changed since BASE.
# Rollback: bash deploy/deploy_home_trial.sh rollback
set -euo pipefail
LIVE=/var/www/quantum_saas
REPO="$(cd "$(dirname "$0")/.." && pwd)"
BASE=961630b
STAMP=/root/backups/home-trial-first.last
COPY=(static/command/app.css static/command/app.js templates/command/ar.html templates/command/en.html)
VERSIONED=(templates/base.html templates/command_home.html)

smoke() {
  for p in "/?lang=ar" "/?lang=en" "/monitoring?lang=ar" "/audit?lang=ar" "/static/command/app.js"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: ather-quantum.com" -H "X-Forwarded-Proto: https" \
      -A "Mozilla/5.0 QA-deploy-smoke" "http://127.0.0.1:8000$p")
    echo "smoke $p $code"; [[ "$code" == 200 ]] || return 1
  done
  n=$(curl -s -H "Host: ather-quantum.com" -H "X-Forwarded-Proto: https" -A "Mozilla/5.0 QA-deploy-smoke" \
      "http://127.0.0.1:8000/?lang=ar" | grep -o 'id="trial"' | wc -l)
  echo "home trial form: $n"; [[ "$n" -eq 1 ]]
}

if [[ "${1:-}" == "rollback" ]]; then
  B="$(cat "$STAMP")"
  for f in "${COPY[@]}" "${VERSIONED[@]}"; do cp -a "$B/$f" "$LIVE/$f"; done
  systemctl restart quantum_saas; sleep 4; smoke || true; echo "ROLLED BACK from $B"; exit 0
fi

for f in "${COPY[@]}"; do
  git -C "$REPO" show "$BASE:$f" | cmp -s - "$LIVE/$f" || { echo "live $f changed since $BASE - stop"; exit 1; }
done
grep -qF 'command/app.css?v=20261114-ui4"' "$LIVE/templates/base.html" || { echo "base.html: unexpected app.css version - stop"; exit 1; }
grep -qF 'command/app.js?v=20261114-ui4"' "$LIVE/templates/command_home.html" || { echo "command_home.html: unexpected app.js version - stop"; exit 1; }

B="/root/backups/pre-home-trial-first-$(date -u +%Y%m%d%H%M%S)"
for f in "${COPY[@]}" "${VERSIONED[@]}"; do mkdir -p "$B/$(dirname "$f")"; cp -a "$LIVE/$f" "$B/$f"; done
echo "$B" > "$STAMP"; echo "backup: $B"

for f in "${COPY[@]}"; do cp "$REPO/$f" "$LIVE/$f"; done
sed -i -e 's/command\/app\.css?v=20261114-ui4"/command\/app.css?v=20261114-ui5"/' \
       -e 's/command\/app\.js?v=20261114-ui4"/command\/app.js?v=20261114-ui5"/' "${VERSIONED[@]/#/$LIVE/}"
grep -hoE 'command/(app\.css|app\.js)\?v=[^"]+' "${VERSIONED[@]/#/$LIVE/}" | sort | uniq -c

systemctl restart quantum_saas; sleep 4
smoke || { echo "SMOKE FAILED - rolling back"; bash "$0" rollback; exit 1; }
echo "DONE"
