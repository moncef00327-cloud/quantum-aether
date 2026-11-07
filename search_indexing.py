"""Evidence-reviewed, exact-host indexing exceptions; never a request/content filter."""
from functools import lru_cache
import json
from pathlib import Path

POLICY_FILE = Path(__file__).resolve().parent / 'data' / 'indexing_exclusions.json'


@lru_cache(maxsize=1)
def reviewed_hosts():
    """Only explicitly reviewed hostnames; no substring or inherited subdomain matching."""
    policy = json.loads(POLICY_FILE.read_text(encoding='utf-8'))
    return frozenset(entry['domain'] for entry in policy['domains']
                     if entry['classification'] == 'confirmed_pornographic'
                     and entry['sources'])


def is_excluded(domain):
    if not isinstance(domain, str):
        return False
    return domain.lower().rstrip('.') in reviewed_hosts()
