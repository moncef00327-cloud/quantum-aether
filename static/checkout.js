// زر PayPal: الطلب يُنشأ ويُلتقط على خادمنا، فلا يُفتح التقرير إلا بعد تحقق الخادم من الدفع.
(function () {
  var container = document.getElementById("paypal-button-container");
  if (!container || !window.paypal) return;
  var message = document.getElementById("pay-message");
  var scanId = container.dataset.scanId;
  var consent = document.getElementById("consent");

  function fail(text) { message.textContent = text || container.dataset.msgError; }

  window.paypal.Buttons({
    style: { layout: "vertical", color: "gold", shape: "rect", label: "paypal" },
    onClick: function (_data, actions) {
      // الموافقة الصريحة على التسليم الفوري شرط قبل فتح نافذة الدفع.
      if (!consent || !consent.checked) { fail(container.dataset.msgConsent); return actions.reject(); }
      message.textContent = "";
      return actions.resolve();
    },
    createOrder: function () {
      message.textContent = "";
      return fetch("/api/paypal/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scan_id: scanId, consent: !!(consent && consent.checked) })
      }).then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok || !data.id) throw new Error(data.error || "create_failed");
          return data.id;
        });
      });
    },
    onApprove: function (data, actions) {
      return fetch("/api/paypal/orders/" + encodeURIComponent(data.orderID) + "/capture", { method: "POST" })
        .then(function (response) { return response.json(); })
        .then(function (result) {
          if (result.error === "INSTRUMENT_DECLINED") return actions.restart();
          if (result.report_url) { window.location.assign(result.report_url); return; }
          fail(result.status === "PENDING" ? container.dataset.msgPending : null);
        });
    },
    onError: function () { fail(); }
  }).render("#paypal-button-container");
})();
