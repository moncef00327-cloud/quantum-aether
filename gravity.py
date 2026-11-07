"""Offline demand evidence ranking. Never scans domains, publishes, or sends mail."""
import argparse
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

import radar

HOSTS = {
    "GitHub": {"github.com"},
    "Hacker News": {"news.ycombinator.com"},
    "Stack Overflow": {"stackoverflow.com"},
    "Server Fault": {"serverfault.com"},
    "Security SE": {"security.stackexchange.com"},
}


def evidence_url(value, source):
    """Accept discussion permalinks only, removing tracking and comment anchors."""
    try:
        url = urlsplit(value)
        if (url.scheme != "https" or url.hostname not in HOSTS.get(source, set())
                or url.username or url.password or url.port not in (None, 443)):
            return None
    except ValueError:
        return None
    path, query = url.path.rstrip("/"), ""
    if source == "Hacker News":
        ids = parse_qs(url.query).get("id", [])
        if path != "/item" or len(ids) != 1 or not re.fullmatch(r"[1-9][0-9]*", ids[0]):
            return None
        query = "id=" + str(int(ids[0]))
    elif source == "GitHub":
        if not re.fullmatch(r"/[^/]+/[^/]+/(issues|discussions)/[1-9][0-9]*", path):
            return None
    else:
        match = re.fullmatch(r"/(?:questions|q)/([1-9][0-9]*)(?:/.*)?", path)
        if not match:
            return None
        path = "/questions/" + match[1]
    return urlunsplit(("https", url.hostname, path, query, ""))


def opportunities(items):
    """Group independent discussion URLs; scores are heuristics, not search volume."""
    groups, seen = {}, set()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item = {k: str(raw.get(k) or "") for k in ("title", "text", "source", "url", "created")}
        canonical = evidence_url(item["url"], item["source"])
        if canonical is None:
            continue
        item["url"] = canonical
        if item["url"] in seen or not radar.relevant(item):
            continue
        seen.add(item["url"])
        topic = radar.topic_of(item)
        evidence = groups.setdefault(topic, [])
        evidence.append({k: item[k] for k in ("url", "source", "title", "created")})
    rows = []
    for topic, evidence in groups.items():
        count = len(evidence)
        diversity = len({i["source"] for i in evidence})
        components = {"discussion_evidence": min(40, count * 8),
                      "source_diversity": min(20, diversity * 5),
                      "developer_relevance": 20 if topic != "general" else 10,
                      "existing_guide_reuse": 10}
        rows.append({"topic": topic, "score": sum(components.values()),
                     "score_components": components, "discussion_count": count,
                     "status": "needs_review", "existing_guide": radar.GUIDES[topic],
                     "proposal": f"Build a reproducible {topic} PQC compatibility diagnostic",
                     "evidence": sorted(evidence, key=lambda i: i["url"])})
    return sorted(rows, key=lambda i: (-i["score"], i["topic"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON array of discussion metadata exported for review")
    parser.add_argument("output", type=Path, help="Local report; no network requests")
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must be different files")
    try:
        items = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.error(f"cannot read input: {exc}")
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        parser.error("input must be a JSON array of objects")
    report = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "score_type": "editorial heuristic; not measured search volume or conversion probability",
              "publication": "manual approval required", "opportunities": opportunities(items)}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
