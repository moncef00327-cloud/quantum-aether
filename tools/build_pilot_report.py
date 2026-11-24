#!/usr/bin/env python3
"""Build the German MSP Pilot deliverable (HTML + PDF + signed v1 JWS receipts bundle).

Fulfills the MSP Pilot offer (up to 50 hostnames, German Ampel report with TLS version,
hybrid PQ key exchange, certificate summary, prioritized actions, signed Ed25519 JWS
receipts for NIS2 documentation, and optional partner logo).

Examples:
    python3 tools/build_pilot_report.py --org "Musterkunde GmbH" --hosts-file hosts.txt \\
        --partner-name "Muster IT GmbH" --logo partner.png --out /root/audits/pilot1

    python3 tools/build_pilot_report.py --org "Musterkunde GmbH" --domain musterkunde.at \\
        --max-hosts 50 --out /root/audits/pilot1
"""
import argparse
import base64
import concurrent.futures
import datetime as dt
import html
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asn  # noqa: E402
import discovery  # noqa: E402
import guides  # noqa: E402
import quantum_vuln_scanner as qs  # noqa: E402
import receipts  # noqa: E402

BASE_URL = "https://ather-quantum.com"
ENV_FILE = "/etc/quantum_saas.env"
ASN_DB = os.environ.get("QS_ASN_DB", "/var/lib/quantum_saas/ip2asn-v4.tsv.gz")
CHROMIUM = os.environ.get("CHROME_BIN", os.path.expanduser("~/.cache/ms-playwright/chromium-1140/chrome-linux/chrome"))
DEFAULT_MAX_HOSTS = 50
PILOT_PRICE_EUR = 290

HIGH_PRIORITY_TOKENS = (
    "login", "auth", "sso", "id", "account", "api", "online", "banking", "portal",
    "secure", "pay", "vpn", "mobile", "app", "mail", "webmail", "remote", "connect",
    "kunde", "customer", "my", "access", "service", "client", "erp", "crm", "admin",
    "mcp", "a2a", "agent",
)


def load_env(path: str = ENV_FILE) -> None:
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "pilot").lower()).strip("-")
    return s[:48] or "pilot"


def parse_hosts_list(raw_lines: list[str], max_hosts: int = DEFAULT_MAX_HOSTS) -> list[tuple[str, int]]:
    """Parse newline-separated hosts (`host` or `host:port`), deduplicating and capping at `max_hosts`."""
    seen = set()
    targets: list[tuple[str, int]] = []
    for line in raw_lines:
        item = line.split("#", 1)[0].strip()
        if not item:
            continue
        clean_host, clean_port, sub = receipts.parse_host_port_input(item)
        if sub in seen:
            continue
        seen.add(sub)
        targets.append((clean_host, clean_port))
        if len(targets) >= max_hosts:
            break
    return targets


def endpoint_priority(host: str, base_domain: str | None = None) -> str:
    prefix = host
    if base_domain and host.endswith("." + base_domain):
        prefix = host[: -(len(base_domain) + 1)]
    elif base_domain and host == base_domain:
        return "normal"
    labels = prefix.replace("-", ".").split(".")
    hit = any(lbl == tok or (len(tok) >= 4 and tok in lbl) for lbl in labels for tok in HIGH_PRIORITY_TOKENS)
    return "high" if hit else "normal"


def ampel_for_verdict(verdict: dict) -> tuple[str, str, str]:
    """Map `qa-pqc-transport` 1.0 verdict to German traffic light: `(code, label, css_class)`."""
    grade = (verdict or {}).get("grade") or "F"
    if grade in ("A+", "A"):
        return ("green", f"Grün ({grade})", "ampel-green")
    if grade in ("B", "C"):
        return ("yellow", f"Gelb ({grade})", "ampel-yellow")
    return ("red", f"Rot ({grade})", "ampel-red")


def action_for_entry(entry: dict) -> str:
    v = entry["receipt"]["policy_verdict"]
    audit = entry["receipt"]["tls_audit"]
    reasons = set(v.get("fail_reasons") or [])
    warnings = set(v.get("warnings") or [])
    net = (entry.get("network") or "").lower()
    if "HANDSHAKE_FAILED" in reasons:
        return "Erreichbarkeit / TLS-Konfiguration prüfen (Handshake fehlgeschlagen)"
    actions = []
    if "CERT_EXPIRED" in reasons:
        actions.append("Abgelaufenes Zertifikat sofort erneuern")
    if "CERT_CHAIN_INVALID" in reasons:
        actions.append("Zertifikatskette / Intermediate-CA korrigieren")
    if "CERT_HOSTNAME_MISMATCH" in reasons:
        actions.append("SAN/Hostname im Zertifikat korrigieren")
    if "TLS_VERSION_BELOW_1_3" in reasons:
        actions.append("TLS 1.3 aktivieren")
    if "NO_HYBRID_PQ_GROUP" in reasons:
        if any(k in net for k in ("cloudflare", "akamai", "fastly")):
            actions.append("Hybrides PQ-TLS (X25519MLKEM768) im CDN/Proxy aktivieren")
        elif "amazon" in net:
            actions.append("AWS ALB / CloudFront TLS-Policy mit ML-KEM aktivieren")
        else:
            actions.append("X25519MLKEM768 aktivieren (OpenSSL 3.5+ / Nginx / Caddy / HAProxy)")
    if "LEGACY_TLS_ENABLED" in warnings:
        actions.append("TLS 1.0 / 1.1 abschalten")
    if "CERT_EXPIRES_SOON" in warnings:
        actions.append("Zertifikat läuft in < 30 Tagen ab — zeitnah erneuern")
    if not actions:
        return "Bereits mit hybridem Post-Quanten-Schlüsselaustausch geschützt (regelmäßig überwachen)"
    return "; ".join(actions)


def guide_link_for_network(network: str | None) -> tuple[str, str]:
    net = (network or "").lower()
    if "amazon" in net:
        slug = "aws-alb-cloudfront-post-quantum-tls"
    elif any(k in net for k in ("cloudflare", "akamai", "fastly")):
        slug = "post-quantum-tls-apache-caddy-haproxy-cloudflare"
    else:
        slug = "enable-x25519mlkem768-nginx"
    g = guides.GUIDES.get(slug) or {}
    title = (g.get("de") or g.get("en") or {}).get("title") or slug
    lang = "de" if "de" in g else "en"
    return f"{BASE_URL}/guides/{slug}?lang={lang}", title


def encode_logo_data_uri(logo_path: str | None) -> str | None:
    if not logo_path:
        return None
    p = Path(logo_path)
    if not p.exists():
        raise FileNotFoundError(f"Logo file not found: {logo_path}")
    mime, _ = mimetypes.guess_type(str(p))
    if not mime or not mime.startswith("image/"):
        raise ValueError(f"Unsupported logo media type for {logo_path}: {mime}")
    raw = p.read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Logo file exceeds 2 MB limit")
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def scan_and_sign_targets(
    targets: list[tuple[str, int]],
    *,
    scanner=None,
    asn_lookup=None,
    key_path=None,
    kid: str | None = None,
    data_dir=None,
    issuer: str = BASE_URL,
    vantage: str | None = None,
    base_domain: str | None = None,
    workers: int = 6,
) -> list[dict]:
    """Scan each `(host, port)` target and sign a v1 receipt (pass or fail)."""
    scan_fn = scanner or qs.scan_target
    chosen_vantage = vantage or os.environ.get("QA_VANTAGE", "eu-central")

    def one(target: tuple[str, int]) -> dict:
        host, port = target
        try:
            raw = scan_fn(host, port)
            claims = receipts.build_receipt_claims(raw, vantage=chosen_vantage, issuer=issuer)
            resolved_ip = raw.get("ip")
        except qs.ScanError as exc:
            claims = receipts.build_failed_receipt_claims(host, port, vantage=chosen_vantage, issuer=issuer)
            resolved_ip = None
            error_msg = str(exc)
        else:
            error_msg = None
        signed_claims, token = receipts.sign_receipt(
            claims, key_path=key_path, kid=kid, data_dir=data_dir, issuer=issuer
        )
        _, dual = receipts.format_dual_response(signed_claims, token, issuer=issuer)
        network = None
        if resolved_ip and asn_lookup:
            try:
                network = asn_lookup(resolved_ip)[1]
            except Exception:
                network = None
        return {
            "host": host,
            "port": port,
            "sub": signed_claims["sub"],
            "priority": endpoint_priority(host, base_domain),
            "network": network or "-",
            "error": error_msg,
            **dual,
        }

    if workers <= 1 or len(targets) <= 1:
        return [one(t) for t in targets]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, len(targets))) as pool:
        return list(pool.map(one, targets))


CSS = """
@page { size: A4; margin: 14mm 12mm; }
body { font: 9.8pt/1.45 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #111827; margin: 0; }
.hdr { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0f766e; padding-bottom: 10pt; margin-bottom: 12pt; }
.hdr h1 { font-size: 18pt; margin: 0 0 3pt; color: #0f172a; }
.hdr .meta { color: #475569; font-size: 9pt; margin: 0; }
.logo { max-height: 44pt; max-width: 150pt; object-fit: contain; }
.stats { display: flex; gap: 8pt; margin: 10pt 0 14pt; }
.stat { flex: 1; border: 1px solid #e2e8f0; border-radius: 6pt; padding: 8pt 10pt; background: #f8fafc; }
.stat b { display: block; font-size: 17pt; line-height: 1.1; }
.stat.green b { color: #047857; } .stat.yellow b { color: #b45309; } .stat.red b { color: #b91c1c; }
h2 { font-size: 12pt; margin: 16pt 0 6pt; border-bottom: 1px solid #cbd5e1; padding-bottom: 3pt; color: #0f172a; }
table { width: 100%; border-collapse: collapse; font-size: 8.4pt; }
th, td { text-align: left; padding: 4.5pt 4pt; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
th { background: #f1f5f9; font-weight: 600; }
tr { page-break-inside: avoid; }
.badge { display: inline-block; padding: 1.5pt 5pt; border-radius: 4pt; font-weight: 600; font-size: 8pt; white-space: nowrap; }
.ampel-green { background: #dcfce7; color: #166534; }
.ampel-yellow { background: #fef3c7; color: #92400e; }
.ampel-red { background: #fee2e2; color: #991b1b; }
.prio-high { color: #b91c1c; font-weight: 600; }
.prio-normal { color: #475569; }
.box { background: #f8fafc; border-left: 3pt solid #0f766e; padding: 8pt 10pt; margin: 10pt 0; font-size: 9pt; }
.small { font-size: 8pt; color: #475569; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 7.8pt; background: #f1f5f9; padding: 0.5pt 2.5pt; border-radius: 2pt; }
a { color: #0f766e; text-decoration: none; }
"""


def render_pilot_html(
    *,
    org: str,
    entries: list[dict],
    measured_utc: str,
    partner_name: str | None = None,
    logo_data_uri: str | None = None,
    issuer: str = BASE_URL,
) -> str:
    e = html.escape
    counts = {"green": 0, "yellow": 0, "red": 0}
    enriched = []
    for item in entries:
        verdict = item["receipt"]["policy_verdict"]
        color, label, css_cls = ampel_for_verdict(verdict)
        counts[color] += 1
        enriched.append((color, label, css_cls, item))

    order_map = {"red": 0, "yellow": 1, "green": 2}
    enriched.sort(key=lambda x: (order_map[x[0]], x[3]["priority"] != "high", x[3]["sub"]))

    byline = f"{e(partner_name)} · powered by Quantum Aether" if partner_name else "Quantum Aether · ather-quantum.com"
    logo_html = f"<img class='logo' src='{logo_data_uri}' alt='{e(partner_name or 'Partner Logo')}'>" if logo_data_uri else ""

    rows = []
    for color, label, css_cls, item in enriched:
        rcpt = item["receipt"]
        audit = rcpt["tls_audit"]
        cert = audit.get("cert") or {}
        tls_ver = audit.get("tls_version") or "–"
        grp = audit.get("negotiated_group") or "–"
        pq_txt = "Ja" if audit.get("hybrid_pq_key_exchange") else "Nein"
        if cert:
            cert_status = "OK" if (cert.get("chain_valid") and cert.get("hostname_match")) else "Fehler"
            not_after = (cert.get("not_after") or "")[:10]
            cert_cell = f"{cert_status} · {e(cert.get('key_type') or '?')} · bis {e(not_after or '?')}"
        else:
            cert_cell = "Kein Zertifikat"
        prio_label = "Hoch" if item["priority"] == "high" else "Normal"
        prio_cls = "prio-high" if item["priority"] == "high" else "prio-normal"
        action = action_for_entry(item)
        guide_url, _ = guide_link_for_network(item.get("network"))
        jti = rcpt["jti"]
        rows.append(
            "<tr>"
            f"<td><span class='badge {css_cls}'>{e(label)}</span></td>"
            f"<td class='{prio_cls}'>{prio_label}</td>"
            f"<td><code>{e(rcpt['sub'])}</code><br><span class='small'>{e(item.get('network') or '-')}</span></td>"
            f"<td>{e(tls_ver)}</td>"
            f"<td>{e(grp)} ({pq_txt})</td>"
            f"<td>{cert_cell}</td>"
            f"<td>{e(action)}"
            + (f" · <a href='{e(guide_url)}'>Anleitung</a>" if color != "green" else "")
            + f"<br><span class='small'>Beleg: <code>{e(jti)}</code></span></td>"
            "</tr>"
        )

    total = len(entries)
    base = issuer.rstrip("/")
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Post-Quanten-TLS-Bericht · {e(org)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="hdr">
  <div>
    <h1>Post-Quanten-TLS-Prüfbericht</h1>
    <p class="meta">Kunde: <b>{e(org)}</b> · Gemessen am: {e(measured_utc)} · {byline}</p>
  </div>
  {logo_html}
</div>

<div class="stats">
  <div class="stat"><b>{total}</b>Geprüfte Endpunkte</div>
  <div class="stat green"><b>{counts['green']}</b>Grün · Hybrides PQ-TLS (A+/A)</div>
  <div class="stat yellow"><b>{counts['yellow']}</b>Gelb · Klassisches TLS (B/C)</div>
  <div class="stat red"><b>{counts['red']}</b>Rot · Kritisch / Fehler (F)</div>
</div>

<div class="box">
  <b>Einordnung:</b> Dieser Bericht prüft die öffentliche Transportverschlüsselung (TLS-Version, hybrider
  Post-Quanten-Schlüsselaustausch wie <code>X25519MLKEM768</code>, Zertifikatskette/Ablaufdatum und Legacy-TLS 1.0/1.1)
  nach Richtlinie <a href="{e(base)}/policies/qa-pqc-transport/1.0"><code>qa-pqc-transport 1.0</code></a>.
  <b>Abgrenzung:</b> Der Bericht deckt ausschließlich die öffentliche Transportverschlüsselung ab, keine vollständige
  Krypto-Inventur, keine internen Netze und keinen Penetrationstest.
</div>

<h2>Ergebnisse je Endpunkt (Ampel &amp; priorisierte Maßnahmen)</h2>
<table>
  <thead>
    <tr>
      <th>Ampel</th>
      <th>Priorität</th>
      <th>Endpunkt</th>
      <th>TLS</th>
      <th>Schlüsselaustausch (PQ)</th>
      <th>Zertifikat</th>
      <th>Maßnahme &amp; Prüfbeleg</th>
    </tr>
  </thead>
  <tbody>
    {"".join(rows)}
  </tbody>
</table>

<h2>Signierte Prüfbelege für Dokumentation (z. B. NIS2 / DORA)</h2>
<p class="small">
  Für jeden geprüften Endpunkt liegt im beigefügten JSON-Paket (<code>*-receipts.json</code>) ein kryptografisch
  mit Ed25519 signierter Prüfbeleg (Compact JWS, <code>typ: qa-tls-receipt+jwt</code>) vor. Jeder Beleg enthält
  die exakte IP-Adresse, den Zeitpunkt, die angebotenen Gruppen, die Zertifikats-Fingerabdrücke (<code>leaf_sha256</code>,
  <code>spki_sha256</code>) und das Richtlinienurteil. Die Prüfung erfolgt unabhängig und offline gegen den
  öffentlichen Schlüssel unter <a href="{e(base)}/.well-known/jwks.json"><code>{e(base)}/.well-known/jwks.json</code></a>
  (z. B. mit <code>qa_verify.py --host &lt;host&gt; --file receipts.json</code>).
</p>
<p class="small">
  Hinweis zur Authentifizierung: Heutige öffentliche TLS-Zertifikate nutzen klassische Signaturen (RSA/ECDSA), daher
  ist <code>pq_authentication</code> in allen aktuellen Belegen <code>false</code>. Sobald PQ-Zertifikate (ML-DSA)
  von CAs breit ausgestellt werden, erfolgt die Bewertung unter einer neuen Richtlinienversion.
</p>
</body>
</html>
"""


def to_pdf(html_path: str, pdf_path: str) -> bool:
    import shutil
    wp = shutil.which("weasyprint")
    if wp:
        subprocess.run([wp, os.path.abspath(html_path), os.path.abspath(pdf_path)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        return True
    if os.path.exists(CHROMIUM):
        subprocess.run(
            [CHROMIUM, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={pdf_path}", "file://" + os.path.abspath(html_path)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
        )
        return True
    return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build German MSP Pilot report (HTML + PDF + signed v1 receipts)")
    ap.add_argument("--org", required=True, help="Customer organization name")
    ap.add_argument("--hosts-file", help="Path to text file with up to 50 hostnames (one per line)")
    ap.add_argument("--domain", help="Base domain to discover subdomains automatically if --hosts-file is omitted")
    ap.add_argument("--max-hosts", type=int, default=DEFAULT_MAX_HOSTS, help=f"Max hostnames (default: {DEFAULT_MAX_HOSTS})")
    ap.add_argument("--partner-name", default=None, help="Optional IT-Dienstleister partner name")
    ap.add_argument("--logo", default=None, help="Optional partner logo path (PNG/JPG/SVG)")
    ap.add_argument("--out", default=".", help="Output directory")
    ap.add_argument("--no-pdf", action="store_true", help="Skip headless Chromium PDF generation")
    args = ap.parse_args(argv)

    if not args.hosts_file and not args.domain:
        ap.error("Provide --hosts-file or --domain")

    load_env()
    base_domain = None
    if args.hosts_file:
        lines = Path(args.hosts_file).read_text(encoding="utf-8").splitlines()
        targets = parse_hosts_list(lines, max_hosts=args.max_hosts)
        if args.domain:
            base_domain = discovery.base_domain(qs.normalize_domain(args.domain))
    else:
        import requests
        base_domain = discovery.base_domain(qs.normalize_domain(args.domain))
        names, _ = discovery.discover_names(base_domain, requests.Session())
        targets = parse_hosts_list(names, max_hosts=args.max_hosts)

    if not targets:
        print("No valid targets to scan.", file=sys.stderr)
        return 1

    try:
        asn_lookup = asn.AsnLookup(ASN_DB).lookup
    except OSError:
        asn_lookup = None

    logo_uri = encode_logo_data_uri(args.logo) if args.logo else None
    measured = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entries = scan_and_sign_targets(
        targets,
        asn_lookup=asn_lookup,
        data_dir=os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas"),
        base_domain=base_domain,
    )

    os.makedirs(args.out, exist_ok=True)
    stem = os.path.join(args.out, f"pilot-{slugify(args.org)}-{dt.date.today().isoformat()}-de")
    html_doc = render_pilot_html(
        org=args.org,
        entries=entries,
        measured_utc=measured,
        partner_name=args.partner_name,
        logo_data_uri=logo_uri,
    )
    Path(stem + ".html").write_text(html_doc, encoding="utf-8")

    bundle = {
        "schema": "quantum-aether-pilot-receipts/1.0",
        "organization": args.org,
        "partner": args.partner_name,
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "jwks_uri": f"{BASE_URL}/.well-known/jwks.json",
        "policy_uri": f"{BASE_URL}{receipts.POLICY_PATH}",
        "count": len(entries),
        "endpoints": [
            {
                "sub": item["sub"],
                "priority": item["priority"],
                "network": item["network"],
                "receipt": item["receipt"],
                "signed_receipt_jws": item["signed_receipt_jws"],
                "verify": item["verify"],
            }
            for item in entries
        ],
    }
    Path(stem + "-receipts.json").write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")

    pdf_ok = False if args.no_pdf else to_pdf(stem + ".html", stem + ".pdf")
    print(f"html={stem}.html pdf={'ok:' + stem + '.pdf' if pdf_ok else 'skipped'} receipts={stem}-receipts.json count={len(entries)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
