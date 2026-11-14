// The PayPal button is mounted only after every required business, billing and consent field is valid.
(function () {
  var form = document.getElementById("audit-checkout-form");
  var container = document.getElementById("audit-paypal-buttons");
  var message = document.getElementById("audit-pay-message");
  if (!form || !container || !window.paypal) return;

  var mounted = false;
  function valid() { return form.checkValidity(); }
  function syncVisibility() {
    if (valid() && !mounted) {
      mounted = true;
      window.paypal.Buttons({
        style: { layout: "vertical", color: "gold", shape: "rect", label: "paypal" },
        onClick: function (_data, actions) {
          if (!valid()) { form.reportValidity(); return actions.reject(); }
          message.textContent = "";
          return actions.resolve();
        },
        createOrder: function () {
          var payload = {};
          ["name", "email", "org", "street", "postal_code", "city", "country", "domain"].forEach(function (key) {
            payload[key] = form.elements[key].value.trim();
          });
          payload.company_buyer = form.elements.company_buyer.checked;
          payload.agb_consent = form.elements.agb_consent.checked;
          payload.contact_consent = form.elements.contact_consent.checked;
          payload.lang = form.dataset.lang;
          return fetch("/api/paypal/audit", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
          }).then(function (response) {
            return response.json().then(function (data) {
              if (!response.ok || !data.id) throw new Error(data.error || "create_failed");
              return data.id;
            });
          });
        },
        onApprove: function (data, actions) {
          return fetch("/api/paypal/audit/" + encodeURIComponent(data.orderID) + "/capture", { method: "POST" })
            .then(function (response) {
              return response.json().then(function (result) {
                if (result.error === "INSTRUMENT_DECLINED") return actions.restart();
                if (!response.ok || result.status !== "COMPLETED") throw new Error(result.error || "capture_failed");
                container.hidden = true;
                message.textContent = result.invoice_email_sent
                  ? container.dataset.msgSuccess.replace("{invoice_number}", result.invoice_number)
                  : container.dataset.msgEmailPending;
              });
            });
        },
        onError: function () { message.textContent = container.dataset.msgError; }
      }).render(container);
    }
    container.hidden = !valid();
  }
  form.addEventListener("input", syncVisibility);
  form.addEventListener("change", syncVisibility);
  syncVisibility();
})();
