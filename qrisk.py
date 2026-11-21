# qrisk.py — درجة التعرّض الكمّي (0–100) وملف CBOM بصيغة CycloneDX 1.6 من نتيجة فحص TLS واحدة.
# 2026-11-21. الدرجة شفافة: كل نقطة لها بند ظاهر وسبب، والمعادلة منشورة في FORMULA_VERSION.
# تُبنى فقط على ما قاسه الفحص فعلاً (لا تخمين عن البرمجيات أو البيانات). ملاحظة خارجية وليست شهادة امتثال.
# أعلى = تعرّض أكبر. نتيجة «غير محدد» لا تُعطى درجة (None) حتى لا نخترع رقماً.
import datetime as dt
import uuid

import scan_experience

FORMULA_VERSION = "qes-1"

# الأوزان (المجموع الأقصى 100). تبادل المفاتيح هو الخطر العملي الوحيد اليوم: «احصد الآن، فكّ لاحقاً».
W_KX_TLS12 = 70          # TLS 1.2: لا يوجد تبادل مفاتيح هجين معياري أصلاً
W_KX_CLASSICAL = 60      # TLS 1.3 بتبادل كلاسيكي (x25519 / secp256r1 ...)
W_ENDPOINTS_MIXED = 30   # بعض عناوين النطاق ما بعد كمّية وبعضها لا (حسب DNS قد يصل الزائر لعنوان كلاسيكي)
W_HOST_EACH = 5          # كل نطاق فرعي شائع (www/api/mail/auth/login) يجيب بتبادل كلاسيكي
W_HOSTS_MAX = 20
W_CERT_CLASSICAL = 10    # توقيع الشهادة كلاسيكي — عام في كل الويب اليوم، لا إجراء مطلوب الآن (لا شهادات PQ في WebPKI)

BANDS = ((0, 15, "low"), (16, 45, "moderate"), (46, 100, "high"))


def _band(score):
    for lo, hi, name in BANDS:
        if lo <= score <= hi:
            return name
    return "high"


def score(result, insights=None):
    """→ {"score": int|None, "band", "items": [{"code","points","params"}], "hosts_checked": bool, "version"}.

    insights = scan_insights.compute() result (optional; the common-hosts check runs asynchronously)."""
    state = scan_experience.status(result)
    out = {"version": FORMULA_VERSION, "hosts_checked": insights is not None, "items": []}
    if state == "undetermined":
        return dict(out, score=None, band="undetermined")
    kx, cert = result.get("key_exchange") or {}, result.get("certificate") or {}
    items = out["items"]
    tls = str(kx.get("version") or cert.get("negotiated_version") or "")
    if state == "observed_classical":
        if tls and "1.3" not in tls:
            items.append({"code": "kx_tls12", "points": W_KX_TLS12, "params": {"version": tls}})
        else:
            items.append({"code": "kx_classical", "points": W_KX_CLASSICAL, "params": {"group": kx.get("group") or "?"}})
    else:
        summary = result.get("endpoint_summary") or {}
        if summary.get("mixed"):
            items.append({"code": "endpoints_mixed", "points": W_ENDPOINTS_MIXED,
                          "params": {"pq": summary.get("pq"), "total": summary.get("total")}})
    if insights is not None:
        classical = list(insights.get("classical") or [])
        if classical:
            items.append({"code": "hosts_classical", "points": min(W_HOSTS_MAX, W_HOST_EACH * len(classical)),
                          "params": {"hosts": classical}})
    sig = str(cert.get("signature_algorithm") or "").lower()
    if not any(p in sig for p in ("ml-dsa", "mldsa", "slh-dsa", "slhdsa", "falcon", "fn-dsa")):
        items.append({"code": "cert_classical", "points": W_CERT_CLASSICAL,
                      "params": {"algorithm": cert.get("signature_algorithm") or "?"}})
    total = min(100, sum(i["points"] for i in items))
    return dict(out, score=total, band=_band(total))


# ---------------------------------------------------------------- CBOM (CycloneDX 1.6 cryptographic assets)

_GROUP_PRIMITIVE = {"x25519mlkem768": ("kem", "X25519MLKEM768", True), "secp256r1mlkem768": ("kem", "SecP256r1MLKEM768", True),
                    "secp384r1mlkem1024": ("kem", "SecP384r1MLKEM1024", True), "x25519kyber768draft00": ("kem", "X25519Kyber768Draft00", True),
                    "x25519": ("key-agree", "X25519", False), "x448": ("key-agree", "X448", False),
                    "secp256r1": ("key-agree", "ECDH-P256", False), "secp384r1": ("key-agree", "ECDH-P384", False),
                    "secp521r1": ("key-agree", "ECDH-P521", False)}


def _nist_level(pq):
    return 3 if pq else 0  # ML-KEM-768 ≈ category 3; classical key agreement offers no quantum security


def cbom(result, insights=None, now=None):
    """Minimal CycloneDX 1.6 CBOM for the observed public TLS endpoint. Only observed facts; no inferred assets."""
    now = now or dt.datetime.now(dt.timezone.utc)
    kx, cert = result.get("key_exchange") or {}, result.get("certificate") or {}
    domain = result["domain"]
    tls = kx.get("version") or cert.get("negotiated_version")
    comps = []

    def add(ref, name, props):
        comps.append({"type": "cryptographic-asset", "bom-ref": ref, "name": name, "cryptoProperties": props})

    if tls:
        add("protocol-tls", str(tls), {"assetType": "protocol", "protocolProperties": {
            "type": "tls", "version": str(tls).replace("TLSv", ""),
            "cipherSuites": [{"name": c} for c in {kx.get("cipher"), cert.get("negotiated_cipher")} if c]}})
    group = (kx.get("group") or "").lower()
    if group:
        primitive, name, pq = _GROUP_PRIMITIVE.get(group, ("key-agree", kx.get("group"), bool(kx.get("pq"))))
        add("kx-" + group, name, {"assetType": "algorithm", "algorithmProperties": {
            "primitive": primitive, "executionEnvironment": "unknown", "cryptoFunctions": ["keygen", "encapsulate" if pq else "keyderive"],
            "nistQuantumSecurityLevel": _nist_level(pq)}})
    cipher = kx.get("cipher") or cert.get("negotiated_cipher")
    if cipher:
        add("cipher-" + cipher.lower(), cipher, {"assetType": "algorithm", "algorithmProperties": {
            "primitive": "ae", "cryptoFunctions": ["encrypt", "decrypt"],
            # AES-128 → ~64-bit vs Grover (NIST still counts AES-128 as category 1); AES-256/ChaCha20 → category 5
            "nistQuantumSecurityLevel": 1 if "128" in cipher else 5}})
    if cert.get("key_algorithm"):
        key = f"{cert['key_algorithm']}-{cert.get('key_bits') or '?'}"
        add("cert-key", key, {"assetType": "algorithm", "algorithmProperties": {
            "primitive": "signature", "cryptoFunctions": ["sign", "verify"], "nistQuantumSecurityLevel": 0,
            **({"curve": cert["curve"]} if cert.get("curve") else {})}})
        add("certificate", cert.get("subject") or domain, {"assetType": "certificate", "certificateProperties": {
            "subjectName": cert.get("subject") or domain, "issuerName": cert.get("issuer") or "",
            "notValidAfter": cert.get("not_after") or "", "signatureAlgorithmRef": "cert-key",
            "certificateFormat": "X.509"}})
    risk = score(result, insights)
    props = [{"name": "quantum-aether:exposure-score", "value": "" if risk["score"] is None else str(risk["score"])},
             {"name": "quantum-aether:exposure-band", "value": risk["band"]},
             {"name": "quantum-aether:formula", "value": FORMULA_VERSION},
             {"name": "quantum-aether:scanned-at", "value": result.get("scanned_at") or ""},
             {"name": "quantum-aether:observed-address", "value": result.get("ip") or ""},
             {"name": "quantum-aether:limitation", "value": scan_experience.LIMITATION}]
    for h in (insights or {}).get("classical") or []:
        props.append({"name": "quantum-aether:classical-subdomain", "value": h})
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.6", "serialNumber": f"urn:uuid:{uuid.uuid4()}", "version": 1,
        "metadata": {"timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "tools": {"components": [{"type": "application", "name": "Quantum Aether",
                                               "version": str(result.get("scanner_version") or "")}]},
                     "component": {"type": "application", "bom-ref": "service", "name": domain,
                                   "description": f"Public TLS endpoint {domain}:{result.get('port') or 443}"},
                     "properties": props},
        "components": comps,
        "dependencies": [{"ref": "service", "dependsOn": [c["bom-ref"] for c in comps]}],
    }
