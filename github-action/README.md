Privacy disclosure - the hosted API stores the domain and result and returns a public scan page. Anyone with its URL can view the summary; the full report is sold for USD 49. Do not submit confidential hostnames. Noindex is not access control.
Grades combine key exchange with certificate validity and key strength. A post-quantum exchange can still receive F for a certificate issue. The min-grade policy and require-post-quantum policy check different conditions.
Self-host matching scanner and action revisions with declared dependencies. Hosted-only fields are not guaranteed in local deployments. The current scanner source exposes observation status and limitations; review the deployed revision before relying on additional response fields.
# Post-quantum TLS check — GitHub Action

Check on every deploy that your site negotiates the hybrid post-quantum TLS key exchange
**X25519MLKEM768** (ML-KEM, FIPS 203) — the one Chrome, Firefox and Edge use by default.
The result appears in the workflow summary. Free, no API key.

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

## Inputs

| Input | Default | Meaning |
|---|---|---|
| `domain` | — | Hostname to check (required) |
| `require-post-quantum` | `false` | Fail the job if X25519MLKEM768 is not negotiated |
| `min-grade` | empty | Fail the job if the grade is worse than `A`, `B`, `C` or `F` |
| `base-url` | `https://ather-quatum.cloud` | Scanner URL |

## Outputs

`grade`, `post-quantum` (`true`/`false`), `key-exchange`, `scan-url`.

## Behaviour

- Completed scans are checked against the requested policy. Invalid domains and failed scans fail the job.
- Unavailable scans fail the job, including rate limits, server errors and incomplete responses.
- The runner sends the domain to the hosted API. Its server probes the first public IPv4 address on port 443 from one location. CDN and anycast results can vary by location.

Methodology and open data: https://ather-quatum.cloud/adoption
