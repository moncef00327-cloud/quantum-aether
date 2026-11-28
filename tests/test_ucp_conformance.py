"""Official UCP v2026-08-25 schema validation & E2E conformance tests for Quantum Aether."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import uuid

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

import quantum_saas_app
import ucp_commerce
from tests.test_app import RESULT

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "ucp" / "2026-08-25"
UCP_BASE_URI = "https://ucp.dev/2026-08-25/"
AGENT_META = {"ucp-agent": {"profile": "https://platform.example.com/.well-known/ucp"}}


def _build_registry() -> Registry:
    resources = []
    for path in sorted((FIXTURE_ROOT / "schemas").rglob("*.json")):
        rel = path.relative_to(FIXTURE_ROOT).as_posix()
        doc = json.loads(path.read_text(encoding="utf-8"))
        uri = doc.get("$id") or (UCP_BASE_URI + rel)
        res = Resource.from_contents(doc)
        resources.append((uri, res))
        if uri != UCP_BASE_URI + rel:
            resources.append((UCP_BASE_URI + rel, res))
    return Registry().with_resources(resources)


REGISTRY = _build_registry()


def _assert_schema(tc: unittest.TestCase, instance: dict, schema_ref: str):
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$ref": schema_ref}
    validator = Draft202012Validator(schema, registry=REGISTRY)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors[:5])
        tc.fail(f"Schema validation failed against {schema_ref}: {detail}")


class Ucp20260825ConformanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.scanner = Mock(return_value=copy.deepcopy(RESULT))
        self.app = quantum_saas_app.create_app(
            {
                "TESTING": True,
                "DATA_DIR": self.tmp.name,
                "PUBLIC_URL": "https://ather-quantum.com",
                "USDC_BASE_ADDR": "0x" + "55" * 20,
                "SCANS_PER_HOUR": 5,
                "GLOBAL_SCANS_PER_HOUR": 20,
            },
            scanner=self.scanner,
        )
        self.settle_calls = 0

        def fake_facilitator(path, body):
            if path == "/verify":
                return {"isValid": True}
            self.settle_calls += 1
            return {"success": True, "network": "eip155:8453", "transaction": "0x" + f"{self.settle_calls:064x}"}

        self.app.extensions["x402_facilitator"] = fake_facilitator
        self.client = self.app.test_client()

    def ucp_rpc(self, method: str, params=None, rid=1):
        body = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            body["params"] = params
        return self.client.post("/ucp/mcp", json=body)

    def ucp_tool(self, name: str, arguments: dict, rid=1):
        return self.ucp_rpc("tools/call", {"name": name, "arguments": arguments}, rid=rid)

    def test_profile_conforms_to_official_business_schema_and_keys(self):
        r1 = self.client.get("/.well-known/ucp")
        r2 = self.client.get("/.well-known/ucp.json")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertIn("application/json", r1.content_type)
        self.assertEqual(r1.json, r2.json)
        profile = r1.json

        _assert_schema(self, profile, UCP_BASE_URI + "schemas/profile.json#/$defs/business_schema")
        self.assertEqual(set(profile.keys()), {"ucp", "keys"})
        self.assertEqual(profile["ucp"]["version"], "2026-08-25")

        # Services clean, no preferred field, MCP -> /ucp/mcp
        svcs = profile["ucp"]["services"]["dev.ucp.shopping"]
        by_t = {s["transport"]: s for s in svcs}
        self.assertEqual(set(by_t.keys()), {"mcp", "rest", "a2a"})
        for s in svcs:
            self.assertNotIn("preferred", s)
        self.assertEqual(by_t["mcp"]["endpoint"], "https://ather-quantum.com/ucp/mcp")
        self.assertEqual(by_t["mcp"]["schema"], UCP_BASE_URI + "services/shopping/mcp.openrpc.json")
        self.assertEqual(by_t["rest"]["endpoint"], "https://ather-quantum.com/api/v1/ucp")
        self.assertEqual(by_t["rest"]["schema"], UCP_BASE_URI + "services/shopping/rest.openapi.json")
        self.assertEqual(by_t["a2a"]["endpoint"], "https://ather-quantum.com/.well-known/agent-card.json")

        # Capabilities exact
        self.assertEqual(
            set(profile["ucp"]["capabilities"].keys()),
            {"dev.ucp.shopping.catalog.search", "dev.ucp.shopping.catalog.lookup", "dev.ucp.shopping.checkout"},
        )

        # Authority-bound payment handlers hosted on ather-quantum.com
        handlers = profile["ucp"]["payment_handlers"]
        self.assertEqual(
            set(handlers.keys()),
            {
                "com.ather-quantum.x402",
                "com.ather-quantum.paypal",
                "com.ather-quantum.stablecoin_transfer",
                "com.ather-quantum.invoice",
            },
        )
        for ns, entries in handlers.items():
            self.assertTrue(entries)
            for h in entries:
                self.assertTrue(h["schema"].startswith("https://ather-quantum.com/ucp/handlers/"))
                self.assertTrue(h["spec"].startswith("https://ather-quantum.com/ucp/handlers/"))
                path_schema = h["schema"].replace("https://ather-quantum.com", "")
                path_spec = h["spec"].replace("https://ather-quantum.com", "")
                self.assertEqual(self.client.get(path_schema).status_code, 200, path_schema)
                self.assertEqual(self.client.get(path_spec).status_code, 200, path_spec)

        # Top-level keys match /.well-known/jwks.json Ed25519 public keys
        jwks_keys = self.client.get("/.well-known/jwks.json").json["keys"]
        self.assertEqual(len(profile["keys"]), len(jwks_keys))
        for k in profile["keys"]:
            self.assertEqual(k["kty"], "OKP")
            self.assertEqual(k["crv"], "Ed25519")
            self.assertEqual(k["alg"], "EdDSA")
            self.assertEqual(k["use"], "sig")
            self.assertNotIn("d", k)

    def test_all_9_products_minor_units_and_iso_currencies(self):
        expected = {
            "qa-batch-scan-10": (10, "USD"),
            "qa-live-cbom": (25, "USD"),
            "qa-sector-snapshot": (50, "USD"),
            "qa-tls-attestation": (500, "USD"),
            "qa-full-report": (4900, "USD"),
            "qa-monitoring-starter": (2900, "EUR"),
            "qa-monitoring-business": (9900, "EUR"),
            "qa-msp-pilot": (29000, "EUR"),
            "qa-org-audit": (49000, "EUR"),
        }
        res = self.ucp_tool("search_catalog", {"meta": AGENT_META, "catalog": {}}).json["result"]["structuredContent"]
        _assert_schema(self, res, UCP_BASE_URI + "schemas/shopping/catalog_search.json#/$defs/search_response")
        self.assertEqual(len(res["products"]), 9)
        actual = {}
        for p in res["products"]:
            self.assertEqual(len(p["variants"]), 1)
            v = p["variants"][0]
            self.assertIs(type(v["price"]["amount"]), int)
            self.assertEqual(v["price"], p["price_range"]["min"])
            self.assertEqual(v["price"], p["price_range"]["max"])
            actual[p["id"]] = (v["price"]["amount"], v["price"]["currency"])
        self.assertEqual(actual, expected)

    def test_ucp_mcp_tools_list_and_protocol_validation(self):
        tlist = self.ucp_rpc("tools/list").json["result"]["tools"]
        self.assertEqual(
            {t["name"] for t in tlist},
            {
                "search_catalog", "lookup_catalog", "get_product",
                "create_checkout", "get_checkout", "update_checkout", "complete_checkout", "cancel_checkout",
            },
        )
        # Missing meta['ucp-agent'].profile -> JSON-RPC -32000
        err_meta = self.ucp_tool("search_catalog", {"catalog": {}}).json
        self.assertEqual(err_meta["error"]["code"], -32000)

        # checkout containing id -> JSON-RPC -32000
        err_id = self.ucp_tool(
            "create_checkout",
            {"meta": AGENT_META, "checkout": {"id": "forged", "line_items": [{"item": {"id": "qa-batch-scan-10"}, "quantity": 1}]}},
        ).json
        self.assertEqual(err_id["error"]["code"], -32000)

        # complete_checkout & cancel_checkout require UUID idempotency-key -> -32000
        err_idem = self.ucp_tool("cancel_checkout", {"meta": AGENT_META, "id": "chk_missing"}).json
        self.assertEqual(err_idem["error"]["code"], -32000)
        err_bad_uuid = self.ucp_tool("cancel_checkout", {"meta": {**AGENT_META, "idempotency-key": "not-a-uuid"}, "id": "chk_missing"}).json
        self.assertEqual(err_bad_uuid["error"]["code"], -32000)

        # Unknown tool -> -32001
        err_unk = self.ucp_tool("nonexistent_tool", {"meta": AGENT_META}).json
        self.assertEqual(err_unk["error"]["code"], -32001)

    def test_catalog_lookup_get_product_and_mixed_currency_rejection(self):
        lk = self.ucp_tool(
            "lookup_catalog",
            {"meta": AGENT_META, "catalog": {"ids": ["qa-batch-scan-10", "qa-msp-pilot:default", "missing-id"]}},
        ).json["result"]["structuredContent"]
        _assert_schema(self, lk, UCP_BASE_URI + "schemas/shopping/catalog_lookup.json#/$defs/lookup_response")
        self.assertEqual({p["id"] for p in lk["products"]}, {"qa-batch-scan-10", "qa-msp-pilot"})
        self.assertTrue(lk.get("messages"))

        gp = self.ucp_tool("get_product", {"meta": AGENT_META, "catalog": {"id": "qa-live-cbom"}}).json["result"]["structuredContent"]
        _assert_schema(self, gp, UCP_BASE_URI + "schemas/shopping/catalog_lookup.json#/$defs/get_product_response")
        self.assertEqual(gp["product"]["id"], "qa-live-cbom")

        gp_miss = self.ucp_tool("get_product", {"meta": AGENT_META, "catalog": {"id": "nope"}}).json["result"]["structuredContent"]
        _assert_schema(self, gp_miss, UCP_BASE_URI + "schemas/common/types/error_response.json")
        self.assertEqual(gp_miss["ucp"]["status"], "error")

        # Mixed USD + EUR line items rejected with spec-compliant error_response
        mixed = self.ucp_tool(
            "create_checkout",
            {
                "meta": AGENT_META,
                "checkout": {
                    "line_items": [
                        {"item": {"id": "qa-batch-scan-10"}, "quantity": 1},
                        {"item": {"id": "qa-msp-pilot"}, "quantity": 1},
                    ]
                },
            },
        ).json["result"]["structuredContent"]
        _assert_schema(self, mixed, UCP_BASE_URI + "schemas/common/types/error_response.json")
        self.assertEqual(mixed["messages"][0]["code"], "mixed_currency")

    def test_e2e_ucp_mcp_checkout_lifecycle_all_statuses_and_idempotency(self):
        # 1. search_catalog -> 2. get_product
        sr = self.ucp_tool("search_catalog", {"meta": AGENT_META, "catalog": {"query": "cbom"}}).json["result"]["structuredContent"]
        _assert_schema(self, sr, UCP_BASE_URI + "schemas/shopping/catalog_search.json#/$defs/search_response")
        prod_id = next(p["id"] for p in sr["products"] if p["id"] == "qa-live-cbom")

        gp = self.ucp_tool("get_product", {"meta": AGENT_META, "catalog": {"id": prod_id}}).json["result"]["structuredContent"]
        _assert_schema(self, gp, UCP_BASE_URI + "schemas/shopping/catalog_lookup.json#/$defs/get_product_response")
        var_id = gp["product"]["variants"][0]["id"]

        # 3. create_checkout -> status = incomplete
        created = self.ucp_tool(
            "create_checkout",
            {"meta": AGENT_META, "checkout": {"line_items": [{"item": {"id": var_id}, "quantity": 1}]}},
        ).json["result"]["structuredContent"]
        _assert_schema(self, created, UCP_BASE_URI + "schemas/shopping/checkout.json")
        self.assertEqual(created["status"], "incomplete")
        cid = created["id"]

        # 4. update_checkout -> attach payment instrument -> status = ready_for_complete
        x402_instrument = {
            "id": "inst_x402_1",
            "handler_id": "x402_base_usdc",
            "type": "x402_eip3009_usdc",
            "selected": True,
            "credential": {
                "type": "x402_payment_signature",
                "payload": {
                    "x402Version": 2,
                    "accepted": {
                        "network": "eip155:8453",
                        "payTo": "0x" + "55" * 20,
                        "amount": "500000",  # qty 2 * $0.25 = $0.50 = 500000 USDC atomic units
                    },
                    "payload": {"signature": "0x" + "aa" * 65},
                },
            },
        }
        updated = self.ucp_tool(
            "update_checkout",
            {
                "meta": AGENT_META,
                "id": cid,
                "checkout": {
                    "line_items": [{"item": {"id": var_id}, "quantity": 2}],
                    "payment": {"instruments": [x402_instrument]},
                },
            },
        ).json["result"]["structuredContent"]
        _assert_schema(self, updated, UCP_BASE_URI + "schemas/shopping/checkout.json")
        self.assertEqual(updated["status"], "ready_for_complete")
        self.assertEqual(next(t["amount"] for t in updated["totals"] if t["type"] == "total"), 50)

        # Verify update_checkout is blocked while status == complete_in_progress
        with self.app.app_context():
            conn = quantum_saas_app.db()
            in_prog = dict(updated, status="complete_in_progress")
            ucp_commerce._save_checkout(conn, in_prog)
            _assert_schema(self, in_prog, UCP_BASE_URI + "schemas/shopping/checkout.json")
        blocked_upd = self.ucp_tool(
            "update_checkout",
            {"meta": AGENT_META, "id": cid, "checkout": {"line_items": [{"item": {"id": var_id}, "quantity": 1}]}},
        ).json["result"]["structuredContent"]
        _assert_schema(self, blocked_upd, UCP_BASE_URI + "schemas/shopping/checkout.json")
        self.assertEqual(blocked_upd["status"], "complete_in_progress")
        self.assertEqual(blocked_upd["line_items"][0]["quantity"], 2)  # unchanged!
        self.assertTrue(any(m.get("severity") == "recoverable" for m in blocked_upd.get("messages", [])))

        # Restore ready_for_complete before completing
        with self.app.app_context():
            ucp_commerce._save_checkout(quantum_saas_app.db(), updated)

        # 5. complete_checkout (with UUID idempotency-key) -> completed
        idem_complete = str(uuid.uuid4())
        completed = self.ucp_tool(
            "complete_checkout",
            {"meta": {**AGENT_META, "idempotency-key": idem_complete}, "id": cid, "checkout": {"payment": {"instruments": [x402_instrument]}}},
        ).json["result"]["structuredContent"]
        _assert_schema(self, completed, UCP_BASE_URI + "schemas/shopping/checkout.json")
        self.assertEqual(completed["status"], "completed")
        self.assertIn("order", completed)
        self.assertEqual(self.settle_calls, 1)

        # 6. get_checkout == completed
        fetched = self.ucp_tool("get_checkout", {"meta": AGENT_META, "id": cid}).json["result"]["structuredContent"]
        _assert_schema(self, fetched, UCP_BASE_URI + "schemas/shopping/checkout.json")
        self.assertEqual(fetched["status"], "completed")

        # 7. Replay complete_checkout with same idempotency-key -> identical result, zero duplicate settlement!
        replayed = self.ucp_tool(
            "complete_checkout",
            {"meta": {**AGENT_META, "idempotency-key": idem_complete}, "id": cid, "checkout": {"payment": {"instruments": [x402_instrument]}}},
        ).json["result"]["structuredContent"]
        self.assertEqual(replayed, completed)
        self.assertEqual(self.settle_calls, 1)

        # 8. Also validate requires_escalation and canceled statuses against checkout.json
        esc = self.ucp_tool(
            "create_checkout",
            {"meta": AGENT_META, "checkout": {"line_items": [{"item": {"id": "qa-msp-pilot"}, "quantity": 1}]}},
        ).json["result"]["structuredContent"]
        _assert_schema(self, esc, UCP_BASE_URI + "schemas/shopping/checkout.json")
        self.assertEqual(esc["status"], "requires_escalation")

        idem_cancel = str(uuid.uuid4())
        canceled = self.ucp_tool(
            "cancel_checkout",
            {"meta": {**AGENT_META, "idempotency-key": idem_cancel}, "id": esc["id"]},
        ).json["result"]["structuredContent"]
        _assert_schema(self, canceled, UCP_BASE_URI + "schemas/shopping/checkout.json")
        self.assertEqual(canceled["status"], "canceled")
        canceled_replay = self.ucp_tool(
            "cancel_checkout",
            {"meta": {**AGENT_META, "idempotency-key": idem_cancel}, "id": esc["id"]},
        ).json["result"]["structuredContent"]
        self.assertEqual(canceled_replay, canceled)

    def test_rest_binding_matches_openapi_and_legacy_catalog_preserved(self):
        # REST catalog search, lookup, product
        r_s = self.client.post("/api/v1/ucp/catalog/search", json={"query": "batch"})
        self.assertEqual(r_s.status_code, 200)
        _assert_schema(self, r_s.json, UCP_BASE_URI + "schemas/shopping/catalog_search.json#/$defs/search_response")

        r_l = self.client.post("/api/v1/ucp/catalog/lookup", json={"ids": ["qa-batch-scan-10"]})
        self.assertEqual(r_l.status_code, 200)
        _assert_schema(self, r_l.json, UCP_BASE_URI + "schemas/shopping/catalog_lookup.json#/$defs/lookup_response")

        r_p = self.client.post("/api/v1/ucp/catalog/product", json={"id": "qa-batch-scan-10"})
        self.assertEqual(r_p.status_code, 200)
        _assert_schema(self, r_p.json, UCP_BASE_URI + "schemas/shopping/catalog_lookup.json#/$defs/get_product_response")

        # REST checkout create -> get -> put -> cancel
        r_c = self.client.post("/api/v1/ucp/checkout-sessions", json={"line_items": [{"item": {"id": "qa-batch-scan-10"}, "quantity": 1}]})
        self.assertEqual(r_c.status_code, 201)
        _assert_schema(self, r_c.json, UCP_BASE_URI + "schemas/shopping/checkout.json")
        cid = r_c.json["id"]

        r_g = self.client.get(f"/api/v1/ucp/checkout-sessions/{cid}")
        self.assertEqual(r_g.status_code, 200)
        _assert_schema(self, r_g.json, UCP_BASE_URI + "schemas/shopping/checkout.json")

        r_u = self.client.put(f"/api/v1/ucp/checkout-sessions/{cid}", json={"line_items": [{"item": {"id": "qa-batch-scan-10"}, "quantity": 3}]})
        self.assertEqual(r_u.status_code, 200)
        self.assertEqual(next(t["amount"] for t in r_u.json["totals"] if t["type"] == "total"), 30)

        r_x = self.client.post(f"/api/v1/ucp/checkout-sessions/{cid}/cancel", headers={"Idempotency-Key": str(uuid.uuid4())})
        self.assertEqual(r_x.status_code, 200)
        self.assertEqual(r_x.json["status"], "canceled")

        # Legacy GET /api/v1/ucp/catalog preserved with deprecated=True
        leg = self.client.get("/api/v1/ucp/catalog")
        self.assertEqual(leg.status_code, 200)
        self.assertTrue(leg.json["deprecated"])
        self.assertEqual(len(leg.json["items"]), 9)
        self.assertIn("catalog_search", leg.json["replacement_endpoints"])

        # Existing /mcp (18) and /mcp/free (10) untouched!
        mcp_tools = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json["result"]["tools"]
        free_tools = self.client.post("/mcp/free", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).json["result"]["tools"]
        self.assertEqual(len(mcp_tools), 18)
        self.assertEqual(len(free_tools), 10)


if __name__ == "__main__":
    unittest.main()
