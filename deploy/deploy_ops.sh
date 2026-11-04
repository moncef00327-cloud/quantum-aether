#!/bin/bash
# Deploys: snapshot cache + indexes, uptime watchdog (every 5 min), weekly scorecard (Mon 07:00 UTC). Backs up first.
set -e
cd /root/quantum-aether
B=/root/backups/pre-ops-$(date +%Y%m%d%H%M)
mkdir -p "$B"
cp -rp /var/www/quantum_saas/{adoption.py,quantum_saas_app.py,templates} "$B"/
for f in adoption.py quantum_saas_app.py scorecard.py scorecard_job.py uptime_check.py templates/admin.html; do
  ref=/var/www/quantum_saas/quantum_saas_app.py
  install -o "$(stat -c %U "$ref")" -g "$(stat -c %G "$ref")" -m 644 "$f" "/var/www/quantum_saas/$f"
done
for u in quantum_uptime.service quantum_uptime.timer quantum_scorecard.service quantum_scorecard.timer; do
  install -m 644 "deploy/$u" "/etc/systemd/system/$u"
done
systemctl daemon-reload
systemctl restart quantum_saas
sleep 4
systemctl is-active quantum_saas
systemctl enable --now quantum_uptime.timer quantum_scorecard.timer
systemctl start quantum_uptime.service && journalctl -u quantum_uptime.service -n 2 --no-pager -o cat
systemctl list-timers quantum_uptime.timer quantum_scorecard.timer --no-pager | head -4
for p in / /site/github.com /llms-full.txt /adoption; do
  curl -s -o /dev/null -w "$p: %{http_code} %{time_total}s\n" "https://ather-quatum.cloud$p"
done
echo "backup: $B"
