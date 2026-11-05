#!/bin/bash
# Deploys merged traffic sources in admin (LinkedIn variants -> one row). Backs up first.
set -e
cd /root/quantum-aether
B=/root/backups/pre-sources-$(date +%Y%m%d%H%M); mkdir -p "$B"
cp -p /var/www/quantum_saas/analytics_db.py "$B"/
install -o root -g root -m 644 analytics_db.py /var/www/quantum_saas/analytics_db.py
systemctl restart quantum_saas; sleep 4; systemctl is-active quantum_saas
for p in "/?lang=en" /site/github.com; do curl -s -o /dev/null -w "$p: %{http_code}\n" "https://ather-quatum.cloud$p"; done
journalctl -u quantum_saas --since "-2min" --no-pager | grep -ciE "traceback" || true
echo "backup: $B"
