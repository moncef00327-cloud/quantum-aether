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

- Fails only when you ask it to (`require-post-quantum`, `min-grade`) or the domain is invalid.
- If the scanner is unreachable or rate-limited, it logs a warning and does **not** break your deploy.
- Each run makes the same two TLS connections to port 443 as a browser; nothing else is sent.

Methodology and open data: https://ather-quatum.cloud/adoption
