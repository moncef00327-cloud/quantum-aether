p = "quantum_saas_app.py"
s = open(p).read()
old = """@app.route(\"/\")\ndef dashboard():\n    init_sales_log()\n    df = pd.read_csv(DATA_FILE)\n    total = len(df)\n    paid = df[df[\"PaymentStatus\"] == \"Paid\"]\n    rev = paid[\"Amount\"].sum() if len(paid) else 0\n    return f\"<h1>Quantum SaaS Dashboard</h1><p>Scans: {total}</p><p>Paid: {len(paid)}</p><p>Revenue: ${rev}</p>\"""
new = """TEXTS = {\n    \"ar\": {\"title\": \"لوحة التحكم الإدارية\", \"scans\": \"إجمالي الفحوصات\", \"paid\": \"المدفوعة\", \"rev\": \"الأرباح\"},\n    \"en\": {\"title\": \"Quantum SaaS Dashboard\", \"scans\": \"Total Scans\", \"paid\": \"Paid\", \"rev\": \"Revenue\"},\n}\n@app.route(\"/\")\ndef dashboard():\n    init_sales_log()\n    df = pd.read_csv(DATA_FILE)\n    total = len(df)\n    paid = df[df[\"PaymentStatus\"] == \"Paid\"]\n    rev = paid[\"Amount\"].sum() if len(paid) else 0\n    lang = \"ar\" if \"ar\" in request.headers.get(\"Accept-Language\", \"\") else \"en\"\n    t = TEXTS[lang]\n    return f\"<h1>{t[\"title\"]}</h1><p>{t[\"scans\"]}: {total}</p><p>{t[\"paid\"]}: {len(paid)}</p><p>{t[\"rev\"]}: ${rev}</p>\"""
assert old in s, "old block not found"
s = s.replace(old, new)
open(p, "w").write(s)
print("DONE")
