"""Build the paid estate-audit deliverable (HTML + PDF) for one organization.

    python tools/build_audit.py example.com --org "Example Bank AG" --lang de --out /root/audits

Runs a fresh subdomain discovery (Certificate Transparency names, up to discovery.MAX_HOSTS), looks up the
hosting network of each responding host, ranks hosts without post-quantum key exchange, and renders a dated
report. The PDF is printed with the local headless Chromium. Nothing is written to the production database.
"""
import argparse
import datetime as dt
import html
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402

import asn  # noqa: E402
import discovery  # noqa: E402
import guides  # noqa: E402
import quantum_vuln_scanner as qs  # noqa: E402

BASE_URL = "https://ather-quantum.com"
CHROMIUM = os.environ.get("CHROME_BIN", os.path.expanduser("~/.cache/ms-playwright/chromium-1140/chrome-linux/chrome"))
ASN_DB = os.environ.get("QS_ASN_DB", "/var/lib/quantum_saas/ip2asn-v4.tsv.gz")
# Host names that usually carry logins, payments or APIs: fix these first.
HIGH = ("login", "auth", "sso", "id", "account", "api", "online", "banking", "portal", "secure", "pay", "vpn",
        "mobile", "app", "mail", "webmail", "remote", "connect", "kunde", "customer", "my", "access", "service", "client",
        "wealth", "ebanking", "trade", "card")


def priority(host, base):
    labels = host[: -len(base)].rstrip(".").replace("-", ".").split(".") if host != base else ["www"]
    # Short keywords must be the whole label ("id", "my"); longer ones may sit inside it ("efxauth", "ciamselfservice").
    hit = any(label == k or (len(k) >= 4 and k in label) for label in labels for k in HIGH)
    return "high" if hit else "normal"


def fix_guide(network):
    net = (network or "").lower()
    if "amazon" in net:
        return "aws-alb-cloudfront-post-quantum-tls"
    if any(n in net for n in ("cloudflare", "akamai", "fastly")):
        return "post-quantum-tls-apache-caddy-haproxy-cloudflare"
    return "enable-x25519mlkem768-nginx"


def make_probe(lookup):
    def probe(host):
        try:
            ip = qs.resolve_public_ip(host)
        except qs.ScanError:
            return None
        found = discovery.probe_host(host)
        if found:
            found["ip"] = ip
            found["network"] = (lookup(ip)[1] if lookup else None) or "unknown"
        return found
    return probe


TEXT = {
    "en": dict(
        title="Post-quantum TLS audit", prepared="Prepared for", date="Measured on", scope="Scope",
        scope_text="All names under {base} found in public Certificate Transparency logs ({names} names; "
                   "{checked} checked, {responding} answered on port 443).",
        summary="Summary", not_pq="without post-quantum key exchange", pq="with post-quantum key exchange",
        unknown="undetermined (firewall or non-standard TLS)",
        verdict_bad="{n} of {r} public HTTPS endpoints still use classical key exchange only. Traffic to them can be "
                    "recorded today and decrypted once a large quantum computer exists (harvest now, decrypt later).",
        verdict_good="All {r} responding public HTTPS endpoints negotiate post-quantum key exchange.",
        fix_title="Hosts to fix", fix_intro="High priority = names that usually carry logins, payments or APIs.",
        th=["Priority", "Host", "TLS", "Key exchange", "Network", "How to fix"], high="High", normal="Normal",
        unknown_title="Undetermined hosts", unknown_intro="These hosts did not answer our post-quantum ClientHello "
        "in a standard way. Check them from inside your network or with your vendor.",
        pq_title="Hosts already protected",
        reg_title="Regulatory context",
        reg=["NIS2 Directive (EU) 2022/2555, Article 21(2)(h): \"policies and procedures regarding the use of "
             "cryptography and, where appropriate, encryption\".",
             "DORA Delegated Regulation (EU) 2024/1774, Article 6(4): provisions for \"updating or changing, where "
             "necessary, the cryptographic technology on the basis of developments in cryptanalysis\"; "
             "Recital 9 names \"threats from quantum advancements\".",
             "Neither text names a post-quantum algorithm or deadline. This report is evidence for the public "
             "TLS part of your cryptographic inventory."],
        limits_title="What this report does not cover",
        limits="Only the key exchange of public HTTPS endpoints on port 443 at the time of measurement. Not covered: "
               "internal links, CDN-to-origin connections, certificates and signatures, stored data, key management "
               "and application security. This is not a penetration test.",
        recheck="Free re-check: reply to the delivery email after 30 days and we will measure again.",
        method="Method: names from crt.sh / Cert Spotter; one TLS 1.3 ClientHello per host offering X25519MLKEM768; "
               "network from the ip2asn database.",
    ),
    "de": dict(
        title="Post-Quanten-TLS-Audit", prepared="Erstellt für", date="Gemessen am", scope="Umfang",
        scope_text="Alle Namen unter {base} aus öffentlichen Certificate-Transparency-Logs ({names} Namen; "
                   "{checked} geprüft, {responding} antworteten auf Port 443).",
        summary="Zusammenfassung", not_pq="ohne Post-Quanten-Schlüsselaustausch",
        pq="mit Post-Quanten-Schlüsselaustausch", unknown="nicht bestimmbar (Firewall oder abweichendes TLS)",
        verdict_bad="{n} von {r} öffentlichen HTTPS-Endpunkten nutzen nur klassischen Schlüsselaustausch. Verkehr "
                    "zu ihnen kann heute aufgezeichnet und später mit einem Quantencomputer entschlüsselt werden "
                    "(Harvest now, decrypt later).",
        verdict_good="Alle {r} erreichbaren öffentlichen HTTPS-Endpunkte nutzen Post-Quanten-Schlüsselaustausch.",
        fix_title="Zu behebende Hosts", fix_intro="Hohe Priorität = Namen, die üblicherweise Logins, Zahlungen "
        "oder APIs tragen.",
        th=["Priorität", "Host", "TLS", "Schlüsselaustausch", "Netz", "Lösung"], high="Hoch", normal="Normal",
        unknown_title="Nicht bestimmbare Hosts", unknown_intro="Diese Hosts antworteten nicht standardgemäß auf "
        "unseren Post-Quanten-ClientHello. Prüfen Sie sie intern oder mit Ihrem Anbieter.",
        pq_title="Bereits geschützte Hosts",
        reg_title="Regulatorischer Rahmen",
        reg=["NIS2-Richtlinie (EU) 2022/2555, Art. 21 Abs. 2 lit. h: Konzepte und Verfahren für den Einsatz von "
             "Kryptografie und gegebenenfalls Verschlüsselung.",
             "DORA, Delegierte Verordnung (EU) 2024/1774, Art. 6 Abs. 4: Aktualisierung oder Änderung der "
             "kryptografischen Technologie auf Grundlage von Entwicklungen in der Kryptoanalyse; Erwägungsgrund 9 "
             "nennt Bedrohungen durch Quantenfortschritte.",
             "Keiner der Texte nennt einen Post-Quanten-Algorithmus oder eine Frist. Dieser Bericht belegt den "
             "öffentlichen TLS-Teil Ihres Kryptografie-Inventars."],
        limits_title="Was dieser Bericht nicht abdeckt",
        limits="Nur der Schlüsselaustausch öffentlicher HTTPS-Endpunkte auf Port 443 zum Messzeitpunkt. Nicht "
               "abgedeckt: interne Verbindungen, CDN-zu-Origin, Zertifikate und Signaturen, gespeicherte Daten, "
               "Schlüsselverwaltung und Anwendungssicherheit. Dies ist kein Penetrationstest.",
        recheck="Kostenlose Nachprüfung: Antworten Sie nach 30 Tagen auf die Liefer-E-Mail, wir messen erneut.",
        method="Methode: Namen aus crt.sh / Cert Spotter; ein TLS-1.3-ClientHello pro Host mit X25519MLKEM768; "
               "Netz aus der ip2asn-Datenbank.",
    ),
}

CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font: 10.5pt/1.45 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #111827; }
h1 { font-size: 22pt; margin: 0 0 4pt; } h2 { font-size: 13pt; margin: 18pt 0 6pt; border-bottom: 1px solid #d1d5db; }
.meta { color: #4b5563; margin: 0 0 14pt; } .verdict { font-size: 12pt; padding: 10pt; background: #f3f4f6; }
.stats { display: flex; gap: 10pt; margin: 10pt 0; } .stat { flex: 1; border: 1px solid #d1d5db; padding: 8pt; }
.stat b { display: block; font-size: 18pt; } .bad b { color: #b91c1c; } .good b { color: #047857; }
table { width: 100%; border-collapse: collapse; font-size: 9pt; } th, td { text-align: left; padding: 4pt; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
th { background: #f9fafb; } tr { page-break-inside: avoid; } .high { color: #b91c1c; font-weight: 600; }
.small { font-size: 8.5pt; color: #4b5563; } a { color: #1d4ed8; } code { font-size: 8.5pt; }
"""


def render(base, org, lang, result, measured):
    T = TEXT[lang]
    e = html.escape
    hosts = result["hosts"]
    bad = sorted((h for h in hosts if h["status"] == "not_pq"),
                 key=lambda h: (priority(h["host"], base) != "high", h["host"]))
    unknown = [h for h in hosts if h["status"] == "unknown"]
    good = [h for h in hosts if h["status"] == "pq"]
    r = result["responding"]
    verdict = T["verdict_bad"].format(n=len(bad), r=r) if bad else T["verdict_good"].format(r=r)
    out = [f"<!doctype html><html lang='{lang}'><head><meta charset='utf-8'><title>{e(T['title'])} · {e(base)}</title>"
           f"<style>{CSS}</style></head><body>",
           f"<h1>{e(T['title'])}: {e(base)}</h1>",
           f"<p class='meta'>{e(T['prepared'])}: <b>{e(org)}</b> · {e(T['date'])}: {measured} · Quantum Aether</p>",
           f"<p class='verdict'>{e(verdict)}</p>",
           "<div class='stats'>"
           f"<div class='stat bad'><b>{len(bad)}</b>{e(T['not_pq'])}</div>"
           f"<div class='stat good'><b>{len(good)}</b>{e(T['pq'])}</div>"
           f"<div class='stat'><b>{len(unknown)}</b>{e(T['unknown'])}</div></div>",
           f"<p class='small'>{e(T['scope'])}: " + e(T["scope_text"].format(
               base=base, names=result["names"], checked=min(result["names"], discovery.MAX_HOSTS), responding=r)) + "</p>"]
    if bad:
        out.append(f"<h2>{e(T['fix_title'])}</h2><p class='small'>{e(T['fix_intro'])}</p><table><tr>"
                   + "".join(f"<th>{e(c)}</th>" for c in T["th"]) + "</tr>")
        for h in bad:
            p = priority(h["host"], base)
            slug = fix_guide(h.get("network"))
            g = guides.GUIDES[slug]
            title = (g.get(lang) or g["en"])["title"]
            link = f"{BASE_URL}/guides/{slug}?lang={lang if lang in g else 'en'}"
            out.append(f"<tr><td class='{p}'>{e(T[p])}</td><td><code>{e(h['host'])}</code></td>"
                       f"<td>{e((h.get('version') or '').replace('TLSv', ''))}</td><td>{e(h.get('group') or '-')}</td>"
                       f"<td>{e(h.get('network') or '-')}</td><td><a href='{link}'>{e(title)}</a></td></tr>")
        out.append("</table>")
    if unknown:
        out.append(f"<h2>{e(T['unknown_title'])}</h2><p class='small'>{e(T['unknown_intro'])}</p><p>"
                   + ", ".join(f"<code>{e(h['host'])}</code>" for h in unknown) + "</p>")
    if good:
        out.append(f"<h2>{e(T['pq_title'])}</h2><p class='small'>"
                   + ", ".join(f"<code>{e(h['host'])}</code>" for h in good) + "</p>")
    out.append(f"<h2>{e(T['reg_title'])}</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in T["reg"]) + "</ul>")
    out.append(f"<h2>{e(T['limits_title'])}</h2><p>{e(T['limits'])}</p><p><b>{e(T['recheck'])}</b></p>"
               f"<p class='small'>{e(T['method'])} {e(result['source'])}.</p></body></html>")
    return "".join(out)


def to_pdf(html_path, pdf_path):
    subprocess.run([CHROMIUM, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", "file://" + os.path.abspath(html_path)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("domain")
    ap.add_argument("--org", required=True)
    ap.add_argument("--lang", choices=sorted(TEXT), default="en")
    ap.add_argument("--out", default=".")
    a = ap.parse_args(argv)
    base = discovery.base_domain(qs.normalize_domain(a.domain))
    try:
        lookup = asn.AsnLookup(ASN_DB).lookup
    except OSError:
        lookup = None
    result = discovery.run_discovery(base, requests.Session(), probe=make_probe(lookup))
    measured = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    os.makedirs(a.out, exist_ok=True)
    stem = os.path.join(a.out, f"audit-{base}-{dt.date.today().isoformat()}-{a.lang}")
    with open(stem + ".html", "w", encoding="utf-8") as f:
        f.write(render(base, a.org, a.lang, result, measured))
    to_pdf(stem + ".html", stem + ".pdf")
    print(f"{stem}.pdf  names={result['names']} responding={result['responding']} "
          f"not_pq={result['not_pq']} pq={result['pq']} unknown={result['unknown']}")


if __name__ == "__main__":
    main()
