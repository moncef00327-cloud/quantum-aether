// زر PayPal: الطلب يُنشأ ويُلتقط على خادمنا، فلا يُفتح التقرير إلا بعد تحقق الخادم من الدفع.
(function () {
  var container = document.getElementById("paypal-button-container");
  if (!container || !window.paypal) return;
  var message = document.getElementById("pay-message");
  var scanId = container.dataset.scanId;
  var consent = document.getElementById("consent");

  function fail(text) { message.textContent = text || container.dataset.msgError; }
  // خانة الموافقة فوق أزرار الدفع وقد تكون خارج الشاشة على الجوال: نمرّر إليها ونبرزها بدل رسالة لا يُعرف مكانها.
  function showConsent(el) {
    if (!el) return;
    var label = el.closest("label") || el;
    try { label.scrollIntoView({ block: "center" }); } catch (e) { label.scrollIntoView(); }
    el.focus({ preventScroll: true });
    label.style.outline = "3px solid #f59e0b"; label.style.outlineOffset = "4px"; label.style.borderRadius = "6px";
    setTimeout(function () { label.style.outline = ""; label.style.outlineOffset = ""; }, 4000);
    el.addEventListener("change", function () { label.style.outline = ""; }, { once: true });
  }


  window.paypal.Buttons({
    style: { layout: "vertical", color: "gold", shape: "rect", label: "paypal" },
    onClick: function (_data, actions) {
      // الموافقة الصريحة على التسليم الفوري شرط قبل فتح نافذة الدفع.
      if (!consent || !consent.checked) { fail(container.dataset.msgConsent); showConsent(consent); return actions.reject(); }
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
