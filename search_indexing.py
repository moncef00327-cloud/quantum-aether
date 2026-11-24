"""Evidence-reviewed, exact-host indexing exceptions; never a request/content filter.

Indexable /site/<domain> pages are an allow-list of notable institutions, plus
domains with real human traffic or a high public rank (household-name lookups).
Everyone else still has a live /site/ page (noindex, follow) but is kept out of
the sitemap. Googlebot is not Disallowed in robots.txt.
"""
from functools import lru_cache
import csv
import json
from pathlib import Path
import re

CLASSIFICATIONS = frozenset({'confirmed_pornographic', 'confirmed_gambling'})
POLICY_FILE = Path(__file__).resolve().parent / 'data' / 'indexing_exclusions.json'
INFRASTRUCTURE_FILE = Path(__file__).resolve().parent / 'data' / 'indexing_infrastructure.json'
# Automated backstop: hosts that Cloudflare family DNS (1.1.1.3) resolves to 0.0.0.0
# (adult/malware). Populated by tools/family_dns_scan.py; never indexed, so new
# adult/malicious domains are de-indexed without waiting for manual review.
FAMILY_DNS_FILE = Path(__file__).resolve().parent / 'data' / 'family_dns_blocked.json'
WATCHLIST_FILE = Path(__file__).resolve().parent / 'data' / 'adoption_watchlists.json'
DACH_STUDY_FILE = Path(__file__).resolve().parent / 'data' / 'dach_hosting_results.json'
BANK_REPORTS_DIR = Path(__file__).resolve().parent / 'data' / 'bank_reports'
# Optional PQ-TLS Index org list (column "domain" or "host"). Absent until the
# index ships; drop the CSV here or at data/pq_index_orgs.csv.
ORGS_CSV_CANDIDATES = (
    Path(__file__).resolve().parent / 'data' / 'pq_index_orgs.csv',
    Path(__file__).resolve().parent / 'data' / 'orgs.csv',
)

# Curated, 100%-clean institutional & commercial watchlists (DACH + global/MENA
# banks, fintech/payments, cloud/security, enterprise SaaS, PQC vendors, crypto
# exchanges, telecom, secure comms). Every host still passes excluded, family-DNS,
# sensitive-keyword, and infrastructure checks; Tranco random ranks stay capped at
# REFERENCE_MAX_RANK = 50 so zero adult/gambling/junk domains ever enter the index.
NOTABLE_WATCHLIST_SECTORS = frozenset({
    "government-dach", "banks-dach", "companies-dach", "health-insurance-dach",
    "payments-fintech", "crypto-exchanges", "cloud-security", "enterprise-saas-b2b",
    "pqc-security-vendors", "secure-communication", "banks-mena", "banks-europe", "telecom",
})

# Household-name lookups such as "does amazon.com use post-quantum TLS?".
# 2026-11-21: was INDEX_MAX_RANK = 100 plus every buyer-sector watchlist (~736
# domains), which still left Google crawling thin /site/ templates.
# 50, not 25: Tranco's top 25 is heavy on CDNs/trackers, while Amazon (30),
# GitHub (34) and Wikipedia (38) sit just outside that cut.
REFERENCE_MAX_RANK = 50

# Kept as a deprecated alias so older tests/comments that import the name do not
# explode; it is no longer used as a blanket sector pass.
INDEX_MAX_RANK = REFERENCE_MAX_RANK
PRIORITY_SECTORS = NOTABLE_WATCHLIST_SECTORS


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


def bare_host(domain):
    """Lowercase host without a leading www. Used to match watchlists to /site/ slugs."""
    host = _normal(domain)
    if not host:
        return None
    return host[4:] if host.startswith("www.") else host


def host_aliases(domain):
    host = _normal(domain)
    if not host:
        return frozenset()
    bare = bare_host(host)
    return frozenset({host, bare, "www." + bare})


# Reviewed hosts that a keyword would catch but are not adult/gambling.
_KEYWORD_ALLOW_HOSTS = frozenset({
    "cosmopolitan.com", "sofascore.com", "flashscore.com.br", "flashscore.fr", "livescore.in",
    "playtika.com", "match.com", "jeuxvideo.com", "nflxvideo.net", "xxxlutz.de", "xxxlutz.at",
})

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


# Keyword backstop (2026-11-23): Search Console showed /site/<adult host> pages ranking for
# porn queries. Reviewed exclusions (410) stay exact-host only; a keyword match never 410s and
# never drops a host from statistics. It only keeps the page out of the index (noindex, nofollow),
# out of the sitemap and out of internal /site/ links, so a false positive costs nothing visible.
_SENSITIVE_KEYWORDS = re.compile(
    r"porn|xxx|xvideo|xhamster|xnxx|hentai|redtube|youporn|brazzers|onlyfans|chaturbate|stripchat"
    r"|camgirl|camsoda|bongacams|livejasmin|nsfw|milf|pussy|w4nk|wank|fap|nude|naked|boob|tits|bokep"
    r"|javhd|javxxx|jav\d|sex|kamaveri|kahani|desi.?(?:sex|mms)|erotic|fetish|bdsm|escort"
    r"|casino|1xbet|bet365|betwin|sportsbet|gambl|poker|roulette|blackjack|slotgacor|judi|togel")
# Substrings that contain a keyword but are not adult/gambling (place names, words, brands).
_KEYWORD_FALSE_POSITIVES = (
    "essex", "sussex", "wessex", "middlesex", "sexton", "sextant", "unisex", "sextet",
    "nflxvideo", "jeuxvideo", "xxxlutz", "naked-wines", "nakedwines", "fapesp", "faperj", "fapemig",
    "fapeam", "fapesc", "fapergs", "fapemat", "fapeg", "fapespa", "fapepi", "fapitec",
    "dnsexit", "saasex", "gambleaware", "gamblingcommission", "gamblingtherapy", "gamcare",
)


def _keyword_label(domain):
    host = _normal(domain)
    if not host:
        return ''
    label = host
    for fp in _KEYWORD_FALSE_POSITIVES:
        label = label.replace(fp, ' ')
    return label


def keyword_suspect(domain):
    """Host name looks adult or gambling. Noindex-only signal: never a 410, never a stats filter."""
    host = _normal(domain)
    if not host or host in _KEYWORD_ALLOW_HOSTS:
        return False
    return bool(_SENSITIVE_KEYWORDS.search(_keyword_label(host)))


def is_sensitive(domain):
    """Adult, gambling or family-DNS-blocked host: never indexed, never followed, never linked."""
    return is_excluded(domain) or family_dns_blocked(domain) or keyword_suspect(domain)


def is_infrastructure(domain):
    host = _normal(domain)
    return host is not None and host in infrastructure_hosts()


def _read_orgs_csv(path):
    hosts = set()
    try:
        with path.open(encoding='utf-8', newline='') as fh:
            sample = fh.read(2048)
            fh.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t") if sample.strip() else csv.excel
            reader = csv.DictReader(fh, dialect=dialect)
            if not reader.fieldnames:
                return hosts
            fields = [f.lower().strip() for f in reader.fieldnames]
            col = None
            for candidate in ('domain', 'host', 'hostname', 'site', 'website'):
                if candidate in fields:
                    col = reader.fieldnames[fields.index(candidate)]
                    break
            if col is None:
                col = reader.fieldnames[0]
            for row in reader:
                value = (row.get(col) or '').strip()
                if not value or value.startswith('#'):
                    continue
                # Allow a URL in the column.
                if '://' in value:
                    value = value.split('://', 1)[1].split('/', 1)[0]
                host = bare_host(value)
                if host:
                    hosts.add(host)
    except (OSError, csv.Error, UnicodeError):
        return set()
    return hosts


def _load_notable_hosts():
    """Union of DACH study hosts, notable watchlists, bank-report rows, and optional orgs.csv."""
    hosts = set()
    if DACH_STUDY_FILE.exists():
        try:
            data = json.loads(DACH_STUDY_FILE.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            data = {}
        for provider in data.get('providers') or []:
            website = bare_host(provider.get('website') or provider.get('domain') or '')
            if website:
                hosts.add(website)
            for site in provider.get('sites') or []:
                if isinstance(site, str):
                    host = bare_host(site)
                elif isinstance(site, dict):
                    host = bare_host(site.get('domain') or site.get('host') or '')
                else:
                    host = None
                if host:
                    hosts.add(host)
    if WATCHLIST_FILE.exists():
        try:
            data = json.loads(WATCHLIST_FILE.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            data = {}
        for key, sector in (data.get('sectors') or {}).items():
            if key not in NOTABLE_WATCHLIST_SECTORS:
                continue
            for domain in (sector.get('domains') if isinstance(sector, dict) else sector) or []:
                host = bare_host(domain if isinstance(domain, str) else '')
                if host:
                    hosts.add(host)
    if BANK_REPORTS_DIR.is_dir():
        for path in BANK_REPORTS_DIR.glob('*.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (ValueError, OSError):
                continue
            for row in data.get('rows') or []:
                host = bare_host((row or {}).get('domain') or '')
                if host:
                    hosts.add(host)
    for path in ORGS_CSV_CANDIDATES:
        if path.exists():
            hosts.update(_read_orgs_csv(path))
    return frozenset(hosts)


_notable_cache = {'mtime': None, 'hosts': frozenset()}


def _sources_mtime():
    total = 0
    for path in (DACH_STUDY_FILE, WATCHLIST_FILE) + ORGS_CSV_CANDIDATES:
        try:
            total += path.stat().st_mtime
        except OSError:
            continue
    if BANK_REPORTS_DIR.is_dir():
        for path in BANK_REPORTS_DIR.glob('*.json'):
            try:
                total += path.stat().st_mtime
            except OSError:
                continue
    return total


def notable_institution_hosts():
    mtime = _sources_mtime()
    if _notable_cache['mtime'] != mtime:
        _notable_cache.update(mtime=mtime, hosts=_load_notable_hosts())
    return _notable_cache['hosts']


# Runtime allow-list from analytics (human /site/ visitors) and tests.
_human_traffic_hosts = frozenset()
_extra_allow_hosts = frozenset()


def set_human_traffic_hosts(hosts):
    """Bare hostnames that received real human (non-bot, non-test) /site/ visits."""
    global _human_traffic_hosts
    _human_traffic_hosts = frozenset(filter(None, (bare_host(h) for h in (hosts or ()))))


def set_extra_allow_hosts(hosts):
    """Test hook: extra bare hosts treated as allow-listed notable institutions."""
    global _extra_allow_hosts
    _extra_allow_hosts = frozenset(filter(None, (bare_host(h) for h in (hosts or ()))))


def reset_runtime_state():
    set_human_traffic_hosts(())
    set_extra_allow_hosts(())
    _notable_cache.update(mtime=None, hosts=frozenset())
    notable_institution_hosts.cache_clear() if hasattr(notable_institution_hosts, 'cache_clear') else None


def human_traffic_hosts():
    return _human_traffic_hosts


def is_notable_institution(domain):
    aliases = host_aliases(domain)
    if not aliases:
        return False
    allowed = notable_institution_hosts() | _extra_allow_hosts
    return any(bare_host(a) in allowed for a in aliases)


def is_human_traffic_host(domain):
    aliases = host_aliases(domain)
    return any(bare_host(a) in _human_traffic_hosts for a in aliases)


def is_indexable(domain, rank=None, sector=None, has_human_traffic=None):
    """Should /site/<domain> appear in search results?

    Denied: reviewed exclusions, family-DNS blocked hosts, adult/gambling host-name keywords,
    infrastructure endpoints.
    Allowed: notable institutions (DACH study, DACH watchlists, bank reports, orgs.csv),
    domains with real human /site/ traffic, or a Tranco rank at or below
    REFERENCE_MAX_RANK. A watchlist sector alone is no longer enough.
    """
    if is_excluded(domain) or family_dns_blocked(domain) or keyword_suspect(domain):
        return False
    if is_infrastructure(domain):
        return False
    if is_notable_institution(domain):
        return True
    if has_human_traffic or is_human_traffic_host(domain):
        return True
    if rank is not None and rank <= REFERENCE_MAX_RANK:
        return True
    # Sector is only a hint now: a notable DACH sector still counts if the
    # watchlist file could not be read, so a typo in the file does not hide
    # a Bundesbank page that the tracker already tagged.
    if sector in NOTABLE_WATCHLIST_SECTORS and WATCHLIST_FILE.exists():
        # Prefer the explicit host list; do not re-open the blanket.
        return False
    if sector in NOTABLE_WATCHLIST_SECTORS:
        return True
    return False
