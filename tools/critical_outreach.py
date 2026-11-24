#!/usr/bin/env python3
"""Prepared outreach tool for verified CRITICAL TLS findings (Grade F/C, legacy TLS, cert errors, silent PQ regression).

Prepared, NOT scheduled. Never sends without explicit `--send`.
  python3 tools/critical_outreach.py --dry-run --targets /root/outreach/targets_cf_priority.csv --limit 3
  python3 tools/critical_outreach.py --send    --targets <csv> --limit 10 --daily-cap 20 --pause 60

Safety & compliance:
- Live scan right before rendering/sending (never sends on stale DB data; skips if host is no longer critical).
- Issues a verifiable Ed25519 JWS receipt v1 (`/.well-known/jwks.json`); persisted in SQLite on `--send` only.
- Skips `outreach_suppress`, `outreach_sent`, `growth_outreach`, `adoption_optout`.
- Includes RFC 8058 `List-Unsubscribe` + One-Click headers, `/u/<token>` link, and Austrian Impressum.
- Stops on >2 bounces, any complaint, 3 send errors, pause file, or daily cap.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
from pathlib import Path
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import adoption  # noqa: E402
import outreach_suppress as osup  # noqa: E402
import quantum_vuln_scanner as qs  # noqa: E402
import receipts  # noqa: E402
from tools.outreach_send import (  # noqa: E402
    DB_PATH,
    FROM,
    MAX_BOUNCES,
    PAUSE_FILES,
    REPLY_TO,
    SITE,
    UA,
    already_sent,
    keep_db_owner,
    load_env,
    now_iso,
    resend_send,
    run_events,
    sent_last_24h,
)

DACH_COUNTRIES = {"DE", "AT", "CH", "DACH"}
ARAB_COUNTRIES = {"SA", "AE", "KW", "QA", "BH", "OM", "EG", "JO", "MA", "TN", "LB", "IQ", "DZ"}

FINDING_COPY = {
    "CERT_EXPIRED": {
        "short": {"de": "Zertifikat abgelaufen", "en": "expired TLS certificate", "ar": "شهادة TLS منتهية"},
        "detail": {
            "de": "Das präsentierte TLS-Zertifikat ist abgelaufen (not_after: {not_after}).",
            "en": "The presented TLS certificate has expired (not_after: {not_after}).",
            "ar": "شهادة TLS التي يقدّمها الخادم منتهية الصلاحية (تاريخ الانتهاء: {not_after}).",
        },
        "fix": {
            "de": "Zertifikat umgehend erneuern und automatische Erneuerung/Ablauf-Überwachung prüfen.",
            "en": "Renew the certificate immediately and verify automated renewal and expiry alerts.",
            "ar": "جدّد الشهادة فوراً وتحقّق من التجديد التلقائي وتنبيهات انتهاء الصلاحية.",
        },
    },
    "CERT_CHAIN_INVALID": {
        "short": {"de": "Zertifikatskette ungültig", "en": "invalid certificate chain", "ar": "سلسلة شهادة غير صالحة"},
        "detail": {
            "de": "Die Zertifikatskette lässt sich gegen vertrauenswürdige Root-CAs nicht validieren.",
            "en": "The certificate chain failed validation against trusted root CAs.",
            "ar": "تعذّر التحقق من سلسلة الشهادة أمام الجذور الموثوقة (CA).",
        },
        "fix": {
            "de": "Vollständige Zertifikatskette (Leaf + Intermediate) auf dem TLS-Endpunkt/Proxy hinterlegen.",
            "en": "Serve the full certificate chain (leaf + intermediate CA) on the TLS terminator.",
            "ar": "أرفق سلسلة الشهادة الكاملة (الشهادة مع الشهادات الوسيطة) على الخادم أو الـ Proxy.",
        },
    },
    "CERT_HOSTNAME_MISMATCH": {
        "short": {"de": "Zertifikat passt nicht zum Hostnamen", "en": "certificate hostname mismatch", "ar": "عدم تطابق اسم المضيف في الشهادة"},
        "detail": {
            "de": "Das Zertifikat deckt den Hostnamen {host} nicht ab (Hostname-Mismatch).",
            "en": "The certificate SAN/CN does not cover hostname {host}.",
            "ar": "الشهادة لا تغطّي اسم المضيف {host}.",
        },
        "fix": {
            "de": "Zertifikat mit passendem SAN für {host} ausstellen und dem SNI-Host zuweisen.",
            "en": "Issue a certificate including {host} in SAN and bind it to the matching SNI vhost.",
            "ar": "أصدِر شهادة تتضمّن {host} في حقل SAN واربطها بإعداد SNI الصحيح.",
        },
    },
    "STATIC_RSA_KX": {
        "short": {"de": "Statisches RSA ohne Forward Secrecy", "en": "static RSA key exchange (no PFS)", "ar": "تبادل مفاتيح RSA ثابت دون سرية أمامية"},
        "detail": {
            "de": "Der Server hat statischen RSA-Schlüsselaustausch ausgehandelt (keine Perfect Forward Secrecy).",
            "en": "The server negotiated static RSA key exchange without Perfect Forward Secrecy.",
            "ar": "تفاوض الخادم على تبادل مفاتيح RSA ثابت دون خاصية السرية الأمامية (PFS).",
        },
        "fix": {
            "de": "Statische RSA-Cipher-Suites deaktivieren und TLS 1.3 mit X25519MLKEM768 aktivieren.",
            "en": "Disable static RSA cipher suites and enable TLS 1.3 with X25519MLKEM768.",
            "ar": "عطّل مجموعات RSA الثابتة وفعّل TLS 1.3 مع المجموعة الهجينة X25519MLKEM768.",
        },
    },
    "LEGACY_TLS_ENABLED": {
        "short": {"de": "TLS 1.0/1.1 noch aktiv", "en": "deprecated TLS 1.0/1.1 accepted", "ar": "قبول TLS 1.0/1.1 القديم"},
        "detail": {
            "de": "Der Endpunkt akzeptiert weiterhin veraltetes TLS 1.0/1.1 (nicht mehr Stand der Technik laut BSI/NIST).",
            "en": "The endpoint still accepts deprecated TLS 1.0/1.1 connections.",
            "ar": "لا يزال الخادم يقبل اتصالات TLS 1.0/1.1 المتقادمة وغير الموصى بها أمنياً.",
        },
        "fix": {
            "de": "TLS 1.0 und TLS 1.1 abschalten (nur noch TLS 1.2 + TLS 1.3 mit X25519MLKEM768 zulassen).",
            "en": "Disable TLS 1.0/1.1 and restrict the endpoint to TLS 1.2 + TLS 1.3 with X25519MLKEM768.",
            "ar": "أوقف TLS 1.0 وTLS 1.1 واقتصر على TLS 1.2 وTLS 1.3 مع تفعيل X25519MLKEM768.",
        },
    },
    "TLS_1_2_ONLY": {
        "short": {"de": "nur TLS 1.2 (kein TLS 1.3 / kein PQ)", "en": "TLS 1.2 maximum (no TLS 1.3 / no PQ)", "ar": "TLS 1.2 كحد أقصى (دون TLS 1.3 ودون PQ)"},
        "detail": {
            "de": "Maximal ausgehandeltes Protokoll ist TLS 1.2 ({group}) — kein TLS 1.3 und kein hybrider Post-Quanten-Schlüsselaustausch (X25519MLKEM768).",
            "en": "Maximum negotiated protocol is TLS 1.2 ({group}) — no TLS 1.3 and no hybrid post-quantum key exchange (X25519MLKEM768).",
            "ar": "أعلى إصدار متفاوض عليه هو TLS 1.2 ({group}) — دون TLS 1.3 ودون التبادل الهجين المقاوم للكم (X25519MLKEM768).",
        },
        "fix": {
            "de": "TLS 1.3 und X25519MLKEM768 aktivieren (z. B. Nginx/OpenSSL 3.5+: ssl_protocols TLSv1.2 TLSv1.3; ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;).",
            "en": "Enable TLS 1.3 and X25519MLKEM768 (e.g. nginx/OpenSSL 3.5+: ssl_protocols TLSv1.2 TLSv1.3; ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;).",
            "ar": "فعّل TLS 1.3 وX25519MLKEM768 (مثال Nginx/OpenSSL 3.5+: ssl_protocols TLSv1.2 TLSv1.3; ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;).",
        },
    },
    "SILENT_PQ_REGRESSION": {
        "short": {"de": "PQ-TLS-Rückfall auf klassisch", "en": "silent PQ-TLS regression to classical", "ar": "تراجع صامت عن PQ-TLS إلى التشفير التقليدي"},
        "detail": {
            "de": "Dieser Endpunkt hatte zuvor X25519MLKEM768 unterstützt, fiel heute aber auf klassisches {group} zurück.",
            "en": "This host previously negotiated X25519MLKEM768, but fell back to classical {group} today.",
            "ar": "كان هذا المضيف يفاوض سابقاً على X25519MLKEM768، لكنه تراجع اليوم إلى {group} التقليدي.",
        },
        "fix": {
            "de": "Letzte CDN-/Proxy-/Load-Balancer-Änderung prüfen und X25519MLKEM768 wieder aktivieren.",
            "en": "Inspect recent CDN/proxy/load-balancer changes and restore X25519MLKEM768.",
            "ar": "راجع آخر تعديل على CDN أو الـ Proxy أو موازن الحمل وأعد تفعيل X25519MLKEM768.",
        },
    },
}


def pick_language(target: dict, override: str | None = None) -> str:
    if override in ("de", "en", "ar"):
        return override
    lang = (target.get("lang") or "").strip().lower()
    if lang in ("de", "en", "ar"):
        return lang
    country = (target.get("country") or "").strip().upper()
    region = (target.get("region") or "").strip().lower()
    if country in DACH_COUNTRIES or region == "dach" or (target.get("domain") or "").lower().endswith((".de", ".at", ".ch")):
        return "de"
    if country in ARAB_COUNTRIES or region in ("arab world", "mena"):
        return "ar"
    return "en"


def classify_critical(scan_result: dict, claims: dict, prev_pq: bool = False) -> list[str]:
    """Return ordered critical finding codes. Empty list means host is NOT a critical case (skip)."""
    verdict = claims.get("policy_verdict") or {}
    audit = claims.get("tls_audit") or {}
    kx = scan_result.get("key_exchange") or {}
    reasons = set(verdict.get("fail_reasons") or [])
    warnings = set(verdict.get("warnings") or [])

    codes: list[str] = []
    if "CERT_EXPIRED" in reasons:
        codes.append("CERT_EXPIRED")
    if "CERT_CHAIN_INVALID" in reasons:
        codes.append("CERT_CHAIN_INVALID")
    if "CERT_HOSTNAME_MISMATCH" in reasons:
        codes.append("CERT_HOSTNAME_MISMATCH")
    if kx.get("kx") == "RSA":
        codes.append("STATIC_RSA_KX")
    if "LEGACY_TLS_ENABLED" in warnings or audit.get("tls_version") in ("TLSv1.1", "TLSv1.0", "SSLv3"):
        codes.append("LEGACY_TLS_ENABLED")
    if audit.get("tls_version") == "TLSv1.2":
        codes.append("TLS_1_2_ONLY")
    if prev_pq and not audit.get("hybrid_pq_key_exchange"):
        codes.append("SILENT_PQ_REGRESSION")
    return codes


def render_critical_email(
    *,
    domain: str,
    host: str,
    email: str,
    lang: str,
    claims: dict,
    codes: list[str],
    secret: str,
    source_basis: str = "security.txt",
    date: str | None = None,
) -> dict:
    if not codes:
        raise ValueError("No critical findings to render")
    day = date or dt.date.today().isoformat()
    audit = claims["tls_audit"]
    cert = audit.get("cert") or {}
    verdict = claims["policy_verdict"]
    primary = codes[0]
    slots = {
        "domain": domain,
        "host": host,
        "date": day,
        "ip": (claims.get("target") or {}).get("resolved_ip") or "-",
        "tls_version": audit.get("tls_version") or "unknown",
        "group": audit.get("negotiated_group") or "unknown",
        "not_after": (cert.get("not_after") or "unknown")[:10],
        "grade": verdict.get("grade") or "F",
        "jti": claims["jti"],
        "short_finding": FINDING_COPY[primary]["short"][lang],
    }
    unsub_url = osup.unsubscribe_url(SITE, email, secret)
    receipt_url = f"{SITE}/api/v1/receipts/{claims['jti']}"
    jwks_url = f"{SITE}/.well-known/jwks.json"
    site_url = f"{SITE}/site/{domain}?lang={lang}"
    guide_url = f"{SITE}/guides/enable-x25519mlkem768-nginx?lang={'de' if lang == 'de' else ('ar' if lang == 'ar' else 'en')}"
    monitor_url = f"{SITE}/monitoring?domain={domain}&lang={lang}#trial-form"
    recheck_url = f"{SITE}/?domain={domain}&lang={lang}"

    details_bullets = "\n".join(
        f"– {FINDING_COPY[c]['detail'][lang].format(**slots)}" for c in codes
    )
    fix_bullets = "\n".join(
        f"– {FINDING_COPY[c]['fix'][lang].format(**slots)}" for c in codes
    )

    if lang == "de":
        subject = f"{domain}: Kritischer TLS-Befund am {day} ({slots['short_finding']})"
        body = (
            f"Guten Tag Sicherheitsteam von {domain},\n\n"
            f"am {day} ergab ein öffentlicher TLS-Handshake zu {host}:443 (IP {slots['ip']}) "
            f"folgenden Befund (Richtlinie qa-pqc-transport 1.0, Note {slots['grade']} · {slots['tls_version']} / {slots['group']}):\n\n"
            f"{details_bullets}\n\n"
            f"Empfohlene Sofortmaßnahmen:\n{fix_bullets}\n"
            f"Konfigurations-Leitfaden: {guide_url}\n\n"
            f"Nachprüfbarer, kryptografisch signierter Beleg (Ed25519 JWS, 24h gültig):\n"
            f"– Signierter Prüfbeleg: {receipt_url}\n"
            f"– Öffentlicher Schlüssel (JWKS): {jwks_url}\n"
            f"– Kostenlose Nachprüfung ohne Login: {recheck_url}\n"
            f"– 14 Tage kostenloses tägliches TLS-/Zertifikats-Monitoring (bis 10 Domains, ohne Karte): {monitor_url}\n\n"
            f"Warum diese Nachricht: Die Adresse ist öffentlich in {source_basis} von {domain} hinterlegt. "
            f"Dies ist ein einmaliger technischer Hinweis von Quantum Aether; wir schreiben kein zweites Mal.\n\n"
            f"Mit einem Klick abmelden: {unsub_url} (oder kurz mit „Stop“ antworten).\n\n"
            f"Quantum Aether Team\n"
            f"Quantum Aether, Sparkaßen 11/12, 5280 Braunau am Inn, Austria · {SITE}/impressum"
        )
    elif lang == "ar":
        subject = f"{domain}: رصد حالة TLS حرجة بتاريخ {day} ({slots['short_finding']})"
        body = (
            f"مرحباً فريق أمن {domain}،\n\n"
            f"بتاريخ {day} أظهر فحص TLS عام واحد للمضيف {host}:443 (العنوان {slots['ip']}) "
            f"النتائج التالية (سياسة qa-pqc-transport 1.0، الدرجة {slots['grade']} · {slots['tls_version']} / {slots['group']}):\n\n"
            f"{details_bullets}\n\n"
            f"خطوات الإصلاح المقترحة:\n{fix_bullets}\n"
            f"دليل التفعيل: {guide_url}\n\n"
            f"دليل قابل للتحقق وموقّع رقمياً (Ed25519 JWS، صالح 24 ساعة):\n"
            f"– الإيصال الموقّع: {receipt_url}\n"
            f"– المفتاح العام (JWKS): {jwks_url}\n"
            f"– إعادة فحص مجانية دون تسجيل: {recheck_url}\n"
            f"– تجربة مجانية 14 يوماً للمراقبة اليومية وتنبيهات الشهادات والتراجع الصامت: {monitor_url}\n\n"
            f"سبب هذه الرسالة: هذا العنوان منشور علناً في {source_basis} الخاص بـ {domain}. "
            f"هذا إشعار تقني لمرة واحدة من Quantum Aether ولن نراسلكم مجدداً.\n\n"
            f"لإلغاء الاشتراك بنقرة واحدة: {unsub_url} (أو ردّوا بكلمة «إيقاف» أو stop).\n\n"
            f"Quantum Aether Team\n"
            f"Quantum Aether، Sparkaßen 11/12, 5280 Braunau am Inn, Austria · {SITE}/impressum"
        )
    else:
        subject = f"{domain}: TLS finding observed on {day} ({slots['short_finding']})"
        body = (
            f"Hello {domain} security team,\n\n"
            f"On {day}, one public TLS handshake to {host}:443 (IP {slots['ip']}) observed the following "
            f"(policy qa-pqc-transport 1.0, Grade {slots['grade']} · {slots['tls_version']} / {slots['group']}):\n\n"
            f"{details_bullets}\n\n"
            f"Recommended remediation:\n{fix_bullets}\n"
            f"Configuration guide: {guide_url}\n\n"
            f"Cryptographically signed verification proof (Ed25519 JWS, valid 24h):\n"
            f"– Signed receipt: {receipt_url}\n"
            f"– Public JWKS: {jwks_url}\n"
            f"– Free re-check (no sign-up): {recheck_url}\n"
            f"– Free 14-day daily TLS & certificate monitoring trial (up to 10 domains, no card): {monitor_url}\n\n"
            f"Why this email: this address is published in {domain}'s {source_basis}. "
            f"This is a one-time technical notice from Quantum Aether; we will not write again.\n\n"
            f"Unsubscribe in one click: {unsub_url} (or reply \"stop\").\n\n"
            f"Quantum Aether Team\n"
            f"Quantum Aether, Sparkaßen 11/12, 5280 Braunau am Inn, Austria · {SITE}/impressum"
        )

    return {
        "lang": lang,
        "subject": subject,
        "text": body,
        "codes": codes,
        "headers": osup.list_unsubscribe_headers(SITE, email, secret, mailto=REPLY_TO),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="live-scan & render critical emails; no send, no DB writes")
    mode.add_argument("--send", action="store_true", help="really send via Resend and persist signed receipts")
    ap.add_argument("--targets", required=True, help="CSV with domain, contact_email, optional handshake_host/country/region/lang/prev_pq")
    ap.add_argument("--limit", type=int, default=10, help="max mails this run (default 10)")
    ap.add_argument("--daily-cap", type=int, default=20, help="max mails in any 24h (default 20)")
    ap.add_argument("--pause", type=float, default=60.0, help="seconds between sends (default 60)")
    ap.add_argument("--lang", choices=("de", "en", "ar"), default=None, help="force template language")
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args(argv)

    load_env()
    secret = os.environ.get("QS_HASH_SALT", "")
    if not secret:
        sys.exit("QS_HASH_SALT missing")
    if args.send and not os.environ.get("RESEND_API_KEY"):
        sys.exit("RESEND_API_KEY missing")
    if args.send:
        for p in PAUSE_FILES:
            if os.path.exists(p):
                sys.exit(f"paused: {p} exists")

    if args.dry_run:
        conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(args.db, timeout=30)
        osup.init(conn)
        receipts.init(conn)
        keep_db_owner(args.db)

    import requests
    http = requests.Session()
    optout = adoption.load_optout(conn=conn)
    budget = min(args.limit, max(0, args.daily_cap - sent_last_24h(conn)))
    print(f"mode={'dry-run' if args.dry_run else 'SEND'} budget={budget} targets={args.targets}")

    done, ids, errors = 0, [], 0
    key_path = os.environ.get("QA_SIGNING_KEY_PATH") or None
    kid = os.environ.get("QA_SIGNING_KID") or None
    data_dir = os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas")

    try:
        with open(args.targets, newline="", encoding="utf-8") as handle:
            rows = [r for r in csv.DictReader(handle) if r.get("contact_email") and r.get("domain")]
        for t in rows:
            if done >= budget:
                break
            email = osup.normalize(t["contact_email"])
            domain = t["domain"].strip().lower().removeprefix("www.")
            host = (t.get("handshake_host") or domain).strip().lower()
            if not email or osup.is_suppressed(conn, email, domain) or adoption.opted_out(domain, optout):
                print(f"skip {domain}: suppressed/opted-out")
                continue
            if already_sent(conn, email, domain):
                print(f"skip {domain}: already contacted")
                continue
            try:
                raw = qs.scan_target(host, 443, timeout=7.0)
            except Exception as exc:
                print(f"skip {domain}: scan failed ({exc})")
                continue
            claims = receipts.build_receipt_claims(raw, vantage=os.environ.get("QA_VANTAGE", "eu-central"), issuer=SITE)
            prev_pq = str(t.get("prev_pq") or "").strip().lower() in ("1", "true", "yes")
            codes = classify_critical(raw, claims, prev_pq=prev_pq)
            if not codes:
                print(f"skip {domain}: not critical (grade={claims['policy_verdict']['grade']})")
                continue

            signed_claims, token = receipts.sign_receipt(claims, key_path=key_path, kid=kid, data_dir=data_dir, issuer=SITE)
            _, active_kid, _, _ = receipts.load_signing_bundle(key_path=key_path, kid=kid, data_dir=data_dir)
            lang = pick_language(t, override=args.lang)
            mail = render_critical_email(
                domain=domain, host=host, email=email, lang=lang,
                claims=signed_claims, codes=codes, secret=secret,
            )

            if args.dry_run:
                print("=" * 72)
                print(f"To: {email} | lang={lang} | codes={','.join(codes)} | jti={signed_claims['jti']}")
                print(f"Subject: {mail['subject']}\n\n{mail['text']}")
                done += 1
                continue

            receipts.save_receipt(conn, signed_claims, token, active_kid)
            keep_db_owner(args.db)
            try:
                rid = resend_send(email, mail, http)
            except Exception as exc:
                errors += 1
                print(f"error {domain}: {exc}")
                if errors >= 3:
                    print("stop: 3 send errors")
                    break
                continue
            with conn:
                conn.execute(
                    "INSERT INTO outreach_sent (email, domain, org, lang, kex_group, kex_class, subject, resend_id, sent_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (email, domain, t.get("organization", ""), f"{lang}-critical",
                     signed_claims["tls_audit"].get("negotiated_group") or "", "critical:" + ",".join(codes),
                     mail["subject"], rid, now_iso()),
                )
            keep_db_owner(args.db)
            ids.append(rid)
            done += 1
            print(f"sent {domain} -> {email} ({lang}, {','.join(codes)}) id={rid}")
            time.sleep(args.pause)
            bounced, complained = run_events(conn, ids, http)
            if bounced > MAX_BOUNCES or complained:
                Path(PAUSE_FILES[0]).write_text(f"{now_iso()} critical bounced={bounced} complained={complained}\n", encoding="utf-8")
                print(f"stop: bounced={bounced} complained={complained}")
                break
        print(f"done: {done} {'rendered' if args.dry_run else 'sent'}")
    finally:
        conn.close()
        if not args.dry_run:
            keep_db_owner(args.db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
