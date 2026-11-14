#!/usr/bin/env python3
"""
send_monday_followup.py
أداة المتابعة الذكية ليوم الاثنين (بعد 72 ساعة من إطلاق الحملات الثلاث):
1. تقرأ سجلات الحملات الثلاث من /root/quantum-aether/instance/
2. تفحص قاعدة البيانات الحية (/var/lib/quantum_saas/quantum_saas.db) لمعرفة:
   - الجهات الساخنة (Warm Leads) التي دخلت فعلياً إلى صفحاتها (/site/<domain>) أو شغلت فحصاً منذ إطلاق الحملة.
   - الجهات التي أرسلت بالفعل طلب تدقيق (/audit) لاستثنائها تلقائياً من رسائل التذكير.
3. تدعم 3 أوضاع تشغيل:
   - المعاينة فقط (افتراضي): python3 /root/quantum-aether/tools/send_monday_followup.py --preview
   - إرسال المتابعة للجهات المتفاعلة فقط (Warm Leads): python3 /root/quantum-aether/tools/send_monday_followup.py --send-warm
   - إرسال المتابعة لجميع الجهات في الحملات: python3 /root/quantum-aether/tools/send_monday_followup.py --send-all
"""
import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, "/root/quantum-aether")
from mailer import Mailer

INSTANCE_DIR = "/root/quantum-aether/instance"
LIVE_DB = "/var/lib/quantum_saas/quantum_saas.db"
SUPPRESSIONS = os.path.join(INSTANCE_DIR, "email_suppressions.txt")
# من وصله عرض التجربة يوم 13 نوفمبر: المتابعة له ستكون الرسالة الثالثة في أربعة أيام، فلا نرسلها
RECENTLY_CONTACTED = ("b2b_arab_trial_offer_results.json", "b2b_arab_new_trial_offer_results.json")


def suppressed_addresses():
    """عناوين ارتدّت أو حظرتها Resend: لا نراسلها مجدداً (حماية سمعة الإرسال)."""
    if not os.path.exists(SUPPRESSIONS):
        return set()
    with open(SUPPRESSIONS, encoding="utf-8") as f:
        return {l.strip().lower() for l in f if l.strip() and not l.startswith("#")}


def recently_contacted_domains():
    done = set()
    for name in RECENTLY_CONTACTED:
        path = os.path.join(INSTANCE_DIR, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                done |= {r["domain"] for r in json.load(f).get("results", []) if r.get("status") == "SENT"}
    return done


def load_env(path="/etc/quantum_saas.env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))


def load_all_campaign_targets():
    """يجمع كل الجهات التي أُرسلت لها الحملات الثلاث بدون تكرار."""
    targets_by_domain = {}

    # 1. Wave 1 (b2b_campaign_results.json)
    w1_path = os.path.join(INSTANCE_DIR, "b2b_campaign_results.json")
    if os.path.exists(w1_path):
        with open(w1_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for r in data.get("results", []):
            d = r["domain"]
            subj = r.get("subject", "")
            lang = "ar" if "نقطة" in subj else ("de" if "Endpunkten" in subj else "en")
            targets_by_domain[d] = {
                "domain": d,
                "org": d,
                "to": r["to"],
                "lang": lang,
                "wave": "Wave 1 (Europe & Gulf)",
                "orig_subject": subj,
            }

    # 2. Wave 2 (b2b_arab_emerging_results.json)
    w2_path = os.path.join(INSTANCE_DIR, "b2b_arab_emerging_results.json")
    if os.path.exists(w2_path):
        with open(w2_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for r in data.get("results", []):
            d = r["domain"]
            targets_by_domain[d] = {
                "domain": d,
                "org": r.get("org", d),
                "country": r.get("country", ""),
                "to": r["to"],
                "lang": r.get("lang", "ar"),
                "wave": "Wave 2 (Arab & Emerging)",
                "orig_subject": r.get("subject", ""),
            }

    # 3. Wave 3 (b2b_arab_fomo_results.json)
    w3_path = os.path.join(INSTANCE_DIR, "b2b_arab_fomo_results.json")
    if os.path.exists(w3_path):
        with open(w3_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for r in data.get("results", []):
            d = r["domain"]
            targets_by_domain[d] = {
                "domain": d,
                "org": r.get("org", d),
                "sector": r.get("sector", ""),
                "country": r.get("country", ""),
                "to": r["to"],
                "lang": "ar",
                "wave": "Wave 3 (Arab B2B FOMO)",
                "orig_subject": r.get("subject", ""),
            }

    return targets_by_domain


def enrich_from_live_db(targets_by_domain):
    """يفحص قاعدة البيانات الحية لمعرفة من زار الموقع، ومن شغل فحصاً، ومن طلب تدقيقاً."""
    if not os.path.exists(LIVE_DB):
        return set()

    try:
        conn = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return set()
    conn.row_factory = sqlite3.Row

    # الجهات التي قدمت طلب تدقيق فعلي (نستثنيها من التذكير)
    converted_domains = set()
    for r in conn.execute("SELECT domain FROM audit_requests WHERE is_test = 0"):
        converted_domains.add((r["domain"] or "").lower().strip())

    # عدد الزيارات لكل صفحة /site/<domain> منذ 2026-11-12
    pv_counts = {}
    for r in conn.execute(
        "SELECT path, COUNT(*) as views, COUNT(DISTINCT visitor) as visitors "
        "FROM pageviews WHERE day >= '2026-11-12' AND is_bot = 0 AND is_test = 0 AND path LIKE '/site/%' "
        "GROUP BY path"
    ):
        dom = r["path"].removeprefix("/site/").strip().lower()
        pv_counts[dom] = {"views": r["views"], "visitors": r["visitors"]}

    # الفحوصات الحية منذ 2026-11-12
    scan_counts = {}
    for r in conn.execute(
        "SELECT domain, COUNT(*) as cnt, MAX(grade) as grade "
        "FROM scans WHERE created_at >= '2026-11-12T00:00:00Z' AND is_test = 0 GROUP BY domain"
    ):
        dom = (r["domain"] or "").lower().removeprefix("www.")
        scan_counts[dom] = {"scans": r["cnt"], "grade": r["grade"]}

    # بيانات النطاقات الفرعية المكتشفة
    disc_map = {}
    for r in conn.execute("SELECT base, names, responding, pq, not_pq FROM discoveries WHERE status = 'DONE'"):
        disc_map[r["base"].lower()] = dict(r)

    for dom, item in targets_by_domain.items():
        pv = pv_counts.get(dom, {"views": 0, "visitors": 0})
        sc = scan_counts.get(dom, {"scans": 0, "grade": None})
        disc = disc_map.get(dom)
        item["views"] = pv["views"]
        item["visitors"] = pv["visitors"]
        item["scans"] = sc["scans"]
        item["discovery"] = disc
        item["is_warm"] = (pv["views"] > 0) or (sc["scans"] > 0)

    conn.close()
    return converted_domains


def build_followup_message(t):
    d = t["domain"]
    org = t.get("org") or d
    lang = t.get("lang", "ar")
    disc = t.get("discovery")

    if lang == "ar":
        subject = f"متابعة أمنية: تقييم الجاهزية لما بعد الكم لنطاق {d} ({org})"
        disc_line = ""
        if disc and disc.get("responding"):
            disc_line = (
                f"- آخر قياس مسجل لنطاقاتكم الفرعية: {disc['not_pq']} من أصل {disc['responding']} نقطة HTTPS نشطة "
                f"ما زالت تستخدم تبادل المفاتيح التقليدي فقط (إجمالي النطاقات المكتشفة: {disc['names']}).\n"
            )
        body = (
            f"حضرة فريق القيادة التقنية وأمن المعلومات المحترم في {org}،\n\n"
            f"أتواصل معكم للمتابعة بشأن الفحص التقني لجاهزية التشفير ما بعد الكمومي (Post-Quantum TLS) لنطاق ({d}).\n\n"
            f"في الثغرات التقليدية، ينتهي الخطر بمجرد تطبيق التحديث (Patch). أما في تهديدات الحوسبة الكمومية "
            f"وهجمات «احفظ الآن، وفك التشفير لاحقاً» (Store Now, Decrypt Later)، فإن جلسات الاتصال التي يتم تسجيلها اليوم "
            f"أثناء استخدام تبادل المفاتيح التقليدي (RSA / x25519) لا يمكن حمايتها بأثر رجعي بعد أرشفتها.\n\n"
            f"{disc_line}"
            f"نود تذكيركم بأننا نتيح هذا الأسبوع لأول 3 مؤسسات تتواصل معنا استلام تقرير التدقيق الأولي "
            f"لخارطة النطاقات الفرعية مجاناً، شاملاً أولويات الترقية لتفعيل TLS 1.3 وتبادل المفاتيح الهجين (X25519MLKEM768).\n\n"
            f"- النتيجة المباشرة وطريقة الإصلاح: https://ather-quantum.com/site/{d}?lang=ar\n"
            f"- الملخص التنفيذي للإدارة (Executive Brief): https://ather-quantum.com/executive-brief/{d}?lang=ar\n"
            f"- لطلب القائمة الكاملة للنطاقات الفرعية وتقرير التدقيق المؤرَّخ (PDF): https://ather-quantum.com/audit?domain={d}&lang=ar\n\n"
            f"كما يمكنكم الرد مباشرة على هذا البريد بكلمة «تقرير» لإرسال الملخص الفني المخصص لنطاق {d}.\n\n"
            f"مع خالص التحية،\n"
            f"Quantum Aether\n"
            f"https://ather-quantum.com"
        )
    elif lang == "de":
        subject = f"Kurze Rückfrage: Post-Quanten-TLS-Prüfung für {d}"
        body = (
            f"Sehr geehrte IT-Sicherheitsverantwortliche,\n\n"
            f"ich melde mich kurz bezüglich unserer Messung der öffentlichen Subdomains von {d}.\n\n"
            f"Im Gegensatz zu klassischen Schwachstellen lässt sich bereits aufgezeichneter Datenverkehr "
            f"(Harvest now, decrypt later) nachträglich nicht mehr schützen. Jeder Tag ohne hybriden "
            f"Post-Quanten-Schlüsselaustausch (X25519MLKEM768) vergrößert das rückwirkende Risiko.\n\n"
            f"- Öffentliches Ergebnis & Anleitung: https://ather-quantum.com/site/{d}?lang=de\n"
            f"- Executive Brief (1 Seite): https://ather-quantum.com/executive-brief/{d}?lang=de\n"
            f"- Vollständige Hostliste & PDF-Audit anfordern: https://ather-quantum.com/audit?domain={d}&lang=de\n\n"
            f"Für die ersten drei Organisationen, die diese Woche antworten, stellen wir den vollständigen "
            f"Bericht kostenlos gegen kurzes Feedback bereit. Antworten Sie einfach kurz auf diese E-Mail.\n\n"
            f"Mit freundlichen Grüßen\n"
            f"Quantum Aether\n"
            f"https://ather-quantum.com"
        )
    else:
        subject = f"Follow-up: Post-quantum TLS readiness report for {d}"
        body = (
            f"Dear IT Security Team,\n\n"
            f"I am following up briefly on our post-quantum TLS measurement for {d}.\n\n"
            f"Unlike standard software vulnerabilities where a patch closes past exposure, traffic recorded today "
            f"under classical key exchange (Harvest Now, Decrypt Later) cannot be protected retroactively once stored.\n\n"
            f"- Live result & remediation guide: https://ather-quantum.com/site/{d}?lang=en\n"
            f"- 1-page Executive Risk Brief: https://ather-quantum.com/executive-brief/{d}?lang=en\n"
            f"- Request the full subdomain host list & dated PDF audit: https://ather-quantum.com/audit?domain={d}&lang=en\n\n"
            f"For the first three organizations that reply this week, we provide the complete subdomain audit "
            f"free of charge in exchange for your feedback. Simply reply to this email to request your copy.\n\n"
            f"Best regards,\n"
            f"Quantum Aether\n"
            f"https://ather-quantum.com"
        )
    return subject, body


def main():
    parser = argparse.ArgumentParser(description="Monday B2B Follow-up Tool")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--preview", action="store_true", help="معاينة الجهات المتفاعلة والرسائل بدون إرسال (افتراضي)")
    group.add_argument("--send-warm", action="store_true", help="إرسال المتابعة فقط للجهات التي زارت الموقع وتفاعلت (Warm Leads)")
    group.add_argument("--send-all", action="store_true", help="إرسال المتابعة لجميع جهات الحملات التي لم ترد بعد")
    args = parser.parse_args()

    load_env()
    targets_map = load_all_campaign_targets()
    converted = enrich_from_live_db(targets_map)

    # استبعاد banquemisr.com إذا كنا أرسلنا له المتابعة التفصيلية بالفعل، أو إبقاء القائمة محدثة
    skip_to, skip_dom = suppressed_addresses(), recently_contacted_domains()
    all_targets = [t for d, t in targets_map.items()
                   if d not in converted and d not in skip_dom and t["to"].lower() not in skip_to]
    print(f"مستبعَد: {sum(t['to'].lower() in skip_to for t in targets_map.values())} عنواناً مرتداً، "
          f"{sum(d in skip_dom for d in targets_map)} جهة وصلها عرض التجربة يوم 13 نوفمبر")
    warm_targets = [t for t in all_targets if t.get("is_warm")]

    print("=" * 72)
    print(f"إجمالي الجهات في الحملات الثلاث: {len(targets_map)}")
    print(f"الجهات الساخنة التي تفاعلت وزارت الموقع حتى الآن (Warm Leads): {len(warm_targets)}")
    print("=" * 72)

    if warm_targets:
        print("\nقائمة الجهات التي تفاعلت وزارت صفحاتها على الموقع (مرتبة حسب عدد الزيارات):")
        for idx, t in enumerate(sorted(warm_targets, key=lambda x: (-x["views"], -x["scans"], x["domain"])), 1):
            disc_str = ""
            if t.get("discovery"):
                d_info = t["discovery"]
                disc_str = f" | فحص النطاقات الفرعية: {d_info['not_pq']}/{d_info['responding']} غير محمي"
            print(
                f"  {idx:2d}. {t['domain']:22s} ({t['org']}) -> {t['to']} | "
                f"زيارات: {t['views']} (زوار: {t['visitors']}) | فحوصات حية: {t['scans']}{disc_str}"
            )

    if not args.send_warm and not args.send_all:
        print("\n[وضع المعاينة --preview]: لم يتم إرسال أي بريد الآن.")
        if warm_targets:
            sample = warm_targets[0]
            subj, body = build_followup_message(sample)
            print(f"\n--- نموذج رسالة المتابعة الجاهزة ليوم الاثنين ({sample['domain']}) ---")
            print(f"إلى: {sample['to']}")
            print(f"الموضوع: {subj}\n")
            print(body)
        print("\nلتشغيل الإرسال يوم الاثنين:")
        print("  1) لإرسال المتابعة للجهات المتفاعلة فقط (Warm Leads):")
        print("     python3 /root/quantum-aether/tools/send_monday_followup.py --send-warm")
        print(f"  2) لإرسال المتابعة لجميع الجهات المؤهلة ({len(all_targets)} مؤسسة):")
        print("     python3 /root/quantum-aether/tools/send_monday_followup.py --send-all")
        return 0

    selected = warm_targets if args.send_warm else all_targets
    out_path = os.path.join(INSTANCE_DIR, "b2b_monday_followup_results.json")
    if os.path.exists(out_path):
        print(f"Follow-up already executed ({out_path} exists). Skipping duplicate run.", flush=True)
        return 0

    api_key = os.environ.get("RESEND_API_KEY", "")
    # المرسل نفسه الذي يستخدمه الموقع (النطاق الجديد الموثّق)، والقديم احتياطاً فقط
    sender = os.environ.get("QS_MAIL_FROM", "") or "Quantum Aether <alerts@ather-quantum.com>"
    reply_to = os.environ.get("QS_REPLY_TO", "") or "alerts@ather-quantum.com"
    owner_email = os.environ.get("QS_OWNER_EMAIL", "sajad.vip56@gmail.com")

    if not api_key:
        print("ERROR: Missing RESEND_API_KEY", flush=True)
        return 1

    mailer = Mailer(api_key=api_key, sender=sender, reply_to=reply_to,
                    fallback_sender=os.environ.get("QS_MAIL_FROM_FALLBACK", ""), site_url="https://ather-quantum.com")
    sent_count = 0
    fail_count = 0
    results = []

    mode_label = "Warm Leads Only" if args.send_warm else "All Campaign Targets"
    print(f"\nStarting Monday Follow-up ({mode_label}): {len(selected)} targets...", flush=True)
    for idx, t in enumerate(selected, 1):
        subj, body = build_followup_message(t)
        ok = mailer.send(t["to"], subj, body)
        status = "SENT" if ok else "FAILED"
        if ok:
            sent_count += 1
        else:
            fail_count += 1
        print(f"[{idx}/{len(selected)}] {t['domain']} -> {t['to']} | {status}", flush=True)
        results.append({
            "index": idx,
            "domain": t["domain"],
            "org": t.get("org", t["domain"]),
            "to": t["to"],
            "views": t.get("views", 0),
            "scans": t.get("scans", 0),
            "subject": subj,
            "status": status,
        })
        time.sleep(0.55)

    out_path = os.path.join(INSTANCE_DIR, "b2b_monday_followup_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "mode": mode_label,
            "sender": sender,
            "total": len(selected),
            "sent": sent_count,
            "failed": fail_count,
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    os.chmod(out_path, 0o600)

    mailer.send(
        owner_email,
        f"Quantum Aether: اكتملت متابعة يوم الاثنين ({sent_count}/{len(selected)})",
        f"تم إرسال رسائل المتابعة ({mode_label}) إلى {sent_count} مؤسسة بنجاح.\nالسجل المحمي: {out_path}",
    )
    print(f"Done: {sent_count} sent, {fail_count} failed. Saved privately to {out_path}.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
