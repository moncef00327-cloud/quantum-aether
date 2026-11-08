#!/bin/bash
# Deploy only the offline Gravity tool; preserve the currently active web release.
set -euo pipefail
cd /root/quantum-aether
target=$(readlink -f /var/www/quantum_saas)
backup=$(mktemp -d /root/backups/pre-gravity-XXXXXXXX)
for file in gravity.py GRAVITY_ENGINE.md; do
  if [ -e "$target/$file" ]; then
    cp -p "$target/$file" "$backup/$file"
  else
    touch "$backup/$file.absent"
  fi
done
rollback() {
  for file in gravity.py GRAVITY_ENGINE.md; do
    if [ -e "$backup/$file.absent" ]; then
      rm -f "$target/$file"
    else
      cp -p "$backup/$file" "$target/$file"
    fi
  done
}
trap rollback ERR
for file in gravity.py GRAVITY_ENGINE.md; do
  install -o root -g root -m 644 "$file" "$target/$file"
done
PYTHONDONTWRITEBYTECODE=1 python3 - "$target" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import gravity
assert gravity.opportunities([]) == []
assert gravity.evidence_url('https://github.com/a/b/issues/1?utm_source=test', 'GitHub') == 'https://github.com/a/b/issues/1'
PY
systemctl is-active --quiet quantum_saas
for path in '/?lang=en' /site/github.com; do
  code=$(curl --max-time 25 --silent --show-error --output /dev/null --write-out '%{http_code}' "https://ather-quantum.com$path")
  [ "$code" = 200 ]
  echo "$path: $code"
done
trap - ERR
echo "Deployed offline Gravity tool to $target"
echo "Backup: $backup"
