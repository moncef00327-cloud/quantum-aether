#!/usr/bin/env python3
"""Submit every URL in the live sitemaps of ather-quantum.com to IndexNow (Bing, Yandex, Seznam, Naver, Yep...).

Usage: python3 deploy/indexnow_submit.py [--dry-run] [--key-file data/indexnow.key]
The key file is served by the app at https://ather-quantum.com/<key>.txt (route indexnow_key); keyLocation points there.
Max 10,000 URLs per request (IndexNow limit). Only URLs on ather-quantum.com are sent.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

HOST = "ather-quantum.com"
BASE = f"https://{HOST}"
ENDPOINT = "https://api.indexnow.org/indexnow"
UA = {"User-Agent": "QuantumAether-IndexNow/1.1"}
BATCH = 10000


def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read().decode("utf-8")


def sitemap_urls():
    index = fetch(f"{BASE}/sitemap.xml")
    maps = re.findall(r"<loc>([^<]+)</loc>", index)
    urls = []
    for m in maps:
        urls += re.findall(r"<loc>([^<]+)</loc>", fetch(m.replace("&amp;", "&")))
    urls = [u.replace("&amp;", "&") for u in urls]
    seen, out = set(), []
    for u in urls:
        if u.startswith(BASE + "/") and u not in seen:
            seen.add(u)
            out.append(u)
    return maps, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--key-file", default=os.path.join(os.path.dirname(__file__), "..", "data", "indexnow.key"))
    a = ap.parse_args()
    key = open(a.key_file).read().strip()
    key_url = f"{BASE}/{key}.txt"
    served = fetch(key_url).strip()
    if served != key:
        sys.exit(f"key file at {key_url} does not match {a.key_file} - stop")
    maps, urls = sitemap_urls()
    print(f"sitemaps: {len(maps)}  urls: {len(urls)}  keyLocation: {BASE}/<key>.txt (verified)")
    if a.dry_run:
        return
    failed = False
    for i in range(0, len(urls), BATCH):
        body = json.dumps({"host": HOST, "key": key, "keyLocation": key_url, "urlList": urls[i:i + BATCH]}).encode()
        req = urllib.request.Request(ENDPOINT, data=body, headers=dict(UA, **{"Content-Type": "application/json; charset=utf-8"}))
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                status, text = r.status, r.read().decode("utf-8", "replace")[:200]
        except urllib.error.HTTPError as e:
            status, text, failed = e.code, e.read().decode("utf-8", "replace")[:200], True
        print(f"batch {i // BATCH + 1}: {len(urls[i:i + BATCH])} urls -> HTTP {status} {text.strip()}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
