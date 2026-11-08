#!/usr/bin/env node
// quantum-aether CLI — checks post-quantum TLS readiness. Zero dependencies.
// Usage: npx quantum-aether example.com [--json]
"use strict";
const https = require("https");

const BASE = process.env.QUANTUM_AETHER_BASE || "https://ather-quantum.com";
const args = process.argv.slice(2).filter((a) => a !== "--");
const json = args.includes("--json");
const domain = args.find((a) => !a.startsWith("-"));

if (!domain || args.includes("-h") || args.includes("--help")) {
  console.log("Usage: npx quantum-aether <domain> [--json]\n" +
    "Checks whether a site negotiates post-quantum TLS key exchange (X25519MLKEM768).");
  process.exit(domain ? 0 : 1);
}

const format = json ? "json" : "text";
const url = `${BASE}/api/v1/scan?domain=${encodeURIComponent(domain)}&format=${format}`;

https.get(url, { headers: { "User-Agent": "quantum-aether-cli" } }, (res) => {
  let body = "";
  res.on("data", (chunk) => (body += chunk));
  res.on("end", () => {
    if (res.statusCode >= 400) {
      try { console.error(JSON.parse(body).message || body); }
      catch (_e) { console.error(body.trim()); }
      process.exit(1);
    }
    process.stdout.write(json ? body.trim() + "\n" : body);
  });
}).on("error", (err) => {
  console.error("Network error: " + err.message);
  process.exit(1);
});
