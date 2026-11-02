import socket
import unittest
from unittest import mock

import quantum_vuln_scanner as qs


class FakeSocket:
    """يعيد البيانات على دفعات صغيرة لاختبار إعادة تجميع السجلات."""

    def __init__(self, data: bytes, chunk: int = 7):
        self.data = data
        self.chunk = chunk

    def recv(self, n):
        out, self.data = self.data[:min(n, self.chunk)], self.data[min(n, self.chunk):]
        return out


def record(content_type: int, payload: bytes) -> bytes:
    return bytes([content_type, 3, 3]) + len(payload).to_bytes(2, "big") + payload


def handshake(msg_type: int, body: bytes) -> bytes:
    return bytes([msg_type]) + len(body).to_bytes(3, "big") + body


def server_hello(version_ext=0x0304, group=qs.X25519MLKEM768, key_len=1120, random=b"\x11" * 32, cipher=0x1301):
    ext = b""
    if version_ext:
        ext += b"\x00\x2b\x00\x02" + version_ext.to_bytes(2, "big")
    if group is not None:
        share = group.to_bytes(2, "big") + (key_len.to_bytes(2, "big") + b"\x00" * key_len if key_len else b"")
        ext += b"\x00\x33" + len(share).to_bytes(2, "big") + share
    body = b"\x03\x03" + random + b"\x20" + b"\x22" * 32 + cipher.to_bytes(2, "big") + b"\x00"
    body += len(ext).to_bytes(2, "big") + ext
    return handshake(2, body)


class ClientHelloTests(unittest.TestCase):
    def test_lengths_sni_and_key_shares(self):
        ek = qs.mlkem768_encapsulation_key()
        hello = qs.build_client_hello("example.com", [qs.X25519MLKEM768, qs.X25519],
                                      [(qs.X25519MLKEM768, ek + b"\x01" * 32), (qs.X25519, b"\x01" * 32)])
        self.assertEqual(hello[0], 0x16)
        self.assertEqual(int.from_bytes(hello[3:5], "big"), len(hello) - 5)
        self.assertEqual(hello[5], 0x01)
        self.assertEqual(int.from_bytes(hello[6:9], "big"), len(hello) - 9)
        self.assertIn(b"example.com", hello)
        key_share = bytes.fromhex("11ec") + (1216).to_bytes(2, "big")
        self.assertIn(key_share, hello)
        self.assertIn(bytes.fromhex("001d") + (32).to_bytes(2, "big"), hello)

    def test_mlkem_key_is_well_formed(self):
        ek = qs.mlkem768_encapsulation_key()
        self.assertEqual(len(ek), 1184)
        packed = ek[:1152]
        for i in range(0, len(packed), 3):
            a = packed[i] | ((packed[i + 1] & 0x0F) << 8)
            b = (packed[i + 1] >> 4) | (packed[i + 2] << 4)
            self.assertLess(a, 3329)
            self.assertLess(b, 3329)


class ServerResponseTests(unittest.TestCase):
    def test_tls13_post_quantum(self):
        sock = FakeSocket(record(0x16, server_hello()) + record(0x14, b"\x01"))
        hello = qs.read_server_response(sock)
        self.assertEqual((hello["version"], hello["group"], hello["hrr"]), (0x0304, qs.X25519MLKEM768, False))

    def test_server_hello_split_across_records(self):
        msg = server_hello(group=qs.X25519, key_len=32)
        sock = FakeSocket(record(0x16, msg[:20]) + record(0x16, msg[20:]))
        self.assertEqual(qs.read_server_response(sock)["group"], qs.X25519)

    def test_hello_retry_request(self):
        msg = server_hello(group=0x0017, key_len=0, random=qs.HRR_RANDOM)
        hello = qs.read_server_response(FakeSocket(record(0x16, msg)))
        self.assertTrue(hello["hrr"])
        self.assertEqual(hello["group"], 0x0017)

    def test_tls12_ecdhe_reads_server_key_exchange(self):
        data = (server_hello(version_ext=None, group=None, cipher=0xC02F)
                + handshake(11, b"\x00" * 50)
                + handshake(12, b"\x03\x00\x1d\x20" + b"\x05" * 32))
        hello = qs.read_server_response(FakeSocket(record(0x16, data)))
        self.assertEqual((hello["version"], hello["kx"], hello["group"]), (0x0303, "ECDHE", qs.X25519))

    def test_tls12_static_rsa(self):
        data = server_hello(version_ext=None, group=None, cipher=0x009C) + handshake(11, b"\x00" * 10) + handshake(14, b"")
        hello = qs.read_server_response(FakeSocket(record(0x16, data)))
        self.assertEqual(hello["kx"], "RSA")

    def test_alert_raises(self):
        with self.assertRaises(qs.TLSAlert) as ctx:
            qs.read_server_response(FakeSocket(record(0x15, b"\x02\x28")))
        self.assertEqual(ctx.exception.description, 40)


class DomainTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(qs.normalize_domain(" https://WWW.Example.com:8443/path?q=1 "), "www.example.com")
        self.assertEqual(qs.normalize_domain("example.com."), "example.com")
        self.assertTrue(qs.normalize_domain("مثال.إختبار").startswith("xn--"))

    def test_rejects_bad_input(self):
        for bad in ["", "localhost", "127.0.0.1", "[::1]", "a..b", "-bad-.com", "x" * 64 + ".com"]:
            with self.subTest(bad=bad), self.assertRaises(qs.ScanError):
                qs.normalize_domain(bad)

    def _addrinfo(self, *ips):
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in ips]

    def test_rejects_private_and_mixed_addresses(self):
        for ips in [("10.0.0.5",), ("169.254.169.254",), ("93.184.215.14", "127.0.0.1"), ("::ffff:192.168.1.1",)]:
            with self.subTest(ips=ips), mock.patch("socket.getaddrinfo", return_value=self._addrinfo(*ips)):
                with self.assertRaises(qs.ScanError) as ctx:
                    qs.resolve_public_ip("example.com")
                self.assertEqual(ctx.exception.code, "private_address")

    def test_prefers_ipv4(self):
        with mock.patch("socket.getaddrinfo", return_value=self._addrinfo("2606:4700::1", "104.16.1.1")):
            self.assertEqual(qs.resolve_public_ip("example.com"), "104.16.1.1")


class AssessTests(unittest.TestCase):
    CERT_OK = {"verified": True, "days_left": 60, "key_algorithm": "ECDSA", "key_bits": 256}

    def grade(self, kx, cert=None):
        return qs.assess(kx, cert or self.CERT_OK)

    def test_grades(self):
        self.assertEqual(self.grade({"version": "TLSv1.3", "group": "X25519MLKEM768", "pq": True})["grade"], "A")
        self.assertEqual(self.grade({"version": "TLSv1.3", "group": "x25519", "pq": False})["grade"], "B")
        self.assertEqual(self.grade({"version": "TLSv1.2", "group": "x25519", "kx": "ECDHE"})["grade"], "C")
        self.assertEqual(self.grade({"version": "TLSv1.2", "kx": "RSA"})["grade"], "F")
        bad_cert = dict(self.CERT_OK, verified=False, verify_error="expired")
        self.assertEqual(self.grade({"version": "TLSv1.3", "pq": True}, bad_cert)["grade"], "F")
        weak = dict(self.CERT_OK, key_algorithm="RSA", key_bits=1024)
        self.assertEqual(self.grade({"version": "TLSv1.3", "pq": True}, weak)["grade"], "F")

    def test_rsa_4096_is_still_shor_vulnerable(self):
        cert = dict(self.CERT_OK, key_algorithm="RSA", key_bits=4096)
        codes = {f["code"] for f in self.grade({"version": "TLSv1.3", "pq": True}, cert)["findings"]}
        self.assertIn("CERT_SHOR_VULNERABLE", codes)

    def test_rejected_pq_hello_is_reported(self):
        kx = {"version": "TLSv1.3", "group": "x25519", "pq": False, "pq_hello_ok": False, "pq_hello_error": "reset"}
        codes = {f["code"] for f in self.grade(kx)["findings"]}
        self.assertIn("KX_PQ_HELLO_REJECTED", codes)


if __name__ == "__main__":
    unittest.main()
