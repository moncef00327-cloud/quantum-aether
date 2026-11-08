#!/bin/bash
# Deploys the crawler improvements (commit a0cef55): /site pages for ~8k domains, sitemap index,
# Last-Modified/304, llms-full.txt, security.txt, apple-touch-icon. Backs up first, then pings IndexNow.
set -e
cd /root/quantum-aether
B=/root/backups/pre-crawlers-$(date +%Y%m%d%H%M)
mkdir -p "$B"
cp -rp /var/www/quantum_saas/{adoption.py,i18n.py,quantum_saas_app.py,templates,static} "$B"/
for f in adoption.py i18n.py quantum_saas_app.py templates/site_page.html templates/base.html templates/llms.txt \
         static/style.css static/apple-touch-icon.png; do
  dst=/var/www/quantum_saas/$f
  ref=$dst; [ -e "$ref" ] || ref=$(dirname "$dst")/style.css
  install -o "$(stat -c %U "$ref")" -g "$(stat -c %G "$ref")" -m 644 "$f" "$dst"
done
systemctl restart quantum_saas
sleep 4
systemctl is-active quantum_saas
for p in / /site/github.com /sitemap.xml /sitemap-sites-1.xml /llms-full.txt /.well-known/security.txt /apple-touch-icon.png; do
  curl -s -o /dev/null -w "$p: %{http_code}\n" "https://ather-quantum.com$p"
done
curl -s -o /dev/null -w "/site/wp-login.php (want 404): %{http_code}\n" https://ather-quantum.com/site/wp-login.php
# IndexNow (Bing, Yandex, Seznam, Naver...): announce every sitemap URL, 10,000 per request.
python3 - <<'PY'
import json, re, urllib.request
base = "https://ather-quantum.com"
ua = {"User-Agent": "QuantumAether-IndexNow/1.0"}
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=ua), timeout=60).read().decode()
key = open("/var/www/quantum_saas/data/indexnow.key").read().strip()
urls = []
for part in re.findall(r"<loc>([^<]+)</loc>", get(base + "/sitemap.xml")):
    urls += re.findall(r"<loc>([^<]+)</loc>", get(part))
urls = [u.replace("&amp;", "&") for u in urls]
print("urls:", len(urls))
for i in range(0, len(urls), 10000):
    body = json.dumps({"host": "ather-quantum.com", "key": key, "keyLocation": f"{base}/{key}.txt",
                       "urlList": urls[i:i + 10000]}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8", **ua})
    with urllib.request.urlopen(req, timeout=60) as r:
        print("IndexNow batch", i // 10000 + 1, "->", r.status)
PY
echo "backup: $B"
