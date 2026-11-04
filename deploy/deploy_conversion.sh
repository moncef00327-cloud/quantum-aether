#!/bin/bash
# Deploys the conversion batch (events, example chips, OG images, /deadlines). Installs Pillow. Backs up first.
set -e
cd /root/quantum-aether
B=/root/backups/pre-conversion-$(date +%Y%m%d%H%M); mkdir -p "$B"
cp -rp /var/www/quantum_saas/{analytics_db.py,sales_db.py,quantum_saas_app.py,scorecard.py,i18n.py,templates,static} "$B"/
/var/www/quantum_saas/.venv/bin/pip install -q "Pillow==12.3.0"
mkdir -p /var/www/quantum_saas/data/fonts
for f in analytics_db.py sales_db.py quantum_saas_app.py scorecard.py og_image.py deadlines.py i18n.py requirements.txt \
         templates/base.html templates/index.html templates/scan.html templates/site_page.html templates/admin.html \
         templates/deadlines.html templates/guides_index.html templates/llms.txt static/app.js static/style.css \
         data/fonts/DejaVuSans-Bold.ttf data/fonts/DejaVuSans.ttf data/fonts/DejaVu-LICENSE.txt; do
  install -o root -g root -m 644 "$f" "/var/www/quantum_saas/$f"
done
systemctl restart quantum_saas; sleep 4; systemctl is-active quantum_saas
for p in "/?lang=ar" /deadlines "/deadlines?lang=de" /site/github.com /og/default.png /og/site/github.com.png /badge/microsoft.com.svg /sitemap-pages.xml /feed.xml; do
  curl -s -o /dev/null -w "$p: %{http_code} %{content_type}\n" "https://ather-quatum.cloud$p"
done
curl -s -o /dev/null -w "/api/ev: %{http_code}\n" -X POST -A "QuantumAether-QA-bot" -d '{"name":"focus","page":"/"}' https://ather-quatum.cloud/api/ev
journalctl -u quantum_saas --since "-2min" --no-pager | grep -ciE "traceback" || true
python3 - <<'PY'
import json, urllib.request
key = open("/var/www/quantum_saas/data/indexnow.key").read().strip()
urls = [f"https://ather-quatum.cloud/deadlines?lang={l}" for l in ("en", "ar", "de")] + ["https://ather-quatum.cloud/?lang=en", "https://ather-quatum.cloud/?lang=ar"]
body = json.dumps({"host": "ather-quatum.cloud", "key": key, "keyLocation": f"https://ather-quatum.cloud/{key}.txt", "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "QuantumAether-IndexNow/1.0"})
print("IndexNow:", urllib.request.urlopen(req, timeout=30).status)
PY
echo "backup: $B"
