#!/usr/bin/env node
// quantum-aether — does a site negotiate post-quantum TLS key exchange (X25519MLKEM768)? Zero dependencies.
// Usage: npx quantum-aether <domain> [--json] [--require-pq] [--min-grade A|B|C|F]
// Calls the public scan API (GET /api/v1/scan); the scan runs on Quantum Aether's server from one location, port 443.
"use strict";
const https = require("https");
const { version } = require("../package.json");

const BASE = (process.env.QUANTUM_AETHER_BASE || "https://ather-quantum.com").replace(/\/+$/, "");
const GRADES = ["A", "B", "C", "F"];
const HELP = `quantum-aether ${version} — post-quantum TLS check (X25519MLKEM768)

Usage: npx quantum-aether <domain> [options]

Options:
  --json             print the raw JSON result (for scripts and agents)
  --require-pq       exit 2 if the site does not negotiate X25519MLKEM768
  --min-grade <G>    exit 2 if the grade is worse than G (A, B, C or F)
  -v, --version      print the version
  -h, --help         this help

Exit codes: 0 ok, 1 error (invalid domain, network, service), 2 policy failed.
The domain and result are stored by the hosted service and get a public result page.
Environment: QUANTUM_AETHER_BASE to use another (self-hosted) scanner.`;

function parse(argv) {
  const o = { json: false, requirePq: false, minGrade: null, domain: null, help: false, version: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--") continue;
    else if (a === "--json") o.json = true;
    else if (a === "--require-pq") o.requirePq = true;
    else if (a === "--min-grade") o.minGrade = String(argv[++i] || "").toUpperCase();
    else if (a.startsWith("--min-grade=")) o.minGrade = a.split("=")[1].toUpperCase();
    else if (a === "-h" || a === "--help") o.help = true;
    else if (a === "-v" || a === "--version") o.version = true;
    else if (a.startsWith("-")) throw new Error(`unknown option ${a}`);
    else if (!o.domain) o.domain = a;
    else throw new Error(`unexpected argument ${a}`);
  }
  if (o.minGrade !== null && !GRADES.includes(o.minGrade)) throw new Error("--min-grade must be A, B, C or F");
  return o;
}

function normalize(input) {
  let d = input.trim().toLowerCase();
  d = d.replace(/^[a-z]+:\/\//, "").split(/[/?#]/)[0].replace(/:\d+$/, "").replace(/\.$/, "");
  if (!/^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}$/.test(d)) return null;
  return d;
}

function get(url, timeoutMs = 90000) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers: { "User-Agent": `quantum-aether-cli/${version}`, Accept: "application/json" } }, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (c) => (body += c));
      res.on("end", () => resolve({ status: res.statusCode, body }));
    });
    req.setTimeout(timeoutMs, () => req.destroy(new Error("timed out")));
    req.on("error", reject);
  });
}

function report(r) {
  const pq = r.post_quantum_key_exchange;
  const lines = [
    "",
    "  Quantum Aether — post-quantum TLS check",
    `  domain        ${r.domain}`,
    `  grade         ${r.grade}`,
    `  key exchange  ${r.key_exchange_group || "unknown"}`,
    `  post-quantum  ${pq ? "YES — hybrid X25519MLKEM768" : pq === false ? "NO — classical only (harvest-now-decrypt-later risk)" : "undetermined"}`,
  ];
  if (r.tls_version) lines.push(`  TLS           ${r.tls_version}`);
  if (r.scan_url) lines.push(`  result page   ${r.scan_url}`);
  if (pq === false) lines.push(`  how to fix    ${BASE}/tools/pq-tls-config?utm_source=npm&utm_medium=cli&utm_campaign=cli`);
  lines.push(`  monitor daily ${BASE}/monitoring?domain=${encodeURIComponent(r.domain)}&utm_source=npm&utm_medium=cli&utm_campaign=cli`, "");
  return lines.join("\n");
}

async function main(argv) {
  let o;
  try { o = parse(argv); } catch (e) { console.error(`quantum-aether: ${e.message}\n\n${HELP}`); return 1; }
  if (o.version) { console.log(version); return 0; }
  if (o.help || !o.domain) { (o.help ? console.log : console.error)(HELP); return o.help ? 0 : 1; }
  const domain = normalize(o.domain);
  if (!domain) { console.error(`quantum-aether: "${o.domain}" is not a valid domain name`); return 1; }
  let res;
  try { res = await get(`${BASE}/api/v1/scan?domain=${encodeURIComponent(domain)}`); }
  catch (e) { console.error(`quantum-aether: network error: ${e.message}`); return 1; }
  let data;
  try { data = JSON.parse(res.body); } catch (_e) { data = null; }
  if (res.status >= 400 || !data || !data.grade) {
    const msg = (data && (data.message || data.error)) || res.body.trim().slice(0, 300) || `HTTP ${res.status}`;
    console.error(`quantum-aether: scan failed (HTTP ${res.status}): ${msg}`);
    return 1;
  }
  process.stdout.write(o.json ? JSON.stringify(data, null, 2) + "\n" : report(data) + "\n");
  if (o.requirePq && data.post_quantum_key_exchange !== true) return 2;
  if (o.minGrade && GRADES.includes(data.grade) && GRADES.indexOf(data.grade) > GRADES.indexOf(o.minGrade)) return 2;
  return 0;
}

if (require.main === module) main(process.argv.slice(2)).then((code) => process.exit(code));
module.exports = { parse, normalize, report, main };
