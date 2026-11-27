# Quantum Aether Plugin (Claude Code · Cursor · Codex · Antigravity)

Live post-quantum TLS (`X25519MLKEM768` / ML-KEM, FIPS 203) verification, signed Ed25519 receipts, and copy-paste remediation configs directly inside your AI coding agent — **no signup, no API key required**.

## What it does

- **Live browser-grade PQ-TLS audits (`scan_tls`):** Tests port 443 like Chrome/Firefox/Safari and flags **both** classical endpoints **and** hidden server-preference downgrades (`KX_PQ_SUPPORTED_NOT_PREFERRED`, where a server accepts PQ alone yet downgrades real browsers to classical `X25519`).
- **Offline-verifiable Ed25519 signed receipts (v1):** Every scan returns a compact JWS receipt verifiable locally against `https://ather-quantum.com/.well-known/jwks.json`.
- **Copy-paste fixes (`generate_pq_config`):** Ready-to-deploy configs for Nginx, Apache, HAProxy, Caddy, Go, Node.js, CloudFront, and Cloudflare.
- **Remote MCP security auditing:** Cross-checks remote MCP endpoints against the live leaderboard at [`https://ather-quantum.com/mcp-index`](https://ather-quantum.com/mcp-index).
- **NIS2 / DORA / BSI TR-02102-2 compliance evidence:** Free signed receipts plus optional Auditor PDF + CycloneDX 1.6 CBOM bundle (`get_tls_attestation`) and German MSP Pilot reports (`https://ather-quantum.com/partners`).

## Included skills

1. `pqc-tls-audit` — Audit a domain or host list and explain exact browser vs server-preference PQ-TLS behavior.
2. `pqc-config-fix` — Generate exact `X25519MLKEM768` server configs and verify the rollout live.
3. `nis2-dora-evidence` — Assemble auditor-ready transport encryption evidence with offline JWS verification.
4. `mcp-security-audit` — Audit remote MCP servers in your agent config for post-quantum transport protection.
5. `pqc-ci-gate` — Add an automated CI/CD PQ-TLS regression gate using signed receipts.

## Install

- **Claude Code:**
  ```
  /plugin marketplace add moncef00327-cloud/quantum-aether
  /plugin install quantum-aether@quantum-aether
  ```
- **Agent Skills CLI (`skills.sh` / Cursor / Codex / OpenClaw / Antigravity):**
  ```bash
  npx skills add moncef00327-cloud/quantum-aether
  ```
- **Direct Remote MCP (`100/100` on mcptry):** `https://ather-quantum.com/mcp`
