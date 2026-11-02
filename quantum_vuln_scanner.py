# quantum_vuln_scanner.py
# فحص تلقائي لثغرات التشفير (RSA/ECC) لشهادات TLS
import ssl, socket, sys
from cryptography import x509
from cryptography.hazmat.backends import default_backend

def scan_host(host, port=443):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            cert_bin = ssock.getpeercert(binary_form=True)
    cert = x509.load_der_x509_certificate(cert_bin, default_backend())
    pk = cert.public_key()
    key_type = type(pk).__name__
    key_size = getattr(pk, "key_size", None)
    print(f"Host: {host}")
    print(f"  Key type: {key_type}")
    print(f"  Key size: {key_size} bits")
    if key_size and key_size < 4096:
        print("  [WARNING] RSA/ECC key < 4096 bits may be vulnerable to Shor on future quantum hardware.")
    else:
        print("  [OK] Key size adequate for now.")
    return key_type, key_size
if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "example.com"
    scan_host(host)
