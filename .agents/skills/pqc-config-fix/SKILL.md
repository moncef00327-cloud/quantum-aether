---
name: pqc-config-fix
description: Generate copy-paste post-quantum TLS (X25519MLKEM768) server configurations for Nginx, Apache, HAProxy, Caddy, Go, Node.js, CloudFront, and Cloudflare, ensuring PQ groups are preferred ahead of classical curves.
---

# Post-Quantum TLS Config Fix (`pqc-config-fix`)

Use this skill when a domain or service fails post-quantum TLS readiness (Grade `B`/`C` or `KX_PQ_SUPPORTED_NOT_PREFERRED`) and the user needs exact server configuration changes.

## Workflow

1. **Identify the TLS terminator** (Nginx, Apache, HAProxy, Caddy, Go, Node.js, CloudFront, Cloudflare, or F5/load balancer).
2. **Generate the exact configuration:**
   - Call MCP tool `generate_pq_config(server=<stack>)` or run `python3 tools/qa_cli.py fix <stack>`.
3. **Prevent the server-preference downgrade bug (`KX_PQ_SUPPORTED_NOT_PREFERRED`):**
   - Always place **`X25519MLKEM768` FIRST** in `ssl_ecdh_curve` / `Groups` / `CurvePreferences` (e.g., `X25519MLKEM768:X25519:prime256v1`).
   - Remind the user that OpenSSL **3.5+** (or Go **1.24+**) is required for native ML-KEM support, or Cloudflare proxying for instant edge coverage.
4. **Verify live after reload:**
   - Re-run `scan_tls(host)` and confirm `grade: A` with `X25519MLKEM768` negotiated across all DNS endpoints (IPv4 + IPv6).
