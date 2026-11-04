#!/bin/bash
# Deploys the sales batch (findings on result page, free change alerts, scan source) + agency pack ($199 / 10 reports).
# Backs up code + DB first.
set -e
cd /root/quantum-aether
B=/root/backups/pre-sales-$(date +%Y%m%d%H%M); mkdir -p "$B"
cp -rp /var/www/quantum_saas/{analytics_db.py,sales_db.py,quantum_saas_app.py,monitor_job.py,legal.py,i18n.py,scorecard.py,templates,static} "$B"/
runuser -u quantum -- /var/www/quantum_saas/.venv/bin/python -c "
import sqlite3; s=sqlite3.connect('/var/lib/quantum_saas/quantum_saas.db'); d=sqlite3.connect('/var/lib/quantum_saas/pre-sales-backup.db'); s.backup(d)"
mv /var/lib/quantum_saas/pre-sales-backup.db "$B"/quantum_saas.db
for f in analytics_db.py sales_db.py quantum_saas_app.py monitor_job.py legal.py i18n.py free_alerts.py packs.py scorecard.py \
         templates/scan.html templates/alerts.html templates/index.html templates/site_page.html templates/_scan_box.html \
         templates/admin.html templates/agency.html templates/pack.html templates/llms.txt \
         static/app.js static/style.css static/pack-checkout.js; do
  install -o root -g root -m 644 "$f" "/var/www/quantum_saas/$f"
done
systemctl restart quantum_saas; sleep 4; systemctl is-active quantum_saas
for p in "/?lang=ar" /site/github.com /datenschutz /agb /deadlines "/agency?lang=ar" /static/pack-checkout.js; do
  curl -s -o /dev/null -w "$p: %{http_code}\n" "https://ather-quatum.cloud$p"
done
curl -s -o /dev/null -w "/alerts/confirm/bad (want 404): %{http_code}\n" https://ather-quatum.cloud/alerts/confirm/nope
runuser -u quantum -- /var/www/quantum_saas/.venv/bin/python -c "
import sqlite3; c=sqlite3.connect('/var/lib/quantum_saas/quantum_saas.db')
print('packs table:', c.execute('select count(*) from packs').fetchone()[0], '| free_alerts table:', c.execute('select count(*) from free_alerts').fetchone()[0], '| scans.source column:', 'source' in [r[1] for r in c.execute('pragma table_info(scans)')])"
journalctl -u quantum_saas --since "-2min" --no-pager | grep -ciE "traceback" || true
echo "backup: $B"
