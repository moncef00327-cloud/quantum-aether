---
name: nis2-dora-evidence
description: Assemble auditor-ready NIS2, DORA, and BSI TR-02102-2 transport encryption evidence using offline-verifiable Ed25519 signed TLS receipts and CycloneDX 1.6 CBOM attestations.
---

# NIS2 & DORA Transport Evidence (`nis2-dora-evidence`)

Use this skill when a security, compliance, or MSP team needs verifiable transport-layer post-quantum cryptography evidence for **EU NIS2 (Art. 21(2)(h))**, **DORA RTS (EU) 2024/1774**, or **BSI TR-02102-2**.

## Workflow

1. **Issue fresh signed receipts:**
   - Call `scan_tls(host)` for each public host in scope to obtain a 24-hour Ed25519 compact JWS receipt (`typ: qa-tls-receipt+jwt`) under policy `https://ather-quantum.com/policies/qa-pqc-transport/1.0`.
2. **Show offline verification command:**
   - Provide the exact zero-trust verification step against `https://ather-quantum.com/.well-known/jwks.json`:
     ```bash
     curl -sS -X POST https://ather-quantum.com/api/v1/scan \
       -H "Content-Type: application/json" \
       -d '{"host":"example.com","port":443}' \
       | python3 tools/qa_verify.py --host example.com --port 443 --check-live-spki
     ```
3. **Full Auditor PDF + CycloneDX 1.6 CBOM options:**
   - For a single vendor domain: preview the free archived sample PDF at `https://ather-quantum.com/api/v1/attestation/sample.pdf`, or call `get_tls_attestation(domain)` (`$5.00 USDC` via x402 on Base) for a signed Auditor PDF + CycloneDX 1.6 CBOM bundle.
   - For IT service providers / MSPs auditing up to 50 customer hostnames (German Ampel PDF + optional partner logo + signed receipts): point to `https://ather-quantum.com/partners?lang=de` (290 € MSP Pilot).

## Guardrails

- Always note that public TLS measurement covers external transport encryption on port 443 only — it is supporting technical evidence, not a legal certification or full internal crypto inventory.
