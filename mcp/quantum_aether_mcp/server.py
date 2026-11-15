# server.py — خادم MCP: يعرّض أدوات Quantum Aether لأي مساعد ذكاء اصطناعي (Claude، وغيره).
# التشغيل: python -m quantum_aether_mcp   (عبر stdio، كما تتوقعه عملاء MCP)
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import core

mcp = FastMCP("quantum-aether")

# Client hints only; consent and server-side validation remain authoritative.
_SCAN = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)
_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
_CHECKOUT = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)


@mcp.tool(annotations=_SCAN)
def scan_tls(domain: str) -> str:
    """Check whether a website negotiates post-quantum TLS key exchange (X25519MLKEM768).
    Returns an honest summary: if the site is already protected it says so; if not, it states the
    "harvest now, decrypt later" risk and the available fix (full report) and monitoring options.
    Starts an external scan and stores its result, which is publicly accessible.

    Args:
        domain: the hostname to scan, e.g. "example.com".
    """
    return core.describe(core.scan(domain))


@mcp.tool(annotations=_SCAN)
def scan_tls_raw(domain: str) -> dict:
    """Run the same public scan as scan_tls and return its structured result.

    The scan is stored as a publicly accessible result; this is a measurement, not an
    application security assessment.
    """
    return core.scan(domain)


@mcp.tool(annotations=_READ_ONLY)
def exposure_window(domain: str) -> dict:
    """Quantum Exposure Registry (read-only, never scans): from when the domain was first observed,
    the week it first negotiated post-quantum key exchange (first_pq_week), the observed classical
    exposure window (harvest-now-decrypt-later; a lower bound), regressions, the weekly timeline with
    row fingerprints and OpenTimestamps anchor proofs, and same-network peers.
    External observation of the public HTTPS endpoint, not a compliance certification.

    Args:
        domain: the hostname, e.g. "example.com".
    """
    return core.exposure_window(domain)


@mcp.tool(annotations=_CHECKOUT)
def buy_full_report(scan_id: str, consent_immediate_delivery: bool = False) -> dict:
    """Create a PayPal checkout order for the full report for a prior scan.

    Returns an approval link and status URL; this call does not itself approve or capture payment.
    Set consent_immediate_delivery to true only after the buyer expressly agrees to immediate
    delivery and the applicable withdrawal-right terms (Austrian FAGG).

    Args:
        scan_id: the scan_id returned by scan_tls_raw.
        consent_immediate_delivery: must be true, and only with the buyer's express consent.
    """
    return core.prepare_report_purchase(scan_id, consent_immediate_delivery)


@mcp.tool(annotations=_CHECKOUT)
def start_monitoring(email: str, plan: str = "starter", consent: bool = False) -> dict:
    """Create a daily-monitoring signup using the supplied email and plan.

    Sends the email to the Quantum Aether service and returns the next subscription step.
    Set consent to true only after the customer explicitly agrees to email processing and
    immediate service start.

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
