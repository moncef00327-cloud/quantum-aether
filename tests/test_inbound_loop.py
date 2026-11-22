"""The owner's notice can land in the inbound address itself: it must not trigger another notice (loop 2026-11-22)."""
import json
import sqlite3
import time
import unittest

from flask import Blueprint, Flask

import inbound_mail

SECRET = "whsec_" + "c2VjcmV0c2VjcmV0c2VjcmV0c2VjcmV0"
INBOX = "contact@mail.ather-quantum.com"


class InboundLoopTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.addCleanup(self.conn.close)
        self.sent = []
        outer = self

        class Mailer:
            def send(self, *args):
                outer.sent.append(args)
                return True

        bp = Blueprint("inbound", __name__)
        inbound_mail.register(bp, {"db": lambda: self.conn, "mailer": Mailer, "owner": lambda: INBOX,
                                   "secret": lambda: SECRET})
        app = Flask(__name__)
        app.register_blueprint(bp)
        self.client = app.test_client()

    def receive(self, sender, msg_id):
        body = json.dumps({"type": "email.received", "data": {"from": sender, "to": [INBOX], "subject": "hello"}})
        stamp = str(int(time.time()))
        headers = {"svix-id": msg_id, "svix-timestamp": stamp,
                   "svix-signature": inbound_mail.sign(SECRET, msg_id, stamp, body)}
        self.assertEqual(self.client.post("/hooks/resend/inbound", data=body, headers=headers).status_code, 200)

    def test_own_mail_is_stored_but_never_notified(self):
        for n, domain in enumerate(inbound_mail.OWN_DOMAINS):
            self.receive(f"Quantum Aether <alerts@{domain}>", f"own{n}")
        self.assertEqual(self.sent, [])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM inbound_mail").fetchone()[0], len(inbound_mail.OWN_DOMAINS))

    def test_external_mail_still_notifies_once(self):
        self.receive("Someone <someone@example.org>", "ext")
        self.assertEqual(len(self.sent), 1)


if __name__ == "__main__":
    unittest.main()
