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


_family_cache = {'mtime': None, 'hosts': frozenset()}


def family_dns_blocked_hosts():
    """mtime-aware so the weekly refresh (tools/family_dns_scan.py) applies without an app restart."""
    try:
        mtime = FAMILY_DNS_FILE.stat().st_mtime
    except OSError:
        return frozenset()
    if _family_cache['mtime'] != mtime:
        try:
            data = json.loads(FAMILY_DNS_FILE.read_text(encoding='utf-8'))
            _family_cache.update(mtime=mtime, hosts=frozenset(h.lower() for h in data.get('hosts', [])))
        except (ValueError, OSError):
            return _family_cache['hosts']
    return _family_cache['hosts']


def family_dns_blocked(domain):
    host = _normal(domain)
    return host is not None and host in family_dns_blocked_hosts()


def is_excluded(domain):
    host = _normal(domain)
    return host is not None and host in reviewed_hosts()


def is_infrastructure(domain):
    host = _normal(domain)
    return host is not None and host in infrastructure_hosts()


# 2026-11-20: was 1000 and "every watch-list sector". ~6,700 thin per-domain URLs on a days-old domain made Google
# rate the whole site low (crawl fell 444 -> 6/day; Google landings were unrelated sites such as gambling or news).
# Keep only reference brands plus the sectors that can buy (banks, insurers, finance, DACH companies).
INDEX_MAX_RANK = 100
PRIORITY_SECTORS = frozenset({
    "banks-mena", "banks-europe", "banks-dach", "banks-americas-apac",
    "health-insurance-dach", "global-insurance-healthcare",
    "finance-worldwide", "payments-fintech", "companies-dach",
})


def is_indexable(domain, rank=None, sector=None):
    """Should /site/<domain> appear in search results? Reviewed exclusions never; buyer-sector domains always;
    else the top INDEX_MAX_RANK sites, minus infrastructure endpoints nobody looks up."""
    if is_excluded(domain) or family_dns_blocked(domain):
        return False
    if sector in PRIORITY_SECTORS:
        return True
    if is_infrastructure(domain):
        return False
    return rank is not None and rank <= INDEX_MAX_RANK
