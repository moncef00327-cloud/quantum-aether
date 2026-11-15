"""Append-only snapshots of the public TLS adoption measurements.

Snapshots deliberately omit endpoint IPs and all visitor, account, and query data.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import secrets
import sqlite3
import tempfile
from pathlib import Path

import adoption
import search_indexing

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_VERSION = 1
WEEKLY_COLUMNS = ("week", "domain", "rank", "sector", "ok", "grade", "grp", "tls", "pq", "scanned_at", "asn", "as_name", "unsure")
MONTHLY_COLUMNS = ("month", "domain", "rank", "ok", "grade", "grp", "pq", "asn", "as_name", "scanned_at", "unsure")
SOURCE_FILES = (
    "data/tranco_GQ38K_top100k.csv", "data/adoption_watchlists.json",
    "data/adoption_optout.txt", "data/indexing_exclusions.json",
    "data/source_registry.json", "adoption.py", "adoption_job.py",
    "quantum_vuln_scanner.py", "asn.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_fingerprints() -> dict:
    result = {}
    for relative in SOURCE_FILES:
        path = BASE_DIR / relative
        result[relative] = _sha256(path) if path.is_file() else None
    return result


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _records(conn: sqlite3.Connection, mode: str, period: str) -> list[dict]:
    table, key, columns = (("adoption_results", "week", WEEKLY_COLUMNS) if mode == "weekly"
                           else ("adoption_monthly", "month", MONTHLY_COLUMNS))
    available = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    selected = [column for column in columns if column in available]
    rows = conn.execute(
        f"SELECT {', '.join(selected)} FROM {table} WHERE {key} = ? ORDER BY domain", (period,)
    )
    opted_out = adoption.load_optout(conn=conn)
    return [dict(row) for row in rows
            if not search_indexing.is_excluded(row["domain"])
            and not adoption.opted_out(row["domain"], opted_out)]


def archive_adoption_period(conn: sqlite3.Connection, data_dir: str | os.PathLike,
                            mode: str, period: str, provenance: str = "scheduled") -> dict:
    """Write an immutable gzip JSONL snapshot and its manifest; never overwrite a snapshot."""
    if mode not in ("weekly", "monthly"):
        raise ValueError("mode must be weekly or monthly")
    records = _records(conn, mode, period)
    if not records:
        raise ValueError(f"no adoption rows found for {mode} {period}")
    content = b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        for row in records
    )
    compressed = gzip.compress(content, mtime=0)
    now = dt.datetime.now(dt.timezone.utc)
    root = Path(data_dir) / "repository" / "adoption" / mode / period
    snapshot_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    data_name = f"{snapshot_id}.jsonl.gz"
    manifest_name = f"{snapshot_id}.manifest.json"
    manifest = {
        "schema_version": SCHEMA_VERSION, "dataset": "public_tls_adoption",
        "mode": mode, "period": period, "snapshot_id": snapshot_id,
        "archived_at": now.isoformat(timespec="seconds"), "provenance": provenance,
        "measurement_scope": "public host TLS handshake on TCP/443; no page content",
        "records": len(records), "data_file": data_name,
        "data_sha256": hashlib.sha256(compressed).hexdigest(),
        "source_sha256": _source_fingerprints(),
        "fields_excluded": ["ip", "visitor data", "accounts", "search queries"],
    }
    # Data is written first; an incomplete snapshot without a manifest is ignored by verify.
    _atomic_write(root / data_name, compressed)
    _atomic_write(root / manifest_name, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
    return {"path": str(root / data_name), "manifest": str(root / manifest_name), "records": len(records)}


def verify_repository(data_dir: str | os.PathLike) -> dict:
    root = Path(data_dir) / "repository" / "adoption"
    manifests = sorted(root.glob("**/*.manifest.json"))
    errors, verified = [], 0
    for manifest_path in manifests:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            data_path = manifest_path.parent / manifest["data_file"]
            if _sha256(data_path) != manifest["data_sha256"]:
                raise ValueError("data SHA-256 mismatch")
            with gzip.open(data_path, "rt", encoding="utf-8") as stream:
                count = sum(1 for line in stream if line.strip())
            if count != manifest["records"]:
                raise ValueError(f"record count mismatch: {count} != {manifest['records']}")
            verified += 1
        except Exception as exc:
            errors.append({"manifest": str(manifest_path), "error": str(exc)})
    return {"manifests": len(manifests), "verified": verified, "errors": errors}


def backfill(db_path: str | os.PathLike, data_dir: str | os.PathLike) -> list[dict]:
    """Archive periods already present in a database opened read-only."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        result = []
        for table, key, mode in (("adoption_results", "week", "weekly"), ("adoption_monthly", "month", "monthly")):
            periods = [row[0] for row in conn.execute(f"SELECT DISTINCT {key} FROM {table} ORDER BY {key}")]
            for period in periods:
                period_dir = Path(data_dir) / "repository" / "adoption" / mode / period
                if list(period_dir.glob("*.manifest.json")):
                    continue
                try:
                    result.append(archive_adoption_period(conn, data_dir, mode, period, provenance="historical-backfill"))
                except ValueError:  # period contained only excluded or opted-out domains
                    continue
        return result
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "backfill"))
    parser.add_argument("--data-dir", required=True, help="same DATA_DIR used by the application")
    parser.add_argument("--db", help="database path for read-only backfill")
    args = parser.parse_args()
    if args.command == "verify":
        result = verify_repository(args.data_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result["errors"] else 0
    if not args.db:
        parser.error("backfill requires --db")
    result = backfill(args.db, args.data_dir)
    print(json.dumps({"snapshots_created": len(result), "records": sum(x["records"] for x in result)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
