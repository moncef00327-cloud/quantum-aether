# A Quantum-Bio-SaaS Project: GHZ Entanglement on IBM Hardware, Digital DNA Archiving, and a Post-Quantum TLS Scanner

## Abstract
This project combines three parts: a 3-qubit GHZ experiment executed on IBM Quantum hardware (ibm_marrakesh), a digital DNA encoding of the project's research report with Reed-Solomon error correction, and a web service that checks whether HTTPS servers negotiate the hybrid post-quantum key exchange X25519MLKEM768.

## 1. Introduction
Quantum computing threatens today's public-key cryptography, while DNA is studied as a dense archival medium. The project explores both at small scale and turns the cryptographic part into a practical service.

## 2. GHZ Experiment on Physical Hardware
Circuit: H(q0), CX(q0→q2), CX(q2→q1), measure all. Backend: ibm_marrakesh. Job ID: dbjcpopkdqps7390bqv0. Shots: 1024.
Counts: 000: 503, 111: 483, the other six states: 38 in total.
Population P(000)+P(111) = 986/1024 = 96.29%.

The population is an upper bound on the GHZ state fidelity, not the fidelity: an equal classical mixture of |000⟩ and |111⟩ also reaches 100%. The fidelity follows from the stabilizer expectation values,
F = (1/8)(1 + ⟨ZZI⟩ + ⟨IZZ⟩ + ⟨ZIZ⟩ + ⟨XXX⟩ − ⟨XYY⟩ − ⟨YXY⟩ − ⟨YYX⟩),
implemented in `ghz_fidelity.py`. It gives F = 100% on an ideal simulator and F = 99.65% with the ibm_marrakesh noise model (gate and decoherence noise; readout errors are not included). The hardware fidelity has not been measured yet.

## 3. Quantum Teleportation (Simulator)
Both a dynamic-circuit version (classical feed-forward with `if_test`) and a deferred-measurement version reproduce P(q2 = 0) = cos²(θ/2) within 3σ on AerSimulator for θ = π/3, π/4 and 2π/5 (1024 shots each). Hardware runs are supported (`quantum_teleportation.py --hardware`); none are reported here.

## 4. Digital DNA Archiving
UTF-8 bytes are mapped to bases two bits at a time (00→A, 01→C, 10→G, 11→T; four bases per byte). The archive (header with length and CRC32, then data) is protected with Reed-Solomon RS(255,223), which corrects up to 16 corrupted bytes per 255-byte block, i.e. single-base substitutions; insertions and deletions are not corrected.
The research report (12,029 bytes) becomes 55,080 bases (GC 57.14%, longest homopolymer 9) and restores byte for byte. The sequence is a text file: no DNA was synthesized, and the encoding does not enforce synthesis constraints such as short homopolymers or balanced GC content [6].

## 5. Post-Quantum TLS Readiness Scanner (SaaS)
The scanner sends a TLS 1.3 ClientHello with X25519MLKEM768 and X25519 key shares, reads the group selected in the ServerHello (or HelloRetryRequest; the ServerKeyExchange for TLS 1.2), then verifies the certificate in a standard handshake. Grades: A (TLS 1.3 with hybrid post-quantum key exchange), B (TLS 1.3, classical), C (no TLS 1.3), F (critical issue).
Validation on 2026-11-02: cloudflare.com, google.com and example.com selected X25519MLKEM768 (A); github.com and wikipedia.org selected x25519 (B); tls-v1-2.badssl.com negotiated TLS 1.2 with secp256r1 (C); expired.badssl.com was rejected for its expired certificate (F).
The service offers a free summary and a $49 full report paid via PayPal; the server creates and captures the order and checks amount, currency and reference before unlocking the report.

## 6. Limitations
- The hardware result is a single 1024-shot run; the fidelity on hardware is still to be measured.
- The DNA layer is a digital simulation of DNA storage.
- The scanner checks port 443 only and does not evaluate post-quantum certificates, which public CAs do not issue yet.

## References
[1] NIST FIPS 203 (2024), Module-Lattice-Based Key-Encapsulation Mechanism Standard.
[2] IBM Quantum, ibm_marrakesh backend (2026).
[3] Qiskit SDK 2.6 and Qiskit Runtime documentation (2026).
[4] C. Gidney (2025), How to factor 2048 bit RSA integers with less than a million noisy qubits.
[5] IETF TLS WG, Post-quantum hybrid ECDHE-MLKEM key agreement for TLS 1.3 (draft-ietf-tls-ecdhe-mlkem).
[6] G. M. Church, Y. Gao, S. Kosuri (2012), Next-Generation Digital Information Storage in DNA, Science 337(6102).
