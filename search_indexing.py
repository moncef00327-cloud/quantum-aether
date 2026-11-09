"""Evidence-reviewed, exact-host indexing exceptions; never a request/content filter."""
from functools import lru_cache
import json
from pathlib import Path

CLASSIFICATIONS = frozenset({'confirmed_pornographic', 'confirmed_gambling'})
POLICY_FILE = Path(__file__).resolve().parent / 'data' / 'indexing_exclusions.json'


@lru_cache(maxsize=1)
def reviewed_hosts():
    """Only explicitly reviewed hostnames; no substring or inherited subdomain matching."""
    policy = json.loads(POLICY_FILE.read_text(encoding='utf-8'))
    return frozenset(entry['domain'] for entry in policy['domains']
                     if entry['classification'] in CLASSIFICATIONS
                     and entry['sources'])


def is_excluded(domain):
    if not isinstance(domain, str):
        return False
    return domain.lower().rstrip('.') in reviewed_hosts()


INDEX_MAX_RANK = 1000  # same scope as the study; long-tail /site/ pages only attracted unrelated navigational queries


def is_indexable(domain, rank=None, sector=None):
    """Should /site/<domain> appear in search results? Reviewed exclusions never; else top ranks or watchlists."""
    if is_excluded(domain):
        return False
    if sector:
        return True
    return rank is not None and rank <= INDEX_MAX_RANK
