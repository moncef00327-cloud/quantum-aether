# x402_attestation.py — paid, portable, auditor-ready signed post-quantum TLS attestation bundle (2026-11-25).
#
# Owner decision 2026-11-25: a paid agent-native SKU ($5.00 USDC on Base via x402 v2). Basic scans and signed
# receipts stay FREE; this delivers a structured, auditor-ready EVIDENCE BUNDLE that is not available for free:
#   1) Fresh Ed25519 JWS signed TLS receipt (v1, policy qa-pqc-transport 1.0)
#   2) CycloneDX 1.6 Cryptographic Bill of Materials (CBOM) for the observed endpoint
#   3) Printable, auditor-ready PDF report (measurement timestamp, endpoints, certificate fingerprints,
#      documented methodology, explicit measurement limits, CBOM summary, and offline JWKS verification steps)
#      served at a private tokenized URL with SHA-256 integrity digest
#   4) Bundle-level Ed25519 JWS (`bundle_jws`) binding att_id, receipt_jti, cbom_serial, and pdf_sha256
#
# Longitudinal timeline history is intentionally deferred until customer demand is demonstrated.
# Supporting compliance evidence (e.g. NIS2/DORA transport), NOT a legal compliance certification.
import datetime as dt
import hashlib
import hmac
import html as htmlmod
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import uuid

from flask import Response, jsonify, request

import audit_checkout
import qrisk
import scan_experience
import x402_pay

PRICE_USD = "5.00"  # owner-set 2026-11-25; change only with the owner.
ATT_ID_RE = re.compile(r"^qa_att_[0-9a-f]{24}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS x402_attestations (
    att_id        TEXT PRIMARY KEY,
    token_hash    TEXT NOT NULL,
    domain        TEXT NOT NULL,
    issued_at     TEXT NOT NULL,
    receipt_jti   TEXT,
    bundle_sha256 TEXT NOT NULL,
    pdf_sha256    TEXT NOT NULL,
    pdf_path      TEXT NOT NULL
);
"""


def init(conn):
    with conn:
        conn.executescript(SCHEMA)


def _token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def _safe_filename(domain: str, issued_at: str) -> str:
    dom = re.sub(r"[^a-zA-Z0-9.-]", "_", domain)[:80] or "domain"
    day = (issued_at or "")[:10] or dt.date.today().isoformat()
    return f"qa-attestation-{dom}-{day}.pdf"


def _methodology_block(base: str) -> dict:
    return {
        "name": "Quantum Aether Public TLS Observation Methodology",
        "vantage": "Single external vantage point (eu-central), public HTTPS port 443",
        "key_exchange_probe": (
            "Active TLS 1.3 ClientHello offering hybrid post-quantum group X25519MLKEM768 (ML-KEM, FIPS 203). "
            "A single HelloRetryRequest is answered as modern browsers do; only a failed retry is recorded as undetermined."
        ),
        "certificate_probe": "Separate standard TLS handshake observing negotiated protocol, cipher suite, X.509 chain, leaf SHA-256, and SPKI SHA-256.",
        "observation_states": {
            "observed_pq": "Hybrid post-quantum key exchange (X25519MLKEM768) was negotiated.",
            "observed_classical": "Classical key exchange only was negotiated.",
            "undetermined": "Handshake did not establish a negotiated group; never treat as proof of classical-only support.",
        },
        "limits": [
            "External observation from one vantage point at issued_at; CDN routing, time, or IP family can change results.",
            "Port 443 public endpoint only; may not reflect an origin server behind a CDN or TLS-terminating proxy.",
            "Measures transport key exchange and leaf certificate posture only; does NOT assess application security, HSTS, or internal infrastructure.",
            "Supporting measurement evidence (e.g. NIS2 Art. 21 / DORA Art. 9 transport controls), NOT a legal compliance certification or cryptographic audit.",
        ],
        "reference_url": base + "/api/v1/agent/methodology",
    }


def _render_auditor_html(att_id: str, domain: str, issued_at: str, summary: dict, raw: dict,
                         signed_receipt: dict, cbom: dict, methodology: dict, base: str,
                         is_sample: bool = False) -> str:
    esc = htmlmod.escape
    rcpt = signed_receipt.get("receipt") or {}
    jti = rcpt.get("jti") or "-"
    pol = rcpt.get("policy") or {}
    verdict = str(pol.get("result") or summary.get("grade") or "-").upper()
    grade = str(pol.get("grade") or summary.get("grade") or "-")
    tls_ver = summary.get("tls_version") or (raw.get("key_exchange") or {}).get("version") or "-"
    kx_grp = summary.get("key_exchange_group") or (raw.get("key_exchange") or {}).get("group") or "-"
    obs = summary.get("observation_status") or "-"
    pq_label = "YES (Hybrid Post-Quantum)" if summary.get("post_quantum_key_exchange") else (
        "UNDETERMINED" if obs == "undetermined" else "NO (Classical Only)")
    verdict_cls = "pass" if summary.get("post_quantum_key_exchange") and summary.get("certificate_valid", True) else (
        "warn" if grade in ("B", "C") else "fail")
    sample_banner = (
        '<div style="background:#fef3c7;border:2px solid #d97706;color:#78350f;padding:8px 10px;'
        'border-radius:6px;margin-bottom:10px;font-weight:700;font-size:9pt">'
        'ARCHIVED SAMPLE — NOT A LIVE MEASUREMENT · For format preview only. '
        'Live signed attestations ($5.00 USDC via x402) contain a fresh scan and live Ed25519 JWS signatures.'
        '</div>'
    ) if is_sample else ""

    cert = raw.get("certificate") or {}
    endpoints = raw.get("endpoints") or []
    ep_rows = ""
    if endpoints:
        for ep in endpoints[:8]:
            ep_rows += (
                f"<tr><td>{esc(str(ep.get('ip') or '-'))}</td>"
                f"<td>IPv{esc(str(ep.get('family') or '-'))}</td>"
                f"<td>{esc(str(ep.get('version') or '-'))}</td>"
                f"<td>{esc(str(ep.get('group') or '-'))}</td>"
                f"<td>{'PQ' if ep.get('pq') else ('Undetermined' if ep.get('undetermined') else 'Classical')}</td></tr>"
            )
    else:
        ep_rows = (
            f"<tr><td>{esc(str(raw.get('ip') or '-'))}</td><td>-</td>"
            f"<td>{esc(str(tls_ver))}</td><td>{esc(str(kx_grp))}</td><td>{esc(str(obs))}</td></tr>"
        )

    cbom_rows = ""
    for comp in (cbom.get("components") or [])[:10]:
        cp = comp.get("cryptoProperties") or {}
        atype = cp.get("assetType") or "-"
        ap = cp.get("algorithmProperties") or {}
        lvl = ap.get("nistQuantumSecurityLevel")
        lvl_str = "-" if lvl is None else f"NIST Level {lvl}"
        cbom_rows += (
            f"<tr><td><code>{esc(str(comp.get('bom-ref') or '-'))}</code></td>"
            f"<td>{esc(str(comp.get('name') or '-'))}</td>"
            f"<td>{esc(str(atype))}</td><td>{esc(str(lvl_str))}</td></tr>"
        )

    limits_html = "".join(f"<li>{esc(item)}</li>" for item in methodology["limits"])
    jws = signed_receipt.get("signed_receipt_jws") or ""
    jwks_uri = base + "/.well-known/jwks.json"
    policy_uri = base + "/policies/qa-pqc-transport/1.0"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Quantum Aether TLS Attestation — {esc(domain)}</title>
<style>
  @page {{ size: A4; margin: 16mm 15mm; }}
  body {{ font-family: "DejaVu Sans", Arial, sans-serif; color: #0f172a; font-size: 9.5pt; line-height: 1.45; margin: 0; }}
  .hdr {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #0f172a; padding-bottom: 8px; margin-bottom: 12px; }}
  .brand {{ font-size: 14pt; font-weight: 700; letter-spacing: .01em; }}
  .sub {{ font-size: 8.5pt; color: #475569; margin-top: 2px; }}
  .meta {{ text-align: right; font-size: 8.2pt; color: #334155; }}
  .banner {{ border-radius: 6px; padding: 10px 12px; margin-bottom: 12px; border: 1px solid #cbd5e1; background: #f8fafc; }}
  .banner.pass {{ border-color: #16a34a; background: #f0fdf4; }}
  .banner.warn {{ border-color: #d97706; background: #fffbeb; }}
  .banner.fail {{ border-color: #dc2626; background: #fef2f2; }}
  .banner h1 {{ margin: 0 0 4px 0; font-size: 13pt; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 8.5pt; background: #0f172a; color: #fff; margin-right: 6px; }}
  h2 {{ font-size: 10.5pt; margin: 12px 0 5px 0; border-bottom: 1px solid #cbd5e1; padding-bottom: 3px; color: #0f172a; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 8.6pt; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 4px 6px; text-align: left; vertical-align: top; }}
  th {{ background: #f1f5f9; font-weight: 700; width: 26%; }}
  .tbl-list th {{ width: auto; }}
  code, pre {{ font-family: "DejaVu Sans Mono", monospace; font-size: 7.5pt; word-break: break-all; }}
  pre {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px 8px; white-space: pre-wrap; margin: 4px 0 8px 0; }}
  ul {{ margin: 4px 0 8px 18px; padding: 0; }}
  li {{ margin-bottom: 3px; }}
  .foot {{ margin-top: 12px; padding-top: 6px; border-top: 1px solid #cbd5e1; font-size: 7.8pt; color: #475569; }}
</style>
</head>
<body>
  {sample_banner}
  <div class="hdr">
    <div>
      <div class="brand">Quantum Aether · Post-Quantum TLS Attestation</div>
      <div class="sub">Auditor-Ready Transport Evidence Bundle (NIS2 / DORA Supporting Observation)</div>
    </div>
    <div class="meta">
      <div><strong>Attestation ID:</strong> <code>{esc(att_id)}</code></div>
      <div><strong>Issued (UTC):</strong> {esc(issued_at)}</div>
      <div><strong>Receipt JTI:</strong> <code>{esc(str(jti))}</code></div>
    </div>
  </div>

  <div class="banner {verdict_cls}">
    <h1><span class="badge">Grade {esc(grade)} · {esc(verdict)}</span> {esc(domain)}:443</h1>
    <div><strong>Post-Quantum Key Exchange:</strong> {esc(pq_label)} &nbsp;|&nbsp; <strong>Negotiated Group:</strong> <code>{esc(str(kx_grp))}</code> &nbsp;|&nbsp; <strong>TLS:</strong> <code>{esc(str(tls_ver))}</code></div>
  </div>

  <h2>1. Observed Transport &amp; Endpoints</h2>
  <table class="tbl-list">
    <thead><tr><th>Public IP</th><th>Family</th><th>TLS Version</th><th>Key Exchange Group</th><th>Status</th></tr></thead>
    <tbody>{ep_rows}</tbody>
  </table>

  <h2>2. Certificate &amp; Cryptographic Fingerprints</h2>
  <table>
    <tr><th>Subject / Issuer</th><td>{esc(str(cert.get('subject') or domain))} &nbsp;/&nbsp; {esc(str(cert.get('issuer') or '-'))}</td></tr>
    <tr><th>Public Key</th><td>{esc(str(cert.get('key_algorithm') or '-'))}-{esc(str(cert.get('key_bits') or '-'))} ({esc(str(cert.get('curve') or cert.get('signature_algorithm') or '-'))})</td></tr>
    <tr><th>Validity &amp; Chain</th><td>Valid: {esc(str(cert.get('verified')))} · Chain valid: {esc(str(cert.get('chain_valid')))} · Hostname match: {esc(str(cert.get('hostname_match')))} · Expires: {esc(str(cert.get('not_after') or '-'))} ({esc(str(cert.get('days_left')))}d)</td></tr>
    <tr><th>Leaf SHA-256</th><td><code>{esc(str(cert.get('leaf_sha256') or '-'))}</code></td></tr>
    <tr><th>SPKI SHA-256</th><td><code>{esc(str(cert.get('spki_sha256') or '-'))}</code></td></tr>
    <tr><th>Legacy TLS (&le;1.1)</th><td>{esc(str(raw.get('legacy_tls_enabled')))}</td></tr>
  </table>

  <h2>3. CycloneDX 1.6 Cryptographic Bill of Materials (CBOM Summary)</h2>
  <div class="sub">Serial: <code>{esc(str(cbom.get('serialNumber') or '-'))}</code> · Full CycloneDX 1.6 JSON included in the machine-readable bundle.</div>
  <table class="tbl-list">
    <thead><tr><th>Ref</th><th>Asset Name</th><th>Type</th><th>Quantum Security Level</th></tr></thead>
    <tbody>{cbom_rows}</tbody>
  </table>

  <h2>4. Methodology &amp; Explicit Measurement Limits</h2>
  <div><strong>Vantage &amp; Probe:</strong> {esc(methodology['vantage'])}. {esc(methodology['key_exchange_probe'])}</div>
  <ul>{limits_html}</ul>

  <h2>5. Offline Cryptographic Verification (Ed25519 JWS)</h2>
  <table>
    <tr><th>JWKS Endpoint</th><td><code>{esc(jwks_uri)}</code> (Ed25519 / EdDSA, RFC 7515)</td></tr>
    <tr><th>Policy Document</th><td><code>{esc(policy_uri)}</code></td></tr>
    <tr><th>CLI Verification</th><td><code>python3 tools/qa_verify.py --receipt receipt.json --expect-host {esc(domain)}:443 --jwks-url {esc(jwks_uri)}</code></td></tr>
  </table>
  <pre>{esc(jws)}</pre>

  <div class="foot">
    Issued by Quantum Aether ({esc(base)}) at {esc(issued_at)}. External technical observation only — not a legal compliance certification or full cryptographic audit. Verify the Ed25519 signatures offline against {esc(jwks_uri)} and match the PDF SHA-256 digest in the signed JSON bundle.
  </div>
</body>
</html>"""


def _render_auditor_pdf_bytes(att_id: str, domain: str, issued_at: str, summary: dict, raw: dict,
                              signed_receipt: dict, cbom: dict, methodology: dict, base: str,
                              is_sample: bool = False) -> tuple[bytes, str]:
    """Render auditor PDF via WeasyPrint CLI when available, falling back to pure-Python PDF 1.4."""
    html_str = _render_auditor_html(
        att_id, domain, issued_at, summary, raw, signed_receipt, cbom, methodology, base, is_sample=is_sample
    )
    weasy = shutil.which("weasyprint")
    if weasy:
        with tempfile.TemporaryDirectory() as td:
            html_path = os.path.join(td, "att.html")
            pdf_path = os.path.join(td, "att.pdf")
            with open(html_path, "w", encoding="utf-8") as fh:
                fh.write(html_str)
            try:
                proc = subprocess.run([weasy, html_path, pdf_path], capture_output=True, timeout=20, check=False)
                if proc.returncode == 0 and os.path.exists(pdf_path):
                    data = Path(pdf_path).read_bytes()
                    if data.startswith(b"%PDF"):
                        return data, "weasyprint"
            except (OSError, subprocess.SubprocessError):
                pass

    # Pure-Python fallback (zero external dependencies; ensures valid %PDF-1.4 everywhere including CI)
    cert = raw.get("certificate") or {}
    rcpt = signed_receipt.get("receipt") or {}
    jws = signed_receipt.get("signed_receipt_jws") or ""
    lines = [
        ("Quantum Aether - Post-Quantum TLS Attestation", "title"),
        ("Auditor-Ready Transport Evidence Bundle (NIS2 / DORA Supporting Observation)", "small"),
        ("", "rule"),
        (f"Attestation ID: {att_id}", "mono"),
        (f"Domain: {domain}:443   |   Issued (UTC): {issued_at}", "bold"),
        (f"Grade: {summary.get('grade') or '-'}   |   TLS: {summary.get('tls_version') or '-'}   |   "
         f"Key Exchange: {summary.get('key_exchange_group') or '-'}   |   PQ: {summary.get('post_quantum_key_exchange')}", "body"),
        (f"Observation State: {summary.get('observation_status') or '-'}   |   Receipt JTI: {rcpt.get('jti') or '-'}", "mono"),
        ("", "space"),
        ("Certificate & Fingerprints", "bold"),
        (f"Subject: {cert.get('subject') or domain}   |   Issuer: {cert.get('issuer') or '-'}", "body"),
        (f"Key: {cert.get('key_algorithm') or '-'}-{cert.get('key_bits') or '-'}   |   "
         f"Valid: {cert.get('verified')}   |   Expires: {cert.get('not_after') or '-'} ({cert.get('days_left')}d)", "body"),
        (f"Leaf SHA-256: {cert.get('leaf_sha256') or '-'}", "mono"),
        (f"SPKI SHA-256: {cert.get('spki_sha256') or '-'}", "mono"),
        ("", "space"),
        ("CycloneDX 1.6 CBOM Summary", "bold"),
        (f"Serial: {cbom.get('serialNumber') or '-'}   |   Components: {len(cbom.get('components') or [])}", "mono"),
        ("", "space"),
        ("Methodology & Explicit Measurement Limits", "bold"),
        (f"Vantage: {methodology['vantage']}", "body"),
        (methodology["key_exchange_probe"], "body"),
    ]
    for lim in methodology["limits"]:
        lines.append((f"- {lim}", "small"))
    lines += [
        ("", "space"),
        ("Offline Cryptographic Verification (Ed25519 JWS)", "bold"),
        (f"JWKS: {base}/.well-known/jwks.json   |   Policy: {base}/policies/qa-pqc-transport/1.0", "mono"),
        (f"Receipt JWS: {jws}", "mono"),
    ]
    safe_lines = [(t.encode("cp1252", "replace").decode("cp1252"), s) for t, s in lines]
    return audit_checkout.render_pdf(safe_lines), "builtin-pdf"


def register(bp, deps):
    db = deps["db"]
    public_base = deps["base"]
    perform_scan = deps["perform_scan"]
    scan_summary = deps["scan_summary"]
    issue_receipt = deps["issue_receipt"]
    normalize_domain = deps["normalize_domain"]
    ScanError = deps["scan_error"]
    data_dir_fn = deps.get("data_dir")
    sign_fn = deps.get("sign")
    sample_fn = deps.get("sample")

    def _build_sample():
        raw = sample_fn() if sample_fn else {
            "domain": "github.com", "ip": "140.82.121.4", "port": 443,
            "scanned_at": "2026-11-03T12:00:00+00:00", "scanner_version": "2.0", "grade": "B",
            "key_exchange": {"version": "TLSv1.3", "cipher": "TLS_AES_128_GCM_SHA256", "group": "x25519", "pq": False},
            "certificate": {"verified": True, "chain_valid": True, "hostname_match": True,
                            "key_algorithm": "ECDSA", "key_bits": 256, "subject": "github.com",
                            "issuer": "Sectigo", "not_after": "2027-02-01T00:00:00+00:00", "days_left": 68},
            "legacy_tls_enabled": False,
        }
        domain = raw.get("domain") or "github.com"
        issued_at = (raw.get("scanned_at") or "2026-11-03T12:00:00Z")[:19].replace("+00:00", "") + "Z"
        base = public_base()
        summary = scan_summary("archived-sample", raw)
        cbom_doc = qrisk.cbom(raw)
        meth = _methodology_block(base)
        sample_receipt = {
            "receipt": {
                "jti": "qa_rcpt_archived_sample",
                "sub": f"{domain}:443",
                "policy": {"id": "qa-pqc-transport", "version": "1.0", "result": "FAIL", "grade": summary.get("grade") or "B"},
            },
            "signed_receipt_jws": "SAMPLE_ONLY.NOT_A_LIVE_SIGNATURE.RUN_LIVE_ATTESTATION_FOR_REAL_ED25519_JWS",
            "verify": {"jwks_uri": base + "/.well-known/jwks.json", "policy_uri": base + "/policies/qa-pqc-transport/1.0"},
        }
        pdf_bytes, renderer = _render_auditor_pdf_bytes(
            "qa_att_archived_sample", domain, issued_at, summary, raw, sample_receipt, cbom_doc, meth, base, is_sample=True
        )
        return domain, issued_at, base, summary, cbom_doc, meth, sample_receipt, pdf_bytes, renderer

    @bp.get("/api/v1/attestation/sample")
    def api_v1_attestation_sample():
        """Free read-only archived sample of the v2 Auditor Attestation Bundle (never scans)."""
        domain, issued_at, base, summary, cbom_doc, meth, sample_receipt, pdf_bytes, renderer = _build_sample()
        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        resp = jsonify({
            "type": "qa-pq-tls-attestation",
            "version": "2",
            "is_example": True,
            "is_live": False,
            "example_notice": "Archived sample for format preview only. Never triggers a live scan; live paid attestations ($5.00 USDC via x402) include fresh measurements and live Ed25519 JWS signatures.",
            "att_id": "qa_att_archived_sample",
            "issued_at": issued_at,
            "domain": domain,
            "scan": summary,
            "signed_receipt": sample_receipt,
            "cbom": cbom_doc,
            "methodology": meth,
            "auditor_pdf": {
                "download_url": f"{base}/api/v1/attestation/sample.pdf",
                "filename": f"qa-attestation-sample-{domain}.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(pdf_bytes),
                "sha256": pdf_sha256,
                "renderer": renderer,
            },
            "live_endpoint": f"{base}/api/v1/attestation?domain={domain}",
            "price_usd": PRICE_USD,
        })
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "public, max-age=300"
        return resp

    @bp.get("/api/v1/attestation/sample.pdf")
    def api_v1_attestation_sample_pdf():
        """Free read-only archived sample of the printable Auditor PDF (never scans)."""
        domain, _, _, _, _, _, _, pdf_bytes, _ = _build_sample()
        resp = Response(pdf_bytes, mimetype="application/pdf")
        resp.headers["Content-Disposition"] = f'inline; filename="qa-attestation-sample-{domain}.pdf"'
        resp.headers["Cache-Control"] = "public, max-age=300"
        resp.headers["X-Robots-Tag"] = "noindex"
        return resp

    @bp.get("/api/v1/attestation")
    def api_v1_attestation():
        """Paid auditor-ready signed PQ-TLS attestation bundle for ?domain=. Returns 402 x402 challenge until paid;
        once settled, delivers fresh Ed25519 receipt + CycloneDX 1.6 CBOM + auditor PDF URL + bundle_jws."""
        try:
            domain = normalize_domain(request.args.get("domain", ""))
        except ScanError as exc:
            return jsonify(error=exc.code, message=str(exc)), 400
        conn = db()
        x402_pay.init(conn)
        init(conn)

        def deliver():
            scan_id, result = perform_scan(domain, "pack")  # always a fresh scan
            _, _, _, signed_receipt = issue_receipt(result, scan_id)
            base = public_base()
            issued_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            att_id = "qa_att_" + uuid.uuid4().hex[:24]
            summary = scan_summary(scan_id, result)
            cbom_doc = qrisk.cbom(result)
            meth = _methodology_block(base)

            pdf_bytes, renderer = _render_auditor_pdf_bytes(
                att_id, domain, issued_at, summary, result, signed_receipt, cbom_doc, meth, base
            )
            pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

            data_dir = Path(data_dir_fn()) if data_dir_fn else Path(tempfile.gettempdir()) / "qa_attestations"
            pdf_path = data_dir / "attestations" / f"{att_id}.pdf"
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_pdf = pdf_path.with_suffix(".pdf.tmp")
            tmp_pdf.write_bytes(pdf_bytes)
            os.replace(tmp_pdf, pdf_path)

            token = secrets.token_urlsafe(24)
            receipt_jti = (signed_receipt.get("receipt") or {}).get("jti")

            core_for_hash = {
                "att_id": att_id,
                "version": "2",
                "issued_at": issued_at,
                "domain": domain,
                "receipt_jti": receipt_jti,
                "cbom_serial": cbom_doc.get("serialNumber"),
                "pdf_sha256": pdf_sha256,
            }
            bundle_sha256 = hashlib.sha256(
                json.dumps(core_for_hash, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()

            with conn:
                conn.execute(
                    "INSERT INTO x402_attestations "
                    "(att_id, token_hash, domain, issued_at, receipt_jti, bundle_sha256, pdf_sha256, pdf_path) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (att_id, _token_hash(token), domain, issued_at, receipt_jti, bundle_sha256, pdf_sha256, str(pdf_path)),
                )

            bundle_jws = None
            if sign_fn:
                bundle_jws = sign_fn({
                    "kind": "qa-pq-tls-attestation-v2",
                    "att_id": att_id,
                    "domain": domain,
                    "issued_at": issued_at,
                    "receipt_jti": receipt_jti,
                    "cbom_serial": cbom_doc.get("serialNumber"),
                    "bundle_sha256": bundle_sha256,
                    "pdf_sha256": pdf_sha256,
                })

            return {
                "type": "qa-pq-tls-attestation",
                "version": "2",
                "att_id": att_id,
                "issued_at": issued_at,
                "domain": domain,
                "scan": summary,
                "signed_receipt": signed_receipt,
                "cbom": cbom_doc,
                "methodology": meth,
                "auditor_pdf": {
                    "download_url": f"{base}/api/v1/attestation/{att_id}.pdf?token={token}",
                    "filename": _safe_filename(domain, issued_at),
                    "content_type": "application/pdf",
                    "size_bytes": len(pdf_bytes),
                    "sha256": pdf_sha256,
                    "renderer": renderer,
                },
                "integrity": {
                    "bundle_sha256": bundle_sha256,
                    "pdf_sha256": pdf_sha256,
                    "bundle_jws": bundle_jws,
                },
                "verification": {
                    "jwks": base + "/.well-known/jwks.json",
                    "policy": base + "/policies/qa-pqc-transport/1.0",
                    "how": (
                        "Verify both the Ed25519 JWS in signed_receipt and integrity.bundle_jws offline against "
                        "the JWKS, and compare SHA-256 of the downloaded auditor PDF against auditor_pdf.sha256."
                    ),
                },
                "scope": (
                    "Structured auditor evidence bundle (fresh Ed25519 signed observation, CycloneDX 1.6 CBOM, "
                    "printable PDF report with SHA-256 digest, documented methodology, and explicit limits) for "
                    "public TLS transport from one vantage at issued_at. Supporting compliance evidence (e.g. "
                    "NIS2/DORA transport), NOT a legal certification and NOT a full cryptographic audit."
                ),
            }

        description = (
            "Auditor-ready signed post-quantum TLS attestation bundle for " + domain +
            " — printable PDF report + CycloneDX 1.6 CBOM + Ed25519 signed receipt + methodology & limits "
            "(free basic scan at /api/v1/scan)."
        )
        return x402_pay.paywall(
            conn, PRICE_USD, description, deliver, mime="application/json",
            resource_extra={
                "serviceName": "Quantum Aether — Auditor PQ-TLS Attestation",
                "tags": ["tls", "post-quantum", "compliance", "nis2", "dora", "attestation", "pdf", "cbom", "signed-receipt"],
            },
        )

    @bp.get("/api/v1/attestation/<att_id>.pdf")
    def api_v1_attestation_pdf(att_id):
        """Token-protected download for a paid auditor-ready attestation PDF."""
        if not ATT_ID_RE.match(att_id or ""):
            return jsonify(error="not_found"), 404
        token = (request.args.get("token") or "").strip()
        if not token:
            return jsonify(error="token_required"), 403
        conn = db()
        init(conn)
        row = conn.execute(
            "SELECT token_hash, domain, issued_at, pdf_sha256, pdf_path FROM x402_attestations WHERE att_id = ?",
            (att_id,),
        ).fetchone()
        if not row:
            return jsonify(error="not_found"), 404
        if not hmac.compare_digest(_token_hash(token), row["token_hash"]):
            return jsonify(error="invalid_token"), 403
        pdf_file = Path(row["pdf_path"])
        if not pdf_file.is_file():
            return jsonify(error="file_missing"), 404
        data = pdf_file.read_bytes()
        resp = Response(data, mimetype="application/pdf")
        resp.headers["Content-Disposition"] = f'attachment; filename="{_safe_filename(row["domain"], row["issued_at"])}"'
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Robots-Tag"] = "noindex"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Attestation-SHA256"] = row["pdf_sha256"]
        return resp
