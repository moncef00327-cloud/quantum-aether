#!/usr/bin/env python3
"""GitHub Action: يفحص جاهزية TLS لما بعد الكم لنطاق ويكتب النتيجة في ملخّص الـ workflow.

يفشل حين يطلب المستخدم ذلك صراحةً (require-post-quantum أو min-grade) ويكون الموقع دون المطلوب، أو حين يكون
اسم النطاق غير صالح، أو حين يتعذّر الفحص (حدّ الفحص، عطل الخدمة، رد ناقص): فحص لم يجرِ لا يمرّ بصمت (منذ 2026-11-07).
نتيجة غير محسومة (observation_status = undetermined) لا تُعرض كـ «كلاسيكي» ولا تُعدّ نجاحاً حين يُطلب PQ.
مكتبة بايثون القياسية فقط، فيعمل على كل المشغّلات بلا تثبيت.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

GRADES = ["A", "B", "C", "F"]
GUIDE = "https://ather-quantum.com/guides/enable-x25519mlkem768-nginx"


def fetch(base, domain, timeout=60):
    """يعيد (رمز HTTP، القاموس). لا يرفع استثناء لأخطاء HTTP."""
    url = base.rstrip("/") + "/api/v1/scan?domain=" + urllib.parse.quote(domain)
    req = urllib.request.Request(url, headers={"User-Agent": "quantum-aether-action/1.1.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except ValueError:
            return exc.code, {}


def evaluate(result, require_pq, min_grade):
    """يعيد (ناجح؟، رسالة). يفشل فقط بما طلبه المستخدم صراحةً."""
    grade, pq = result.get("grade"), bool(result.get("post_quantum_key_exchange"))
    group = result.get("key_exchange_group") or "unknown"
    if require_pq and _undetermined(result):
        return False, (f"{result.get('domain')}: post-quantum key exchange is undetermined (the probe did not observe a "
                       "negotiated group). Re-run the check.")
    if require_pq and not pq:
        return False, (f"{result.get('domain')} does not negotiate post-quantum key exchange (got {group}, grade {grade}). "
                       f"How to enable it: {GUIDE}")
    if min_grade in GRADES and grade in GRADES and GRADES.index(grade) > GRADES.index(min_grade):
        return False, f"{result.get('domain')} has grade {grade}, worse than the required {min_grade}."
    state = "undetermined" if _undetermined(result) else ("yes" if pq else "no")
    return True, f"{result.get('domain')}: grade {grade}, key exchange {group}, post-quantum {state}."


def _undetermined(result):
    return result.get("post_quantum_key_exchange") is None or result.get("observation_status") == "undetermined"


def summary_markdown(result):
    pq = bool(result.get("post_quantum_key_exchange"))
    unknown = _undetermined(result)
    lines = [
        "### Post-quantum TLS check",
        "",
        "| Domain | Grade | Key exchange | Post-quantum |",
        "|---|---|---|---|",
        f"| `{result.get('domain')}` | **{result.get('grade')}** | `{result.get('key_exchange_group') or '?'}` | "
        f"{'❔ undetermined' if unknown else ('✅ yes' if pq else '⚠️ no')} |",
        "",
    ]
    if unknown:
        lines += ["The probe did not observe a negotiated key-exchange group, so post-quantum support is undetermined. "
                  "Re-run the check; this is not a classical-only result.", ""]
    elif not pq:
        lines += ["Traffic to this site uses classical key exchange only, so it can be recorded today and decrypted "
                  f"later (\"harvest now, decrypt later\"). [How to enable X25519MLKEM768]({GUIDE})", ""]
    if result.get("scan_url"):
        lines.append(f"[Full result]({result['scan_url']}) · scanned by [Quantum Aether](https://ather-quantum.com)")
    return "\n".join(lines) + "\n"


def write_env_file(name, text):
    path = os.environ.get(name)
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)


def main(fetcher=fetch):
    domain = (os.environ.get("INPUT_DOMAIN") or "").strip()
    require_pq = (os.environ.get("INPUT_REQUIRE_PQ") or "false").strip().lower() == "true"
    min_grade = (os.environ.get("INPUT_MIN_GRADE") or "").strip().upper()
    base = (os.environ.get("INPUT_BASE_URL") or "https://ather-quantum.com").strip()
    if not domain:
        print("::error::input 'domain' is required")
        return 1
    try:
        status, data = fetcher(base, domain)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"::warning::Post-quantum TLS check skipped: scanner unreachable ({exc})")
        return 1
    if status == 429:
        print("::warning::Post-quantum TLS check skipped: scan rate limit reached, try again later")
        return 1
    if status == 400:
        print(f"::error::Invalid domain '{domain}': {data.get('message') or data.get('error')}")
        return 1
    if status != 200 or "grade" not in data:
        print(f"::warning::Post-quantum TLS check skipped: scanner returned HTTP {status}")
        return 1
    write_env_file("GITHUB_OUTPUT", "".join([
        f"grade={data.get('grade')}\n",
        f"post-quantum={'true' if data.get('post_quantum_key_exchange') else 'false'}\n",
        f"key-exchange={data.get('key_exchange_group') or ''}\n",
        f"scan-url={data.get('scan_url') or ''}\n",
    ]))
    write_env_file("GITHUB_STEP_SUMMARY", summary_markdown(data))
    ok, message = evaluate(data, require_pq, min_grade)
    print(message if ok else f"::error::{message}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
