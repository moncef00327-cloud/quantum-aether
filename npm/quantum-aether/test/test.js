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
console.log("ok");
