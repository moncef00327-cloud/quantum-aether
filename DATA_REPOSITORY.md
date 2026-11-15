# Data repository

## What is refreshed

The existing adoption scheduler is the recurring measurement source. Its weekly run measures the current Tranco top 10,000 plus the reviewed watchlists; its monthly run measures the current Tranco top 100,000. Each successful run updates the live adoption tables, so the site's current figures change on the next scheduled scan. The probe is limited to the public hostname's TLS handshake on TCP/443 and does not fetch page content.

Every successful run now also writes an immutable snapshot under:

```text
<DATA_DIR>/repository/adoption/{weekly|monthly}/<period>/
```

Each snapshot is gzip-compressed JSONL plus a manifest. The manifest records its period, archive time, scheduled/backfill provenance, row count, source/code SHA-256 fingerprints, and data SHA-256. Snapshots omit endpoint IP addresses and contain no visitor, account, or search-query data. Reviewed indexing exclusions and opt-outs are applied before the archive is made. Re-running a period creates a new snapshot; it never overwrites the previous one.

The operational SQLite tables retain 52 weekly periods and 6 monthly periods for the live site. Repository snapshots are outside that pruning window and are append-only. Backups of `DATA_DIR/repository/` are still required for disaster recovery.

## Backfill and integrity check

Run from the project environment, pointing at the same data directory as the service:

```bash
python data_repository.py backfill --db /path/to/quantum_saas.db --data-dir /path/to/DATA_DIR
python data_repository.py verify --data-dir /path/to/DATA_DIR
```

Backfill opens SQLite read-only and archives periods currently present in the database. It labels them `historical-backfill`: source fingerprints describe the current code/source files at archive time and do not claim those files were used for the original historical measurement. It appends new snapshots instead of replacing existing ones. `verify` checks each manifest's archive hash and record count.

## Source lineage and boundaries

See [`data/source_registry.json`](data/source_registry.json) for source IDs, update notes, attribution, and privacy boundaries. The Tranco input is currently a pinned snapshot (list ID GQ38K); updating it is a separately reviewed source refresh, not an automatic download. Watchlist additions should be traceable to public source URLs in the change history. The ip-to-ASN mapping is used for network aggregation and is identified as PDDL in the project README; raw IPs are not included in snapshots.

Search Console and GA4 exports are private first-party analytics, not part of the public adoption dataset. They are not automatically imported by this change; adding authenticated connectors requires credentials and should store only access-controlled aggregate reports. Cloudflare Radar is a possible external context source, but is not integrated and requires an authorized API token and a reuse-terms review. No new hostnames are scanned as a result of this archive change.

## Public data

The existing `/adoption.json` and `/adoption.csv` endpoints remain the public current-data exports under the project's stated CC BY 4.0 terms. The permanent operational snapshots under `DATA_DIR` are private service data and are not published by this feature.
