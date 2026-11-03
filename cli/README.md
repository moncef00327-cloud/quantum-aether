# quantum-aether

Check whether an HTTPS site uses **post-quantum TLS** key exchange
(`X25519MLKEM768`, hybrid ML-KEM / FIPS 203) — the same thing Chrome and Firefox
now negotiate. Free, no install, no account.

```sh
npx quantum-aether example.com
```

```
  Quantum Aether — post-quantum TLS scan
  domain        example.com
  grade         B
  key exchange  x25519
  post-quantum  NO — classical, harvest-now-decrypt-later risk
  TLS           TLSv1.3
  certificate   ECDSA-256
  full report   https://ather-quatum.cloud/?domain=example.com  ($49.00)
```

JSON for scripts and agents:

```sh
npx quantum-aether example.com --json
```

No Node? Same check over plain HTTP:

```sh
curl "https://ather-quatum.cloud/api/v1/scan?domain=example.com&format=text"
```

Data and methodology: https://ather-quatum.cloud/study/top-1000-post-quantum-tls
