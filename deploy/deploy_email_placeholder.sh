#!/usr/bin/env bash
# Email field example (2026-11-14): "security@<scanned domain>" -> "you@company.com" in every trial/ProofLab form.
# The first real trial used exactly security@<domain>, i.e. likely the copied example, not a mailbox they read.
# Copies 5 files, bumps app.js ?v= in command_home.html; refuses if any of them changed on live since BASE.
# Rollback: bash deploy/deploy_email_placeholder.sh rollback
set -euo pipefail
LIVE=/var/www/quantum_saas
REPO="$(cd "$(dirname "$0")/.." && pwd)"
BASE=5c0b170
STAMP=/root/backups/email-placeholder.last
COPY=(static/command/app.js templates/command/ar.html templates/command/en.html templates/_trial_cta.html templates/prooflab.html)
VERSIONED=templates/command_home.html

smoke() {
  for p in "/?lang=ar" "/?lang=en" "/monitoring?lang=en" "/prooflab?lang=en" "/scan/example.com" "/static/command/app.js"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: ather-quantum.com" -H "X-Forwarded-Proto: https" \
      -A "Mozilla/5.0 QA-deploy-smoke" "http://127.0.0.1:8000$p")
    echo "smoke $p $code"; [[ "$code" =~ ^(200|404)$ ]] || return 1
  done
  n=$(curl -s -H "Host: ather-quantum.com" -H "X-Forwarded-Proto: https" -A "Mozilla/5.0 QA-deploy-smoke" \
      "http://127.0.0.1:8000/?lang=en" | grep -o 'security@' | wc -l)
  echo "security@ left on home: $n"; [[ "$n" -eq 0 ]]
}

if [[ "${1:-}" == "rollback" ]]; then
  B="$(cat "$STAMP")"
  for f in "${COPY[@]}" "$VERSIONED"; do cp -a "$B/$f" "$LIVE/$f"; done
  systemctl restart quantum_saas; sleep 4; smoke || true; echo "ROLLED BACK from $B"; exit 0
fi

for f in "${COPY[@]}"; do
  git -C "$REPO" show "$BASE:$f" | cmp -s - "$LIVE/$f" || { echo "live $f changed since $BASE - stop"; exit 1; }
done
grep -qF 'command/app.js?v=20261114-ui1"' "$LIVE/$VERSIONED" || { echo "$VERSIONED has no ui1 app.js version - stop"; exit 1; }

B="/root/backups/pre-email-placeholder-$(date -u +%Y%m%d%H%M%S)"
for f in "${COPY[@]}" "$VERSIONED"; do mkdir -p "$B/$(dirname "$f")"; cp -a "$LIVE/$f" "$B/$f"; done
echo "$B" > "$STAMP"; echo "backup: $B"

for f in "${COPY[@]}"; do cp "$REPO/$f" "$LIVE/$f"; done
sed -i 's/command\/app\.js?v=20261114-ui1"/command\/app.js?v=20261114-ui2"/' "$LIVE/$VERSIONED"
grep -oE 'command/app\.js\?v=[^"]+' "$LIVE/$VERSIONED"

systemctl restart quantum_saas; sleep 4
smoke || { echo "SMOKE FAILED - rolling back"; bash "$0" rollback; exit 1; }
echo "DONE"
