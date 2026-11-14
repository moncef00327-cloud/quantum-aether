// Offline unit tests (no network): node test/test.js
"use strict";
const assert = require("assert");
const { parse, normalize, report } = require("../bin/cli.js");
assert.strictEqual(normalize("https://Example.com/path?q=1"), "example.com");
assert.strictEqual(normalize("example.com:443"), "example.com");
assert.strictEqual(normalize("not a domain"), null);
assert.strictEqual(normalize("localhost"), null);
assert.deepStrictEqual(parse(["x.com", "--json", "--min-grade", "b"]).minGrade, "B");
assert.throws(() => parse(["x.com", "--min-grade", "Z"]));
assert.throws(() => parse(["--bogus"]));
const text = report({ domain: "x.com", grade: "B", key_exchange_group: "x25519", post_quantum_key_exchange: false, tls_version: "TLSv1.3" });
assert.ok(text.includes("NO — classical") && text.includes("pq-tls-config"));
const unknown = report({ domain: "x.com", grade: "B", key_exchange_group: null, post_quantum_key_exchange: false,
  observation_status: "undetermined", tls_version: "TLSv1.3" });
assert.ok(unknown.includes("undetermined") && !unknown.includes("NO — classical") && !unknown.includes("pq-tls-config"));
const yes = report({ domain: "x.com", grade: "A", key_exchange_group: "X25519MLKEM768", post_quantum_key_exchange: true,
  observation_status: "observed_pq" });
assert.ok(yes.includes("YES — hybrid"));
console.log("ok");
