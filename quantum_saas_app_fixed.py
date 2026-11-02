from flask import Flask, jsonify, request, redirect
import stripe, pandas as pd, os, time
app = Flask(__name__)
stripe.api_key = "sk_test_YOUR_STRIPE_SECRET_KEY"
STRIPE_PRICE_ID = "price_YOUR_PRODUCT_PRICE_ID"
DATA_FILE = "quantum_saas_sales.csv"
def init_sales_log():
    if not os.path.exists(DATA_FILE):
        pd.DataFrame(columns=["Timestamp","JobID","KeySize","Amount","PaymentStatus"]).to_csv(DATA_FILE, index=False))
@app.route("/")
def dashboard():
    init_sales_log()
    df = pd.read_csv(DATA_FILE)
    total = len(df)
    paid = df[df["PaymentStatus"]=="Paid"]
    rev = paid["Amount"].sum() if len(paid) else 0
    return "<h1>Quantum SaaS Dashboard</h1><p>Scans: %d</p><p>Paid: %d</p><p>Revenue: $%s</p>" % (total, len(paid), rev)
@app.route("/create-checkout-session", methods=["POST"])
def checkout():
    try:
        cs = stripe.checkout.Session.create(line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}], mode="payment", success_url=request.host_url+"payment-success?session_id={CHECKOUT_SESSION_ID}", cancel_url=request.host_url+"payment-cancel")
        init_sales_log()
        df = pd.read_csv(DATA_FILE)
        df = pd.concat([df, pd.DataFrame([{"Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "JobID": "job_"+str(int(time.time())), "KeySize": request.form.get("key_size","2048"), "Amount": 49.0, "PaymentStatus": "Pending"}])], ignore_index=True)
        df.to_csv(DATA_FILE, index=False)
        return redirect(cs.url, code=303)
    except Exception as e:
        return jsonify(error=str(e)), 500
@app.route("/payment-success")
def success():
    sid = request.args.get("session_id")
    try:
        s = stripe.checkout.Session.retrieve(sid)
        if s.payment_status == "paid":
            df = pd.read_csv(DATA_FILE)
            idx = df[df["PaymentStatus"]=="Pending"].index
            if len(idx):
                df.loc[idx[-1], "PaymentStatus"] = "Paid"
                df.to_csv(DATA_FILE, index=False)
    except Exception:
        pass
    return "<h3>Payment successful.</h3>"
if __name__ == "__main__":
    app.run(port=5000, debug=True)
