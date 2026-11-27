---
name: mcp-security-audit
description: Audit remote MCP servers in an agent configuration against the live Quantum Aether Remote MCP PQ-TLS Leaderboard (/mcp-index) to check whether prompts, tokens, and tool responses are protected with post-quantum TLS.
---

# Remote MCP Server Security Audit (`mcp-security-audit`)

Use this skill when auditing an AI agent's `mcp.json` / `.mcp.json` / Claude / Cursor / Codex connectors to check whether remote HTTPS MCP endpoints protect agent traffic against harvest-now-decrypt-later attacks.

## Workflow

1. **Inspect configured remote MCP URLs** (`https://...`) from the user's MCP config or prompt.
2. **Check the live Reverse MCP Security Index first:**
   - Query `https://ather-quantum.com/api/v1/mcp-index` (or `python3 tools/qa_cli.py mcp-index`) to see current registry-wide PQ-TLS adoption and check if any of the user's MCP hosts are already measured.
3. **Scan any unmeasured MCP endpoint live:**
   - Call `scan_tls(host)` for each remote MCP hostname.
4. **Report risk clearly:**
   - Categorize each remote MCP host as **Post-Quantum (`X25519MLKEM768`)**, **Preference Misconfiguration (`KX_PQ_SUPPORTED_NOT_PREFERRED`)**, **Classical TLS 1.3 (`Grade B`)**, or **Legacy TLS 1.2 (`Grade C`)**.
   - Link the user to the public leaderboard at `https://ather-quantum.com/mcp-index` and offer `pqc-config-fix` for any self-hosted MCP endpoints.
