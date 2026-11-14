"""Resolve sourced DACH hosting candidates and verify their observed network."""
import csv
import ipaddress
import json
import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from asn import AsnLookup, ensure_database

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "dach_hosting_sample.csv"
DB_PATH = Path("/tmp/quantum-aether-ip2asn-v4.tsv.gz")
CDN_MARKERS = (
    "cloudflare", "akamai", "fastly", "amazon cloudfront", "google cloud",
    "edgecast", "bunny", "stackpath", "imperva", "incapsula", "azure",
    "microsoft azure", "vercel", "netlify", "keycdn", "cdn77", "gcore",
)
PROVIDER_MARKERS = {
    "ALL-INKL.COM": ("all-inkl", "neue medien munnich", "neue medien münnich"),
    "STRATO": ("strato",),
    "DomainFactory": ("domainfactory", "hosteurope"),
    "World4You": ("world4you", "world4you internet services"),
}


def resolve(host):
    ips = sorted({x[4][0] for x in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
    cname = subprocess.run(["dig", "+short", "CNAME", host], capture_output=True, text=True, timeout=10).stdout
    return ips, [x.rstrip(".").lower() for x in cname.splitlines() if x.strip()]


def main():
    ensure_database(str(DB_PATH))
    lookup = AsnLookup(str(DB_PATH))
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fields = list(rows[0])
    for row in rows:
        try:
            ips, cnames = resolve(row["host"])
            networks = []
            for ip in ips:
                try:
                    asn, name = lookup.lookup(ip)
                except (ValueError, TypeError):
                    asn, name = None, None
                networks.append({"ip": ip, "asn": asn, "name": name})
            row["dns_ips"] = json.dumps(ips, separators=(",", ":"))
            row["asn"] = json.dumps(sorted({x["asn"] for x in networks if x["asn"]}), separators=(",", ":"))
            row["asn_name"] = json.dumps(sorted({x["name"] for x in networks if x["name"]}), ensure_ascii=False)
            row["cdn_status"] = "cdn_excluded" if any(any(m in c for m in CDN_MARKERS) for c in cnames) or any(any(m in (x["name"] or "").lower() for m in CDN_MARKERS) for x in networks) else "no_known_cdn_detected"
            provider = row["provider"]
            markers = PROVIDER_MARKERS.get(provider, ())
            names = " ".join(x["name"] or "" for x in networks).lower()
            asns = {x["asn"] for x in networks if x["asn"] is not None}
            attributed = bool(markers) and any(m in names for m in markers)
            if row["cdn_status"] == "cdn_excluded":
                row["verification_status"] = "excluded_cdn"
            elif not ips or not asns:
                row["verification_status"] = "unresolved_asn"
            elif attributed:
                row["verification_status"] = "asn_matches_provider_candidate"
            else:
                row["verification_status"] = "asn_does_not_match_provider"
        except Exception as exc:
            row["verification_status"] = "dns_error:" + type(exc).__name__
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
