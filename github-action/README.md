Privacy disclosure - the hosted API stores the domain and result and returns a public scan page. Anyone with its URL can view the summary; the full report is sold for USD 49. Do not submit confidential hostnames. Noindex is not access control.
Grades combine key exchange with certificate validity and key strength. A post-quantum exchange can still receive F for a certificate issue. The min-grade policy and require-post-quantum policy check different conditions.
Self-host matching scanner and action revisions with declared dependencies. Hosted-only fields are not guaranteed in local deployments. The current scanner source exposes observation status and limitations; review the deployed revision before relying on additional response fields.
# Post-quantum TLS check — GitHub Action

Run a free TLS/PQC check in any CI pipeline. It reports whether the public endpoint negotiated
the hybrid post-quantum key exchange **X25519MLKEM768** (ML-KEM, FIPS 203) and adds a result
summary to the workflow. By default, a classical or undetermined result is reported without
failing the build; opt into a policy gate when that is your release requirement. No API key.

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
      - uses: moncef00327-cloud/quantum-aether@main
        with:
          domain: example.com
          update-readme: true          # edit a marked live-badge block in the workspace
          require-post-quantum: false   # set true only to make PQ negotiation a build gate
```

## Inputs

| Input | Default | Meaning |
|---|---|---|
| `domain` | — | Hostname to check (required) |
| `require-post-quantum` | `false` | Fail the job if X25519MLKEM768 is not negotiated |
| `min-grade` | empty | Fail the job if the grade is worse than `A`, `B`, `C` or `F` |
| `base-url` | `https://ather-quantum.com` | Scanner URL |
| `update-readme` | `false` | Insert or refresh the action-owned live badge block in `README.md` |
| `write-report` | `false` | Write the scan response to `qa_report.json` |

## Outputs

`grade`, `post-quantum` (`true`/`false`/`undetermined`), `key-exchange`, `scan-url`, `badge-url`.

## Behaviour

- Completed scans are checked against the requested policy. Invalid domains and failed scans fail the job.
- Unavailable scans fail the job, including rate limits, server errors and incomplete responses.
- The runner sends the domain to the hosted API. Its server probes the first public IPv4 address on port 443 from one location. CDN and anycast results can vary by location.
- `update-readme` changes only the checked-out workspace; commit that change in your workflow if you want it persisted. The badge is a public observation, not a security certification.
- The hosted API stores the domain and result on a public result page. Do not submit private hostnames; `noindex` is not access control.

Methodology and open data: https://ather-quantum.com/adoption
