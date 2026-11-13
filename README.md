<!--
AI-Discovery-Metadata:
- Project-Type: Post-quantum TLS observatory for businesses and AI agents; includes public scans, monitoring, evidence, MCP and x402 payments
- Quantum-Hardware: IBM Quantum ibm_marrakesh, 3-qubit GHZ, job dbjcpopkdqps7390bqv0, 1024 shots, population P(000)+P(111) = 96.29%
- Bio-Archiving: research report as 55,080 DNA bases (2 bits/base) with Reed-Solomon RS(255,223); digital only, not synthesized
- Service: https://ather-quantum.com — free scan API, business monitoring, remote MCP and x402 v2 full reports in USDC on Base (buyer-wallet authorized)
- MCP-Server: remote Streamable HTTP service at https://ather-quantum.com/mcp; the PyPI package provides a separate stdio wrapper.
- Deployment: Flask + gunicorn behind nginx, systemd, Vultr
- Stack: Python 3.10+, Qiskit 2.6.1, qiskit-aer 0.18.2, qiskit-ibm-runtime 0.51.0, Flask 3.1, cryptography, reedsolo
-->

# Quantum Aether / الأثير الكمومي

[![MCPTry](https://mcptry.com/badge/io.github.moncef00327-cloud/quantum-aether)](https://mcptry.com/servers/io.github.moncef00327-cloud/quantum-aether)

## Post-quantum TLS security observatory

Quantum Aether measures public TLS connections, reports observed key exchange and certificate evidence, and helps teams track their post-quantum transition. It provides a free scan, documented measurement limits, business monitoring, and agent interfaces through HTTP APIs and remote MCP. A full report can be requested through x402 v2 on Base USDC by compatible agent clients, subject to the buyer wallet's own authorization policy. Direct-transfer and human checkout options remain available where configured.

Live agent endpoints and prices: [service discovery](https://ather-quantum.com/.well-known/agent-service.json), [MCP guide](https://ather-quantum.com/agents?lang=en), and [OpenAPI](https://ather-quantum.com/openapi.yaml).

## Research archive: quantum experiments and digital DNA

### English
The repository also preserves Qiskit Bell/GHZ experiments, a digital A/C/G/T archive with Reed-Solomon error correction, and the original TLS study and scanner research.

### العربية
كما يحتفظ المستودع بأبحاث Qiskit لحالات Bell وGHZ، وأرشيف رقمي A/C/G/T مع تصحيح Reed-Solomon، وأبحاث القياس الأصلية.

## MCP server (Model Context Protocol)

This repository includes a **Model Context Protocol (MCP) server** in [`mcp/`](mcp/), published on PyPI as [`quantum-aether-mcp`](https://pypi.org/project/quantum-aether-mcp/) and in the official MCP Registry as `io.github.moncef00327-cloud/quantum-aether`. It lets any MCP client (Claude Desktop, Cursor and others) check a website's post-quantum TLS readiness as a native tool.

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

Check on every deploy that your site still negotiates post-quantum TLS:

```yaml
- uses: moncef00327-cloud/pq-tls-action@v1
  with:
    domain: example.com
    require-post-quantum: true
```

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
| `experiments/quantum-lab/` | IBM/Qiskit experiments (GHZ, Bell, teleportation, fidelity), and `requirements-quantum.txt`. Not used by the web service; run from the repo root |
| `results/` | Recorded experiment results (JSON), shown on `/research` |
| `dna_encode.py`, `bio_archive_report.py` | DNA encoding and the report archive (`archive` / `restore` / `verify`) |
| `deploy/` | Server install script, systemd unit, PayPal/admin configuration, nginx example |
| `tests/` | Unit tests |

## Run locally / التشغيل المحلي

```bash
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt   # experiments: -r experiments/quantum-lab/requirements-quantum.txt
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
