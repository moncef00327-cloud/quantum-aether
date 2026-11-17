"""Evidence-reviewed, exact-host indexing exceptions; never a request/content filter."""
from functools import lru_cache
import json
from pathlib import Path

CLASSIFICATIONS = frozenset({'confirmed_pornographic', 'confirmed_gambling'})
POLICY_FILE = Path(__file__).resolve().parent / 'data' / 'indexing_exclusions.json'
INFRASTRUCTURE_FILE = Path(__file__).resolve().parent / 'data' / 'indexing_infrastructure.json'
# Automated backstop: hosts that Cloudflare family DNS (1.1.1.3) resolves to 0.0.0.0
# (adult/malware). Populated by tools/family_dns_scan.py; never indexed, so new
# adult/malicious domains are de-indexed without waiting for manual review.
FAMILY_DNS_FILE = Path(__file__).resolve().parent / 'data' / 'family_dns_blocked.json'


@lru_cache(maxsize=1)
def reviewed_hosts():
    """Only explicitly reviewed hostnames; no substring or inherited subdomain matching."""
    policy = json.loads(POLICY_FILE.read_text(encoding='utf-8'))
    return frozenset(entry['domain'] for entry in policy['domains']
                     if entry['classification'] in CLASSIFICATIONS
                     and entry['sources'])


@lru_cache(maxsize=1)
def infrastructure_hosts():
    """Reviewed CDN/DNS/ad/telemetry/API hosts: scanned and counted like any other, but never indexed. Exact hosts."""
    if not INFRASTRUCTURE_FILE.exists():
        return frozenset()
    policy = json.loads(INFRASTRUCTURE_FILE.read_text(encoding='utf-8'))
    return frozenset(host.lower() for host in policy['hosts'])


def _normal(domain):
    return domain.lower().rstrip('.') if isinstance(domain, str) else None


@lru_cache(maxsize=1)
def family_dns_blocked_hosts():
    if not FAMILY_DNS_FILE.exists():
        return frozenset()
    data = json.loads(FAMILY_DNS_FILE.read_text(encoding='utf-8'))
    return frozenset(h.lower() for h in data.get('hosts', []))


def family_dns_blocked(domain):
    host = _normal(domain)
    return host is not None and host in family_dns_blocked_hosts()


def is_excluded(domain):
    host = _normal(domain)
    return host is not None and host in reviewed_hosts()


def is_infrastructure(domain):
    host = _normal(domain)
    return host is not None and host in infrastructure_hosts()


INDEX_MAX_RANK = 1000  # same scope as the study; long-tail /site/ pages only attracted unrelated navigational queries


def is_indexable(domain, rank=None, sector=None):
    """Should /site/<domain> appear in search results? Reviewed exclusions never; watch-list (sector) domains always;
    else top ranks, minus infrastructure endpoints nobody looks up (they only drew unrelated queries)."""
    if is_excluded(domain) or family_dns_blocked(domain):
        return False
    if sector:
        return True
    if is_infrastructure(domain):
        return False
    return rank is not None and rank <= INDEX_MAX_RANK
