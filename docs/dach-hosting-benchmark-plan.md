# DACH post-quantum TLS hosting benchmark — research plan

**Status (2026-11-14):** execution is pending. No sample CSV, DNS/ASN verification, scan round, ranking, or sponsor recommendation exists yet; no plans have been purchased and no providers have been contacted. The workspace is on `main` with 43 pre-existing local changes, and `.git` is read-only in this session, so a separate feature branch could not be created. Do not deploy this work from the current workspace state.

## What the current report can and cannot say

The current provider table is a weekly snapshot of responding sites among the Tranco top 10,000, grouped by the ASN that answered the public TLS connection. In 2026-W46, it included two Cloudflare ASNs (97.3% across 2,010 sites and 100% across 121), two Akamai ASNs (98.8% across 241 and 92.3% across 182), Google ASNs (84.2% across 266 and 98.7% across 232), Amazon ASNs (60.4% across 1,464 and 6.5% across 263), Fastly (82.8% across 343), and Microsoft (41.0% across 144).

This is useful for observing edge networks. It does not currently provide a DACH web-hosting-provider league table. A provider missing from the displayed table may be below the 20-site reporting threshold, outside the Tranco sample, or hidden behind another network. Do not describe that as a measured failure or as proof that the provider is absent from the market.

## Candidate inventory

This is a sourcing list, not a ranking or endorsement. “Priority” means worth trying to build a transparent sample for; it does not imply PQ support. Eligibility is decided at the **product / plan** level: include shared hosting and managed WordPress where the provider controls TLS defaults. Exclude customer-managed VPS, cloud VMs, and dedicated servers from the managed-hosting ranking, even when sold by a listed provider. A company can qualify for one managed plan and be excluded for its self-managed infrastructure offer.

| Market | Provider candidate | Public service page | Initial priority |
|---|---|---|---|
| Germany | IONOS | https://www.ionos.de/hosting/webhosting | High |
| Germany | STRATO | https://www.strato.de/hosting/ | High |
| Germany | Hetzner | https://www.hetzner.com/webhosting/ | High; only provider-managed shared plan, never customer-configured VPS/dedicated |
| Germany | netcup | https://www.netcup.com/de/hosting | High; only provider-managed shared plan, never customer-configured VPS/cloud |
| Germany | ALL-INKL.COM | https://all-inkl.com/webhosting/ | High |
| Germany | DomainFactory | https://www.df.eu/de/webhosting/ | Medium |
| Germany | Host Europe | https://www.hosteurope.de/ | Medium |
| Germany | Mittwald | https://www.mittwald.de/webhosting | Medium |
| Germany | webgo | https://www.webgo.de/webhosting/ | Medium |
| Germany | manitu | https://www.manitu.de/webhosting/ | Medium |
| Germany | goneo | https://www.goneo.de/webhosting.html | Medium |
| Austria | World4You | https://www.world4you.com/en/hosting | High |
| Austria | easyname | https://www.easyname.at/de/hosting | High |
| Austria | Domaintechnik.at | https://www.domaintechnik.at/ | Medium |
| Austria | HostProfis | https://www.hostprofis.com/web/product/webhosting | Medium |
| Austria | hoststar | https://www.hoststar.at/ | Medium |
| Switzerland | Hostpoint | https://www.hostpoint.ch/en/webhosting/webhosting.html | High |
| Switzerland | Infomaniak | https://www.infomaniak.com/en/hosting/web-hosting | High |
| Switzerland | cyon | https://www.cyon.ch/ | Medium |
| Switzerland | METANET | https://www.metanet.ch/de/hosting/webhosting | Medium |
| Switzerland | green.ch | https://www.green.ch/ | Medium |
| Switzerland | hosttech | https://www.hosttech.ch/ | Medium |

## Sampling protocol

1. Fix the observation window, scanner version, and algorithm before scanning. The baseline starts in **2026-W47**; keep earlier snapshots archived separately and do not combine results produced under different HelloRetryRequest handling.
2. Apply the same HelloRetryRequest (HRR) logic to every provider and endpoint. The scanner answers one HRR as a browser would; count the final negotiated group after a successful retry. If the retry cannot be completed, record the result as **undetermined**, not classical or PQ. The current scanner has explicit HRR handling and regression coverage in `quantum_vuln_scanner.py` and `tests/test_scanner_retry.py`.
3. Select 5–8 eligible managed-hosting plans using criteria fixed before reading their TLS results (market coverage, managed-plan fit, and availability of a reproducible default endpoint). Test each provider’s cheapest eligible plan from a fresh, uncustomized setup. Do not add a CDN, change TLS settings, or install a custom proxy. Capture plan/SKU, setup date, and any trial/return conditions. This is a spending step: obtain the owner’s approval for the named providers and maximum total purchase budget before subscribing. Do not buy plans as part of preparing this plan.
4. For the requested preliminary same-day snapshot, scan every verified endpoint in three rounds on the same day, with at least two hours between round start times, using the same scanner version, vantage point, SNI, and TLS offer. Preserve all three raw observations. If outcomes differ, classify the endpoint as variable and investigate before assigning a stable result. A same-day snapshot is not equivalent to the original three-day repeatability protocol and must be labeled accordingly.
5. For each provider, separately collect its own public website plus up to 10 customer websites explicitly shown on the provider’s own project, reference, or case-study pages. Save the source URL and capture date. Do not infer customer status from third-party directories or assume the site is still hosted there.
6. Attribute customer-site observations only when the current endpoint/ASN supports the attribution. If it is behind Cloudflare, Akamai, Fastly, another CDN, or a reverse proxy, label it “edge network observed; underlying host unverified.” Treat customer sites as supplementary evidence, not a substitute for the provider-managed default-plan test.
7. Keep the provider home page in a separate “provider’s own endpoint” row; do not blend it with customer sites. Do not put self-managed VPS/cloud/dedicated plans into the managed-hosting ranking.
8. Publish the full denominator: selected, reachable, PQ-hybrid, classical, edge-obscured, variable, and unresolved. Do not publish a customer-sample percentage with fewer than 10 attributable, reachable customer sites. Show raw counts and uncertainty; mark smaller samples “insufficient sample.”
9. After the findings are frozen, prepare factual German right-of-reply notices for each included provider and show the recipient, sender identity, and final text before transmission. The user has now authorized sending these notices from the project email after results are complete. Send only these non-promotional notices, through a verified project sender, and give recipients 7 days to flag factual errors. Corrections may amend attribution or endpoint ownership, never change the handshake observation without a reproducible re-scan. Do not send any sponsorship pitch.

## Sponsorship rules and screening

- Never offer sponsorship of a ranking report to any hosting provider ranked in that report. Do not mention sponsorship in the same message as the results or right-of-reply notice.
- A hosting provider may be considered for sponsorship of the general tracker or an educational guide only after the ranking report is published, on a separate placement with clear disclosure. The payment must not be conditional on ranking, score, or editorial treatment.
- The cleaner first sponsor prospect is a security consultancy outside the provider ranking. If no suitable sponsor qualifies, publish unsponsored.
- Label any separate paid placement “Anzeige” / “Sponsored by”. A sponsor buys visibility, not a score, ranking position, lead list, or customer-specific recommendation.
- Keep sponsor logos out of per-site B/C results. A “recommended provider” box would imply endorsement and a connection between that provider and the specific site's findings; it is not part of the offer.
- For a separate general-tracker or guide placement, begin with a cancellable one-month founder sponsorship of **€150–€300/month**, or a separately disclosed, explicitly tracked referral fee. Do not promise reach or conversions; report measured impressions and clicks only.
- If a proposal requests legal-entity details, use the site's published imprint accurately: it identifies an individual operator, states small-business VAT status, and says the operator is not registered in the Firmenbuch. Do not represent Quantum Aether as an incorporated company.

## Evidence links

- Current Quantum Aether hosting-network page: https://ather-quantum.com/adoption/hosting?lang=en
- Current snapshot and source dataset: `data/reports/2026-11.json`
- The weekly adoption code groups results by observed ASN and suppresses provider rows under 20 responding sites: `adoption.py` (`PROVIDER_MIN_SITES = 20`).
- Austrian candidates: World4You’s official hosting description says its service is based in Austria: https://www.world4you.com/en/hosting ; easyname identifies Vienna server location and customer projects: https://www.easyname.at/de/hosting ; HostProfis’ official web-hosting offer: https://www.hostprofis.com/web/product/webhosting
- Swiss candidates: official Hostpoint hosting page: https://www.hostpoint.ch/en/webhosting/webhosting.html ; Infomaniak web hosting: https://www.infomaniak.com/en/hosting/web-hosting ; METANET web hosting: https://www.metanet.ch/de/hosting/webhosting
- German candidates: official IONOS, STRATO, and netcup hosting pages: https://www.ionos.de/hosting/webhosting ; https://www.strato.de/hosting/ ; https://www.netcup.com/de/hosting
