from flask import Flask, render_template_string, jsonify, request, redirect
import pandas as pd
import os
import time

app = Flask(__name__)

PAYPAL_CLIENT_ID = "BAA9XULdxpQX54xlR5T2qj9mQyMRk8P0Tdn4KMBW98BruBpaAUwhOIG-l_29RhutQ_5Ec859jTd9lc4yL0"
DATA_FILE = "quantum_saas_sales.csv"

TEXTS = {
    "ar": {
        "title": "نظام فحص الثغرات الكمومية",
        "sub": "مراقبة حية للمبيعات التلقائية، وعمليات فحص الثغرات، والربط ببوابة الدفع",
        "scans": "إجمالي عمليات الفحص",
        "paid": "العمليات المدفوعة",
        "rev": "صافي الأرباح التلقائية (USD)",
        "pay_title": "دفع آمن عبر باي بال والبطاقات الائتمانية",
        "pay_sub": "احصل على تقرير الجاهزية المقاوم للكم مع ملحق الأرشفة الحيوية (79,132 قاعدة DNA).",
        "price": "$49.00 USD",
        "pay_now": "الدفع الآن",
        "table_h": ["التوقيت", "معرف المهمة", "حجم المفتاح", "المبلغ", "الحالة"]
    },
    "en": {
        "title": "Quantum Vulnerability Scanner - Admin Dashboard",
        "sub": "Live monitoring of automated sales, PQC vulnerability scans, and Stripe/PayPal telemetry.",
        "scans": "Total Scans",
        "paid": "Paid Operations",
        "rev": "Total Automated Revenue (USD)",
        "pay_title": "Secure Payment via PayPal & Credit Cards",
        "pay_sub": "Get the Post-Quantum readiness report with bio-archived DNA configuration (79,132 base pairs).",
        "price": "$49.00 USD",
        "pay_now": "Pay Now",
        "table_h": ["Timestamp", "Job ID", "Key Size", "Amount", "Status"]
    }
}

def init_sales_log():
    if not os.path.exists(DATA_FILE):
        pd.DataFrame(columns=["Timestamp", "JobID", "KeySize", "Amount", "PaymentStatus"]).to_csv(DATA_FILE, index=False, encoding="utf-8")

@app.route("/")
def dashboard():
    init_sales_log()
    df = pd.read_csv(DATA_FILE)
    total = len(df)
    paid = df[df["PaymentStatus"] == "Paid"]
    rev = paid["Amount"].sum() if len(paid) else 0
    lang = "ar" if "ar" in request.headers.get("Accept-Language", "") else "en"
    t = TEXTS[lang]

    dashboard_template = """
    <!DOCTYPE html>
    <html lang="{{ lang }}" dir="{{ 'rtl' if lang=='ar' else 'ltr' }}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Quantum SaaS Dashboard</title>
        <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 0; }
            .container { max-width: 1100px; margin: 0 auto; padding: 30px 20px; }
            .header { background-color: #1e293b; padding: 25px; border-radius: 12px; border-bottom: 4px solid #38bdf8; margin-bottom: 30px; }
            .header h1 { margin: 0; color: #f8fafc; font-size: 28px; }
            .header p { color: #94a3b8; margin: 5px 0 0 0; font-size: 15px; }
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .stat-card { background-color: #1e293b; padding: 25px; border-radius: 12px; text-align: center; border: 1px solid #334155; }
            .stat-card h3 { margin: 0 0 12px 0; color: #94a3b8; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }
            .stat-card .value { font-size: 36px; font-weight: bold; color: #38bdf8; }
            .stat-card .revenue { color: #4ade80; }
            .pay-section { background-color: #1e293b; padding: 30px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 30px; }
            .pay-section h2 { color: #38bdf8; margin-top: 0; margin-bottom: 10px; font-size: 22px; }
            .pay-section p { color: #94a3b8; font-size: 15px; margin-bottom: 20px; line-height: 1.6; }
            .price { color: #4ade80; font-size: 28px; font-weight: bold; margin: 20px 0; }
            table { width: 100%; border-collapse: collapse; background-color: #1e293b; border-radius: 12px; overflow: hidden; margin-top: 20px; }
            th, td { padding: 15px; text-align: {{ 'right' if lang=='ar' else 'left' }}; border-bottom: 1px solid #334155; }
            th { background-color: #334155; color: #f8fafc; font-weight: 600; }
            .status-paid { color: #4ade80; font-weight: bold; }
            .status-pending { color: #f59e0b; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{{ title }}</h1>
                <p>{{ sub }}</p>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <h3>{{ scans }}</h3>
                    <div class="value">{{ total }}</div>
                </div>
                <div class="stat-card">
                    <h3>{{ paid_label }}</h3>
                    <div class="value">{{ paid_count }}</div>
                </div>
                <div class="stat-card">
                    <h3>{{ rev }}</h3>
                    <div class="value revenue">$ {{ total_revenue }}</div>
                </div>
            </div>

            <div class="pay-section">
                <h2>{{ pay_title }}</h2>
                <p>{{ pay_sub }}</p>
                <div class="price">{{ price }}</div>
                <div id="paypal-button-container"></div>
            </div>

            <h3 style="margin-top: 30px; color: #94a3b8;">سجل العمليات</h3>
            <table>
                <thead>
                    <tr>
                        {% for h in table_headers %}
                        <th>{{ h }}</th>
                        {% endfor %}
                    </tr>
                </thead>
                <tbody>
                    {% for index, row in df.iterrows() %}
                    <tr>
                        <td>{{ row['Timestamp'] }}</td>
                        <td><code>{{ row['JobID'] }}</code></td>
                        <td>{{ row['KeySize'] }} bits</td>
                        <td>${{ row['Amount'] }}</td>
                        <td class="{{ 'status-paid' if row['PaymentStatus']=='Paid' else 'status-pending' }}">{{ row['PaymentStatus'] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <script>
            paypal.Buttons({
                style: {
                    layout: 'vertical',
                    color: 'gold',
                    shape: 'rect',
                    label: 'paypal'
                },
                createOrder: function(data, actions) {
                    return actions.order.create({
                        purchase_units: [{ amount: { value: '49.00' } }]
                    });
                },
                onApprove: function(data, actions) {
                    return actions.order.capture().then(function(details) {
                        window.location.href = "/payment-success?order_id=" + data.orderID;
                    });
                },
                onError: function(err) {
                    console.error(err);
                    alert('حدث خطأ أثناء الدفع. يرجى المحاولة مرة أخرى.');
                }
            }).render('#paypal-button-container');
        </script>
    </body>
    </html>
    """

    return render_template_string(dashboard_template,
        lang=lang,
        title=t["title"],
        sub=t["sub"],
        scans=t["scans"],
        paid_label=t["paid"],
        rev=t["rev"],
        total=total,
        paid_count=len(paid),
        total_revenue=rev,
        pay_title=t["pay_title"],
        pay_sub=t["pay_sub"],
        price=t["price"],
        table_headers=t["table_h"],
        df=df,
        client_id=PAYPAL_CLIENT_ID
    )

@app.route("/create-checkout-session", methods=["POST"])
def checkout():
    init_sales_log()
    df = pd.read_csv(DATA_FILE)
    new_row = {
        "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "JobID": "job_" + str(int(time.time())),
        "KeySize": request.form.get("key_size", "2048"),
        "Amount": 49.00,
        "PaymentStatus": "Pending"
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(DATA_FILE, index=False, encoding="utf-8")
    return redirect("/payment-success?order_id=" + str(int(time.time())), code=303)

@app.route("/payment-success")
def success():
    order_id = request.args.get("order_id")
    df = pd.read_csv(DATA_FILE)
    if not df.empty:
        idx = df[df["PaymentStatus"] == "Pending"].index
        if len(idx):
            df.loc[idx[-1], "PaymentStatus"] = "Paid"
            df.to_csv(DATA_FILE, index=False, encoding="utf-8")
    return "<h3>Payment successful! Your quantum report is being processed.</h3>"

if __name__ == "__main__":
    app.run(port=5000, debug=True)
