#!/usr/bin/env python3
"""First contact (English) with companies outside the Arab region measured without post-quantum key exchange.

Targets: instance/intl_targets_2026-11-16.json (address published on the company's own site, MX checked).
At send time every domain is re-scanned: if it now negotiates post-quantum key exchange, or the scan fails,
the company is skipped, so the email never states an outdated result. Suppressed addresses are skipped.
One run only (results file guard). The owner gets a summary email.

  python tools/send_intl_trial_offer.py            # preview (re-scans, sends nothing)
  python tools/send_intl_trial_offer.py --send
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import quantum_vuln_scanner  # noqa: E402
from mailer import Mailer  # noqa: E402
from send_arab_trial_offer import load_env, suppressed  # noqa: E402

BASE = "https://ather-quantum.com"
TARGETS = os.path.join(ROOT, "instance", "intl_targets_2026-11-16.json")
OUT = os.path.join(ROOT, "instance", "intl_trial_offer_results.json")


def message(t, grade, group, measured_on):
    d, org = t["domain"], t["org"]
    subject = f"{d}: no post-quantum key exchange yet (free 14-day monitoring)"
    body = (
        f"Dear IT and Information Security Team at {org},\n\n"
        f"On {measured_on} we measured the public TLS connection of {d}: grade {grade}, key exchange {group} "
        "(classical only, no hybrid X25519MLKEM768). Traffic recorded today under classical key exchange can be decrypted "
        "later by a quantum computer (harvest now, decrypt later), and current Chrome, Firefox, Edge and Safari already "
        "support hybrid post-quantum key exchange.\n\n"
        f"Re-check it yourself for free: {BASE}/?domain={d}\n\n"
        "We also offer free daily monitoring for 14 days, up to 10 domains, no payment and no card, with an immediate "
        "alert on any regression (post-quantum key exchange lost, a lower grade, or a certificate nearing expiry):\n"
        f"{BASE}/monitoring?domain={d}&lang=en#trial\n\n"
        "Nothing turns into a subscription automatically. If this isn't your area, please forward it to your technical "
        "team, or reply \"stop\" and we won't write again.\n\n"
        "Best regards,\nQuantum Aether\nhttps://ather-quantum.com"
    )
    return subject, body


def fresh_result(domain):
    """Re-scan now. Returns (grade, group) if still classical, else None (now PQ, inconclusive or unreachable)."""
    try:
        r = quantum_vuln_scanner.scan(domain)
    except Exception as exc:  # unreachable: don't claim anything
        print(f"  {domain}: scan failed ({str(exc)[:60]}), skipped")
        return None
    kx = r["key_exchange"]
    if kx.get("pq") or kx.get("hrr") or kx.get("error"):
        print(f"  {domain}: now {kx.get('group')} (post-quantum or inconclusive), skipped")
        return None
    return r["grade"], kx.get("group")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    args = ap.parse_args()
    load_env()
    if args.send and os.path.exists(OUT):
        print(f"already sent ({OUT} exists); refusing to send twice")
        return 1
    with open(TARGETS, encoding="utf-8") as f:
        targets = json.load(f)
    skip = suppressed()
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    ready = []
    for t in targets:
        if t["to"].lower() in skip:
            print(f"  {t['domain']}: {t['to']} bounced before, skipped")
            continue
        res = fresh_result(t["domain"])
        if res:
            ready.append((t, *res))
    print(f"ready: {len(ready)} of {len(targets)}")
    for t, grade, group in ready:
        print(f"  {t['domain']:16s} {t['org']:12s} -> {t['to']}  ({grade}, {group})")
    if not args.send:
        if ready:
            s, b = message(ready[0][0], ready[0][1], ready[0][2], today)
            print(f"\nSubject: {s}\n\n{b}\n\n[preview only: nothing sent]")
        return 0
    mailer = Mailer(os.environ.get("RESEND_API_KEY", ""), os.environ.get("QS_MAIL_FROM", ""),
                    os.environ.get("QS_REPLY_TO", ""), fallback_sender=os.environ.get("QS_MAIL_FROM_FALLBACK", ""),
                    site_url=BASE)
    if not mailer.enabled:
        print("mailer not configured")
        return 1
    results = []
    for t, grade, group in ready:
        s, b = message(t, grade, group, today)
        ok = mailer.send(t["to"], s, b)
        results.append(dict(t, grade_at_send=grade, kx_at_send=group, subject=s, status="SENT" if ok else "FAILED",
                            sent_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
        print(f"{t['domain']} -> {t['to']} | {results[-1]['status']}", flush=True)
        time.sleep(0.6)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"results": results, "skipped": len(targets) - len(ready)}, f, ensure_ascii=False, indent=2)
    os.chmod(OUT, 0o600)
    owner = os.environ.get("QS_OWNER_EMAIL", "")
    if owner:
        lines = [f"{r['domain']} -> {r['to']}: {r['status']}" for r in results]
        mailer.send(owner, f"[Quantum Aether] International trial offer sent ({sum(r['status'] == 'SENT' for r in results)}/{len(targets)})",
                    "\n".join(lines) + f"\n\nSkipped (now protected, unreachable or bounced before): {len(targets) - len(ready)}\nLog: {OUT}")
    print(f"done: {sum(r['status'] == 'SENT' for r in results)}/{len(ready)} sent; log {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
