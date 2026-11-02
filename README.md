<!--
AI-Discovery-Metadata:
- Project-Type: Quantum computing experiments (Qiskit) + digital DNA data encoding + post-quantum TLS readiness scanner (SaaS)
- Quantum-Hardware: IBM Quantum ibm_marrakesh, 3-qubit GHZ, job dbjcpopkdqps7390bqv0, 1024 shots, population P(000)+P(111) = 96.29%
- Bio-Archiving: research report as 55,080 DNA bases (2 bits/base) with Reed-Solomon RS(255,223); digital only, not synthesized
- Service: https://ather-quatum.cloud — free scan API (POST /api/scan), $49 full report via PayPal (server-verified)
- Deployment: Flask + gunicorn behind nginx, systemd, Vultr
- Stack: Python 3.10+, Qiskit 2.6.1, qiskit-aer 0.18.2, qiskit-ibm-runtime 0.51.0, Flask 3.1, cryptography, reedsolo
-->

# Quantum Aether / الأثير الكمومي
## Quantum experiments · Digital DNA archive · Post-quantum TLS scanner

### English
Three parts in one project:
1. **Quantum experiments** with Qiskit: Bell and GHZ states, teleportation, a GHZ run on IBM's ibm_marrakesh processor, and a script that measures the real GHZ fidelity.
2. **Digital DNA archive**: text is encoded into A/C/G/T with Reed-Solomon error correction and restores byte for byte.
3. **Post-quantum TLS scanner** (web service at ather-quatum.cloud): checks whether a website negotiates the hybrid post-quantum key exchange X25519MLKEM768 and analyzes its certificate. Free summary; $49 full report through PayPal.

### العربية
ثلاثة أجزاء في مشروع واحد:
1. **تجارب كمومية** بـ Qiskit: حالات Bell وGHZ، ونقل الحالة الكمومية، وتشغيل GHZ على معالج IBM الحقيقي ibm_marrakesh، وسكربت لقياس الدقة الفعلية لحالة GHZ.
2. **أرشيف DNA رقمي**: ترميز النص إلى A/C/G/T مع تصحيح أخطاء Reed-Solomon، ويُسترجع حرفاً بحرف.
3. **ماسح جاهزية TLS لما بعد الكم** (خدمة ويب على ather-quatum.cloud): يفحص هل يستخدم الموقع تبادل المفاتيح الهجين X25519MLKEM768 ويحلل شهادته. ملخص مجاني وتقرير كامل بـ 49$ عبر PayPal.

## Files / الملفات

| File | Purpose |
|---|---|
| `quantum_saas_app.py` | Flask web app: scan pages, free API, PayPal checkout, paid report, admin |
| `quantum_vuln_scanner.py` | The scanner (also a CLI: `python quantum_vuln_scanner.py example.com`) |
| `paypal_client.py`, `sales_db.py`, `i18n.py` | PayPal Orders v2 client, SQLite storage, Arabic/English texts |
| `templates/`, `static/` | Web pages, styles, PayPal button script |
| `real_quantum.py` | Run GHZ on IBM hardware, or `--fetch JOB_ID` to download an existing job |
| `ghz_fidelity.py` | GHZ fidelity from stabilizer expectation values (`--noisy`, `--hardware`) |
| `quantum_teleportation.py`, `aether_decoder.py` | Teleportation protocol and Qiskit bit-order analysis |
| `run_bell_state.py`, `run_ghz_relay.py`, `bell_state.ipynb` | Simulator demos |
| `export_quantum_data.py`, `quantum_gui.py` | `quantum_data.csv` (simulator, noise model, hardware) and a Tkinter viewer |
| `dna_encode.py`, `bio_archive_report.py` | DNA encoding and the report archive (`archive` / `restore` / `verify`) |
| `save_ibm_account.py` | Save the IBM Quantum token locally without echoing it |
| `results/` | Recorded experiment results (JSON) |
| `deploy/` | Server install script, systemd unit, PayPal/admin configuration, nginx example |
| `tests/` | Unit tests |

## Run locally / التشغيل المحلي

```bash
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt -r requirements-quantum.txt
python -m unittest discover -s tests -t .
python quantum_saas_app.py        # http://127.0.0.1:5000
```

Payments are disabled until `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` are set; the scan itself works without them.

## Deploy / النشر

On the server (Ubuntu/Debian, as root), from a copy of this repository:

```bash
bash deploy/install.sh           # installs or updates the app, keeps data and settings
bash deploy/configure.sh         # asks for the PayPal secret and admin password (hidden input)
```

Data lives in `/var/lib/quantum_saas`, settings in `/etc/quantum_saas.env`, and the service runs as the unprivileged user `quantum` behind nginx.

## Notes on the science / ملاحظات علمية
- 96.29% is the GHZ **population** P(000)+P(111), an upper bound on the fidelity. Use `ghz_fidelity.py` for the fidelity itself.
- The DNA sequence is a digital encoding; nothing was synthesized.
- Shor's algorithm breaks RSA and elliptic-curve keys of any size; larger RSA keys do not provide quantum safety. What protects recorded traffic today is a post-quantum key exchange such as X25519MLKEM768.
