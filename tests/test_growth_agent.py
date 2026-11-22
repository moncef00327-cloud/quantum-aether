"""Growth agent guard rails: published contacts only, no EU/gov, caps, pause, stop replies, leads drafted not sent."""
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

import growth_agent as g


class FakeResp:
    def __init__(self, status=200, text="", ctype="text/plain", js=None):
        self.status_code, self.text, self.headers, self._js = status, text, {"content-type": ctype}, js or {}

    def json(self):
        return self._js


class FakeHttp:
    def __init__(self, contacts):
        self.contacts, self.posts, self.n = contacts, [], 0

    def get(self, url, **kw):
        if "api.resend.com" in url:
            return FakeResp(js={"last_event": "delivered"})
        host = url.split("/")[2].removeprefix("www.")
        email = self.contacts.get(host)
        return FakeResp(text=f"Contact: mailto:{email}\nExpires: 2027-01-01T00:00:00Z\n") if email else FakeResp(404)

    def post(self, url, **kw):
        self.n += 1
        self.posts.append(kw["json"])
        return FakeResp(js={"id": f"id{self.n}"})


class GrowthAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "q.db")
        c = sqlite3.connect(self.db)
        c.executescript("""
          CREATE TABLE adoption_results (week, domain, rank, sector, ok, grade, grp, tls, pq, scanned_at, unsure);
          CREATE TABLE pageviews (day, path, referrer, visitor, is_bot, is_test);
          CREATE TABLE contacted_orgs (domain, added_at, note);
          CREATE TABLE inbound_mail (from_addr, subject, received_at, is_test);
          CREATE TABLE scans (created_at, is_test); CREATE TABLE monitor_accounts (created_at, status);""")
        rows = [("bank.com.sa", "banks-mena", 0), ("commerzbank.com", "finance-worldwide", 0), ("bank.de", "banks-mena", 0),
                ("cbi.iq", "banks-mena", 0), ("tax.gov.ae", "banks-mena", 0), ("pq.ae", "banks-mena", 1),
                ("old.com.sa", "banks-mena", 0), ("nolist.qa", "banks-mena", 0), ("nowpq.com.sa", "banks-mena", 0),
                ("other.qa", "banks-mena", 0)]
        for d, sec, pq in rows:
            c.execute("INSERT INTO adoption_results VALUES ('2026-W47', ?, 1, ?, 1, 'B', 'x25519', 'TLSv1.3', ?, '', 0)", (d, sec, pq))
        c.execute("INSERT INTO contacted_orgs VALUES ('old.com.sa', '', '')")
        c.commit(); c.close()
        self.contacts = {d: f"security@{d}" for d, _, _ in rows if d != "nolist.qa"}
        self.env = mock.patch.dict(os.environ, {"RESEND_API_KEY": "k", "QS_OUTREACH_FROM": "o@mail.x", "QS_MAIL_FROM": "a@x",
                                                "QS_OWNER_EMAIL": "owner@x"})
        self.env.start()
        self.pause = mock.patch.object(g, "PAUSE_FILE", os.path.join(self.tmp.name, "paused"))
        self.pause.start()

    def tearDown(self):
        self.env.stop(); self.pause.stop(); self.tmp.cleanup()

    def run_once(self, http):
        return g.outreach(g.connect(self.db), http=http, history=set(), pause_between=0, scanner=self.scanner)

    @staticmethod
    def scanner(host):
        pq = host.startswith("nowpq")
        return {"grade": "A" if pq else "B", "scanned_at": "2026-11-22T06:00:00Z",
                "key_exchange": {"negotiation_observed": True, "pq": pq, "group": "X25519MLKEM768" if pq else "x25519",
                                 "version": "TLSv1.3", "error": None}}

    def test_only_published_non_eu_non_gov_new_orgs(self):
        http = FakeHttp(self.contacts)
        sent = [s["domain"] for s in self.run_once(http)["sent"]]
        self.assertEqual(sorted(sent), ["bank.com.sa", "other.qa"])  # PER_RUN = 2
        for p in http.posts:
            self.assertIn("utm_campaign=growth_agent", p["text"])
            self.assertIn("إيقاف", p["text"])
        again = [s["domain"] for s in self.run_once(FakeHttp(self.contacts))["sent"]]
        self.assertNotIn("bank.com.sa", again)
        for bad in ("nowpq.com.sa", "commerzbank.com", "bank.de", "cbi.iq", "tax.gov.ae", "pq.ae", "old.com.sa", "nolist.qa"):
            self.assertNotIn(bad, sent + again)

    def test_pause_file_stops_everything(self):
        open(g.PAUSE_FILE, "w").write("manual")
        http = FakeHttp(self.contacts)
        self.assertEqual(self.run_once(http)["sent"], [])
        self.assertEqual(http.posts, [])

    def test_stop_reply_suppresses_domain(self):
        c = sqlite3.connect(self.db)
        c.execute("INSERT INTO inbound_mail VALUES ('it@other.qa', 'Re: stop', '2026-11-22', 0)"); c.commit(); c.close()
        sent = [s["domain"] for s in self.run_once(FakeHttp(self.contacts))["sent"]]
        self.assertNotIn("other.qa", sent)

    def test_lead_gets_draft_to_owner_only(self):
        http = FakeHttp(self.contacts)
        self.run_once(http)
        c = sqlite3.connect(self.db)
        c.execute("INSERT INTO inbound_mail VALUES ('cto@bank.com.sa', 'Re: TLS', '2026-11-22T10:00Z', 0)"); c.commit(); c.close()
        http.posts.clear()
        new = g.check_leads(g.connect(self.db), http)
        self.assertEqual(len(new), 1)
        self.assertEqual([p["to"] for p in http.posts], [["owner@x"]])
        self.assertIn("NOT sent", http.posts[0]["text"])
        self.assertEqual(g.check_leads(g.connect(self.db), http), [])  # notified once

    def test_expand_finds_published_contacts_and_feeds_outreach(self):
        tranco = os.path.join(self.tmp.name, "t.csv")
        open(tranco, "w").write("1,shop.com.br\n2,news.de\n3,site.online\n4,bank.ru\n5,nomail.jp\n6,casino.us\n7,nowpq.jp\n")
        http = FakeHttp({"shop.com.br": "sec@shop.com.br", "news.de": "s@news.de", "bank.ru": "s@bank.ru",
                         "casino.us": "s@casino.us", "nowpq.jp": "s@nowpq.jp"})
        conn = g.connect(self.db)
        stats = g.expand(conn, http=http, scanner=self.scanner, workers=2, tranco_path=tranco,
                         excluded_fn=lambda d: d.startswith("casino"))
        self.assertEqual(stats, {"probed": 3, "published": 2, "scanned": 2, "classical": 1})  # br, jp(nomail), jp(nowpq)
        self.assertEqual(g.expansion_pool(conn, tranco, lambda d: False), [(6, "casino.us")])  # probed ones wait 30 days
        conn.execute("DELETE FROM adoption_results"); conn.commit()
        sent = [s["domain"] for s in self.run_once(FakeHttp({"shop.com.br": "sec@shop.com.br"}))["sent"]]
        self.assertEqual(sent, ["shop.com.br"])

    def test_one_mail_per_address_and_no_blocked_contact(self):
        c = sqlite3.connect(self.db)
        c.execute("DELETE FROM adoption_results")
        for d in ("a.com.au", "b.com.au", "yandex.com.tr", "ubc.ca"):
            c.execute("INSERT INTO adoption_results VALUES ('2026-W47', ?, 1, 'telecom', 1, 'B', 'x25519', 'TLSv1.3', 0, '', 0)", (d,))
        c.commit(); c.close()
        http = FakeHttp({"a.com.au": "sec@group.com.au", "b.com.au": "sec@group.com.au", "yandex.com.tr": "s@yandex-team.ru",
                         "ubc.ca": "security@ubc.ca"})
        sent = [s["domain"] for s in self.run_once(http)["sent"]]
        self.assertEqual(sent, ["a.com.au"])

    def test_security_txt_parse(self):
        self.assertEqual(g.parse_security_txt("# x\nContact: https://x/form\nContact: mailto:Sec@Ex.com\n"), "sec@ex.com")
        self.assertIsNone(g.parse_security_txt("Contact: https://x/form\n"))


if __name__ == "__main__":
    unittest.main()
