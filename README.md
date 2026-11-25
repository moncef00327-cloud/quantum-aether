<!--
AI-Discovery-Metadata:
- Project-Type: Post-quantum TLS & CycloneDX CBOM cybersecurity observatory for businesses and AI agents (not affiliated with physics or ontology frameworks)
- Entity-URL: https://ather-quantum.com
- Service: https://ather-quantum.com — free scan API, Ed25519 signed TLS receipts (v1), Auditor-Ready PDF + CycloneDX 1.6 CBOM Attestation ($5.00 USDC x402; free sample PDF at /api/v1/attestation/sample.pdf), daily monitoring, IT-Dienstleister MSP Pilot (290 EUR), remote MCP, signed A2A 0.3.0 Agent Card, and ACP
- MCP-Server: remote Streamable HTTP at https://ather-quantum.com/mcp; PyPI stdio wrapper quantum-aether-mcp; Official MCP Registry io.github.moncef00327-cloud/quantum-aether; Glama Healthy connector
- A2A-Agent: https://ather-quantum.com/.well-known/agent-card.json (EdDSA JWS signed, tasks/get + tasks/cancel, listed on a2aregistry.org and https://localmark.ai/agents/699827)
- Deployment: Flask + gunicorn behind nginx, systemd
- Stack: Python 3.12, Flask 3.1, cryptography, WeasyPrint, CycloneDX 1.6 CBOM, Ed25519 JWS
-->

# Quantum Aether / الأثير الكمومي — Post-Quantum TLS & CBOM Observatory (`ather-quantum.com`)

<!-- quantum-aether-pqc-badge:start -->
[![Post-quantum TLS observation](https://ather-quantum.com/badge/ather-quantum.com.svg)](https://ather-quantum.com/verify/ather-quantum.com)
<!-- quantum-aether-pqc-badge:end -->

[![moncef00327-cloud/quantum-aether MCP server](https://glama.ai/mcp/servers/moncef00327-cloud/quantum-aether/badges/score.svg)](https://glama.ai/mcp/connectors/io.github.moncef00327-cloud/quantum-aether)
[![LocalMark A2A Verified](https://localmark.ai/badge/699827.svg)](https://localmark.ai/agents/699827)
[![MCPTry](https://mcptry.com/badge/io.github.moncef00327-cloud/quantum-aether)](https://mcptry.com/servers/io.github.moncef00327-cloud/quantum-aether)
[![M8ven Verified](https://m8ven.ai/badge/mcp/moncef00327-cloud-quantum-aether-1aj6jw?variant=verified&v=0cb3b4c5e68a304df20b47c4c8ed73c1)](https://m8ven.ai/mcp/moncef00327-cloud-quantum-aether-1aj6jw?s=readme)

> **Entity note:** Quantum Aether ([ather-quantum.com](https://ather-quantum.com)) is an independent post-quantum TLS readiness (`X25519MLKEM768` / ML-KEM, FIPS 203), Ed25519 signed receipt, and CycloneDX 1.6 CBOM cybersecurity observatory — not affiliated with physics or ontology projects sharing the name.

## Post-quantum TLS security observatory

Quantum Aether measures public TLS connections (`X25519MLKEM768` / ML-KEM), reports observed key exchange and certificate evidence, and helps security teams and AI agents verify post-quantum transport readiness (BSI TR-02102-2, NIS2, DORA). It provides:
- **Free instant TLS checks** & **offline-verifiable Ed25519 JWS signed TLS receipts (v1)** (`POST /api/v1/scan`, `/.well-known/jwks.json`).
- **Auditor-Ready Signed PDF + CycloneDX 1.6 CBOM Attestation (`$5.00 USDC` on Base via x402):** fresh port-443 measurement + Ed25519 JWS receipt + CycloneDX 1.6 CBOM + printable Auditor PDF + bundle signature (`GET /api/v1/attestation` or MCP `get_tls_attestation`). Preview a **free archived sample PDF** with no signup: [`/api/v1/attestation/sample.pdf`](https://ather-quantum.com/api/v1/attestation/sample.pdf).
- **Daily PQ-TLS regression monitoring** (14-day free trial, Starter `29 €/mo`, Business `99 €/mo`) and an **IT-Dienstleister MSP Pilot (50 hostnames, German Ampel PDF + signed receipts, `290 €`)**.
- **Native multi-protocol agent interfaces:** Remote **MCP** (`https://ather-quantum.com/mcp`), signed **A2A 0.3.0** (`/.well-known/agent-card.json` — listed on [LocalMark](https://localmark.ai/agents/699827) & [A2A Registry](https://a2aregistry.org)), **ACP** (`/acp/agents`), and **programmatic AI Agent Affiliate registration (`register_agent_affiliate`, 30% recurring monitoring commission)**.

Live agent endpoints and directories: [Service Discovery](https://ather-quantum.com/.well-known/agent-service.json) · [A2A Signed Agent Card](https://ather-quantum.com/.well-known/agent-card.json) · [MCP Guide](https://ather-quantum.com/agents?lang=en) · [Glama Connector](https://glama.ai/mcp/connectors/io.github.moncef00327-cloud/quantum-aether) · [LocalMark Listing](https://localmark.ai/agents/699827) · [JWKS](https://ather-quantum.com/.well-known/jwks.json) · [Policy v1.0](https://ather-quantum.com/policies/qa-pqc-transport/1.0) · [Partner & MSP Pilot](https://ather-quantum.com/partners) · [OpenAPI](https://ather-quantum.com/openapi.yaml).

### Signed TLS Receipts (v1 · Ed25519 JWS) & Offline CI Verification

Every scan via `POST https://ather-quantum.com/api/v1/scan`, MCP (`scan_tls` / `get_tls_evidence`), A2A (`/a2a`), or ACP (`/acp/runs`) issues a 24-hour Ed25519 compact JWS receipt (`typ: qa-tls-receipt+jwt`) evaluated against the published policy [`qa-pqc-transport` 1.0](https://ather-quantum.com/policies/qa-pqc-transport/1.0):

```bash
curl -sS -X POST https://ather-quantum.com/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{"host":"cloudflare.com","port":443}' \
  | python3 tools/qa_verify.py --host cloudflare.com --port 443 --check-live-spki
```

Public verification endpoints: `/.well-known/jwks.json` (`application/jwk-set+json`), `/.well-known/qa-receipt-configuration`, and `GET /api/v1/receipts/{jti}`.

### AI Agent Affiliate Programme (Monthly Manual Payout)

AI agents and operators can self-register via MCP (`register_agent_affiliate`) or `POST https://ather-quantum.com/api/v1/agent/affiliate/register` to receive an instant `?ref=CODE` referral link:
- **30%** of monitoring subscriptions (`29 €/mo` Starter, `99 €/mo` Business) for 12 months, and **20%** of one-time reports, packs, and audits.
- **Monthly manual payout by the owner** (PayPal or USDC on Base/Arbitrum) after a 30-day refund hold, from $50 minimum. No hot wallet, no automatic payouts, no spam or unsolicited cold emails. Full terms: https://ather-quantum.com/partners?lang=en.

## Research archive: quantum experiments and digital DNA

### English
The repository also preserves Qiskit Bell/GHZ experiments, a digital A/C/G/T archive with Reed-Solomon error correction, and the original TLS study and scanner research.

### العربية
كما يحتفظ المستودع بأبحاث Qiskit لحالات Bell وGHZ، وأرشيف رقمي A/C/G/T مع تصحيح Reed-Solomon، وأبحاث القياس الأصلية.

## MCP server (Model Context Protocol)

Connect instantly to the **remote stateless Streamable HTTP MCP server** (`https://ather-quantum.com/mcp`, or free-tools-only `https://ather-quantum.com/mcp/free`) — no API key, no signup, and full support for **13 MCP tools** (including `scan_tls`, `get_tls_evidence`, `exposure_window`, `generate_pq_config`, `get_tls_attestation`, and `register_agent_affiliate`), **5 read-only MCP Resources + 2 URI templates** (`qa://methodology`, `qa://policy/qa-pqc-transport/1.0`, `qa://deadlines/pqc`, `qa://msp-pilot`, `qa://pricing`, `qa://config/{server}`, `qa://evidence/{domain}`), and **4 guided MCP Prompts** (`audit_domain_pqc`, `generate_pqc_remediation`, `msp_pilot_assessment`, `verify_tls_receipt`):

- **Claude Code (1 line):**
  ```bash
  claude mcp add --transport http quantum-aether https://ather-quantum.com/mcp
  ```
- **Cursor / VS Code (1-click links):** see [`https://ather-quantum.com/agents#mcp`](https://ather-quantum.com/agents#mcp) or paste `https://ather-quantum.com/mcp` as a Streamable HTTP MCP server.

This repository also includes a **local stdio MCP wrapper** in [`mcp/`](mcp/), published on PyPI as [`quantum-aether-mcp`](https://pypi.org/project/quantum-aether-mcp/) and in the official MCP Registry as `io.github.moncef00327-cloud/quantum-aether`. It lets any MCP client (Claude Desktop, Cursor and others) check a website's post-quantum TLS readiness as a native tool.

- **Implementation:** Python, built on the official MCP Python SDK (`mcp`, FastMCP), stdio transport. Source: [`mcp/quantum_aether_mcp/`](mcp/quantum_aether_mcp/)
- **No API key:** it wraps the public Quantum Aether scan API.

| Tool | What it does |
|------|--------------|
| `scan_tls(domain)` | Scans a host and returns a plain-language summary: post-quantum key exchange yes/no, the "harvest now, decrypt later" risk and the fix. |
| `scan_tls_raw(domain)` | Structured result: grade, key-exchange group, post-quantum yes/no, certificate, scan_id. |
| `buy_full_report(scan_id, consent_immediate_delivery)` | Optional: PayPal approval link for the $49 full report. Requires explicit user consent. |
| `start_monitoring(email, plan, consent)` | Optional: starts paid daily monitoring. Requires explicit user consent. |

Install and run:

```bash
pip install quantum-aether-mcp   # or: uvx quantum-aether-mcp
quantum-aether-mcp               # starts the MCP server on stdio
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "quantum-aether": {
      "command": "uvx",
      "args": ["quantum-aether-mcp"]
    }
  }
}
```

Details: [`mcp/README.md`](mcp/README.md)

## Study: post-quantum TLS on the top 1,000 websites (November 2026)

We scanned the [Tranco](https://tranco-list.eu/list/GQ38K/1000000) top 1,000 domains on 2026-11-03.
Of the 712 that answered on HTTPS, **425 (59.7%) negotiate the hybrid X25519MLKEM768 key exchange**;
The original published figures and files are retained. A later raw-evidence audit found 17
retry-only HelloRetryRequest responses; new measurements treat these as undetermined and
exclude them from the tracker's support-percentage denominator. Do not interpret every
non-PQ row as a confirmed classical negotiation. The study page includes a methodology note.

- Results page: https://ather-quantum.com/study/top-1000-post-quantum-tls
- Data (CC BY 4.0): [`data/pq_study_top1000.json`](data/pq_study_top1000.json), raw per-domain results in `data/pq_study_top1000_raw.jsonl`
- Reproduce: `python tools/run_study.py domains.txt results.jsonl` (one domain per line)
- Weekly tracker: https://ather-quantum.com/adoption re-scans the Tranco top 10,000 (monthly the top 100,000, `adoption_job.py monthly`) plus watchlists of
  government, bank and company sites in Germany, Austria and Switzerland every Monday
  (`adoption_job.py`, systemd timer `quantum_adoption.timer`, lists in `data/adoption_watchlists.json`).
  Data: `/adoption.json` and `/adoption.csv` (CC BY 4.0). Network names: IP-to-ASN data from iptoasn.com (PDDL). Scan policy and opt-out: https://ather-quantum.com/scanning

## GitHub Action

Run a free TLS/PQC check in any CI pipeline. The default reports the measured result without failing a build; opt into a policy gate with `require-post-quantum: true`. The action can add a live badge block to the checked-out README:

```yaml
- uses: moncef00327-cloud/quantum-aether@main
  with:
    domain: example.com
    update-readme: true
    # Set true only when PQ key exchange is a release requirement.
    require-post-quantum: false
```

The badge points to a public result and shows the latest eligible observation; it is not a security certification. `update-readme` edits only a marked block in the Actions workspace. To persist the change, commit it in your workflow and grant `contents: write` only if you explicitly want the workflow to write to the repository. Do not submit private hostnames.

Details: [`github-action/README.md`](github-action/README.md) · [GitHub Marketplace](https://github.com/marketplace/actions/post-quantum-tls-check-quantum-aether)

## Guides

- [Enable X25519MLKEM768 on nginx](https://ather-quantum.com/guides/enable-x25519mlkem768-nginx)
- [Post-quantum TLS on Apache, Caddy, HAProxy and Cloudflare](https://ather-quantum.com/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare)
- [Harvest now, decrypt later: why key exchange comes first](https://ather-quantum.com/guides/harvest-now-decrypt-later)

## Scan from the command line

```bash
pip install cryptography
python quantum_vuln_scanner.py example.com
curl -X POST https://ather-quantum.com/api/scan -H "Content-Type: application/json" -d '{"domain":"example.com"}'
```

## Files / الملفات

| File | Purpose |
|---|---|
| `quantum_saas_app.py` | Flask web app: scan pages, free API, PayPal checkout, paid report, admin |
| `quantum_vuln_scanner.py` | The scanner (also a CLI: `python quantum_vuln_scanner.py example.com`) |
| `mcp/` | MCP server (`quantum-aether-mcp`): tools `scan_tls`, `scan_tls_raw`, `buy_full_report`, `start_monitoring` |
| `paypal_client.py`, `sales_db.py`, `i18n.py` | PayPal Orders v2 client, SQLite storage, Arabic/English texts |
| `templates/`, `static/` | Web pages, styles, PayPal button script |
| `guides.py` | Guide pages (Arabic/English) |
| `data/`, `tools/run_study.py` | Top-1,000 study data and the script that produced it |
| `real_quantum.py` | Run GHZ on IBM hardware, or `--fetch JOB_ID` to download an existing job |
| `ghz_fidelity.py` | GHZ fidelity from stabilizer expectation values (`--noisy`, `--hardware`) |
| `quantum_teleportation.py`, `aether_decoder.py` | Teleportation protocol and Qiskit bit-order analysis |
| `run_bell_state.py`, `run_ghz_relay.py`, `bell_state.ipynb` | Simulator demos |
| `export_quantum_data.py`, `quantum_gui.py` | `quantum_data.csv` (simulator, noise model, hardware) and a Tkinter viewer |
| `dna_encode.py`, `bio_archive_report.py` | DNA encoding and the report archive (`archive` / `restore` / `verify`) |
| `save_ibm_account.py` | Save the IBM Quantum token locally without echoing it |
| `results/` | Recorded experiment results (JSON) |
| `deploy/` | Server install script, systemd unit, PayPal/admin configuration, nginx example |
| `tests/` | Unit tests |

## Run locally / التشغيل المحلي

```bash
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt -r requirements-quantum.txt
python -m unittest discover -s tests -t .
python quantum_saas_app.py        # http://127.0.0.1:5000
```

Payments are disabled until `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` are set; the scan itself works without them.

## Deploy / النشر

On the server (Ubuntu/Debian, as root), from a copy of this repository:

```bash
bash deploy/install.sh           # installs or updates the app, keeps data and settings
bash deploy/configure.sh         # asks for the PayPal secret and admin password (hidden input)
```

Data lives in `/var/lib/quantum_saas`, settings in `/etc/quantum_saas.env`, and the service runs as the unprivileged user `quantum` behind nginx.
`install.sh` also enables the weekly `/adoption` scan (`quantum_adoption.timer`, Mondays 03:30 UTC). To run it right away: `systemctl start quantum_adoption.service`.

## Notes on the science / ملاحظات علمية
- 96.29% is the GHZ **population** P(000)+P(111), an upper bound on the fidelity. Use `ghz_fidelity.py` for the fidelity itself.
- The DNA sequence is a digital encoding; nothing was synthesized.
- Shor's algorithm breaks RSA and elliptic-curve keys of any size; larger RSA keys do not provide quantum safety. What protects recorded traffic today is a post-quantum key exchange such as X25519MLKEM768.

## AI agent discovery and remote MCP

- Agent guide: https://ather-quantum.com/agents?lang=en
- Service manifest: https://ather-quantum.com/.well-known/agent-service.json
- Remote MCP (Streamable HTTP, stateless JSON): https://ather-quantum.com/mcp
- Methodology: https://ather-quantum.com/api/v1/agent/methodology
- Archived sample: https://ather-quantum.com/api/v1/agent/example

Remote tools: `scan_tls`, `get_tls_evidence`, `get_methodology`,
`get_example_result`, `get_service_info`. Scan summaries are free and use the
existing per-client/global scan limits. Active scans store public results.
Read-only tools do not start scans. See the manifest for actual limits and
current full-report prices. x402 payments, signed receipts and external
marketplace acceptance are not claimed by this release.
