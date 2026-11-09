#!/usr/bin/env bash
# Move production from Python 3.10 to 3.12 so Pillow 13 (39 advisories fixed) can be installed.
# Builds a NEW venv next to the old one, runs the full test suite with it, then points the systemd
# units at it. The old venv stays untouched: rollback = `bash deploy/upgrade_python312.sh rollback`.
set -euo pipefail
LIVE=/var/www/quantum_saas
SRC=/root/quantum-aether
OLD=$LIVE/.venv
NEW=$LIVE/.venv312
UNITS="quantum_saas quantum_adoption quantum_adoption_monthly quantum_monitor quantum_scorecard quantum_uptime"

if [ "${1:-}" = rollback ]; then
  for u in $UNITS; do sed -i "s#$NEW/#$OLD/#g" /etc/systemd/system/$u.service; done
  systemctl daemon-reload && systemctl restart quantum_saas && systemctl is-active quantum_saas
  echo "Rolled back to $OLD"; exit 0
fi

# 1. Python 3.12 (deadsnakes PPA: the standard source for newer Python on Ubuntu 22.04)
if ! command -v python3.12 >/dev/null; then
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get install -y python3.12 python3.12-venv
fi

# 2. New venv with the same pinned requirements (Pillow 13 is selected on Python >= 3.11)
rm -rf "$NEW"
python3.12 -m venv "$NEW"
"$NEW/bin/pip" install -q --upgrade pip
"$NEW/bin/pip" install -q -r "$SRC/requirements.txt"
"$NEW/bin/python" -c "import PIL, flask; print('Pillow', PIL.__version__)"

# 3. Full test suite with the new interpreter; abort (nothing switched) if anything fails
cd "$SRC" && PYTHONPATH=.:tests "$NEW/bin/python" -m unittest discover -s tests -t . 2>&1 | tail -3
PYTHONPATH=.:tests "$NEW/bin/python" -m unittest discover -s tests -t . >/dev/null 2>&1 || { echo "TESTS FAILED - not switching"; exit 1; }

# 4. Switch every unit to the new venv, restart, health-check; auto-rollback on failure
cp "$SRC/requirements.txt" "$LIVE/requirements.txt"
for u in $UNITS; do
  cp -p /etc/systemd/system/$u.service /root/backups/$u.service.pre-py312
  sed -i "s#$OLD/#$NEW/#g" /etc/systemd/system/$u.service
done
systemctl daemon-reload
systemctl restart quantum_saas
sleep 5
if systemctl is-active -q quantum_saas && curl -fsS -o /dev/null https://ather-quantum.com/ && curl -fsS -o /dev/null https://ather-quantum.com/og/default.png; then
  echo "OK: production now runs $("$NEW/bin/python" -V) with Pillow $("$NEW/bin/python" -c 'import PIL;print(PIL.__version__)')"
else
  echo "Health check failed - rolling back"; bash "$0" rollback; exit 1
fi
