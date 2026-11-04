#!/bin/bash
# Deploys owner-connection test marking (CLI/MCP/API scans from the owner's connection count as tests). Backs up first.
set -e
cd /root/quantum-aether
B=/root/backups/pre-owner-$(date +%Y%m%d%H%M); mkdir -p "$B"
cp -p /var/www/quantum_saas/{quantum_saas_app.py,sales_db.py} "$B"/
for f in quantum_saas_app.py sales_db.py; do install -o root -g root -m 644 "$f" "/var/www/quantum_saas/$f"; done
systemctl restart quantum_saas; sleep 4; systemctl is-active quantum_saas
for p in "/?lang=en" /site/github.com /adoption/countries; do curl -s -o /dev/null -w "$p: %{http_code}\n" "https://ather-quatum.cloud$p"; done
runuser -u quantum -- /var/www/quantum_saas/.venv/bin/python -c "
import sqlite3; c=sqlite3.connect('/var/lib/quantum_saas/quantum_saas.db'); print('owner_clients table rows:', c.execute('select count(*) from owner_clients').fetchone()[0])"
journalctl -u quantum_saas --since "-2min" --no-pager | grep -ciE "traceback" || true
echo "backup: $B"
