# Quantum Aether MCP server

<!-- mcp-name: io.github.moncef00327-cloud/quantum-aether -->

Let any MCP-compatible AI assistant (Claude Desktop, and others) **check a website's
post-quantum TLS readiness** — and, with the user's consent, buy the full report or start
monitoring — by calling Quantum Aether as a native tool.

It wraps the public Quantum Aether API. The stdio package does not read server environment files or
Resend, IBM, PayPal, or database credentials. `QUANTUM_AETHER_BASE` optionally selects the API base
URL. A scan sends the requested hostname; signup sends the supplied email and consent to the service.

## Tools

| Tool | What it does |
|------|--------------|
| `scan_tls(domain)` | Starts an external scan of a public hostname on port 443 and returns a summary. The result is stored and publicly accessible. |
| `scan_tls_raw(domain)` | Starts the same scan and returns its structured result (grade, key exchange group, certificate, scan ID and price). |
| `exposure_window(domain)` | Reads the stored exposure timeline and proof data. It does not start a scan. |
| `buy_full_report(scan_id, consent_immediate_delivery)` | Creates a PayPal approval order; this call does not approve or capture payment. Immediate-delivery consent is required. |
| `start_monitoring(email, plan, consent)` | Sends the supplied email to the service to create a monitoring signup. Explicit consent is required. |
| `register_agent_affiliate(name, contact_email, payout_method, payout_destination, consent_terms, ...)` | Registers an AI agent or operator in the partner programme and immediately returns a `?ref=CODE` referral link (30% monitoring for 12 months / 20% one-time, monthly manual owner payout after 30-day hold, min $50). |

Tools carry behavioral annotations for compatible clients. Scans and actions are non-read-only;
the exposure lookup is read-only. These hints do not replace consent or server-side validation.

## Install

```sh
pip install quantum-aether-mcp
# or from source:
pip install -e .
```

## Use with Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "quantum-aether": {
      "command": "python",
      "args": ["-m", "quantum_aether_mcp"]
    }
  }
}
```

Then ask your assistant: *"Is example.com ready for post-quantum TLS?"* — it will call `scan_tls`.

## Honesty by design

The tool reports the **real** scan result. A site that already negotiates X25519MLKEM768 is told
it is protected, with no upsell. A problem is surfaced only when it genuinely exists. This is what
makes AI assistants trust and reuse the tool.

Scanner, methodology and open dataset: https://ather-quantum.com

## Remote MCP

Connect a Streamable HTTP client to `https://ather-quantum.com/mcp`.
The stateless remote service exposes `scan_tls`, `get_tls_evidence`,
`exposure_window`, `get_methodology`, `get_example_result`, `get_service_info`,
`get_full_report`, `get_sector_snapshot`, `create_full_report_order`,
`verify_full_report_payment`, and `register_agent_affiliate`.
Every scan issues an offline-verifiable Ed25519 JWS signed TLS receipt (v1,
`alg: EdDSA`, `typ: qa-tls-receipt+jwt`, JWKS at `https://ather-quantum.com/.well-known/jwks.json`).
The paid report tool returns a standard x402 v2 payment
challenge for exact USDC on Base. An x402-capable MCP client can sign and retry
under the buyer wallet's own spend policy; the service settles before it returns
the report. Direct-transfer tools for Polygon USDT remain available as a manual
fallback.
It returns JSON, does not open an SSE stream, and accepts supported versions
2025-11-25, 2025-06-18 and 2025-03-26. Active scans consume the ordinary API scan limits
and store public results. Scan results are observations, not authorization to
execute changes on the scanned system.

Agent guide: https://ather-quantum.com/agents?lang=en
Service manifest: https://ather-quantum.com/.well-known/agent-service.json
MCP Server Card: https://ather-quantum.com/.well-known/mcp/server-card.json
JWKS: https://ather-quantum.com/.well-known/jwks.json

The MCP registry metadata declares remote server version 1.6.0. The separate
PyPI stdio wrapper is version 1.4.2 (defaults to ather-quantum.com) and wraps
the public HTTP API; automatic x402 payment is provided by the remote MCP tool.
Ed25519 JWS signed scan receipts (v1) are live on both HTTP (`/api/v1/scan`)
and remote MCP (`scan_tls`, `get_tls_evidence`).


## get_sector_snapshot(sector) — remote only, paid x402

Read-only. Every domain of one sector watch list (for example `banks-mena`, `government-gcc`,
`cyber-agencies-worldwide`) in the latest weekly registry measurement: grade, key-exchange group, TLS version and
post-quantum status, plus a summary. $0.50 USDC on Base per call via x402 v2 (exact scheme). Without a signed
payment it returns the x402 PaymentRequired challenge and never charges. HTTP: `GET /api/v1/agent/sector/<sector>`.

## exposure_window(domain)

Read-only lookup in the Quantum Exposure Registry (`GET /api/v1/exposure/<domain>`): first observation, first post-quantum week, observed exposure window, weekly timeline and OpenTimestamps anchor proofs. Never scans. External observation, not a compliance certification.
