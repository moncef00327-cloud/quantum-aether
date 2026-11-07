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

Scanner, methodology and open dataset: https://ather-quatum.cloud

## Remote MCP

Connect a Streamable HTTP client to `https://ather-quatum.cloud/mcp`.
The stateless remote service exposes `scan_tls`, `get_tls_evidence`,
`get_methodology`, `get_example_result` and `get_service_info`.
It returns JSON, does not open an SSE stream, and accepts supported versions
2025-11-25 and 2025-06-18. Active scans consume the ordinary API scan limits
and store public results. The remote transport does not expose purchase tools.

Agent guide: https://ather-quatum.cloud/agents?lang=en
Service manifest: https://ather-quatum.cloud/.well-known/agent-service.json

The server registration metadata was prepared for a remote-enabled release;
this README does not assert that an external registry accepted it. The existing
PyPI wrapper remains version 1.0.1. Automatic x402 payments and signed receipts
are not implemented by this release.
