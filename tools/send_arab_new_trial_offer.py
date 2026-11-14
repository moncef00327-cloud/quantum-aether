#!/usr/bin/env python3
"""First contact with new Arab companies measured without post-quantum key exchange (13 Nov 2026):
measured result inline + 14-day free monitoring trial. Addresses are the ones each company publishes on its own site.
  python tools/send_arab_new_trial_offer.py [--send]"""
import argparse, json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from mailer import Mailer  # noqa: E402
from send_arab_trial_offer import load_env, suppressed  # noqa: E402

BASE = "https://ather-quantum.com"
OUT = os.path.join(ROOT, "instance", "b2b_arab_new_trial_offer_results.json")
MEASURED = "2026-11-13"
# domain, org, published address (source page), grade, key-exchange group
TARGETS = [
    ("kpc.com.kw", "Kuwait Petroleum Corporation", "info@kpc.com.kw", "B", "x25519"),
    ("urpay.com.sa", "urpay", "info@urpay.com", "C", "secp256r1"),
    ("orange.jo", "Orange Jordan", "businesscare@orange.com", "C", "secp384r1"),
    ("bankofafrica.ma", "Bank of Africa", "relationclient@bankofafrica.ma", "B", "x25519"),
    ("aaib.com", "Arab African International Bank", "inquiry@aaib.com", "B", "x25519"),
]


def message(d, org, grade, group):
    check = f"{BASE}/?domain={d}"
    trial_ar, trial_en = f"{BASE}/monitoring?domain={d}&lang=ar#trial", f"{BASE}/monitoring?domain={d}&lang=en#trial"
    subject = f"{d}: لا يوجد تبادل مفاتيح مقاوم للكم بعد | no post-quantum key exchange yet"
    body = (
        f"حضرة فريق تقنية وأمن المعلومات في {org}،\n\n"
        f"قسنا بتاريخ {MEASURED} اتصال TLS العام لموقع {d}: الدرجة {grade}، وتبادل المفاتيح {group} (تقليدي فقط، بلا X25519MLKEM768). "
        "الاتصالات المسجّلة اليوم بتبادل تقليدي يمكن فك تشفيرها لاحقاً بحاسوب كمّي (احفظ الآن، فك التشفير لاحقاً)، "
        "وأغلب المتصفحات الحديثة تدعم التبادل الهجين المقاوم للكم الآن.\n\n"
        f"أعيدوا الفحص بأنفسكم مجاناً: {check}\n\n"
        "ونتيح لكم مراقبة يومية مجانية لمدة 14 يوماً لحتى 10 نطاقات، بلا دفع ولا بطاقة، مع تنبيه فوري عند أي تراجع:\n"
        f"{trial_ar}\n\n"
        "لا يتحوّل شيء إلى اشتراك تلقائياً. إن لم يكن هذا من اختصاصكم، نرجو تحويل الرسالة إلى الفريق التقني، "
        "أو الرد بكلمة «إيقاف» ولن نراسلكم مجدداً.\n\n"
        "مع التحية،\nQuantum Aether\n\n———\n\n"
        f"Dear IT and Information Security Team at {org},\n\n"
        f"On {MEASURED} we measured the public TLS connection of {d}: grade {grade}, key exchange {group} (classical only, no X25519MLKEM768). "
        "Traffic recorded today under classical key exchange can be decrypted later by a quantum computer (harvest now, decrypt later), "
        "and most current browsers already support hybrid post-quantum key exchange.\n\n"
        f"Re-check it yourself for free: {check}\n\n"
        "We also offer free daily monitoring for 14 days, up to 10 domains, no payment and no card, with an immediate alert on any regression:\n"
        f"{trial_en}\n\n"
        "Nothing turns into a subscription automatically. If this isn't your area, please forward it to your technical team, "
        "or reply \"stop\" and we won't write again.\n\n"
        "Best regards,\nQuantum Aether\nhttps://ather-quantum.com"
    )
    return subject, body


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--send", action="store_true"); args = ap.parse_args()
    load_env()
    for t in TARGETS: print(f"{t[0]:18s} {t[1]:34s} -> {t[2]}  ({t[3]}, {t[4]})")
    if not args.send:
        s, b = message(*[TARGETS[0][i] for i in (0, 1, 3, 4)])
        print(f"\nSubject: {s}\n\n{b}\n\n[preview only]"); return 0
    if os.path.exists(OUT):
        print("already sent; refusing to send twice"); return 1
    m = Mailer(os.environ.get("RESEND_API_KEY", ""), os.environ.get("QS_MAIL_FROM", ""), os.environ.get("QS_REPLY_TO", ""),
               fallback_sender=os.environ.get("QS_MAIL_FROM_FALLBACK", ""), site_url=BASE)
    results = []
    skip = suppressed()
    for d, org, to, grade, group in TARGETS:
        if to.lower() in skip:
            print(f"{d} -> {to} | SKIPPED (bounced before)"); continue
        s, b = message(d, org, grade, group)
        ok = m.send(to, s, b)
        results.append({"domain": d, "org": org, "to": to, "subject": s, "status": "SENT" if ok else "FAILED"})
        print(f"{d} -> {to} | {results[-1]['status']}", flush=True); time.sleep(0.6)
    json.dump({"results": results}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2); os.chmod(OUT, 0o600)
    print(f"done: {sum(r['status']=='SENT' for r in results)}/{len(results)}"); return 0


if __name__ == "__main__":
    sys.exit(main())
