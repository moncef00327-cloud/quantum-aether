# Quantum Aether MCP server

<!-- mcp-name: io.github.moncef00327-cloud/quantum-aether -->

Let any MCP-compatible AI assistant (Claude Desktop, and others) **check a website's
post-quantum TLS readiness** — and, with the user's consent, buy the full report or start
monitoring — by calling Quantum Aether as a native tool.

It wraps the public Quantum Aether API. No API key. No secrets.

## Tools

| Tool | What it does |
|------|--------------|
| `scan_tls(domain)` | Scans a host and returns an honest summary. If the site already uses post-quantum key exchange it says so; otherwise it states the "harvest now, decrypt later" risk and the fix. |
| `scan_tls_raw(domain)` | The structured result (grade, key exchange group, post-quantum yes/no, certificate, scan_id, price). |
| `buy_full_report(scan_id, consent_immediate_delivery)` | Returns a PayPal approval link for the $49 report. Consent required (Austrian FAGG). |
| `start_monitoring(email, plan, consent)` | Starts a daily monitoring subscription ($29 or $99 / month). |

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
`get_methodology`, `get_example_result`, `get_service_info` and
`get_full_report`. The paid report tool returns a standard x402 v2 payment
challenge for exact USDC on Base. An x402-capable MCP client can sign and retry
under the buyer wallet's own spend policy; the service settles before it returns
the report. Direct-transfer tools for Polygon USDT remain available as a manual
fallback.
It returns JSON, does not open an SSE stream, and accepts supported versions
2025-11-25 and 2025-06-18. Active scans consume the ordinary API scan limits
and store public results. Scan results are observations, not authorization to
execute changes on the scanned system.

Agent guide: https://ather-quantum.com/agents?lang=en
Service manifest: https://ather-quantum.com/.well-known/agent-service.json

The MCP registry metadata declares remote server version 1.4.0. The separate
PyPI stdio wrapper is version 1.0.2 (defaults to ather-quantum.com) and uses the human-assisted checkout
flow described by its local tools; automatic x402 payment is provided by the
remote MCP tool. Signed scan receipts are not implemented.
