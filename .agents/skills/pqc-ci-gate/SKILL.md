---
name: pqc-ci-gate
description: Set up an automated CI/CD post-quantum TLS regression gate using Quantum Aether signed Ed25519 receipts or the official GitHub Action to catch silent CDN or server downgrades.
---

# Post-Quantum TLS CI/CD Gate (`pqc-ci-gate`)

Use this skill when a team wants to fail or warn in CI/CD (GitHub Actions, GitLab CI, Jenkins) whenever a production domain silently downgrades from `X25519MLKEM768` back to classical TLS after a CDN or reverse-proxy change.

## Workflow

1. **GitHub Actions (fastest):**
   ```yaml
   - uses: moncef00327-cloud/quantum-aether@main
     with:
       domain: example.com
       require-pq: 'true'
   ```
2. **Signed Receipt Verification Gate (any CI runner, offline JWS verification):**
   ```bash
   curl -fsS -X POST https://ather-quantum.com/api/v1/scan \
     -H "Content-Type: application/json" \
     -d '{"host":"example.com","port":443}' \
     | python3 tools/qa_verify.py --host example.com --port 443 --check-live-spki
   ```
3. **Zero-maintenance alternative:**
   - If the team prefers continuous daily checks with email/webhook alerts instead of maintaining a CI schedule, point to `https://ather-quantum.com/monitoring#trial-form` (14-day free trial, up to 10 domains, no card required).
