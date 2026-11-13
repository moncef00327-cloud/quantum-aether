# server.py — خادم MCP: يعرّض أدوات Quantum Aether لأي مساعد ذكاء اصطناعي (Claude، وغيره).
# التشغيل: python -m quantum_aether_mcp   (عبر stdio، كما تتوقعه عملاء MCP)
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import __version__, core

mcp = FastMCP(
    "quantum-aether",
    instructions=(
        "Quantum Aether measures whether a public website negotiates post-quantum TLS key exchange "
        "(X25519MLKEM768 / ML-KEM). Typical flow: scan_tls or scan_tls_raw -> optionally get_scan later with "
        "the scan_id. Paid actions (buy_full_report, start_monitoring) need the user's explicit consent; after "
        "a purchase, poll get_order_status with the order_id until it returns report_url."
    ),
)
# FastMCP 1.x reports the SDK version by default; report this package's version instead.
if hasattr(mcp, "_mcp_server"):
    mcp._mcp_server.version = __version__

_READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
_PAID = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)


@mcp.tool(annotations=_READ)
def scan_tls(domain: str) -> str:
    """Check whether a website negotiates post-quantum TLS key exchange (X25519MLKEM768).
    Returns an honest summary: if the site is already protected it says so; if not, it states the
    "harvest now, decrypt later" risk and the available fix (full report) and monitoring options.

    Args:
        domain: the hostname to scan, e.g. "example.com".
    """
    return core.describe(core.scan(domain))


@mcp.tool(annotations=_READ)
def scan_tls_raw(domain: str) -> dict:
    """Same scan as scan_tls but returns the structured result (scan_id, grade, key_exchange_group,
    post_quantum_key_exchange, observation_status, certificate_key, scan_url, full_report_price).
    Use the scan_id with get_scan or buy_full_report.

    Args:
        domain: the hostname to scan, e.g. "example.com".
    """
    return core.scan(domain)


@mcp.tool(annotations=_READ)
def get_scan(scan_id: str) -> dict:
    """Fetch the stored result of an earlier scan by its scan_id, without running a new scan.
    Returns the same structured fields as scan_tls_raw, or error "scan_not_found".

    Args:
        scan_id: the scan_id returned by scan_tls_raw.
    """
    return core.get_scan(scan_id)


@mcp.tool(annotations=_PAID)
def buy_full_report(scan_id: str, consent_immediate_delivery: bool = False) -> dict:
    """Buy the full post-quantum readiness report ($49) for a prior scan. Returns order_id, a PayPal
    approval link (approve_url) and a status_url. Set consent_immediate_delivery to true ONLY after
    the buyer expressly agreed the report is delivered immediately and that they lose the right of
    withdrawal (Austrian FAGG). After the buyer approves in PayPal, call get_order_status with the
    order_id to get the report_url.

    Args:
        scan_id: the scan_id returned by scan_tls_raw.
        consent_immediate_delivery: must be true, and only with the buyer's express consent.
    """
    return core.prepare_report_purchase(scan_id, consent_immediate_delivery)


@mcp.tool(annotations=_READ)
def get_order_status(order_id: str) -> dict:
    """Check a report order created by buy_full_report. Returns status (e.g. CREATED, COMPLETED),
    amount and currency; once the payment is COMPLETED it also returns report_url.

    Args:
        order_id: the order_id returned by buy_full_report.
    """
    return core.order_status(order_id)


@mcp.tool(annotations=_PAID)
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
