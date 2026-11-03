import shutil
from decimal import Decimal
import tempfile
import time
import unittest
from contextlib import closing

import crypto_pay
import quantum_saas_app
import sales_db
from test_app import fake_scanner
from test_monitor import FakeMailer

POLY_ADDR = "0xea9dfd40deeb7d91ba780a3d2a2d855599642023"
ARB_ADDR = "0x3855475de54c955b6d0785b6d02f57291addb064"
USDT = crypto_pay.NETWORKS["polygon-usdt"]["contract"]
TX = "0x" + "ab" * 32


def transfer_log(contract, to, units):
    return {"address": contract, "topics": [crypto_pay.TRANSFER_TOPIC, "0x" + "0" * 24 + "1" * 40, "0x" + "0" * 24 + to[2:]],
            "data": hex(units)}


class FakeChain:
    """شبكة وهمية: إيصالات المعاملات وأرقام الكتل."""

    def __init__(self):
        self.receipts = {}
        self.latest = 1000
        self.block_time = int(time.time())
        self.down = False

    def call(self, network, method, params):
        if self.down:
            raise crypto_pay.ChainError("down")
        if method == "eth_getTransactionReceipt":
            return self.receipts.get(params[0])
        if method == "eth_blockNumber":
            return hex(self.latest)
        if method == "eth_getBlockByNumber":
            return {"timestamp": hex(self.block_time)}
        raise AssertionError(method)

    def pay(self, tx, units, to=POLY_ADDR, contract=USDT, block=900, status="0x1"):
        self.receipts[tx] = {"status": status, "blockNumber": hex(block), "logs": [transfer_log(contract, to, units)]}


class CryptoPaymentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.chain = FakeChain()
        self.mailer = FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://example.test", "HASH_SALT": "s",
             "USDT_POLYGON_ADDR": POLY_ADDR, "USDC_ARBITRUM_ADDR": ARB_ADDR, "OWNER_EMAIL": "owner@example.test"},
            scanner=fake_scanner, paypal=None, mailer=self.mailer, chain=self.chain)
        self.client = self.app.test_client()
        self.scan_id = self.client.post("/api/scan", json={"domain": "example.com"}).get_json()["scan_id"]

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def order(self, network="polygon-usdt", **extra):
        body = dict({"scan_id": self.scan_id, "network": network, "consent": True}, **extra)
        return self.client.post("/api/crypto/orders", json=body)

    def units(self, amount):
        return crypto_pay.to_units(amount, 6)

    def test_scan_page_offers_both_networks(self):
        body = self.client.get(f"/scan/{self.scan_id}?lang=ar").get_data(as_text=True)
        self.assertIn('data-network="polygon-usdt"', body)
        self.assertIn('data-network="arbitrum-usdc"', body)
        self.assertIn("crypto.js", body)

    def test_disabled_without_addresses(self):
        app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp, "USDT_POLYGON_ADDR": "",
                                           "USDC_ARBITRUM_ADDR": "not-an-address"}, scanner=fake_scanner, paypal=None)
        r = app.test_client().post("/api/crypto/orders", json={"scan_id": self.scan_id, "network": "polygon-usdt",
                                                                 "consent": True})
        self.assertEqual(r.status_code, 503)

    def test_requires_consent_and_known_network(self):
        self.assertEqual(self.order(consent=False).status_code, 400)
        r = self.order(network="bitcoin")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["networks"], ["arbitrum-usdc", "polygon-usdt"])

    def test_unique_amount_and_instructions(self):
        a = self.order().get_json()
        b = self.order().get_json()
        self.assertEqual(a["pay_to"], POLY_ADDR)
        self.assertEqual(a["token"], "USDT")
        self.assertTrue(a["amount"].startswith("49.0"))
        self.assertNotEqual(a["amount"], b["amount"])
        self.assertGreater(float(a["amount"]), 49.0)
        self.assertEqual(self.order("arbitrum-usdc").get_json()["pay_to"], ARB_ADDR)

    def test_report_locked_until_confirmed_payment(self):
        o = self.order().get_json()
        verify = lambda: self.client.post(f"/api/crypto/orders/{o['order_id']}/verify", json={"tx_hash": TX})
        self.assertEqual(verify().get_json()["status"], "PENDING")
        self.chain.pay(TX, self.units(o["amount"]), block=995)
        r = verify()
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.get_json()["status"], "CONFIRMING")
        self.chain.latest = 1100
        r = verify()
        self.assertEqual(r.get_json()["status"], "COMPLETED")
        self.assertEqual(self.client.get(r.get_json()["report_url"].replace("https://example.test", "")).status_code, 200)
        status = self.client.get(f"/api/v1/orders/{o['order_id']}").get_json()
        self.assertEqual(status["status"], "COMPLETED")
        self.assertEqual(status["currency"], "USDT")
        self.assertIn("polygonscan.com/tx/" + TX, self.mailer.sent[-1][2])
        with closing(sales_db.connect(f"{self.tmp}/quantum_saas.db")) as c:
            self.assertEqual(sales_db.stats(c)["revenue"], {"USDT": f"{Decimal(o['amount']):.2f}"})

    def test_rejects_wrong_amount_wrong_address_wrong_token(self):
        o = self.order().get_json()
        url = f"/api/crypto/orders/{o['order_id']}/verify"
        cases = [
            ("0x" + "01" * 32, dict(units=self.units(o["amount"]) - 1), "wrong_amount"),
            ("0x" + "02" * 32, dict(units=self.units(o["amount"]), to=ARB_ADDR), "no_transfer"),
            ("0x" + "03" * 32, dict(units=self.units(o["amount"]), contract="0x" + "9" * 40), "no_transfer"),
            ("0x" + "04" * 32, dict(units=self.units(o["amount"]), status="0x0"), "failed"),
        ]
        for tx, kwargs, error in cases:
            self.chain.pay(tx, **kwargs)
            r = self.client.post(url, json={"tx_hash": tx})
            self.assertEqual((r.status_code, r.get_json()["error"]), (402, error), error)
        self.assertEqual(self.client.post(url, json={"tx_hash": "0x123"}).status_code, 400)
        self.assertEqual(self.client.get(f"/api/v1/orders/{o['order_id']}").get_json()["status"], "CREATED")

    def test_old_transaction_and_reused_transaction_are_rejected(self):
        o1, o2 = self.order().get_json(), self.order().get_json()
        self.chain.block_time = int(time.time()) - 3600
        self.chain.pay(TX, self.units("50"))
        r = self.client.post(f"/api/crypto/orders/{o1['order_id']}/verify", json={"tx_hash": TX})
        self.assertEqual(r.get_json()["error"], "too_old")
        self.chain.block_time = int(time.time())
        self.assertEqual(self.client.post(f"/api/crypto/orders/{o1['order_id']}/verify",
                                          json={"tx_hash": TX}).get_json()["status"], "COMPLETED")
        r = self.client.post(f"/api/crypto/orders/{o2['order_id']}/verify", json={"tx_hash": TX})
        self.assertEqual((r.status_code, r.get_json()["error"]), (409, "tx_already_used"))

    def test_chain_outage_is_reported_not_paid(self):
        o = self.order().get_json()
        self.chain.down = True
        r = self.client.post(f"/api/crypto/orders/{o['order_id']}/verify", json={"tx_hash": TX})
        self.assertEqual(r.status_code, 502)

    def test_crypto_purchase_emails_receipt_when_email_given(self):
        o = self.order(email="payer@wallet.test").get_json()
        self.chain.pay(TX, self.units(o["amount"]), block=900)
        self.chain.latest = 1100
        r = self.client.post(f"/api/crypto/orders/{o['order_id']}/verify", json={"tx_hash": TX})
        self.assertEqual(r.get_json()["status"], "COMPLETED")
        receipt = [m for m in self.mailer.sent if m[0] == "payer@wallet.test"]
        self.assertEqual(len(receipt), 1)
        self.assertIn("example.com", receipt[0][1])
        self.assertIn("USDT", receipt[0][2])

    def test_crypto_rejects_bad_email(self):
        self.assertEqual(self.order(email="not-an-email").status_code, 400)

    def test_agent_api_alias(self):
        r = self.client.post("/api/v1/crypto/orders", json={"scan_id": self.scan_id, "network": "arbitrum-usdc",
                                                             "consent_immediate_delivery": True})
        self.assertEqual(r.status_code, 201)
        self.assertIn("Send exactly", r.get_json()["instructions"])


if __name__ == "__main__":
    unittest.main()
