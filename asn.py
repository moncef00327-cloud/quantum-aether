# asn.py — من عنوان IP إلى الشبكة المشغّلة (استضافة أو CDN)، من قاعدة iptoasn.com المفتوحة (PDDL).
# بحث ثنائي في الذاكرة على حوالي 540 ألف نطاق عناوين. يُحدَّث الملف شهرياً من المهمة الأسبوعية.
import bisect
import gzip
import ipaddress
import os
import re
import time
import urllib.request

SOURCE_URL = "https://iptoasn.com/data/ip2asn-v4.tsv.gz"
MAX_AGE_DAYS = 30


def ensure_database(path, max_age_days=MAX_AGE_DAYS, fetch=None):
    """ينزّل القاعدة إن غابت أو قدُمت. فشل التنزيل لا يوقف شيئاً إن وُجدت نسخة قديمة."""
    fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400
    if fresh:
        return path
    try:
        data = (fetch or _download)(SOURCE_URL)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        if not os.path.exists(path):
            raise
    return path


def _download(url):
    req = urllib.request.Request(url, headers={"User-Agent": "QuantumAether/1.0 (+https://ather-quatum.cloud/scanning)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


HANDLE = re.compile(r"^[A-Z0-9-]+$")


def provider_name(description):
    """اسم مقروء للشبكة. «CLOUDFLARENET - Cloudflare, Inc.» و«HETZNER-AS Hetzner Online GmbH» و«OVH OVH SAS»
    تصير «Cloudflare, Inc.» و«Hetzner Online GmbH» و«OVH SAS». تطبيقها مرتين لا يغيّر النتيجة."""
    description = (description or "").strip()
    if " - " in description:
        return description.split(" - ", 1)[1].strip()
    first, _, rest = description.partition(" ")
    if rest and HANDLE.match(first) and ("-" in first or any(c.isdigit() for c in first) or len(first) >= 10
                                         or rest.upper().startswith(first)):
        return rest.strip()
    return description


class AsnLookup:
    def __init__(self, path):
        starts, ends, info = [], [], []
        opener = gzip.open if path.endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 5 or parts[2] == "0":  # 0 = غير موجّه
                    continue
                try:
                    starts.append(int(ipaddress.IPv4Address(parts[0])))
                    ends.append(int(ipaddress.IPv4Address(parts[1])))
                except ValueError:
                    continue
                info.append((int(parts[2]), provider_name(parts[4])))
        self.starts, self.ends, self.info = starts, ends, info

    def lookup(self, ip):
        """يعيد (رقم الشبكة ASN، اسم المشغّل) أو (None, None)."""
        try:
            value = int(ipaddress.IPv4Address(ip))
        except (ValueError, TypeError):
            return None, None
        i = bisect.bisect_right(self.starts, value) - 1
        if i >= 0 and value <= self.ends[i]:
            return self.info[i]
        return None, None
