# server.py — خادم MCP: يعرّض أدوات Quantum Aether لأي مساعد ذكاء اصطناعي (Claude، وغيره).
# التشغيل: python -m quantum_aether_mcp   (عبر stdio، كما تتوقعه عملاء MCP)
from mcp.server.fastmcp import FastMCP

from . import core

mcp = FastMCP("quantum-aether")


@mcp.tool()
def scan_tls(domain: str) -> str:
    """Check whether a website negotiates post-quantum TLS key exchange (X25519MLKEM768).
    Returns an honest summary: if the site is already protected it says so; if not, it states the
    "harvest now, decrypt later" risk and the available fix (full report) and monitoring options.

    Args:
        domain: the hostname to scan, e.g. "example.com".
    """
    return core.describe(core.scan(domain))


@mcp.tool()
def scan_tls_raw(domain: str) -> dict:
    """Same scan as scan_tls but returns the structured result (grade, key_exchange_group,
    post_quantum_key_exchange, certificate_key, scan_url, full_report_price, scan_id)."""
    return core.scan(domain)


@mcp.tool()
def buy_full_report(scan_id: str, consent_immediate_delivery: bool = False) -> dict:
    """Buy the full post-quantum readiness report ($49) for a prior scan. Returns a PayPal
    approval link (approve_url) and a status_url. Set consent_immediate_delivery to true ONLY after
    the buyer expressly agreed the report is delivered immediately and that they lose the right of
    withdrawal (Austrian FAGG). After the buyer approves in PayPal, the report link appears at status_url.

    Args:
        scan_id: the scan_id returned by scan_tls_raw.
        consent_immediate_delivery: must be true, and only with the buyer's express consent.
    """
    return core.prepare_report_purchase(scan_id, consent_immediate_delivery)


@mcp.tool()
def start_monitoring(email: str, plan: str = "starter", consent: bool = False) -> dict:
    """Start a daily monitoring subscription (plan "starter" = $29/mo up to 10 domains,
    "business" = $99/mo up to 100 domains). Returns the PayPal plan id to complete the subscription.
    Set consent to true ONLY after the customer agreed to email processing and immediate start.

    Args:
        email: the customer's email.
        plan: "starter" or "business".
        consent: must be true, with the customer's agreement.
    """
    return core.start_monitoring(email, plan, consent)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
