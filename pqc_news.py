"""Load the checked-in PQC news snapshot and refresh it from the scheduled GitHub feed."""
from __future__ import annotations

import json
from pathlib import Path
import threading
import time
from urllib.request import Request, urlopen

FEED_URL = "https://raw.githubusercontent.com/moncef00327-cloud/quantum-aether/main/analytics/news_feed.json"
REFRESH_SECONDS = 900
MAX_BYTES = 512_000
_LOCK = threading.Lock()
_CACHE = {"checked_at": 0.0, "data": None}


def _valid(document):
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        return False
    if not isinstance(document.get("items"), list) or len(document["items"]) > 100:
        return False
    allowed_hosts = ("nist.gov", "ibm.com", "blog.google", "cloudflare.com", "arxiv.org")
    for item in document["items"]:
        if not isinstance(item, dict) or not all(item.get(k) for k in ("title", "url", "source", "category", "importance", "takeaway")):
            return False
        if not isinstance(item["title"], str) or len(item["title"]) > 300:
            return False
        if not isinstance(item["takeaway"], dict) or not all(isinstance(item["takeaway"].get(lang), str) for lang in ("en", "ar", "de")):
            return False
        from urllib.parse import urlparse
        link = urlparse(item["url"])
        host = (link.hostname or "").lower().rstrip(".")
        if link.scheme != "https" or not any(host == domain or host.endswith("." + domain) for domain in allowed_hosts):
            return False
        if item["category"] not in {"standards", "vulnerability", "implementation", "research"}:
            return False
        if item["importance"] not in {"high", "medium"}:
            return False
    return True


def load_feed(snapshot_path: str | Path | None = None):
    """Refresh at most every 15 minutes; use the bundled snapshot if GitHub is unavailable."""
    now = time.monotonic()
    if _CACHE["data"] is not None and now - _CACHE["checked_at"] < REFRESH_SECONDS:
        return _CACHE["data"]
    with _LOCK:
        now = time.monotonic()
        if _CACHE["data"] is not None and now - _CACHE["checked_at"] < REFRESH_SECONDS:
            return _CACHE["data"]
        snapshot = Path(snapshot_path or Path(__file__).resolve().parent / "analytics" / "news_feed.json")
        data = None
        try:
            candidate = json.loads(snapshot.read_text(encoding="utf-8"))
            if _valid(candidate):
                data = candidate
        except (OSError, ValueError):
            pass
        remote = None
        try:
            request = Request(FEED_URL, headers={"User-Agent": "QuantumAether-Analytics/1.0"})
            with urlopen(request, timeout=3) as response:
                raw = response.read(MAX_BYTES + 1)
            if len(raw) <= MAX_BYTES:
                candidate = json.loads(raw.decode("utf-8"))
                if _valid(candidate):
                    remote = candidate
        except Exception:
            remote = None
        if remote and (not data or remote.get("updated_at", "") >= data.get("updated_at", "")):
            data = remote
        _CACHE["data"] = data or {"schema_version": 1, "updated_at": None, "sources": [], "items": []}
        _CACHE["checked_at"] = time.monotonic()
        return _CACHE["data"]
