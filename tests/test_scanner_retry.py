"""HelloRetryRequest is answered once, like a browser: the requested group decides the result."""
import contextlib
import unittest
from unittest import mock

import quantum_vuln_scanner as qs
from tests.test_scanner import handshake, record


def hello_body(group, key_len, random=b"\x11" * 32, cookie=None, cipher=0x1301):
    ext = b"\x00\x2b\x00\x02\x03\x04"
    share = group.to_bytes(2, "big") + (key_len.to_bytes(2, "big") + b"\x00" * key_len if key_len else b"")
    ext += b"\x00\x33" + len(share).to_bytes(2, "big") + share
    if cookie is not None:
        ext += b"\x00\x2c" + len(cookie).to_bytes(2, "big") + cookie
    body = b"\x03\x03" + random + b"\x20" + b"\x22" * 32 + cipher.to_bytes(2, "big") + b"\x00"
    return handshake(2, body + len(ext).to_bytes(2, "big") + ext)


class ScriptedServer:
    """Answers each ClientHello with the next scripted reply and keeps what the client sent."""

    def __init__(self, replies):
        self.replies, self.sent, self.pending = list(replies), [], b""

    def settimeout(self, _):
        pass

    def sendall(self, data):
        self.sent.append(data)
        self.pending += self.replies.pop(0) if self.replies else b""

    def recv(self, n):
        out, self.pending = self.pending[:n], self.pending[n:]
        return out


def parse_client_hello(data):
    assert data[0] == 0x16
    record_version = int.from_bytes(data[1:3], "big")
    body = data[9:]
    random, sid_len = body[2:34], body[34]
    session_id = body[35:35 + sid_len]
    pos = 35 + sid_len
    pos += 2 + int.from_bytes(body[pos:pos + 2], "big")
    pos += 1 + body[pos]
    end = pos + 2 + int.from_bytes(body[pos:pos + 2], "big")
    pos += 2
    exts = {}
    while pos < end:
        t, l = int.from_bytes(body[pos:pos + 2], "big"), int.from_bytes(body[pos + 2:pos + 4], "big")
        exts[t] = body[pos + 4:pos + 4 + l]
        pos += 4 + l
    shares, ks = [], exts[0x0033][2:]
    while ks:
        g, l = int.from_bytes(ks[:2], "big"), int.from_bytes(ks[2:4], "big")
        shares.append((g, l))
        ks = ks[4 + l:]
    groups = exts[0x000A][2:]
    return {"record_version": record_version, "random": random, "session_id": session_id, "exts": exts,
            "shares": shares, "groups": [int.from_bytes(groups[i:i + 2], "big") for i in range(0, len(groups), 2)]}


def run(replies):
    server = ScriptedServer(replies)
    with mock.patch.object(qs, "_connect", lambda ip, timeout: contextlib.nullcontext(server)):
        result = qs.probe_key_exchange("192.0.2.1", "example.test", timeout=2)
    return result, server


class RetryTests(unittest.TestCase):
    def test_retry_to_post_quantum_group_counts_as_post_quantum(self):
        hrr = record(0x16, hello_body(0x11EB, 0, random=qs.HRR_RANDOM, cookie=b"\x00\x03abc"))
        final = record(0x16, hello_body(0x11EB, 65 + 1088))
        result, server = run([hrr, final])
        self.assertEqual((result["group"], result["pq"], result["hrr"]), ("SecP256r1MLKEM768", True, False))
        self.assertEqual(result["hello_retry"], "SecP256r1MLKEM768")
        self.assertTrue(result["negotiation_observed"])
        first, second = (parse_client_hello(m) for m in server.sent)
        self.assertEqual(first["random"], second["random"])
        self.assertEqual(first["session_id"], second["session_id"])
        self.assertEqual(second["exts"][0x002C], b"\x00\x03abc")
        self.assertEqual(second["shares"], [(0x11EB, 65 + 1184)])
        self.assertEqual((first["record_version"], second["record_version"]), (0x0301, 0x0303))

    def test_retry_to_classical_group_is_a_definite_classical_result(self):
        result, _ = run([record(0x16, hello_body(0x0018, 0, random=qs.HRR_RANDOM)),
                         record(0x16, hello_body(0x0018, 97))])
        self.assertEqual((result["group"], result["pq"], result["hrr"]), ("secp384r1", False, False))

    def test_failed_retry_stays_undetermined(self):
        result, _ = run([record(0x16, hello_body(0x0017, 0, random=qs.HRR_RANDOM)), record(0x15, b"\x02\x46")])
        self.assertTrue(result["hrr"])
        self.assertFalse(result["pq"])
        self.assertFalse(result["negotiation_observed"])
        self.assertIn("protocol_version", result["hello_retry_error"])

    def test_inconsistent_second_hello_stays_undetermined(self):
        result, _ = run([record(0x16, hello_body(0x0017, 0, random=qs.HRR_RANDOM)),
                         record(0x16, hello_body(qs.X25519, 32))])
        self.assertTrue(result["hrr"])
        self.assertIn("inconsistently", result["hello_retry_error"])

    def test_pq_offer_includes_pure_mlkem_for_pq_only_servers(self):
        result, server = run([record(0x16, hello_body(0x0202, 0, random=qs.HRR_RANDOM)),
                              record(0x16, hello_body(0x0202, 1568))])
        self.assertEqual((result["group"], result["pq"]), ("MLKEM1024", True))
        first = parse_client_hello(server.sent[0])
        self.assertIn(0x0201, first["groups"])
        self.assertIn(0x0202, first["groups"])
        self.assertEqual(parse_client_hello(server.sent[1])["shares"], [(0x0202, 1568)])

    def test_key_share_sizes(self):
        sizes = {qs.X25519: 32, 0x0017: 65, 0x0018: 97, 0x0201: 1184, 0x0202: 1568,
                 qs.X25519MLKEM768: 1216, 0x11EB: 65 + 1184, 0x11ED: 97 + 1568}
        for group, size in sizes.items():
            with self.subTest(group=hex(group)):
                self.assertEqual(len(qs.key_share_for(group)), size)


if __name__ == "__main__":
    unittest.main()
