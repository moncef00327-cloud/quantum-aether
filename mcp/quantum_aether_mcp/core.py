# core.py — منطق خادم MCP لـ Quantum Aether، مستقل عن مكتبة MCP ليَسهل اختباره.
# يغلّف واجهة الموقع العامة فقط؛ لا أسرار هنا.
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

from . import __version__

DEFAULT_BASE = "https://ather-quantum.com"
TIMEOUT = 30
USER_AGENT = f"quantum-aether-mcp/{__version__}"


def base_url():
    return (os.environ.get("QUANTUM_AETHER_BASE") or DEFAULT_BASE).rstrip("/")


def _decode(raw):
    """JSON → dict. أي رد آخر (HTML من وكيل، نص فارغ، مصفوفة) يصبح خطأً مفهوماً بدل استثناء."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError):
        return None
    return data if isinstance(data, dict) else None


def _request(path, payload=None):
    """طلب واحد إلى الواجهة العامة. لا يرمي استثناءً أبداً: كل فشل يعود كـ {"error", "message"}
    حتى يرى المساعد سبباً واضحاً بدل «urlopen error» خام."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base_url() + path, data=data, headers=headers,
                                 method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = _decode(r.read())
    except urllib.error.HTTPError as exc:
        body = _decode(exc.read() or b"")
        if body is None:
            return {"error": f"http_{exc.code}", "message": f"Quantum Aether API returned HTTP {exc.code}."}
        return body
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
        reason = getattr(exc, "reason", exc)
        return {"error": "network_error",
                "message": f"Could not reach the Quantum Aether API at {base_url()} ({reason}). "
                           "Check the network connection and try again."}
    if body is None:
        return {"error": "invalid_response", "message": "The Quantum Aether API returned a non-JSON response."}
    return body


def _clean_id(value, name):
    value = value.strip() if isinstance(value, str) else ""
    if not value:
        return None, {"error": f"{name}_required", "message": f"Provide the {name} returned by an earlier call."}
    return value, None


def scan(domain):
    """يفحص نطاقاً ويعيد الملخص (درجة، تبادل المفاتيح، هل هو مقاوم للكم، إلخ)."""
    domain = domain.strip() if isinstance(domain, str) else ""
    if not domain:
        return {"error": "invalid_domain", "message": "Provide a domain name, e.g. example.com."}
    return _request("/api/v1/scan?domain=" + urllib.parse.quote(domain, safe=""))


def get_scan(scan_id):
    """يعيد نتيجة فحص سابق بمعرّفه، دون فحص جديد."""
    scan_id, err = _clean_id(scan_id, "scan_id")
    if err:
        return err
    return _request("/api/scan/" + urllib.parse.quote(scan_id, safe=""))


def order_status(order_id):
    """حالة طلب شراء التقرير؛ عند اكتمال الدفع يحوي report_url."""
    order_id, err = _clean_id(order_id, "order_id")
    if err:
        return err
    return _request("/api/v1/orders/" + urllib.parse.quote(order_id, safe=""))


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
    scan_id, err = _clean_id(scan_id, "scan_id")
    if err:
        return err
    return _request("/api/v1/orders", {"scan_id": scan_id, "consent_immediate_delivery": True})


def start_monitoring(email, plan, consent):
    """يبدأ اشتراك مراقبة يومية ($29 starter / $99 business). يعيد خطة PayPal للمتابعة."""
    if consent is not True:
        return {"error": "consent_required",
                "message": "Set consent to true only after the customer agreed to processing their email and to "
                           "monitoring starting immediately."}
    if plan not in ("starter", "business"):
        return {"error": "invalid_plan", "message": 'plan must be "starter" or "business".'}
    return _request("/api/monitor/signup", {"email": email, "plan": plan, "consent": True})
