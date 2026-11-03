# tools/paypal_setup_plans.py
# ينشئ منتج «المراقبة» وخطتي الاشتراك الشهري في PayPal مرة واحدة، ويطبع معرّفات الخطط لملف البيئة.
# التشغيل: set -a; . /etc/quantum_saas.env; set +a; python tools/paypal_setup_plans.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import monitor  # noqa: E402
from paypal_client import PayPalClient  # noqa: E402


def main():
    client = PayPalClient(os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_CLIENT_SECRET"], os.environ.get("PAYPAL_ENV", "live"))
    product = client.create_product("Quantum Aether Monitoring",
                                    "Daily post-quantum TLS readiness monitoring with email alerts",
                                    "https://ather-quatum.cloud/monitoring")
    print(f"# product {product['id']}")
    for name, plan in monitor.PLANS.items():
        created = client.create_plan(product["id"], f"Quantum Aether {plan['name']} (monthly)",
                                     f"Daily monitoring of up to {plan['domains']} domains with email alerts",
                                     plan["price"], "USD")
        print(f"{plan['env']}={created['id']}   # {created['status']} ${plan['price']}/month")


if __name__ == "__main__":
    main()
