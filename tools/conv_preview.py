"""Loopback-only preview for screenshots of the trial-first pages (fake mailer/PayPal/probes, temp data). Never deploys."""
import copy, os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import quantum_saas_app, sales_db, monitor_db
from tests.test_app import RESULT
from tests.test_monitor import PLAN_IDS, FakeMailer, FakePayPal
from tests.test_eur_checkout import EUR_IDS

def scanner(raw):
    r = copy.deepcopy(dict(RESULT, domain=raw))
    if raw.startswith("secure"):
        r["grade"] = "A"
        r["key_exchange"] = dict(RESULT["key_exchange"], pq=True, group="X25519MLKEM768")
    return r

def probe(host):
    p = host.split(".")[0]
    if p in ("auth", "login"):
        return None
    pq = p in ("www", "api")
    return {"host": host, "status": "pq" if pq else "not_pq", "group": "X25519MLKEM768" if pq else "x25519", "version": "TLSv1.3"}

data_dir = tempfile.mkdtemp()
mailer = FakeMailer()
app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": data_dir, "PAYPAL_CLIENT_ID": "sb-preview",
                                   "OWNER_EMAIL": "owner@example.com", **PLAN_IDS, **EUR_IDS},
                                  scanner=scanner, paypal=FakePayPal(), mailer=mailer, discovery_probe=probe)
app.extensions["server_header"] = lambda ip, host: "cloudflare" if host.startswith("secure") else "nginx/1.24.0 (Ubuntu)"
c = app.test_client()
sid = c.post("/api/scan", json={"domain": "secure-shop.example"}).get_json()["scan_id"]
sid_b = c.post("/api/scan", json={"domain": "acme-gmbh.example"}).get_json()["scan_id"]
c.post("/monitoring/trial?lang=ar", data={"email": "it@acme-gmbh.example", "consent": "1"})
mail = next(m for m in mailer.sent if m[0] == "it@acme-gmbh.example")
token = mail[2].split("/monitor/")[1].split("?")[0].split()[0]
# sample history: 6 earlier days at grade A (post-quantum), then the regression to B, plus a second domain
conn = sales_db.connect(os.path.join(data_dir, "quantum_saas.db"))
acc = monitor_db.get_account_by_token(conn, token)
monitor_db.add_domain(conn, acc["id"], "api.acme-gmbh.example")
for d in monitor_db.list_domains(conn, acc["id"]):
    a = scanner("secure"); a["domain"] = d["domain"]; a["certificate"] = dict(a["certificate"], days_left=67)
    b = scanner(d["domain"]); b["certificate"] = dict(b["certificate"], days_left=21 if d["domain"].startswith("api") else 60)
    for i in range(6):
        monitor_db.save_check(conn, d["id"], a)
        conn.execute("UPDATE monitor_checks SET checked_at = ? WHERE id = (SELECT MAX(id) FROM monitor_checks)",
                     (f"2026-11-{8 + i:02d}T05:00:00Z",)); conn.commit()
    monitor_db.save_check(conn, d["id"], b)
    if not d["domain"].startswith("api"):
        monitor_db.add_alert(conn, acc["id"], d["domain"], "PQ_LOST", {"group": "x25519"})
conn.close()
Path("/tmp/conv_preview.txt").write_text(f"scan_a=/scan/{sid}?lang=ar\nscan_b=/scan/{sid_b}?lang=ar\ndashboard=/monitor/{token}?lang=ar\n"
                                         f"evidence=/monitor/{token}/evidence.pdf\n")
print(open("/tmp/conv_preview.txt").read(), flush=True)
app.run(host="127.0.0.1", port=5077)
