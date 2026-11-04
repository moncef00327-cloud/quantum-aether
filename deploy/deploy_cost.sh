#!/bin/bash
# Deploys the scorecard cost update (~$123/month after the Vultr credit). Backs up first.
set -e
cd /root/quantum-aether
B=/root/backups/pre-cost-$(date +%Y%m%d%H%M); mkdir -p "$B"
cp -p /var/www/quantum_saas/scorecard.py /var/www/quantum_saas/templates/admin.html "$B"/
for f in scorecard.py templates/admin.html; do install -o root -g root -m 644 "$f" "/var/www/quantum_saas/$f"; done
systemctl restart quantum_saas; sleep 3; systemctl is-active quantum_saas
cd /var/www/quantum_saas && runuser -u quantum -- bash -c 'set -a; . /etc/quantum_saas.env; set +a; .venv/bin/python3 scorecard_job.py --dry-run' | tail -3
echo "backup: $B"
