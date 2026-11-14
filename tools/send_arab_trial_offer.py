#!/usr/bin/env python3
"""Offer the 14-day free monitoring trial to the Arab organizations contacted in the 12 Nov campaigns.

Same addresses as the original campaigns (no new address harvesting), Arabic + English body,
the site's own verified sender (QS_MAIL_FROM via Resend), one run only (results file guard).

  python tools/send_arab_trial_offer.py            # preview, sends nothing
  python tools/send_arab_trial_offer.py --send     # send
"""
import argparse
import json
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from mailer import Mailer  # noqa: E402

INSTANCE = os.path.join(ROOT, "instance")
LIVE_DB = "/var/lib/quantum_saas/quantum_saas.db"
OUT = os.path.join(INSTANCE, "b2b_arab_trial_offer_results.json")
BASE = "https://ather-quantum.com"
ARAB_CODES = ("(SA)", "(EG)", "(AE)", "(KW)", "(QA)", "(MA)", "(OM)", "(BH)", "(JO)", "(TN)", "(DZ)", "(LB)", "(IQ)")
WAVE1_ARAB = {"nbk.com", "mashreq.com", "bankfab.com", "alinma.com", "arabbank.com", "alrajhibank.com.sa",
              "riyadbank.com", "dib.ae", "sab.com", "cbq.qa"}


def load_env(path="/etc/quantum_saas.env"):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))


SUPPRESSIONS = os.path.join(INSTANCE, "email_suppressions.txt")


def suppressed():
    """Addresses that bounced or were suppressed in Resend: never write to them again (protects sender reputation)."""
    if not os.path.exists(SUPPRESSIONS):
        return set()
    return {l.strip().lower() for l in open(SUPPRESSIONS, encoding="utf-8") if l.strip() and not l.startswith("#")}


def targets():
    out = {}
    w1 = json.load(open(os.path.join(INSTANCE, "b2b_campaign_results.json"), encoding="utf-8"))["results"]
    for r in w1:
        if r["domain"] in WAVE1_ARAB and r.get("status") == "SENT":
            out[r["domain"]] = {"domain": r["domain"], "org": r["domain"], "to": r["to"]}
    for name in ("b2b_arab_emerging_results.json", "b2b_arab_fomo_results.json"):
        for r in json.load(open(os.path.join(INSTANCE, name), encoding="utf-8"))["results"]:
            if r.get("status") == "SENT" and any(c in (r.get("country") or "") for c in ARAB_CODES):
                out[r["domain"]] = {"domain": r["domain"], "org": r.get("org") or r["domain"], "to": r["to"]}
    # جهات طلبت تدقيقاً أو بدأت تجربة: لا نرسل لها عرضاً
    conn = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    done = {(d or "").lower() for (d,) in conn.execute("SELECT domain FROM audit_requests WHERE is_test = 0")}
    done |= {(d or "").lower() for (d,) in conn.execute(
        "SELECT d.domain FROM monitor_domains d JOIN monitor_accounts a ON a.id = d.account_id WHERE a.status != 'PENDING'")}
    conn.close()
    skip = suppressed()
    return [t for d, t in sorted(out.items()) if d not in done and t["to"].lower() not in skip]


def message(t):
    d, org = t["domain"], t["org"]
    site_ar, site_en = f"{BASE}/site/{d}?lang=ar", f"{BASE}/site/{d}?lang=en"
    trial_ar, trial_en = f"{BASE}/monitoring?domain={d}&lang=ar#trial", f"{BASE}/monitoring?domain={d}&lang=en#trial"
    subject = f"مراقبة مجانية لمدة 14 يوماً لنطاق {d} | 14-day free monitoring for {d}"
    body = (
        f"حضرة فريق أمن المعلومات في {org}،\n\n"
        f"نتابع معكم قياسنا لتبادل المفاتيح المقاوم للكم على {d}. النتيجة الحالية وطريقة الإصلاح:\n{site_ar}\n\n"
        "إعداد التشفير قد يتراجع بصمت بعد أي تحديث للخادم أو لشبكة توزيع المحتوى (CDN). لذلك نتيح لكم مراقبة يومية مجانية "
        "لمدة 14 يوماً لحتى 10 نطاقات، بلا دفع ولا بطاقة، مع تنبيه فوري بالبريد عند أي تراجع "
        "(فقدان التبادل المقاوم للكم، أو انخفاض الدرجة، أو اقتراب انتهاء شهادة):\n"
        f"{trial_ar}\n\n"
        "لا يتحوّل شيء إلى اشتراك تلقائياً. إن لم يكن هذا الموضوع من اختصاصكم، نرجو تحويل الرسالة إلى الفريق المعني، "
        "أو الرد بكلمة «إيقاف» ولن نراسلكم مجدداً.\n\n"
        "مع التحية،\nQuantum Aether\n\n"
        "———\n\n"
        f"Dear Information Security Team at {org},\n\n"
        f"Following up on our post-quantum key-exchange measurement for {d}. Current result and how to fix it:\n{site_en}\n\n"
        "TLS settings can silently regress after any server or CDN change, so we offer free daily monitoring for 14 days, "
        "up to 10 domains, no payment and no card, with an immediate email alert on any regression "
        "(post-quantum key exchange lost, a lower grade, or a certificate nearing expiry):\n"
        f"{trial_en}\n\n"
        "Nothing turns into a subscription automatically. If this isn't your area, please forward it to the right team, "
        "or reply \"stop\" and we won't write again.\n\n"
        "Best regards,\nQuantum Aether\nhttps://ather-quantum.com"
    )
    return subject, body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    args = ap.parse_args()
    load_env()
    tl = targets()
    print(f"targets: {len(tl)}")
    for i, t in enumerate(tl, 1):
        print(f"{i:3d}. {t['domain']:24s} -> {t['to']}")
    if not args.send:
        s, b = message(tl[0])
        print(f"\n--- sample to {tl[0]['to']} ---\nSubject: {s}\n\n{b}\n\n[preview only: nothing sent]")
        return 0
    if os.path.exists(OUT):
        print(f"already sent ({OUT} exists); refusing to send twice")
        return 1
    mailer = Mailer(os.environ.get("RESEND_API_KEY", ""), os.environ.get("QS_MAIL_FROM", ""),
                    os.environ.get("QS_REPLY_TO", ""), fallback_sender=os.environ.get("QS_MAIL_FROM_FALLBACK", ""),
                    site_url=BASE)
    if not mailer.enabled:
        print("mailer not configured")
        return 1
    results = []
    for i, t in enumerate(tl, 1):
        s, b = message(t)
        ok = mailer.send(t["to"], s, b)
        results.append(dict(t, subject=s, status="SENT" if ok else "FAILED",
                            error=None if ok else getattr(mailer, "last_error", None),
                            sent_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
        print(f"[{i}/{len(tl)}] {t['domain']} -> {t['to']} | {results[-1]['status']}", flush=True)
        time.sleep(0.6)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"total": len(tl), "sent": sum(r["status"] == "SENT" for r in results), "results": results},
                  f, ensure_ascii=False, indent=2)
    os.chmod(OUT, 0o600)
    print(f"done: {sum(r['status'] == 'SENT' for r in results)}/{len(tl)} sent; log {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
