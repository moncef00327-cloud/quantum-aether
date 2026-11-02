p = "quantum_saas_app.py"
s = open(p).read()
s = s.replace("stripe.api_key = \\\"sk_test_YOUR_STRIPE_SECRET_KEY\\\"", "stripe.api_key = os.environ.get(\\\"STRIPE_SECRET_KEY\\\", \\\"sk_test_YOUR_STRIPE_SECRET_KEY\\\")")
s = s.replace("STRIPE_PRICE_ID = \\\"price_YOUR_PRODUCT_PRICE_ID\\\"", "STRIPE_PRICE_ID = os.environ.get(\\\"STRIPE_PRICE_ID\\\", \\\"price_YOUR_PRODUCT_PRICE_ID\\\")")
s = s.replace("mode=\\\"payment\\\",\n            success_url=", "mode=\\\"payment\\\",\n            payment_method_types=[\\\"card\\\", \\\"apple_pay\\\", \\\"google_pay\\\"],\n            success_url=")
open(p, "w").write(s)
print("DONE")
