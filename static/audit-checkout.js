// Small-company audit checkout. The PayPal buttons stay hidden until every field is filled, the billing data is
// in Latin script (the invoice font), and all three boxes are ticked. The server repeats every check.
// While something is missing the hint names the exact field and marks it, so the buttons never vanish silently.
(function () {
  var form = document.getElementById("audit-checkout-form");
  var container = document.getElementById("audit-paypal-buttons");
  var message = document.getElementById("audit-pay-message");
  var hint = document.getElementById("audit-form-hint");
  if (!form) return;

  var TEXT = ["org", "name", "email", "domain", "street", "postal_code", "city", "country"];
  var LATIN = ["org", "name", "street", "postal_code", "city", "country", "email"];
  var BOXES = ["company_buyer", "agb_consent", "contact_consent"];
  // Printable cp1252 (Latin-1 + the Windows-1252 extras such as the euro sign and dashes).
  var LATIN_RE = /^[\u0020-\u007E\u00A0-\u00FF\u0152\u0153\u0160\u0161\u0178\u017D\u017E\u0192\u02C6\u02DC\u2013\u2014\u2018-\u201A\u201C-\u201E\u2020-\u2022\u2026\u2030\u2039\u203A\u20AC\u2122]*$/;
  var EMAIL_RE = /^[^@\s]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,}$/;
  var SERVER_ERRORS = { latin_required: "msgLatin", required_fields: "msgFields", consent_required: "msgFields",
                        invalid_email: "msgEmail", invalid_domain: "msgDomain", rate_limited: "msgLimit" };
  var touched = false;

  function value(name) { return (form.elements[name].value || "").trim(); }
  function label(name) {
    var el = form.elements[name];
    var lab = el && el.closest("label");
    if (!lab) return "";
    var span = lab.querySelector("span");
    var text = (span ? span.textContent : lab.textContent).replace(/\s+/g, " ").trim();
    return text.length > 70 ? text.slice(0, 67) + "…" : text;
  }
  function problem() {
    for (var i = 0; i < TEXT.length; i++) if (!value(TEXT[i])) return { key: "msgFields", field: TEXT[i] };
    for (var j = 0; j < BOXES.length; j++) if (!form.elements[BOXES[j]].checked) return { key: "msgFields", field: BOXES[j] };
    for (var k = 0; k < LATIN.length; k++) if (!LATIN_RE.test(value(LATIN[k]))) return { key: "msgLatin", field: LATIN[k] };
    if (!EMAIL_RE.test(value("email"))) return { key: "msgEmail", field: "email" };
    if (value("domain").indexOf(".") < 0) return { key: "msgDomain", field: "domain" };
    return null;
  }
  function mark(field) {
    TEXT.concat(BOXES).forEach(function (name) {
      var el = form.elements[name];
      var bad = touched && name === field;
      el.setAttribute("aria-invalid", bad ? "true" : "false");
      el.style.outline = bad ? "2px solid #c0392b" : "";
    });
  }

  var mounted = false;
  function mount() {
    if (mounted || !container) return;
    if (!window.paypal) { if (message) message.textContent = container.dataset.msgError; return; }
    mounted = true;
    window.paypal.Buttons({
      style: { layout: "vertical", color: "gold", shape: "rect", label: "paypal" },
      onClick: function (_data, actions) {
        if (problem()) { touched = true; sync(); return actions.reject(); }
        if (message) message.textContent = "";
        return actions.resolve();
      },
      createOrder: function () {
        var payload = {};
        TEXT.forEach(function (key) { payload[key] = value(key); });
        BOXES.forEach(function (key) { payload[key] = form.elements[key].checked; });
        payload.lang = form.dataset.lang;
        return fetch("/api/paypal/audit", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
        }).then(function (response) {
          return response.json().then(function (data) {
            if (!response.ok || !data.id) {
              var key = SERVER_ERRORS[data.error];
              if (key && message) message.textContent = form.dataset[key];
              throw new Error(data.error || "create_failed");
            }
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
              form.querySelectorAll("input, select").forEach(function (el) { el.disabled = true; });
              message.textContent = result.invoice_email_sent
                ? container.dataset.msgSuccess.replace("{invoice_number}", result.invoice_number)
                : container.dataset.msgEmailPending;
            });
          });
      },
      onError: function () { if (message && !message.textContent) message.textContent = container.dataset.msgError; }
    }).render(container);
  }

  function sync() {
    var p = problem();
    if (hint) {
      var text = p ? form.dataset[p.key] : "";
      // Once the visitor has started typing, name the first field that blocks the buttons.
      if (p && touched && label(p.field)) text = "⚠ " + label(p.field) + " — " + text;
      hint.textContent = text;
      hint.hidden = !p;
      hint.className = p && touched ? "form-error small" : "muted small";
    }
    mark(p ? p.field : null);
    if (!container) return;
    if (!p) mount();
    container.hidden = !!p;
  }
  function onEdit() { touched = true; sync(); }
  form.addEventListener("input", onEdit);
  form.addEventListener("change", onEdit);
  form.addEventListener("submit", function (e) { e.preventDefault(); });
  sync();
})();
