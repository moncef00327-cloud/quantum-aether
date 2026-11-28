"""A2UI (Agent-to-User Interface, v0.8) declarative UI cards for Quantum Aether A2A & HTTP.

Pure stdlib, zero external dependencies. Emits spec-compliant A2UI v0.8 messages
(`surfaceUpdate`, `dataModelUpdate`, `beginRendering`) using the standard component
catalog (`Card`, `Column`, `Row`, `Text`, `Divider`, `Button`) and wraps them as
A2A `DataPart` objects with `metadata.mimeType = "application/json+a2ui"`.
"""
from __future__ import annotations

import re

A2UI_VERSION = "0.8"
A2UI_EXTENSION_URI = "https://a2ui.org/a2a-extension/a2ui/v0.8"
A2UI_CATALOG_ID = "https://a2ui.org/specification/v0_8/standard_catalog_definition.json"
A2UI_MIME = "application/json+a2ui"

_SAFE_ID_RE = re.compile(r"[^a-z0-9_-]+")


def _surface_id(prefix: str, key: str = "") -> str:
    slug = _SAFE_ID_RE.sub("-", (key or "default").lower()).strip("-")[:48] or "default"
    return f"qa-{prefix}-{slug}"


def client_wants_a2ui(headers=None, params=None, message=None, data=None) -> bool:
    """Return True if the caller negotiated the A2UI A2A extension or opted in explicitly."""
    if headers:
        ext_hdr = headers.get("X-A2A-Extensions") or headers.get("x-a2a-extensions") or ""
        if "a2ui.org/a2a-extension/a2ui" in ext_hdr.lower() or "application/json+a2ui" in (headers.get("Accept") or "").lower():
            return True
    for container in (params, message):
        if isinstance(container, dict):
            meta = container.get("metadata")
            if isinstance(meta, dict):
                if meta.get("a2ui") is True:
                    return True
                exts = meta.get("extensions") or meta.get("a2a_extensions") or []
                if isinstance(exts, str) and "a2ui" in exts.lower():
                    return True
                if isinstance(exts, list) and any("a2ui" in str(x).lower() for x in exts):
                    return True
    if isinstance(data, dict):
        if data.get("a2ui") is True:
            return True
        if str(data.get("format") or "").strip().lower() == "a2ui":
            return True
    return False


def create_a2ui_part(a2ui_message: dict) -> dict:
    """Wrap a single A2UI v0.8 message in an A2A 0.3 DataPart with application/json+a2ui MIME."""
    return {
        "kind": "data",
        "data": a2ui_message,
        "metadata": {
            "mimeType": A2UI_MIME,
            "extensionUri": A2UI_EXTENSION_URI,
        },
    }


def create_a2ui_parts(messages: list[dict]) -> list[dict]:
    """Wrap a sequence of A2UI v0.8 messages (`surfaceUpdate`, `dataModelUpdate`, `beginRendering`)."""
    return [create_a2ui_part(m) for m in messages if isinstance(m, dict)]


def _str_entry(key: str, value: str) -> dict:
    return {"key": key, "valueString": str(value)}


def _status_copy(state: str, obs_status: str, pq: bool | None, lang: str) -> tuple[str, str]:
    l = lang if lang in ("ar", "de", "en") else "en"
    if state == "not_scanned":
        return {
            "ar": ("لم يُفحص بعد", "لا يوجد قياس مخزّن لهذا النطاق بعد — يمكنك تشغيل فحص مباشر فوري."),
            "de": ("Noch nicht geprüft", "Für diese Domain liegt noch kein gespeicherter Messwert vor — Live-Scan starten."),
            "en": ("Not Scanned Yet", "No stored measurement exists yet — run a live port-443 TLS scan."),
        }[l]
    if pq is True or obs_status == "observed_pq":
        return {
            "ar": ("جاهز لما بعد الكم ✓", "يتفاوض الخادم على تبادل مفاتيح هجين مقاوم للكم (PQ-TLS)."),
            "de": ("Post-Quantum-bereit ✓", "Der Server handelt hybriden Post-Quantum-Schlüsselaustausch aus."),
            "en": ("Post-Quantum Ready ✓", "Server negotiates hybrid post-quantum TLS key exchange."),
        }[l]
    if pq is False or obs_status == "observed_classical":
        return {
            "ar": ("تشفير تقليدي فقط", "لم يُرصد تبادل مفاتيح ما بعد الكم (عرضة لخطر Harvest Now, Decrypt Later)."),
            "de": ("Nur klassisches TLS", "Kein Post-Quantum-Schlüsselaustausch beobachtet (Harvest-Now-Decrypt-Later-Risiko)."),
            "en": ("Classical TLS Only", "No post-quantum key exchange negotiated (Harvest Now, Decrypt Later exposure)."),
        }[l]
    return {
        "ar": ("غير محسوم", "تعذّر حسم حالة تبادل المفاتيح؛ أعد الفحص للتحقق."),
        "de": ("Nicht eindeutig", "Schlüsselaustausch konnte nicht eindeutig bestimmt werden."),
        "en": ("Undetermined", "Key exchange could not be conclusively determined."),
    }[l]


def tls_result_messages(
    domain: str,
    data: dict,
    *,
    base: str = "https://ather-quantum.com",
    lang: str = "en",
) -> list[dict]:
    """Build A2UI v0.8 messages (`surfaceUpdate`, `dataModelUpdate`, `beginRendering`) for a TLS evidence/scan payload."""
    b = base.rstrip("/")
    l = lang if lang in ("ar", "de", "en") else "en"
    sid = _surface_id("tls", domain)

    state = str(data.get("state") or "")
    obs = str(data.get("observation_status") or "")
    pq = data.get("post_quantum_key_exchange")
    if pq is None and obs:
        pq = True if obs == "observed_pq" else (False if obs == "observed_classical" else None)

    status_badge, status_detail = _status_copy(state, obs, pq, l)
    grade = str(data.get("grade") or ("—" if state == "not_scanned" else "?"))
    group = str(data.get("key_exchange_group") or data.get("group") or ("—" if state == "not_scanned" else "unknown"))
    tls_ver = str(data.get("tls_version") or ("TLS 1.3" if pq else "—"))
    checked_at = str(data.get("checked_at") or data.get("scanned_at") or "—")
    scan_id = str(data.get("scan_id") or "")

    receipt_obj = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}
    receipt_jti = str(receipt_obj.get("jti") or "")
    has_jws = bool(data.get("signed_receipt_jws") or data.get("receipt_jws"))
    receipt_label = (
        f"Ed25519 JWS ✓ ({receipt_jti})" if receipt_jti
        else ("Ed25519 JWS ✓" if has_jws else "—")
    )

    verify_url = (
        f"{b}/scan/{scan_id}?lang={l}" if scan_id
        else str(data.get("verification_url") or f"{b}/verify/{domain}")
    )
    monitoring_url = f"{b}/monitoring?domain={domain}#trial-form"
    jwks_url = f"{b}/.well-known/jwks.json"
    msp_url = f"{b}/partners?lang={l}#msp-pilot"

    labels = {
        "ar": {
            "brand": "Quantum Aether · دليل TLS لما بعد الكم",
            "grade": "الدرجة",
            "group": "تبادل المفاتيح",
            "tls": "إصدار TLS",
            "checked": "آخر قياس",
            "receipt": "الإيصال الموقّع",
            "primary_btn": "افحص النطاق الآن" if state == "not_scanned" else "فتح صفحة التحقق والإيصال",
            "rescan_btn": "إعادة الفحص المباشر",
            "monitor_btn": "مراقبة مجانية 14 يوماً",
            "msp_btn": "MSP Pilot (290 €)",
        },
        "de": {
            "brand": "Quantum Aether · Post-Quantum-TLS-Nachweis",
            "grade": "Note",
            "group": "Schlüsselaustausch",
            "tls": "TLS-Version",
            "checked": "Geprüft am",
            "receipt": "Signierte Quittung",
            "primary_btn": "Live-Scan starten" if state == "not_scanned" else "Nachweis & Quittung öffnen",
            "rescan_btn": "Neu prüfen",
            "monitor_btn": "14 Tage kostenlos überwachen",
            "msp_btn": "MSP Pilot (290 €)",
        },
        "en": {
            "brand": "Quantum Aether · Post-Quantum TLS Evidence",
            "grade": "Grade",
            "group": "Key Exchange",
            "tls": "TLS Version",
            "checked": "Checked At",
            "receipt": "Signed Receipt",
            "primary_btn": "Run Live Scan" if state == "not_scanned" else "Open Report & Receipt",
            "rescan_btn": "Re-scan Now",
            "monitor_btn": "14-Day Free Monitoring",
            "msp_btn": "MSP Pilot (290 €)",
        },
    }[l]

    primary_action = (
        {
            "name": "tls_scan",
            "context": [
                {"key": "skill", "value": {"literalString": "tls-scan"}},
                {"key": "domain", "value": {"path": "/domain"}},
            ],
        }
        if state == "not_scanned"
        else {
            "name": "open_url",
            "context": [{"key": "url", "value": {"path": "/verifyUrl"}}],
        }
    )

    button_ids = ["btn-primary", "btn-monitor"]
    if state != "not_scanned":
        button_ids.insert(1, "btn-rescan")
    button_ids.append("btn-msp")

    components = [
        {"id": "root-card", "component": {"Card": {"child": "main-col"}}},
        {
            "id": "main-col",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": [
                            "brand-caption",
                            "header-row",
                            "status-detail",
                            "divider-1",
                            "metrics-row-1",
                            "metrics-row-2",
                            "receipt-row",
                            "divider-2",
                            "actions-row",
                        ]
                    }
                }
            },
        },
        {"id": "brand-caption", "component": {"Text": {"text": {"literalString": labels["brand"]}, "usageHint": "caption"}}},
        {"id": "header-row", "component": {"Row": {"children": {"explicitList": ["domain-title", "status-badge"]}}}},
        {"id": "domain-title", "component": {"Text": {"text": {"path": "/domain"}, "usageHint": "h2"}}},
        {"id": "status-badge", "component": {"Text": {"text": {"path": "/statusBadge"}, "usageHint": "h3"}}},
        {"id": "status-detail", "component": {"Text": {"text": {"path": "/statusDetail"}, "usageHint": "body"}}},
        {"id": "divider-1", "component": {"Divider": {}}},
        {"id": "metrics-row-1", "component": {"Row": {"children": {"explicitList": ["metric-grade", "metric-group"]}}}},
        {"id": "metric-grade", "component": {"Column": {"children": {"explicitList": ["lbl-grade", "val-grade"]}}}},
        {"id": "lbl-grade", "component": {"Text": {"text": {"literalString": labels["grade"]}, "usageHint": "caption"}}},
        {"id": "val-grade", "component": {"Text": {"text": {"path": "/grade"}, "usageHint": "h3"}}},
        {"id": "metric-group", "component": {"Column": {"children": {"explicitList": ["lbl-group", "val-group"]}}}},
        {"id": "lbl-group", "component": {"Text": {"text": {"literalString": labels["group"]}, "usageHint": "caption"}}},
        {"id": "val-group", "component": {"Text": {"text": {"path": "/keyExchangeGroup"}, "usageHint": "body"}}},
        {"id": "metrics-row-2", "component": {"Row": {"children": {"explicitList": ["metric-tls", "metric-checked"]}}}},
        {"id": "metric-tls", "component": {"Column": {"children": {"explicitList": ["lbl-tls", "val-tls"]}}}},
        {"id": "lbl-tls", "component": {"Text": {"text": {"literalString": labels["tls"]}, "usageHint": "caption"}}},
        {"id": "val-tls", "component": {"Text": {"text": {"path": "/tlsVersion"}, "usageHint": "body"}}},
        {"id": "metric-checked", "component": {"Column": {"children": {"explicitList": ["lbl-checked", "val-checked"]}}}},
        {"id": "lbl-checked", "component": {"Text": {"text": {"literalString": labels["checked"]}, "usageHint": "caption"}}},
        {"id": "val-checked", "component": {"Text": {"text": {"path": "/checkedAt"}, "usageHint": "caption"}}},
        {"id": "receipt-row", "component": {"Row": {"children": {"explicitList": ["lbl-receipt", "val-receipt"]}}}},
        {"id": "lbl-receipt", "component": {"Text": {"text": {"literalString": labels["receipt"]}, "usageHint": "caption"}}},
        {"id": "val-receipt", "component": {"Text": {"text": {"path": "/receiptStatus"}, "usageHint": "caption"}}},
        {"id": "divider-2", "component": {"Divider": {}}},
        {"id": "actions-row", "component": {"Row": {"children": {"explicitList": button_ids}}}},
        {"id": "btn-primary", "component": {"Button": {"child": "btn-primary-txt", "primary": True, "action": primary_action}}},
        {"id": "btn-primary-txt", "component": {"Text": {"text": {"literalString": labels["primary_btn"]}}}},
        {
            "id": "btn-monitor",
            "component": {
                "Button": {
                    "child": "btn-monitor-txt",
                    "primary": False,
                    "action": {"name": "open_url", "context": [{"key": "url", "value": {"path": "/monitoringUrl"}}]},
                }
            },
        },
        {"id": "btn-monitor-txt", "component": {"Text": {"text": {"literalString": labels["monitor_btn"]}}}},
        {
            "id": "btn-msp",
            "component": {
                "Button": {
                    "child": "btn-msp-txt",
                    "primary": False,
                    "action": {"name": "open_url", "context": [{"key": "url", "value": {"path": "/mspPilotUrl"}}]},
                }
            },
        },
        {"id": "btn-msp-txt", "component": {"Text": {"text": {"literalString": labels["msp_btn"]}}}},
    ]

    if state != "not_scanned":
        components.extend([
            {
                "id": "btn-rescan",
                "component": {
                    "Button": {
                        "child": "btn-rescan-txt",
                        "primary": False,
                        "action": {
                            "name": "tls_scan",
                            "context": [
                                {"key": "skill", "value": {"literalString": "tls-scan"}},
                                {"key": "domain", "value": {"path": "/domain"}},
                            ],
                        },
                    }
                },
            },
            {"id": "btn-rescan-txt", "component": {"Text": {"text": {"literalString": labels["rescan_btn"]}}}},
        ])

    return [
        {"surfaceUpdate": {"surfaceId": sid, "components": components}},
        {
            "dataModelUpdate": {
                "surfaceId": sid,
                "path": "/",
                "contents": [
                    _str_entry("domain", domain),
                    _str_entry("statusBadge", status_badge),
                    _str_entry("statusDetail", status_detail),
                    _str_entry("grade", grade),
                    _str_entry("keyExchangeGroup", group),
                    _str_entry("tlsVersion", tls_ver),
                    _str_entry("checkedAt", checked_at),
                    _str_entry("receiptStatus", receipt_label),
                    _str_entry("verifyUrl", verify_url),
                    _str_entry("monitoringUrl", monitoring_url),
                    _str_entry("jwksUrl", jwks_url),
                    _str_entry("mspPilotUrl", msp_url),
                ],
            }
        },
        {"beginRendering": {"surfaceId": sid, "root": "root-card", "catalogId": A2UI_CATALOG_ID}},
    ]


def info_card_messages(
    skill: str,
    text: str,
    data: dict,
    *,
    lang: str = "en",
) -> list[dict]:
    """Build a clean A2UI v0.8 summary card for non-TLS skills (`msp-pilot`, `qa-assistant`, `paid-data`, etc.)."""
    l = lang if lang in ("ar", "de", "en") else "en"
    topic = str((data or {}).get("topic") or skill or "info")
    sid = _surface_id("card", topic)
    titles = {
        "msp-pilot": {"ar": "MSP Pilot لمزودي خدمات IT (290 €)", "de": "IT-Dienstleister MSP Pilot (290 €)", "en": "IT-Dienstleister MSP Pilot (290 €)"},
        "tls-attestation": {"ar": "حزمة المدقّق (PDF + CycloneDX CBOM)", "de": "Auditor-PDF + CycloneDX CBOM", "en": "Auditor-Ready TLS Attestation"},
        "agent-affiliate": {"ar": "برنامج شركاء الوكلاء (30% متكررة)", "de": "AI-Agent-Partnerprogramm (30 %)", "en": "AI Agent Affiliate Programme (30%)"},
        "paid-data": {"ar": "البيانات والتقارير المدفوعة (x402)", "de": "Berichte & Sektor-Snapshots (x402)", "en": "Paid Reports & Sector Snapshots (x402)"},
    }
    title = titles.get(skill, {}).get(l) or "Quantum Aether"

    children = ["card-title", "card-body"]
    components = [
        {"id": "root-card", "component": {"Card": {"child": "main-col"}}},
        {"id": "card-title", "component": {"Text": {"text": {"path": "/title"}, "usageHint": "h2"}}},
        {"id": "card-body", "component": {"Text": {"text": {"path": "/summary"}, "usageHint": "body"}}},
    ]
    contents = [
        _str_entry("title", title),
        _str_entry("summary", text),
    ]

    points = (data or {}).get("points") if isinstance(data, dict) else None
    if isinstance(points, list) and points:
        children.append("divider-pts")
        components.append({"id": "divider-pts", "component": {"Divider": {}}})
        for idx, pt in enumerate(points[:5]):
            cid = f"pt-{idx}"
            children.append(cid)
            components.append({"id": cid, "component": {"Text": {"text": {"literalString": f"• {pt}"}, "usageHint": "body"}}})

    code = (data or {}).get("code") if isinstance(data, dict) else None
    if isinstance(code, str) and code.strip():
        children.extend(["divider-code", "code-block"])
        components.append({"id": "divider-code", "component": {"Divider": {}}})
        components.append({"id": "code-block", "component": {"Text": {"text": {"path": "/code"}, "usageHint": "caption"}}})
        contents.append(_str_entry("code", code.strip()))

    actions = (data or {}).get("actions") if isinstance(data, dict) else None
    if isinstance(actions, list) and actions:
        btn_ids = []
        for idx, act in enumerate(actions[:4]):
            if not isinstance(act, dict) or not act.get("label"):
                continue
            bid = f"act-btn-{idx}"
            tid = f"act-txt-{idx}"
            if act.get("url"):
                action_spec = {"name": "open_url", "context": [{"key": "url", "value": {"literalString": str(act["url"])}}]}
            elif act.get("scan_domain"):
                action_spec = {
                    "name": "tls_scan",
                    "context": [
                        {"key": "skill", "value": {"literalString": "tls-scan"}},
                        {"key": "domain", "value": {"literalString": str(act["scan_domain"])}},
                    ],
                }
            elif act.get("prompt"):
                action_spec = {"name": "send_prompt", "context": [{"key": "prompt", "value": {"literalString": str(act["prompt"])}}]}
            else:
                continue
            btn_ids.append(bid)
            components.append({"id": bid, "component": {"Button": {"child": tid, "primary": idx == 0, "action": action_spec}}})
            components.append({"id": tid, "component": {"Text": {"text": {"literalString": str(act["label"])}}}})
        if btn_ids:
            children.extend(["divider-act", "actions-row"])
            components.append({"id": "divider-act", "component": {"Divider": {}}})
            components.append({"id": "actions-row", "component": {"Row": {"children": {"explicitList": btn_ids}}}})

    components.insert(1, {"id": "main-col", "component": {"Column": {"children": {"explicitList": children}}}})

    return [
        {"surfaceUpdate": {"surfaceId": sid, "components": components}},
        {"dataModelUpdate": {"surfaceId": sid, "path": "/", "contents": contents}},
        {"beginRendering": {"surfaceId": sid, "root": "root-card", "catalogId": A2UI_CATALOG_ID}},
    ]
