# Quantum Aether 2.0 — audit and implementation plan

Audit date: 2026-11-06. Local checkout: `7e8ab94` plus existing uncommitted
Gravity/interface work, retained. This task does not authorize deployment.

## Architecture and baseline

- Python/Flask 3.1.3, a `site` Blueprint in `quantum_saas_app.py`, Jinja server
  rendering and SQLite. Gunicorn/systemd behind a reverse proxy; deployment
  examples reference nginx. No frontend framework, bundler or TypeScript.
- All 27 HTML templates reviewed: shared shell; homepage; scanner/report;
  comparison; adoption/country/study; Gravity; guides/research/deadlines;
  monitoring/accounts; payments/packs; admin; legal/errors/scanning policy.
- Existing CSS is a three-file cascade (~43 KB uncompressed). Shared JS is
  approximately 4.8 KB; payment scripts are loaded only on relevant pages.
  Fonts use system fallbacks; scientific plots and local font assets are retained.
- Existing features: free scan + APIs/CLI, paid report, monitoring, badge SVG,
  two-domain live comparison, migration snippets/guides, published studies,
  adoption history/countries/providers, Gravity scoring, MCP and GitHub Action.
- Baseline: 203 tests passed. Chromium inspected 203 localized page/viewport
  combinations at 320, 375, 390, 430, 768, 1024, 1440px. No document overflow,
  but 44 cases contained horizontal scrolling regions, including deliberate
  card strips and data tables. Screenshots preserved under `/tmp/aether-v2-before`.
- Authentication, payment verification, report tokens, owner-test exclusion,
  scanner attempt limits, public-address-only DNS checking and pinned-IP socket
  connections already exist. The scanner does not follow HTTP redirects or fetch
  submitted application URLs. SQL uses parameters for user inputs.

## Priorities, based on code inspection

| Priority | Finding | Planned small change |
| --- | --- | --- |
| P0 | A HelloRetryRequest can currently be reported as negotiated PQ support | Treat retry-only evidence as undetermined, propagate that state to results, datasets and badge verification; add regression tests |
| P0 | ServerHello parsing accepts inconsistent lengths/extension boundaries | Bound and validate messages and key-share structures; test truncation and oversized responses |
| P0 | Non-object JSON can raise `.get` errors in public APIs | Validate JSON shape consistently and bound request bodies without changing authorization |
| P1 | URL normalization silently strips credentials, arbitrary schemes and ports | Explicit HTTP(S)/hostname parsing, reject credentials and ambiguous hosts; document fixed port 443 behavior |
| P1 | Badge exists but has no explicit verification/expiration view; daily cache may outlive freshness | Reuse stored data only; add verification metadata/page, uncertain/stale statuses and expiry-bounded caching |
| P1 | Loading disables the first button and may remain disabled on browser Back; no network recovery | Determinate submitted/waiting/done/error states without fabricated progress; local validation, retry and BFCache recovery |
| P1 | Canonicals/OG use request URLs; comparison language links lose domains; scan indexing headers incomplete | Trusted configured origin, meaningful comparison query preservation, privacy/noindex and cache controls for scan APIs/results |
| P1 | New navy overrides drift from requested emerald identity; phone navigation and card strips require extra scrolling | Restore emerald tokens, readable compact scanner, full-width cards without horizontal card scrolling, safe bottom navigation and keyboard behavior |
| P2 | Migration advice is identical regardless of observations | Evidence-based next steps with explicit infrastructure uncertainty, reusing guides |
| P2 | Tracker already has sources, dates and denominators | Retain those; improve table wrapping/headers and chart accessibility rather than invent data |

## Verification and release boundary

Use isolated temporary databases and labeled test fixtures; never seed production
with test results. Run regression/unit/integration tests, Python compilation,
JavaScript syntax and responsive/browser checks, including scanner error/retry and
keyboard flows. Produce before/after images. No production build is required by
this server-rendered application. MCP distribution build depends on optional
packaging tools; document any unavailable check. No production writes, secrets,
authentication changes, DNS changes, scheduled jobs, publishing or deployment.

## References used to validate the audit

- [TLS 1.3 HelloRetryRequest semantics](https://www.rfc-editor.org/rfc/rfc8446#section-4.1.4)
- [OWASP SSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [Google localized-page guidance](https://developers.google.com/search/docs/specialty/international/localized-versions)

The security review is scoped code review and regression testing, not an external
penetration test or a claim that every vulnerability has been eliminated.
