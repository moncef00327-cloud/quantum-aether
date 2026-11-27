#!/usr/bin/env python3
"""Reverse DACH IT-Dienstleister (MSP) Proof Radar & Compliant Outreach Queue.

Instead of waiting for IT service providers to search for NIS2/PQC TLS audits, this radar:
  1) Discovers DACH IT-Dienstleister / Systemhaus / Managed IT candidates (curated pool + optional DuckDuckGo web discovery),
  2) Fetches each company's public Impressum page to extract ONLY official B2B business addresses (info@/kontakt@/office@/vertrieb@)
     and STRICTLY REJECTS security.txt / CSIRT / abuse / datenschutz / noreply addresses,
  3) Runs a live Quantum Aether TLS probe (including PQ-supported-but-not-preferred server misconfig detection!),
  4) Prioritizes verified leads into /root/outreach/msp-radar-queue.csv and /var/lib/quantum_saas/msp_radar.json,
  5) Renders (--dry-run) or sends (--send, explicit flag only) personalized German MSP Pilot (290 EUR, 50 hostnames)
     emails with live TLS proof, RFC 8058 one-click unsubscribe (/u/<token>), and strict suppression checks.

Usage:
  python3 tools/msp_reverse_radar.py --discover [--search] [--limit 25]
  python3 tools/msp_reverse_radar.py --dry-run [--limit 5]
  python3 tools/msp_reverse_radar.py --send [--limit 10 --daily-cap 10 --pause 45]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import os
from pathlib import Path
import pwd
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import outreach_suppress as osup  # noqa: E402
import quantum_vuln_scanner as qs  # noqa: E402

ENV_FILE = "/etc/quantum_saas.env"
DATA_DIR = os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas")
DB_PATH = os.path.join(DATA_DIR, "quantum_saas.db")
QUEUE_CSV = "/root/outreach/msp-radar-queue.csv"
STATE_JSON = os.path.join(DATA_DIR, "msp_radar.json")
PAUSE_FILE = os.path.join(DATA_DIR, "msp_outreach.paused")
SITE = "https://ather-quantum.com"
FROM = "Quantum Aether Team <sales@ather-quantum.com>"
REPLY_TO = "reply@mail.ather-quantum.com"
USER_AGENT = "Mozilla/5.0 (compatible; QuantumAetherMSPRadar/1.0; +https://ather-quantum.com/partners)"

# Strictly allow B2B business/sales/general Impressum mailboxes; NEVER security/CSIRT/privacy/support!
PREFERRED_PREFIXES = ("vertrieb", "sales", "business", "partner", "kontakt", "contact", "office", "info", "mail", "hallo", "hello", "anfrage")
FORBIDDEN_PREFIXES = (
    "security", "csirt", "cert", "soc", "infosec", "abuse", "noc", "postmaster", "hostmaster", "webmaster",
    "noreply", "no-reply", "donotreply", "datenschutz", "privacy", "dsb", "dpo", "gdpr", "dsgvo",
    "bewerbung", "karriere", "jobs", "hr", "recruiting", "support", "helpdesk", "ticket", "billing", "buchhaltung", "rechnung",
)

EMAIL_RE = re.compile(r"\b([a-zA-Z0-9._%+-]{1,64}@[a-zA-Z0-9.-]+\.(?:de|at|ch|eu|com|net|io|it))\b")
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
IMPRESSUM_HREF_RE = re.compile(r'href=["\']([^"\']*(?:impressum|imprint|kontakt|legal)[^"\']*)["\']', re.I)

# Curated DACH Systemhaus / IT-Dienstleister / MSP seed pool (DE / AT / CH)
CURATED_DACH_MSPS = [
    ("DE", "computacenter.de"),
    ("DE", "bechtle.com"),
    ("DE", "cancom.de"),
    ("DE", "sva.de"),
    ("DE", "netgo.de"),
    ("DE", "medialine.com"),
    ("DE", "kramerundcrew.de"),
    ("DE", "sepago.de"),
    ("DE", "axians.de"),
    ("DE", "plusserver.com"),
    ("DE", "claranet.de"),
    ("DE", "arvato-systems.de"),
    ("DE", "materna.de"),
    ("DE", "adesso.de"),
    ("DE", "consol.de"),
    ("DE", "noris.de"),
    ("DE", "heinlein-support.de"),
    ("DE", "syseleven.de"),
    ("DE", "netways.de"),
    ("DE", "b1-systems.de"),
    ("DE", "univention.de"),
    ("DE", "secunet.com"),
    ("DE", "rohde-schwarz.com"),
    ("DE", "syss.de"),
    ("DE", "usd.de"),
    ("DE", "ernw.de"),
    ("DE", "cure53.de"),
    ("DE", "schutzwerk.com"),
    ("DE", "it-novum.com"),
    ("DE", "credativ.de"),
    ("AT", "acp.at"),
    ("AT", "snt.at"),
    ("AT", "conova.com"),
    ("AT", "ntx.at"),
    ("AT", "nessus.at"),
    ("AT", "world4you.com"),
    ("AT", "anexia.com"),
    ("AT", "easyname.com"),
    ("AT", "sba-research.org"),
    ("AT", "sec-consult.com"),
    ("AT", "radarcs.com"),
    ("AT", "ikarussecurity.com"),
    ("AT", "x-tention.com"),
    ("AT", "fabasoft.com"),
    ("AT", "brz.gv.at"),
    ("CH", "infoguard.ch"),
    ("CH", "compass-security.com"),
    ("CH", "scip.ch"),
    ("CH", "nine.ch"),
    ("CH", "vshn.ch"),
    ("CH", "hostpoint.ch"),
    ("CH", "cybersystems.ch"),
    ("CH", "abraxas.ch"),
    ("CH", "bison-group.com"),
    # Wave-5+ DACH mid-market Systemhäuser, MSPs & InfoSec firms
    ("DE", "datagroup.de"),
    ("DE", "controlware.de"),
    ("DE", "it-haus.com"),
    ("DE", "timetoact.de"),
    ("DE", "mittwald.de"),
    ("DE", "manitu.de"),
    ("DE", "dogado.de"),
    ("DE", "secorvo.de"),
    ("DE", "x41-dsec.de"),
    ("DE", "mgm-sp.com"),
    ("DE", "koramis.de"),
    ("DE", "genua.de"),
    ("DE", "intevation.de"),
    ("DE", "gonicus.de"),
    ("DE", "ip-projects.de"),
    ("DE", "netcup.de"),
    ("DE", "proact.de"),
    ("DE", "q-beyond.de"),
    ("DE", "all-for-one.com"),
    ("DE", "synaix.de"),
    ("DE", "teuto.net"),
    ("DE", "profihost.com"),
    ("DE", "space.net"),
    ("DE", "artfiles.de"),
    ("DE", "punkt.de"),
    ("AT", "ebcont.com"),
    ("AT", "internex.at"),
    ("AT", "edis.at"),
    ("AT", "sil.at"),
    ("AT", "netconomy.net"),
    ("AT", "itdesign.at"),
    ("CH", "umb.ch"),
    ("CH", "netcloud.ch"),
    ("CH", "everyware.ch"),
    ("CH", "green.ch"),
    ("CH", "init7.net"),
    ("CH", "bedag.ch"),
    ("CH", "elca.ch"),
    ("CH", "redguard.ch"),
    ("CH", "dreamlab.net"),
]

SEARCH_QUERIES = [
    '"IT-Dienstleister" "Impressum" "Managed Services" site:.de',
    '"Systemhaus" "Impressum" "IT-Sicherheit" site:.de',
    '"IT-Dienstleister" "Impressum" "NIS2" site:.at',
    '"Managed Service Provider" "Impressum" site:.at',
    '"IT-Dienstleister" "Impressum" "ISO 27001" site:.ch',
]


def load_env(path: str = ENV_FILE) -> None:
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def keep_owner(path: str) -> None:
    try:
        pw = pwd.getpwnam("quantum")
        uid, gid = pw.pw_uid, pw.pw_gid
    except KeyError:
        return
    for suffix in ("", "-wal", "-shm", "-journal"):
        p = path + suffix
        if os.path.exists(p):
            try:
                os.chown(p, uid, gid)
            except OSError:
                pass


def is_valid_b2b_email(email: str, domain: str) -> bool:
    clean = osup.normalize(email)
    if not clean or "@" not in clean:
        return False
    local, _, edom = clean.partition("@")
    base_dom = domain.lower().removeprefix("www.")
    if edom != base_dom:
        return False
    if re.fullmatch(r"[0-9a-f]{16,}", local):
        return False
    if any(local == p or local.startswith(p + ".") or local.startswith(p + "-") or local.startswith(p + "_") for p in FORBIDDEN_PREFIXES):
        return False
    if re.search(r"(^|[._-])(sec|security|csirt|cert|abuse|privacy|dsb|dpo|feedback)([._-]|$)", local):
        return False
    if local in ("example", "test", "name", "vorname.nachname", "mustermann"):
        return False
    return True


def pick_best_b2b_email(emails: list[str], domain: str) -> str:
    valid = []
    seen = set()
    for raw in emails:
        clean = osup.normalize(raw)
        if clean and clean not in seen and is_valid_b2b_email(clean, domain):
            seen.add(clean)
            valid.append(clean)
    if not valid:
        return ""

    def rank(e: str) -> tuple[int, int]:
        local = e.partition("@")[0]
        for idx, pref in enumerate(PREFERRED_PREFIXES):
            if local == pref:
                return (0, idx)
            if local.startswith(pref):
                return (1, idx)
        return (2, len(local))

    valid.sort(key=rank)
    return valid[0]


def _fetch_html(url: str, timeout: float = 6.0) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        final_url = resp.geturl()
        body = resp.read(300_000).decode("utf-8", "replace")
        return final_url, body


def _deobfuscate_emails(text: str) -> str:
    s = html.unescape(text)
    s = re.sub(r"\s*\[(?:at|ät)\]\s*|\s*\((?:at|ät)\)\s*", "@", s, flags=re.I)
    s = re.sub(r"\s*\[(?:dot|punkt)\]\s*|\s*\((?:dot|punkt)\)\s*", ".", s, flags=re.I)
    return s


def extract_impressum(domain: str, timeout: float = 6.0, fetcher=_fetch_html) -> dict:
    """Fetch public Impressum (or homepage -> Impressum link) and extract official B2B email + company title."""
    candidates = [
        f"https://{domain}/impressum",
        f"https://www.{domain}/impressum",
        f"https://{domain}/imprint",
        f"https://{domain}/kontakt",
        f"https://{domain}/",
    ]
    visited = set()
    best_title = domain
    found_email = ""
    impressum_url = ""

    for url in candidates:
        if url in visited:
            continue
        visited.add(url)
        try:
            final_url, body = fetcher(url, timeout)
        except Exception:
            continue
        m_title = TITLE_RE.search(body)
        if m_title:
            cleaned_title = re.sub(r"\s+", " ", html.unescape(m_title.group(1))).strip()
            if cleaned_title and len(cleaned_title) <= 120:
                best_title = cleaned_title
        deobf = _deobfuscate_emails(body)
        email = pick_best_b2b_email(EMAIL_RE.findall(deobf), domain)
        if email:
            found_email = email
            impressum_url = final_url
            break
        if url.endswith("/"):
            for href in IMPRESSUM_HREF_RE.findall(body)[:3]:
                next_url = urllib.parse.urljoin(final_url, href)
                if next_url not in visited and domain in next_url:
                    candidates.append(next_url)

    return {"title": best_title, "email": found_email, "impressum_url": impressum_url}


def search_dach_msps(timeout: float = 8.0) -> list[tuple[str, str]]:
    """Optional web discovery via DuckDuckGo HTML for additional DACH IT-Dienstleister."""
    found: list[tuple[str, str]] = []
    seen = set()
    for q in SEARCH_QUERIES:
        country = "AT" if ".at" in q else ("CH" if ".ch" in q else "DE")
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q)
        try:
            _, body = _fetch_html(url, timeout=timeout)
        except Exception:
            continue
        for raw_u in re.findall(r'uddg=(https?%3A%2F%2F[^&"\']+)', body):
            target = urllib.parse.unquote(raw_u)
            host = (urllib.parse.urlsplit(target).hostname or "").lower().removeprefix("www.")
            if not host or host in seen or "." not in host:
                continue
            if any(bad in host for bad in ("duckduckgo.", "wikipedia.", "linkedin.", "xing.", "kununu.", "stepstone.", "indeed.", "heise.", "golem.", "github.", "youtube.", "facebook.", "instagram.", "google.")):
                continue
            if not host.endswith((".de", ".at", ".ch")):
                continue
            seen.add(host)
            found.append((country, host))
    return found


def already_contacted(conn: sqlite3.Connection, email: str, domain: str) -> bool:
    if osup.is_suppressed(conn, email, domain):
        return True
    if conn.execute("SELECT 1 FROM outreach_sent WHERE email = ? OR domain = ?", (email, domain)).fetchone():
        return True
    try:
        if conn.execute("SELECT 1 FROM growth_outreach WHERE email = ? OR domain = ?", (email, domain)).fetchone():
            return True
    except sqlite3.Error:
        pass
    return False


def probe_company_tls(domain: str, timeout: float = 6.0) -> dict:
    host = domain
    try:
        ip = qs.resolve_public_ip(host)
    except qs.ScanError:
        host = f"www.{domain}"
        ip = qs.resolve_public_ip(host)
    kx = qs.probe_key_exchange(ip, host, timeout=timeout)
    grade = "A" if (kx.get("pq") and kx.get("version") == "TLSv1.3") else ("B" if kx.get("version") == "TLSv1.3" else ("C" if kx.get("version") == "TLSv1.2" else "F"))
    return {
        "handshake_host": host,
        "tls_version": kx.get("version") or "",
        "group": kx.get("group") or "",
        "pq": bool(kx.get("pq")),
        "pq_supported_not_preferred": bool(kx.get("pq_supported_not_preferred")),
        "pq_supported_group": kx.get("pq_supported_group") or "",
        "grade": grade,
        "error": kx.get("error") or "",
    }


def priority_of(tls: dict) -> int:
    if tls.get("pq_supported_not_preferred"):
        return 1  # killer finding: server supports PQ, silently downgrades real browsers!
    if tls.get("grade") in ("C", "F"):
        return 2
    if tls.get("grade") == "B":
        return 3
    return 4


def render_msp_email(lead: dict, secret: str) -> dict:
    """Render owner-approved German MSP Pilot email enriched with a 1-line live TLS observation."""
    domain = lead["domain"]
    host = lead.get("handshake_host") or domain
    email = lead["email"]
    unsub_url = osup.unsubscribe_url(SITE, email, secret)
    scan_url = f"{SITE}/?domain={domain}&lang=de"

    if lead.get("pq_supported_not_preferred") and lead.get("pq_supported_group"):
        obs_line = (
            f"Kurz-Check heute für {host}: Ihr Server unterstützt zwar {lead['pq_supported_group']}, "
            f"bevorzugt in der Server-Reihenfolge aber klassisches {lead['group']} – "
            f"dadurch handeln Chrome, Firefox und Safari in der Praxis klassisch aus (Live-Prüfung: {scan_url})."
        )
    elif not lead.get("pq") and lead.get("tls_version"):
        obs_line = (
            f"Kurz-Check heute für {host}: {lead['tls_version']} mit klassischem Schlüsselaustausch {lead['group']} "
            f"(noch ohne hybrides X25519MLKEM768 – Live-Prüfung: {scan_url})."
        )
    else:
        obs_line = (
            f"Kurz-Check heute für {host}: bereits {lead.get('tls_version', 'TLSv1.3')} mit {lead.get('group', 'X25519MLKEM768')} "
            f"(sehr gut aufgestellt – bei den meisten Kundendomains fehlt das noch: {scan_url})."
        )

    subject = f"Post-Quanten-Check für Ihre Kunden ({domain}) – Pilot mit 3 Partnern"
    text = (
        "Guten Tag,\n\n"
        "laut EU-Fahrplan sollen die Mitgliedstaaten bis Ende 2026 mit dem Umstieg auf Post-Quanten-Kryptografie beginnen "
        "und Hochrisiko-Anwendungen bis spätestens 2030 umstellen. Viele Ihrer Kunden werden bald fragen, wo sie stehen – "
        "und die meisten wissen es nicht.\n\n"
        f"{obs_line}\n\n"
        "Mit Quantum Aether (ather-quantum.com) entwickle ich einen Scanner, der genau das für öffentliche TLS-Endpunkte prüft. "
        "Für drei IT-Dienstleister in Österreich, Deutschland und der Schweiz biete ich einen bezahlten Pilot an:\n\n"
        "– Prüfung von bis zu 50 Hostnamen eines Kunden Ihrer Wahl\n"
        "– Bericht auf Deutsch mit Ampel je Endpunkt: TLS-Version, hybrider Post-Quanten-Schlüsselaustausch, Zertifikat, priorisierte Maßnahmen\n"
        "– signierte Ed25519-Prüfbelege, die Ihr Kunde für seine Dokumentation (z. B. NIS2) nutzen kann\n"
        "– auf Wunsch mit Ihrem Logo\n"
        "– Lieferung innerhalb von 5 Werktagen, Pilotpreis 290 €\n\n"
        "Damit es keine Missverständnisse gibt: Der Bericht deckt die Transportverschlüsselung ab, keine vollständige Krypto-Inventur.\n\n"
        "Hätten Sie nächste Woche 15 Minuten für ein kurzes Gespräch? Infos: https://ather-quantum.com/partners?lang=de\n\n"
        "Viele Grüße\n"
        "Quantum Aether Team\n"
        "Quantum Aether, Sparkaßen 11/12, 5280 Braunau am Inn, Austria · https://ather-quantum.com/impressum\n\n"
        f"Kein Interesse? Abmelden mit einem Klick: {unsub_url} (oder einfach mit \"abmelden\" antworten)."
    )
    return {
        "subject": subject,
        "text": text,
        "headers": osup.list_unsubscribe_headers(SITE, email, secret, mailto=REPLY_TO),
    }


def discover_leads(
    conn: sqlite3.Connection,
    *,
    extra_domains: list[tuple[str, str]] | None = None,
    use_search: bool = False,
    limit: int = 25,
    queue_csv: str = QUEUE_CSV,
    state_json: str = STATE_JSON,
) -> list[dict]:
    osup.init(conn)
    pool: list[tuple[str, str]] = list(CURATED_DACH_MSPS)
    if extra_domains:
        pool.extend(extra_domains)
    if use_search:
        pool.extend(search_dach_msps())

    # Deduplicate while preserving order
    seen: set[str] = set()
    candidates: list[tuple[str, str]] = []
    for country, dom in pool:
        d = dom.strip().lower().removeprefix("www.")
        if not d or d in seen or d.endswith(".gv.at"):
            continue
        seen.add(d)
        candidates.append((country, d))

    leads: list[dict] = []
    for country, dom in candidates:
        if len(leads) >= limit:
            break
        if already_contacted(conn, "", dom):
            continue
        imp = extract_impressum(dom)
        if not imp["email"]:
            continue
        if already_contacted(conn, imp["email"], dom):
            continue
        try:
            tls = probe_company_tls(dom)
        except Exception:
            continue
        if tls.get("error") or not tls.get("tls_version"):
            continue
        leads.append({
            "priority": priority_of(tls),
            "country": country,
            "domain": dom,
            "title": imp["title"],
            "email": imp["email"],
            "impressum_url": imp["impressum_url"],
            "handshake_host": tls["handshake_host"],
            "tls_version": tls["tls_version"],
            "group": tls["group"],
            "pq": tls["pq"],
            "pq_supported_not_preferred": tls["pq_supported_not_preferred"],
            "pq_supported_group": tls["pq_supported_group"],
            "grade": tls["grade"],
            "discovered_at": now_iso(),
        })

    leads.sort(key=lambda r: (r["priority"], r["country"], r["domain"]))

    cols = [
        "priority", "country", "domain", "title", "email", "impressum_url",
        "handshake_host", "tls_version", "group", "pq", "pq_supported_not_preferred",
        "pq_supported_group", "grade", "discovered_at",
    ]
    qpath = Path(queue_csv)
    qpath.parent.mkdir(parents=True, exist_ok=True)
    with open(qpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in leads:
            w.writerow(row)

    spath = Path(state_json)
    spath.parent.mkdir(parents=True, exist_ok=True)
    tmp = spath.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps({"updated_at": now_iso(), "count": len(leads), "leads": leads}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(tmp, spath)
    keep_owner(str(spath))
    return leads


def read_queue(path: str = QUEUE_CSV) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r.get("email") or not r.get("domain"):
                continue
            r["pq"] = str(r.get("pq", "")).lower() == "true"
            r["pq_supported_not_preferred"] = str(r.get("pq_supported_not_preferred", "")).lower() == "true"
            out.append(r)
    return out


def sent_today(conn: sqlite3.Connection) -> int:
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    return conn.execute("SELECT COUNT(*) FROM outreach_sent WHERE substr(sent_at, 1, 10) = ?", (today,)).fetchone()[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--discover", action="store_true", help="discover verified DACH IT-Dienstleister + live TLS proof")
    mode.add_argument("--dry-run", action="store_true", help="preview personalized German MSP Pilot emails (sends nothing)")
    mode.add_argument("--send", action="store_true", help="send verified MSP Pilot queue via Resend (explicit flag)")
    ap.add_argument("--search", action="store_true", help="also run DuckDuckGo HTML discovery during --discover")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--daily-cap", type=int, default=10)
    ap.add_argument("--pause", type=float, default=45.0)
    ap.add_argument("--queue", default=QUEUE_CSV)
    ap.add_argument("--db", default=DB_PATH)
    a = ap.parse_args(argv)

    load_env()
    conn = sqlite3.connect(a.db, timeout=30)
    osup.init(conn)
    keep_owner(a.db)

    try:
        if a.discover:
            leads = discover_leads(conn, use_search=a.search, limit=a.limit, queue_csv=a.queue)
            print(f"discovered {len(leads)} verified DACH IT-Dienstleister leads -> {a.queue}")
            for row in leads:
                flag = f" [PQ-NOT-PREF:{row['pq_supported_group']}]" if row["pq_supported_not_preferred"] else ""
                print(f"  P{row['priority']} [{row['country']}] {row['domain']:26s} {row['email']:34s} Grade {row['grade']} ({row['tls_version']} {row['group']}){flag}")
            return 0

        secret = os.environ.get("QS_HASH_SALT", "")
        if not secret:
            sys.exit("QS_HASH_SALT missing")
        if a.send:
            if not os.environ.get("RESEND_API_KEY"):
                sys.exit("RESEND_API_KEY missing")
            if os.path.exists(PAUSE_FILE):
                sys.exit(f"paused: {PAUSE_FILE} exists")

        import requests
        http = requests.Session()
        budget = min(a.limit, max(0, a.daily_cap - sent_today(conn))) if a.send else a.limit
        done = 0
        for lead in read_queue(a.queue):
            if done >= budget:
                break
            email = osup.normalize(lead["email"])
            domain = lead["domain"].strip().lower()
            if not is_valid_b2b_email(email, domain) or already_contacted(conn, email, domain):
                continue
            mail = render_msp_email(lead, secret)
            if a.dry_run:
                print("=" * 72)
                print(f"To: {email} ({lead['country']} · Grade {lead['grade']})\nSubject: {mail['subject']}\n\n{mail['text']}")
                done += 1
                continue
            r = http.post(
                "https://api.resend.com/emails",
                timeout=20,
                headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}", "User-Agent": USER_AGENT},
                json={"from": FROM, "to": [email], "subject": mail["subject"], "text": mail["text"],
                      "reply_to": REPLY_TO, "headers": mail["headers"]},
            )
            if r.status_code >= 300:
                print(f"error {domain}: resend HTTP {r.status_code}")
                continue
            rid = r.json().get("id")
            kex_class = "hybrid-pq" if lead["pq"] else ("pq-not-preferred" if lead["pq_supported_not_preferred"] else "classical")
            with conn:
                conn.execute(
                    "INSERT INTO outreach_sent (email, domain, org, lang, kex_group, kex_class, subject, resend_id, sent_at)"
                    " VALUES (?, ?, ?, 'de', ?, ?, ?, ?, ?)",
                    (email, domain, lead.get("title", ""), lead.get("group", ""), kex_class, mail["subject"], rid, now_iso()),
                )
            keep_owner(a.db)
            done += 1
            print(f"sent {domain} -> {email} (Grade {lead['grade']}, {lead['group']}) id={rid}")
            time.sleep(a.pause)
        print(f"done: {done} {'rendered' if a.dry_run else 'sent'}")
        return 0
    finally:
        conn.close()
        keep_owner(a.db)


if __name__ == "__main__":
    sys.exit(main())
