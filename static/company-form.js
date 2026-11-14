// Company billing form (agency pack and monitoring subscriptions), same rules as the audit checkout:
// every field filled, billing data in Latin script (the invoice font), a valid email and domain, and all three
// boxes ticked. Until then the pay buttons stay hidden. The server repeats every check.
// While something is missing the hint names the exact field and marks it, so the buttons never vanish silently.
(function () {
  var TEXT = ["org", "name", "email", "domain", "street", "postal_code", "city", "country"];
  var LATIN = ["org", "name", "street", "postal_code", "city", "country", "email"];
  var BOXES = ["company_buyer", "agb_consent", "contact_consent"];
  var LATIN_RE = /^[\u0020-\u007E\u00A0-\u00FF\u0152\u0153\u0160\u0161\u0178\u017D\u017E\u0192\u02C6\u02DC\u2013\u2014\u2018-\u201A\u201C-\u201E\u2020-\u2022\u2026\u2030\u2039\u203A\u20AC\u2122]*$/;
  var EMAIL_RE = /^[^@\s]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,}$/;
  var SERVER_ERRORS = { latin_required: "msgLatin", required_fields: "msgFields", consent_required: "msgFields",
                        invalid_email: "msgEmail", invalid_domain: "msgDomain", rate_limited: "msgLimit" };

  window.CompanyForm = function (form, onChange) {
    var hint = form.querySelector(".company-form-hint");
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
    function check() {
      for (var i = 0; i < TEXT.length; i++) if (!value(TEXT[i])) return { key: "msgFields", field: TEXT[i] };
      for (var j = 0; j < BOXES.length; j++) if (!form.elements[BOXES[j]].checked) return { key: "msgFields", field: BOXES[j] };
      for (var k = 0; k < LATIN.length; k++) if (!LATIN_RE.test(value(LATIN[k]))) return { key: "msgLatin", field: LATIN[k] };
      if (!EMAIL_RE.test(value("email"))) return { key: "msgEmail", field: "email" };
      if (value("domain").indexOf(".") < 0) return { key: "msgDomain", field: "domain" };
      return null;
    }
    function problem() { var p = check(); return p ? p.key : null; }
    function mark(field) {
      TEXT.concat(BOXES).forEach(function (name) {
        var el = form.elements[name];
        var bad = touched && name === field;
        el.setAttribute("aria-invalid", bad ? "true" : "false");
        el.style.outline = bad ? "2px solid #c0392b" : "";
      });
    }
    function payload() {
      var p = {};
      TEXT.forEach(function (n) { p[n] = value(n); });
      BOXES.forEach(function (n) { p[n] = form.elements[n].checked; });
      p.lang = form.dataset.lang;
      return p;
    }
    function serverMessage(code) { var key = SERVER_ERRORS[code]; return key ? form.dataset[key] : null; }
    function sync() {
      var p = check();
      if (hint) {
        var text = p ? form.dataset[p.key] : "";
        // Once the visitor has started typing, name the first field that blocks the buttons.
        if (p && touched && label(p.field)) text = "⚠ " + label(p.field) + " — " + text;
        hint.textContent = text;
        hint.hidden = !p;
        hint.className = "company-form-hint " + (p && touched ? "form-error small" : "muted small");
      }
      mark(p ? p.field : null);
      onChange(!p);
    }
    function onEdit() { touched = true; sync(); }
    form.addEventListener("input", onEdit);
    form.addEventListener("change", onEdit);
    form.addEventListener("submit", function (e) { e.preventDefault(); });
    sync();
    return { problem: problem, payload: payload, serverMessage: serverMessage,
             touch: function () { touched = true; sync(); },
             disable: function () {
               Array.prototype.forEach.call(form.querySelectorAll("input, select"), function (el) { el.disabled = true; });
             } };
  };
})();
