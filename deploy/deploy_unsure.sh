#!/bin/bash
# Deploys the "undetermined" adoption status + % column + homepage text. Backs up first.
set -e
cd /root/quantum-aether
B=/root/backups/pre-unsure-$(date +%Y%m%d%H%M)
mkdir -p "$B"
cp -rp /var/www/quantum_saas/{adoption.py,i18n.py,quantum_saas_app.py,templates} "$B"/
cp /var/lib/quantum_saas/quantum_saas.db "$B"/
for f in adoption.py i18n.py quantum_saas_app.py templates/adoption.html templates/site_page.html; do
  dst=/var/www/quantum_saas/$f
  install -o "$(stat -c %U "$dst")" -g "$(stat -c %G "$dst")" -m "$(stat -c %a "$dst")" "$f" "$dst"
done
systemctl restart quantum_saas
sleep 4
systemctl is-active quantum_saas
curl -s -o /dev/null -w "adoption page: %{http_code}\n" https://ather-quatum.cloud/adoption
# Mark rows whose key-exchange probe was blocked (column is added on app start).
runuser -u quantum -- /var/www/quantum_saas/.venv/bin/python - <<'PY'
import sqlite3
c = sqlite3.connect("/var/lib/quantum_saas/quantum_saas.db")
n = c.execute("UPDATE adoption_results SET unsure=1 WHERE ok=1 AND (grp IS NULL OR grp='') "
              "AND pq=0 AND COALESCE(tls,'')<>'TLSv1.2'").rowcount
c.commit()
print("rows marked undetermined:", n)
PY
echo "backup: $B"
