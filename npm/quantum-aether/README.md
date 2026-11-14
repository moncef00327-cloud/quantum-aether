# quantum-aether

Does a website negotiate **post-quantum TLS** key exchange — the hybrid `X25519MLKEM768`
(ML-KEM, FIPS 203) that Chrome, Firefox and Edge use by default? Free, no install, no account,
zero dependencies.

```sh
npx quantum-aether example.com
```

```
  Quantum Aether — post-quantum TLS check
  domain        example.com
  grade         B
  key exchange  x25519
  post-quantum  NO — classical only (harvest-now-decrypt-later risk)
  TLS           TLSv1.3
  result page   https://ather-quantum.com/scan/…
  how to fix    https://ather-quantum.com/tools/pq-tls-config
```

## Options

| Option | Meaning |
|---|---|
| `--json` | raw JSON result, for scripts and AI agents |
| `--require-pq` | exit code 2 if X25519MLKEM768 is not negotiated (CI gate) |
| `--min-grade A\|B\|C\|F` | exit code 2 if the grade is worse |
| `-v`, `--version` / `-h`, `--help` | version / help |

Exit codes: `0` ok · `1` error (invalid domain, network, service) · `2` policy failed.

```sh
npx quantum-aether example.com --require-pq || echo "not post-quantum yet"
```

## How it works

The CLI calls the public API `GET https://ather-quantum.com/api/v1/scan?domain=…`. The scan runs on
Quantum Aether's server: one TLS 1.3 handshake offering X25519MLKEM768 on port 443 of the first
public address, from one location (a CDN edge may differ from your origin). The hosted service stores
the domain and result and creates a public result page — do not submit confidential hostnames.
Set `QUANTUM_AETHER_BASE` to use a self-hosted scanner.

No Node? `curl "https://ather-quantum.com/api/v1/scan?domain=example.com&format=text"`

Also: [GitHub Action](https://github.com/marketplace/actions/post-quantum-tls-check-quantum-aether) ·
[MCP server](https://pypi.org/project/quantum-aether-mcp/) ·
[config generator](https://ather-quantum.com/tools/pq-tls-config) ·
[daily monitoring, 14 days free](https://ather-quantum.com/monitoring)

MIT licensed.
