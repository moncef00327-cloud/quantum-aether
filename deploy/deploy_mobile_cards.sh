#!/usr/bin/env bash
# Mobile home fix (2026-11-14): on phones (<=600px) the stats card and the grade card (which now carries the
# 14-day trial form) each take the full row instead of half, so the form no longer wraps one word per line.
# Deploys only static/command/app.css and bumps its ?v= in base.html and command_home.html (other live edits kept).
# Rollback: bash deploy/deploy_mobile_cards.sh rollback
set -euo pipefail
LIVE=/var/www/quantum_saas
REPO="$(cd "$(dirname "$0")/.." && pwd)"
STAMP=/root/backups/mobile-cards.last
OLD_V='app.css?v=20261114-t4"'; NEW_V='app.css?v=20261114-ui1"'

smoke() {
  for p in "/?lang=ar" "/?lang=en" "/monitoring" "/static/command/app.css"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: ather-quantum.com" -H "X-Forwarded-Proto: https" \
      -A "Mozilla/5.0 QA-deploy-smoke" "http://127.0.0.1:8000$p")
    echo "smoke $p $code"; [[ "$code" == 200 ]] || return 1
  done
}

if [[ "${1:-}" == "rollback" ]]; then
  B="$(cat "$STAMP")"
  cp -a "$B/app.css" "$LIVE/static/command/app.css"
  cp -a "$B/base.html" "$B/command_home.html" "$LIVE/templates/"
  systemctl restart quantum_saas; sleep 4; smoke; echo "ROLLED BACK"; exit 0
fi

grep -qF "$OLD_V" "$LIVE/templates/base.html" || { echo "base.html no longer has $OLD_V - stop, check by hand"; exit 1; }
grep -qF "$OLD_V" "$LIVE/templates/command_home.html" || { echo "command_home.html no longer has $OLD_V - stop"; exit 1; }
git -C "$REPO" show HEAD~1:static/command/app.css | cmp -s - "$LIVE/static/command/app.css" \
  || { echo "live app.css changed since this fix was built - stop, rebuild first"; exit 1; }

B="/root/backups/pre-mobile-cards-$(date -u +%Y%m%d%H%M%S)"; mkdir -p "$B"
cp -a "$LIVE/static/command/app.css" "$LIVE/templates/base.html" "$LIVE/templates/command_home.html" "$B/"
echo "$B" > "$STAMP"; echo "backup: $B"

cp "$REPO/static/command/app.css" "$LIVE/static/command/app.css"
sed -i "s/app\.css?v=20261114-t4\"/app.css?v=20261114-ui1\"/" "$LIVE/templates/base.html" "$LIVE/templates/command_home.html"
grep -hF "$NEW_V" "$LIVE/templates/base.html" "$LIVE/templates/command_home.html" | sed 's/^ */version: /'

systemctl restart quantum_saas; sleep 4
smoke || { echo "SMOKE FAILED - rolling back"; bash "$0" rollback; exit 1; }
echo "DONE"
