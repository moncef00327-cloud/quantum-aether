// الدفع بـ USDT/USDC: الخادم ينشئ طلباً بمبلغ فريد، ثم يتحقق من رقم المعاملة على الشبكة نفسها قبل فتح التقرير.
(function () {
  var box = document.getElementById("crypto-pay");
  if (!box) return;
  var msgs = JSON.parse(box.dataset.msg);
  var consent = document.getElementById("consent");
  var details = box.querySelector(".crypto-details");
  var message = box.querySelector(".crypto-message");
  var order = null;

  function say(text) { message.textContent = text || ""; }
  function fill(template, values) {
    return template.replace(/\{(\w+)\}/g, function (_m, k) { return values[k] != null ? values[k] : ""; });
  }

  box.querySelector(".crypto-create").addEventListener("click", function () {
      if (!consent || !consent.checked) { say(box.dataset.msgConsent); return; }
      say("");
      fetch("/api/crypto/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scan_id: box.dataset.scanId, network: box.querySelector(".crypto-network").value, consent: true,
                               email: (box.querySelector(".crypto-email") || {}).value || "" })
      }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          if (!res.ok) { say(res.d.error === "already_paid" ? null : msgs.choose_failed); if (res.d.error === "already_paid") location.reload(); return; }
          order = res.d;
          box.querySelector(".crypto-amount").textContent = order.amount;
          box.querySelector(".crypto-token").textContent = order.token;
          box.querySelector(".crypto-chain").textContent = order.chain;
          box.querySelector(".crypto-address").textContent = order.pay_to;
          details.hidden = false;
        })
        .catch(function () { say(msgs.choose_failed); });
  });

  box.querySelector(".crypto-copy").addEventListener("click", function () {
    if (!order || !navigator.clipboard) return;
    navigator.clipboard.writeText(order.pay_to).then(function () { say(msgs.copied); });
  });

  box.querySelector(".crypto-verify").addEventListener("click", function () {
    if (!order) return;
    var tx = box.querySelector(".crypto-tx").value.trim();
    if (!/^0x[0-9a-fA-F]{64}$/.test(tx)) { say(msgs.invalid_tx_hash); return; }
    var button = this;
    button.disabled = true;
    say("…");
    fetch("/api/crypto/orders/" + encodeURIComponent(order.order_id) + "/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tx_hash: tx })
    }).then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.report_url) { location.assign(d.report_url); return; }
        var key = (d.status || d.error || "chain_unavailable").toLowerCase();
        say(fill(msgs[key] || msgs.chain_unavailable, {
          c: d.confirmations, n: d.confirmations_required, token: order.token,
          received: d.received, expected: d.expected || order.amount
        }));
      })
      .catch(function () { say(msgs.chain_unavailable); })
      .then(function () { button.disabled = false; });
  });
})();
