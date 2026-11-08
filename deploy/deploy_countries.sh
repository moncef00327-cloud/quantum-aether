#!/bin/bash
# Deploys the country ranking (/adoption/countries). Backs up first, then pings IndexNow.
set -e
cd /root/quantum-aether
B=/root/backups/pre-countries-$(date +%Y%m%d%H%M); mkdir -p "$B"
cp -rp /var/www/quantum_saas/{quantum_saas_app.py,og_image.py,i18n.py,templates} "$B"/
for f in countries.py quantum_saas_app.py og_image.py i18n.py templates/countries.html templates/country.html \
         templates/adoption.html templates/site_page.html templates/llms.txt; do
  install -o root -g root -m 644 "$f" "/var/www/quantum_saas/$f"
done
systemctl restart quantum_saas; sleep 4; systemctl is-active quantum_saas
for p in "/adoption/countries?lang=ar" /adoption/countries/at /adoption/countries/de /adoption/countries.json /og/country/at.png /site/spiegel.de /adoption /feed.xml /sitemap-pages.xml; do
  curl -s -o /dev/null -w "$p: %{http_code}\n" "https://ather-quantum.com$p"
done
journalctl -u quantum_saas --since "-2min" --no-pager | grep -ciE "traceback" || true
python3 - <<'PY'
import json, re, urllib.request
ua = {"User-Agent": "QuantumAether-IndexNow/1.0"}
sm = urllib.request.urlopen(urllib.request.Request("https://ather-quantum.com/sitemap-pages.xml", headers=ua), timeout=30).read().decode()
urls = [u.replace("&amp;", "&") for u in re.findall(r"<loc>([^<]+)</loc>", sm) if "/adoption/countries" in u]
key = open("/var/www/quantum_saas/data/indexnow.key").read().strip()
body = json.dumps({"host": "ather-quantum.com", "key": key, "keyLocation": f"https://ather-quantum.com/{key}.txt", "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8", **ua})
print("IndexNow:", len(urls), "urls ->", urllib.request.urlopen(req, timeout=30).status)
PY
echo "backup: $B"
