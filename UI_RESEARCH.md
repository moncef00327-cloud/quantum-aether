# Quantum Aether interface refresh — 2026-11-06

Scope: the complete Flask website, through its shared shell and component system,
with dedicated homepage and Gravity layouts. Existing scan, consent, subscription,
analytics and payment behavior is retained.

## Competitive teardown

These are selected relevant references, not a claim of verified market ranking.
Analysis covers publicly available page content and interaction structure.

| Reference | Observed pattern | Application in Aether |
| --- | --- | --- |
| [Cloudflare Radar PQ dashboard](https://radar.cloudflare.com/post-quantum) | Separate adoption, origin readiness and browser/website tools; contextual measurement explanations | Clear destinations for observatory, scanner and demand evidence; methodology beside evidence |
| [Qualys SSL Labs](https://www.ssllabs.com/ssltest/) | Direct hostname input with visible grading and recent results | Make the scanner the primary homepage interaction; keep real result grades readable |
| [Internet.nl](https://internet.nl/) | Task-specific test entry points, knowledge base and aggregate test statistics | Separate practical developer guides, free scanning and open data; avoid invented activity counters |
| [Hardenize](https://www.hardenize.com/) | Public test alongside continuous monitoring; distinct product and dashboard navigation | Show the free check first, then monitoring and research as clear next steps |

The implementation is original; no competitor assets or source code are copied.

## Implementation and versions

The verified current Flask release on [PyPI](https://pypi.org/project/Flask/) is
3.1.3, already pinned by the project and present in the serving environment.
This visual refresh adds no framework or CDN dependency. It uses native CSS Grid,
logical direction properties, responsive layout, accessible HTML details and
small progressive JavaScript. No library upgrade is necessary to deliver it.

- Light research canvas, dark green hero, restrained mint accents and readable
  tables replace the uniformly dark card stack.
- Shared header, grouped resources, language switcher, footer, forms, findings,
  grade badges, charts, pricing, consent blocks and code examples are redesigned.
- Arabic RTL, English and existing German pages retain their language behavior.
- Mobile navigation works with keyboard and Escape. Without JavaScript, navigation
  stays visible. Reduced motion and print layouts are supported.
- Homepage scan submission fields and analytics hooks remain intact.
- Gravity displays actual stored evidence, an honest empty state and explained
  editorial scores; it does not fabricate opportunities or live activity.

Deployment must copy only the revised templates, interface assets and Gravity
module, preserving newer production backend changes. Versioned asset URLs avoid
stale cached styles after deployment. Backups and automatic rollback are required.

## User-directed dark and horizontal revision

Following desktop and iPhone screenshots, the shared interface now uses a dark
navy canvas, blue-grey surfaces and mint actions (`static/aether-dark.css`). The
white scanner panel, header and content cards have been replaced. Existing
semantic result states remain distinct from general text and surfaces.

On phones, the scanner input and short submit label share a row, while the full
accessible button label is retained. Examples and discovery cards scroll within
their own horizontal regions, without making the document overflow. Desktop
content expands to a 1600px frame while prose retains bounded line lengths.

A fixed four-destination dock provides direct navigation on phones and tablets.
The header remains sticky and its expanded resources and language controls fit
within a scrollable menu. Safe-area spacing and bottom document padding keep the
last content reachable. Print output remains light.

QA checks include real Chromium screenshots before deployment, mobile input and
submit alignment, example-strip scrolling, dock visibility, menu/Escape behavior,
localized template rendering and existing scanner/monitoring tests. Browser
emulation does not constitute an actual iOS Safari device test.
