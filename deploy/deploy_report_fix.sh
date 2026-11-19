#!/bin/bash
# Deploy fixed daily_report_job.py (bars scaled to peak + alerts@ather-quantum.com)
set -e
cd /root/quantum-aether
mkdir -p /root/backups
cp -p /var/www/quantum_saas/daily_report_job.py /root/backups/daily_report_job.py.pre-bars-$(date +%Y%m%d%H%M)
O=$(stat -c %U:%G /var/www/quantum_saas/daily_report_job.py)
cp daily_report_job.py /var/www/quantum_saas/daily_report_job.py
chown "$O" /var/www/quantum_saas/daily_report_job.py
diff -q daily_report_job.py /var/www/quantum_saas/daily_report_job.py && echo "DEPLOYED"
git add daily_report_job.py deploy/deploy_report_fix.sh
git commit -qm "daily report: scale 7-day bars to peak; correct alerts@ather-quantum.com" && echo COMMITTED || true
