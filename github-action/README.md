# Post-quantum TLS check — GitHub Action

[![Release](https://img.shields.io/github/v/release/moncef00327-cloud/pq-tls-action)](https://github.com/moncef00327-cloud/pq-tls-action/releases)
[![License: MIT](https://img.shields.io/github/license/moncef00327-cloud/pq-tls-action)](https://github.com/moncef00327-cloud/pq-tls-action/blob/main/LICENSE)
[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-Post--quantum%20TLS%20check-blue?logo=github)](https://github.com/marketplace/actions/post-quantum-tls-check-quantum-aether)

Fail CI when a site stops negotiating **post-quantum TLS** key exchange (**X25519MLKEM768** / **ML-KEM**, FIPS 203) — the hybrid group Chrome, Firefox and Edge use by default. Use it to catch **harvest-now-decrypt-later** exposure and to track **quantum-safe** / **NIS2**-era TLS readiness. The result appears in the workflow summary. Free, no API key.

The published action lives at [`moncef00327-cloud/pq-tls-action`](https://github.com/moncef00327-cloud/pq-tls-action). This directory is the in-repo copy.

## 30-second quick start

Add `.github/workflows/pq-tls.yml`:

```yaml
name: Post-quantum TLS
on:
  push:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1"   # also every Monday
jobs:
  pq-tls:
    runs-on: ubuntu-latest
    steps:
      - uses: moncef00327-cloud/pq-tls-action@v1
        with:
          domain: example.com
          require-post-quantum: true   # fail the job if it is missing
```

Example workflow summary after a successful check:

```
### Post-quantum TLS check

| Domain | Grade | Key exchange | Post-quantum |
|---|---|---|---|
| `cloudflare.com` | **A** | `X25519MLKEM768` | ✅ yes |
```

- Live scanner: https://ather-quantum.com
- Open dataset (weekly Tranco top 10,000, CC BY 4.0): https://ather-quantum.com/adoption

## Inputs

| Input | Default | Meaning |
|---|---|---|
| `domain` | — | Hostname to check (required) |
| `require-post-quantum` | `false` | Fail the job if X25519MLKEM768 is not negotiated |
| `min-grade` | empty | Fail the job if the grade is worse than `A`, `B`, `C` or `F` |
| `base-url` | `https://ather-quantum.com` | Scanner URL |

## Outputs

`grade`, `post-quantum` (`true`/`false`), `key-exchange`, `scan-url`.

## Behaviour

- Completed scans are checked against the requested policy. Invalid domains and failed scans fail the job.
- Unavailable scans fail the job, including rate limits, server errors and incomplete responses.
- Undetermined results (no negotiated key-exchange group observed) are reported as undetermined, never as classical, and fail `require-post-quantum`.
- The runner sends the domain to the hosted API. Its server probes the first public IPv4 address on port 443 from one location. CDN and anycast results can vary by location.

## Privacy and measurement limits

The hosted API stores the domain and result and returns a public scan page. Anyone with its URL can view the summary; the full report is sold for USD 49. Do not submit confidential hostnames. Noindex is not access control.

Grades combine key exchange with certificate validity and key strength. A post-quantum exchange can still receive F for a certificate issue. The `min-grade` policy and `require-post-quantum` policy check different conditions.

Self-host matching scanner and action revisions with declared dependencies. Hosted-only fields are not guaranteed in local deployments. The current scanner source exposes observation status and limitations; review the deployed revision before relying on additional response fields.

Methodology and open data: https://ather-quantum.com/adoption
