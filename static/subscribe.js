// Monitoring subscription: the company form must be complete before the PayPal subscribe buttons appear.
// The server stores the billing data with a pending account, PayPal creates the subscription (EUR plan), then the
// server verifies it before activating. On the trial dashboard (data-token) the same account is upgraded.
(function () {
  var form = document.getElementById("sub-company-form");
  var message = document.getElementById("sub-message");
  var subSection = document.getElementById("subscribe");
  var token = subSection ? (subSection.dataset.token || "") : "";
  var variant = subSection ? (subSection.dataset.variant || "") : "";
  if (!window.paypal || !message || !form || !window.CompanyForm) return;
  var lang = form.dataset.lang || document.documentElement.lang || "en";
  var mounted = false, company;

  function fail(text) { message.textContent = text || message.dataset.msgError; }

  function post(url, body) {
    return fetch(url + "?lang=" + encodeURIComponent(lang), {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
    }).then(function (r) {
      return r.json().then(function (d) {
        if (!r.ok) { var text = company.serverMessage(d.error); if (text) fail(text); throw new Error(d.error || "failed"); }
        return d;
      });
    });
  }

  function mount() {
    if (mounted) return;
    mounted = true;
    document.querySelectorAll(".paypal-sub").forEach(function (box) {
      var accountId = null;
      window.paypal.Buttons({
        style: { layout: "vertical", color: "gold", shape: "rect", label: "subscribe" },
        onClick: function (_data, actions) {
          message.textContent = "";
          if (company.problem()) { company.touch(); return actions.reject(); }
          if (window.qaTrackEvent) window.qaTrackEvent("checkout_started");
          return actions.resolve();
        },
        createSubscription: function (_data, actions) {
          var body = company.payload();
          body.plan = box.dataset.plan;
          body.variant = variant;
          var start = token ? post("/api/monitor/upgrade", Object.assign(body, { token: token }))
                            : post("/api/monitor/signup", body);
          return start.then(function (d) {
            accountId = d.account_id;
            return actions.subscription.create({ plan_id: d.plan_id, custom_id: d.account_id });
          });
        },
        onApprove: function (data) {
          var body = { account_id: accountId, subscription_id: data.subscriptionID };
          if (token) body.token = token;
          return post("/api/monitor/activate", body)
            .then(function (d) { company.disable(); window.location.assign(d.dashboard_url); })
            .catch(function () { fail(); });
        },
        onError: function () { if (!message.textContent) fail(); }
      }).render(box);
    });
  }

  company = window.CompanyForm(form, function (ok) {
    if (ok) mount();
    document.querySelectorAll(".paypal-sub").forEach(function (box) { box.hidden = !ok; });
  });
})();
