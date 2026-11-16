#!/usr/bin/env python3
"""Build a source-linked PQC/TLS intelligence feed from official RSS/Atom sources.

This uses deterministic topic rules (no LLM/API key) and stores article metadata only;
the takeaways are explicitly editorial prompts, not claims from the linked sources.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "analytics" / "news_feed.json"
MAX_AGE_DAYS = 180
MAX_ITEMS = 80
MAX_RESPONSE_BYTES = 3_000_000

SOURCES = [
    ("IBM Research", "https://research.ibm.com/rss", "ibm.com"),
    ("Google Blog", "https://blog.google/rss/", "blog.google"),
    ("Cloudflare Blog", "https://blog.cloudflare.com/rss", "blog.cloudflare.com"),
    ("NIST Cybersecurity", "https://www.nist.gov/news-events/cybersecurity/rss.xml", "www.nist.gov"),
    ("NIST Standards", "https://www.nist.gov/news-events/standards/rss.xml", "www.nist.gov"),
    ("arXiv quant-ph", "https://rss.arxiv.org/rss/quant-ph", "arxiv.org"),
    ("arXiv cs.CR", "https://rss.arxiv.org/rss/cs.CR", "arxiv.org"),
]

PQC_TERMS = (
    "post-quantum", "post quantum", "postquantum", "ml-kem", "mlkem", "kyber",
    "dilithium", "slh-dsa", "x25519mlkem768", "quantum-safe", "quantum resistant",
    "harvest now, decrypt later", "cryptographic agility", "quantum cryptography",
)
VULN_TERMS = ("vulnerability", "vulnerabilities", "vulnerable", "security advisory", "cve-")
STANDARD_TERMS = ("nist", "fips", "standards", "standardization", "transition", "migration", "guidance", "roadmap")
IMPLEMENTATION_TERMS = ("tls", "openssl", "cloudflare", "nginx", "browser", "deployment", "implementation")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value: str) -> str:
    parser = _Text()
    parser.feed(value or "")
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            result = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_source(source):
    name, url, expected_host = source
    request = Request(url, headers={"User-Agent": "QuantumAether-PQC-Intelligence/1.0 (+https://ather-quantum.com/analytics)"})
    with urlopen(request, timeout=15) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError("feed response exceeded 3 MB")
    root = ET.fromstring(payload)
    entries = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1].lower()
        if tag not in ("item", "entry"):
            continue
        values = {}
        for child in node:
            key = child.tag.rsplit("}", 1)[-1].lower()
            if key == "link":
                link = child.attrib.get("href") or child.text or ""
                if child.attrib.get("rel") in (None, "alternate"):
                    values.setdefault(key, link.strip())
            elif key in ("title", "description", "summary", "content", "pubdate", "published", "updated", "date", "guid", "id"):
                values.setdefault(key, "".join(child.itertext()).strip())
        link = (values.get("link") or values.get("guid") or values.get("id") or "").strip()
        parsed = urlparse(link)
        if parsed.scheme != "https" or not parsed.hostname or not (parsed.hostname == expected_host or parsed.hostname.endswith("." + expected_host)):
            continue
        title = plain(values.get("title", ""))
        description = plain(values.get("description") or values.get("summary") or values.get("content") or "")
        published = parse_date(values.get("published") or values.get("pubdate") or values.get("updated") or values.get("date"))
        if title:
            entries.append({"source": name, "url": link, "title": title[:300], "description": description[:1400], "published_at": published})
    return name, entries


def classify(entry):
    text = f"{entry['title']} {entry['description']}".lower()
    pq_specific = (any(term in text for term in PQC_TERMS)
                   or bool(re.search(r"\bpqc\b", text)))
    crypto_context = any(term in text for term in ("cryptography", "cryptographic", "encryption", "rsa",
                                                    "elliptic curve", "public key", "tls"))
    quantum_threat = ("quantum computer" in text or "quantum computers" in text or "shor" in text)
    if not (pq_specific or (quantum_threat and crypto_context)):
        return None
    if any(term in text for term in VULN_TERMS):
        category = "vulnerability"
        importance = "high"
    elif ("nist" in entry["source"].lower()
          or (any(term in text for term in STANDARD_TERMS)
              and any(term in entry["title"].lower() for term in ("standard", "transition", "migration", "guidance", "roadmap")))):
        category = "standards"
        importance = "high"
    elif any(term in text for term in IMPLEMENTATION_TERMS):
        category = "implementation"
        importance = "medium"
    else:
        category = "research"
        importance = "medium"
    takeaways = {
        "standards": {
            "en": "Editorial takeaway: compare your cryptographic inventory and migration plan with the linked guidance; scope and deadlines depend on the organization.",
            "ar": "قراءة تحريرية: قارن جرد التشفير وخطة الانتقال لديك بالإرشادات المرتبطة؛ يختلف النطاق والجدول حسب المؤسسة.",
            "de": "Redaktionelle Einordnung: Gleichen Sie Kryptoinventar und Migrationsplan mit den verlinkten Leitlinien ab; Umfang und Fristen hängen von der Organisation ab.",
        },
        "vulnerability": {
            "en": "Editorial takeaway: read the original advisory and verify affected products and versions; this headline alone does not show that X25519MLKEM768 is affected.",
            "ar": "قراءة تحريرية: راجع التنبيه الأصلي وتحقق من المنتجات والإصدارات المتأثرة؛ العنوان وحده لا يثبت تأثر X25519MLKEM768.",
            "de": "Redaktionelle Einordnung: Lesen Sie die Originalwarnung und prüfen Sie betroffene Produkte und Versionen; diese Meldung belegt allein keine Betroffenheit von X25519MLKEM768.",
        },
        "implementation": {
            "en": "Editorial takeaway: check relevant TLS library, proxy and CDN release notes, then retest the public endpoint after changes.",
            "ar": "قراءة تحريرية: راجع ملاحظات إصدار مكتبات TLS والوكيل وCDN ذات الصلة، ثم أعد فحص نقطة الاتصال العامة بعد التغييرات.",
            "de": "Redaktionelle Einordnung: Prüfen Sie relevante TLS-Bibliotheken, Proxy- und CDN-Änderungen und testen Sie den öffentlichen Endpunkt anschließend erneut.",
        },
        "research": {
            "en": "Editorial takeaway: research context, not a production security advisory or evidence of a new cryptographic break; assess before changing policy.",
            "ar": "قراءة تحريرية: هذا سياق بحثي، وليس تنبيهاً أمنياً للإنتاج أو دليلاً على كسر تشفيري جديد؛ قيّم النتائج قبل تغيير السياسة.",
            "de": "Redaktionelle Einordnung: Forschungskontext, keine Produktionswarnung und kein Beleg für einen neuen kryptografischen Bruch; vor einer Richtlinienänderung bewerten.",
        },
    }
    return {"category": category, "importance": importance, "takeaway": takeaways[category]}


def load_existing():
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"items": []}


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    old = load_existing()
    fetched, source_status = [], []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(fetch_source, source): source for source in SOURCES}
        for future, source in futures.items():
            try:
                name, entries = future.result()
                fetched.extend(entries)
                source_status.append({"name": name, "ok": True, "entries": len(entries)})
            except Exception as exc:
                source_status.append({"name": source[0], "ok": False, "error": type(exc).__name__})
    if not any(status["ok"] for status in source_status):
        print("All official feeds failed; leaving the existing feed unchanged.", file=sys.stderr)
        return 1
    now = datetime.now(timezone.utc)
    healthy_sources = {source["name"] for source in source_status if source["ok"]}
    # Replace each healthy source's RSS window on refresh so a formerly broad classification
    # cannot linger in the public feed. Keep prior entries only for sources that failed this run.
    merged = {item.get("url"): item for item in old.get("items", [])
              if item.get("url") and item.get("source") not in healthy_sources}
    new_count = 0
    for entry in fetched:
        analyzed = classify(entry)
        if analyzed is None:
            continue
        published = parse_date(entry.get("published_at"))
        if published and datetime.fromisoformat(published.replace("Z", "+00:00")) < now - timedelta(days=MAX_AGE_DAYS):
            continue
        item = {k: entry[k] for k in ("source", "url", "title", "published_at")}
        item.update(analyzed)
        item["id"] = hashlib.sha256(entry["url"].encode()).hexdigest()[:16]
        if entry["url"] not in merged:
            new_count += 1
        merged[entry["url"]] = item
    items = list(merged.values())
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    items = [item for item in items if not item.get("published_at") or datetime.fromisoformat(item["published_at"].replace("Z", "+00:00")) >= cutoff]
    items.sort(key=lambda item: item.get("published_at") or "", reverse=True)
    document = {
        "schema_version": 1,
        "updated_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "classification": "Deterministic keyword rules; impact notes are editorial context, not source quotations or security advisories.",
        "sources": source_status,
        "items": items[:MAX_ITEMS],
    }
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    try:
        output_label = OUTPUT.relative_to(ROOT)
    except ValueError:
        output_label = OUTPUT
    print(f"Updated {output_label}: {len(document['items'])} items, {new_count} new, "
          f"{sum(1 for source in source_status if source['ok'])}/{len(SOURCES)} feeds available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
