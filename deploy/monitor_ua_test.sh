#!/bin/bash
# 2026-11-22: SealKeeperBot (synthetic MCP/API checker, scans example.com every few hours) -> is_test.
# Deploys quantum_saas_app.py (backup/smoke/rollback in deploy_files.py), then re-labels its past scans as tests
# (DB copy kept next to the code backup).
set -e
cd /root/quantum-aether
C=$(git log -1 --format=%h --grep='SealKeeperBot synthetic checks')
python3 deploy/deploy_files.py --base "$C^" --tag monitor-ua --expect '/?lang=en::<title>' quantum_saas_app.py
DB=/var/lib/quantum_saas/quantum_saas.db
/var/www/quantum_saas/.venv312/bin/python - "$DB" <<'PY'
import sqlite3, sys, datetime
db = sys.argv[1]
src = sqlite3.connect(db)
bak = db + ".pre-monitor-ua-" + datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
src.backup(sqlite3.connect(bak)); print("db backup:", bak)
# client 4b12bcab... = 34.96.45.183 (SealKeeperBot), the only non-owner example.com scan source since 2026-11-21
with src:
    n = src.execute("UPDATE scans SET is_test = 1 WHERE is_test = 0 AND client_hash LIKE '4b12bcab%'").rowcount
print("re-labelled scans:", n)
PY
git add deploy/monitor_ua_test.sh && git commit -q -m "deploy: monitor_ua_test.sh

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || true
git fetch -q origin && git rebase -q origin/main && git push -q origin main && echo pushed
echo DONE
