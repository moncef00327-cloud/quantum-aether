# AETHER GRAVITY ENGINE — pilot

Offline command-line tool. No scheduler, outbound messages, domain scans, or
automatic page publication is enabled. `deploy/deploy_gravity.sh` installs only
the tool and this document into the active release, with backup and rollback on
failure; it does not replace the web application or restart it.

## Repository audit

- `radar.py` already collects public discussion metadata through HN Algolia,
  Stack Exchange and GitHub APIs. Its existing job sends an owner digest;
  the new prototype does not invoke that job or its mailer.
- `adoption.py`, `adoption_job.py` and the study datasets already cover the
  observatory concept. Reuse these before building a second scanner.
- `templates/base.html` includes canonical, language alternatives, social metadata
  and a verification tag. `quantum_saas_app.py` exposes robots and split sitemaps.
  These are source-code observations, not confirmation of search indexing.
- `analytics_db.py` records sources and interaction events, excludes tests and bots,
  and uses daily visitor identifiers. Its visitor totals represent visitor-days,
  not distinct people across an entire month.
- API, OpenAPI, CLI and MCP already exist. Registry publication and usage
  attribution still need verification; availability alone does not prove usage.
- The reported 106 visits have not been verified. A date range and a read-only
  production analytics export are required before attributing them to sources.

## Run the local opportunity scorer

Provide a JSON array of permitted discussion metadata with `url`, `source`,
`title`, `text`, and optionally `created`. Supported source labels are GitHub,
Hacker News, Stack Overflow, Server Fault and Security SE. Retain only metadata
you are permitted to process; public accessibility is not a content reuse license.

```sh
python3 gravity.py /tmp/discussions.json /tmp/gravity-report.json
python3 -m unittest tests.test_gravity tests.test_radar
```

The scorer makes no network calls. It validates source hosts, excludes noise,
deduplicates discussion permalinks (including tracking links and Stack Exchange
question aliases) and groups evidence by platform using the existing radar filters.
Each opportunity retains evidence links, an existing guide, review status and
the score breakdown. Repeated collection of the same URL does not increase demand.
Scores are editorial heuristics, not market research, search volume, conversion
probabilities or permission to publish. Sparse evidence is allowed; no invented
opportunities are added to reach a target of 30–50.

Current limits: platform groups do not yet distinguish individual problems,
cross-posts may count separately, and freshness is not yet scored. Reviewed input
must specify its collection window. This is the first ranking layer, not all five
proposed crawlers or a completed autonomous growth system.

## Next review gates

1. Export the last 21 days of aggregate analytics in read-only mode; compare
   sources, landing pages, submissions, results and signup events. Record the
   date range and distinguish views from visitor-days.
2. Review permitted API access, quotas and retry rules before enabling collection;
   gather a bounded sample and record partial source failures. No new collector
   or scheduled job is enabled by this prototype.
3. Choose one repeated problem from evidence. Prefer a local diagnostic that
   accepts version/configuration input without fetching arbitrary URLs.
4. Prepare one original tool and technical page with methodology, timestamp,
   limitations and evidence. Obtain approval before publication or live changes.
5. Measure tool usage and downstream actions over 21 days. Set continuation
   thresholds against the measured baseline; do not infer demand from impressions
   or assume that registrations imply paying customers.
