// Agency pack checkout: the company form must be complete before the PayPal buttons (PayPal, card, EPS where
// PayPal offers it) appear. The server creates and captures the order and verifies amount and currency.
(function () {
  var form = document.getElementById("pack-checkout-form");
  var container = document.getElementById("paypal-button-container");
  var message = document.getElementById("pay-message");
  if (!form || !container || !window.CompanyForm) return;
  var mounted = false, company;

  function fail(text) { message.textContent = text || container.dataset.msgError; }

  function mount() {
    if (mounted || !window.paypal) return;
    mounted = true;
    window.paypal.Buttons({
      style: { layout: "vertical", color: "gold", shape: "rect", label: "pay" },
      onClick: function (_data, actions) {
        if (company.problem()) { company.touch(); return actions.reject(); }
        message.textContent = "";
        return actions.resolve();
      },
      createOrder: function () {
        message.textContent = "";
        return fetch("/api/paypal/packs?lang=" + encodeURIComponent(form.dataset.lang), {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(company.payload())
        }).then(function (response) {
          return response.json().then(function (data) {
            if (!response.ok || !data.id) {
              var text = company.serverMessage(data.error);
              if (text) fail(text);
              throw new Error(data.error || "create_failed");
            }
            return data.id;
          });
        });
      },
      onApprove: function (data, actions) {
        return fetch("/api/paypal/packs/" + encodeURIComponent(data.orderID) + "/capture", { method: "POST" })
          .then(function (response) { return response.json(); })
          .then(function (result) {
            if (result.error === "INSTRUMENT_DECLINED") return actions.restart();
            if (result.pack_url) { company.disable(); window.location.assign(result.pack_url); return; }
            fail(result.status === "PENDING" ? container.dataset.msgPending : null);
          });
      },
      onError: function () { if (!message.textContent) fail(); }
    }).render(container);
  }

  company = window.CompanyForm(form, function (ok) {
    if (ok) mount();
    container.hidden = !ok;
  });
})();
