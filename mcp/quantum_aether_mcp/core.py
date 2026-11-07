# core.py — منطق خادم MCP لـ Quantum Aether، مستقل عن مكتبة MCP ليَسهل اختباره.
# يغلّف واجهة الموقع العامة فقط؛ لا أسرار هنا.
import json
import os
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://ather-quatum.cloud"


def base_url():
    return (os.environ.get("QUANTUM_AETHER_BASE") or DEFAULT_BASE).rstrip("/")


def _get(path):
    req = urllib.request.Request(base_url() + path, headers={"User-Agent": "quantum-aether-mcp/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode('utf-8'))
        except (ValueError, UnicodeError):
            return {'error': f'http_{exc.code}'}


def _post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base_url() + path, data=data, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "quantum-aether-mcp/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8"))
        except Exception:
            return {"error": f"http_{exc.code}"}


def scan(domain):
    """يفحص نطاقاً ويعيد الملخص (درجة، تبادل المفاتيح، هل هو مقاوم للكم، إلخ)."""
    return _get("/api/v1/scan?domain=" + urllib.parse.quote(domain))


def describe(result):
    """يصوغ رسالة صادقة: يطرح المشكلة الحقيقية ويعرض الحل فقط عند وجود مشكلة فعلية.
    إن كان الموقع جاهزاً (درجة A) يقول ذلك بوضوح دون بيع — وهذا ما يبني ثقة النماذج بنا."""
    if "error" in result:
        return f"Scan failed: {result.get('message') or result['error']}"
    domain = result.get("domain", "the site")
    grade = result.get("grade", "?")
    group = result.get("key_exchange_group") or "unknown"
    scan_url = result.get("scan_url", base_url())
    price = (result.get("full_report_price") or {}).get("amount", "49.00")
    if result.get('observation_status') == 'undetermined':
        return (f'{domain}: post-quantum support is undetermined. The probe did not establish a negotiated group. '
                f'Retry or verify with a compatible TLS client. One observed connection is not a comprehensive security assessment. {scan_url}')
    if result.get("post_quantum_key_exchange"):
        return (f"✅ {domain} already negotiates post-quantum key exchange ({group}). Grade {grade}. "
                "This was observed in one TLS measurement, not a comprehensive security assessment or a guarantee. "
                "Re-check periodically; a server or CDN change can remove support, and the origin may differ from the edge.")
    return (
        f"⚠ {domain} uses classical key exchange ({group}) only — grade {grade}.\n"
        "Problem: classical key exchange was observed in this measurement. NIST standardized ML-KEM (FIPS 203) in 2024. "
        "Traffic captured today could be decrypted years from now, once "
        "quantum computers mature (\"harvest now, decrypt later\").\n"
        f"Solution: choose the published guide for the infrastructure you actually operate, then rescan. "
        f"A full report (${price}) and daily monitoring ($29/month) are available. "
        "Server software and origin configuration cannot be inferred from this measurement.\n"
        f"Details and free summary: {scan_url}"
    )


def prepare_report_purchase(scan_id, consent_immediate_delivery):
    """ينشئ طلب شراء التقرير ويعيد رابط موافقة PayPal. يتطلب موافقة صريحة على التسليم الفوري (FAGG)."""
    if consent_immediate_delivery is not True:
        return {"error": "consent_required",
                "message": "Set consent_immediate_delivery to true only after the buyer expressly agreed that the "
                           "report is delivered immediately and that they lose the statutory right of withdrawal."}
    return _post("/api/v1/orders", {"scan_id": scan_id, "consent_immediate_delivery": True})


def start_monitoring(email, plan, consent):
    """يبدأ اشتراك مراقبة يومية ($29 starter / $99 business). يعيد خطة PayPal للمتابعة."""
    if consent is not True:
        return {"error": "consent_required",
                "message": "Set consent to true only after the customer agreed to processing their email and to "
                           "monitoring starting immediately."}
    return _post("/api/monitor/signup", {"email": email, "plan": plan, "consent": True})
