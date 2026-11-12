// اشتراك المراقبة: الخادم ينشئ حساباً معلقاً، PayPal ينشئ الاشتراك، ثم يتحقق الخادم منه قبل التفعيل.
(function () {
  var message = document.getElementById("sub-message");
  var emailInput = document.getElementById("sub-email");
  var consent = document.getElementById("consent");
  var subSection = document.getElementById("subscribe");
  var initialDomain = subSection ? (subSection.dataset.domain || "") : "";
  if (!window.paypal || !message || !emailInput) return;
  var lang = document.documentElement.lang || "en";

  function fail(text, target) {
    message.textContent = text || message.dataset.msgError;
    if (target && target.focus) {
      try { target.scrollIntoView({ behavior: "smooth", block: "center" }); } catch (e) {}
      target.focus();
    }
  }

  function post(url, body) {
    return fetch(url + "?lang=" + encodeURIComponent(lang), {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
    }).then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || "failed"); return d; }); });
  }

  document.querySelectorAll(".paypal-sub").forEach(function (box) {
    var accountId = null;
    window.paypal.Buttons({
      style: { layout: "vertical", color: "gold", shape: "rect", label: "subscribe" },
      onClick: function (_data, actions) {
        message.textContent = "";
        if (!emailInput.checkValidity() || !emailInput.value) { fail(message.dataset.msgEmail, emailInput); return actions.reject(); }
        if (!consent || !consent.checked) { fail(message.dataset.msgConsent, consent); return actions.reject(); }
        return actions.resolve();
      },
      createSubscription: function (_data, actions) {
        return post("/api/monitor/signup", { email: emailInput.value, plan: box.dataset.plan, consent: consent.checked, domain: initialDomain }).then(function (d) {
          accountId = d.account_id;
          return actions.subscription.create({ plan_id: d.plan_id, custom_id: d.account_id });
        });
      },
      onApprove: function (data) {
        return post("/api/monitor/activate", { account_id: accountId, subscription_id: data.subscriptionID })
          .then(function (d) { window.location.assign(d.dashboard_url); })
          .catch(function () { fail(); });
      },
      onError: function () { fail(); }
    }).render(box);
  });
})();
