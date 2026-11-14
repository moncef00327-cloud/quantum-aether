# tools/paypal_setup_plans.py
# ينشئ منتج «المراقبة» وخطتي الاشتراك الشهري في PayPal مرة واحدة، ويطبع معرّفات الخطط لملف البيئة.
# Creates the monitoring product and the two monthly plans once and prints the plan ids for the env file.
# التشغيل: set -a; . /etc/quantum_saas.env; set +a; python tools/paypal_setup_plans.py [--currency EUR]
# --currency EUR (default) prints PAYPAL_PLAN_*_EUR; --currency USD the legacy PAYPAL_PLAN_* names.
# Existing plans are never changed or deactivated; existing subscribers keep their plan.
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import monitor  # noqa: E402
from paypal_client import PayPalClient  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--currency", default="EUR", choices=["EUR", "USD"])
    args = parser.parse_args()
    client = PayPalClient(os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_CLIENT_SECRET"], os.environ.get("PAYPAL_ENV", "live"))
    suffix = " (EUR)" if args.currency == "EUR" else ""
    product = client.create_product(f"Quantum Aether Monitoring{suffix}",
                                    "Daily post-quantum TLS readiness monitoring with email alerts",
                                    "https://ather-quantum.com/monitoring")
    print(f"# product {product['id']}")
    for name, plan in monitor.PLANS.items():
        created = client.create_plan(product["id"], f"Quantum Aether {plan['name']} (monthly){suffix}",
                                     f"Daily monitoring of up to {plan['domains']} domains with email alerts",
                                     plan["price"], args.currency)
        key = plan["env_eur"] if args.currency == "EUR" else plan["env"]
        print(f"{key}={created['id']}   # {created['status']} {plan['price']} {args.currency}/month")


if __name__ == "__main__":
    main()
