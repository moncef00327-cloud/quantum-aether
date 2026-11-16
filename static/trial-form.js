/* Trial forms (any form posting to /monitoring/trial, including the home page app):
   check email, domain and consent before sending and say clearly what is missing, in the page language.
   The browser's own bubbles were easy to miss (consent box sits below the button), so clicks never became requests.
   The server checks everything again; this only explains. No text the visitor typed is sent to analytics. */
(function () {
  var lang = (document.documentElement.lang || "en").slice(0, 2);
  var ALL = {
    en: { email: "Please enter a valid email address, for example security@company.com.",
          domain: "Personal mailboxes are welcome: please also enter the domain to monitor (for example company.com).",
          consent: "Almost done: please tick the box to accept the Terms and the Privacy Policy, then press the button again." },
    de: { email: "Bitte geben Sie eine gültige E-Mail-Adresse ein, z. B. security@firma.at.",
          domain: "Private Adressen sind willkommen: Bitte geben Sie zusätzlich die zu überwachende Domain ein (z. B. firma.at).",
          consent: "Fast geschafft: Bitte bestätigen Sie die AGB und die Datenschutzerklärung (Kästchen anhaken) und klicken Sie erneut." },
    ar: { email: "اكتب بريداً صحيحاً، مثل security@company.com.",
          domain: "البريد الشخصي مقبول: اكتب أيضاً النطاق المراد مراقبته (مثل company.com).",
          consent: "بقيت خطوة: ضع علامة الموافقة على الشروط وسياسة الخصوصية، ثم اضغط الزر مرة أخرى." }
  };
  var MSG = ALL[lang] || ALL.en;
  var REASON = { email: "bad_email", domain: "need_domain", consent: "consent_missing" };
  var FREE = ("gmail.com googlemail.com outlook.com hotmail.com hotmail.de live.com live.de msn.com yahoo.com yahoo.de " +
    "ymail.com icloud.com me.com mac.com aol.com gmx.at gmx.de gmx.net gmx.ch web.de t-online.de freenet.de aon.at " +
    "chello.at a1.net bluewin.ch proton.me protonmail.com pm.me mail.com mail.ru yandex.com yandex.ru zoho.com " +
    "tutanota.com tuta.io posteo.de mailbox.org outlook.de qq.com 163.com").split(" ");
  var EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  var sent = {};
  function ev(name, form, reason) {
    var key = name + ":" + (reason || "");
    if (sent[key]) return;
    sent[key] = true;
    try {
      var src = "";
      if (form) src = form.getAttribute("data-trial-source") || ((form.querySelector('[name="src"]') || {}).value) || "";
      var detail = src || "";
      if (reason) detail = src ? (src + "|" + reason) : reason;
      var body = JSON.stringify({ name: name, page: location.pathname, lang: document.documentElement.lang, detail: detail });
      if (navigator.sendBeacon) navigator.sendBeacon("/api/ev", body);
      else fetch("/api/ev", { method: "POST", body: body, keepalive: true });
    } catch (e) { /* analytics are optional */ }
  }
  function isTrial(form) {
    return !!(form && form.getAttribute && /\/monitoring\/trial/.test(form.getAttribute("action") || ""));
  }
  function box(form) {
    var el = form.querySelector(".trial-error");
    if (!el) {
      el = document.createElement("p");
      el.className = "form-error trial-error";
      el.setAttribute("role", "alert");
      form.insertBefore(el, form.firstChild);
    }
    el.style.cssText = "color:#ff6b6b;font-weight:600;margin:0 0 .6rem";
    return el;
  }
  // Take over validation only for trial forms: set before the browser runs its own check on this click/Enter.
  document.addEventListener("click", function (e) {
    var b = e.target && e.target.closest ? e.target.closest("button, input[type=submit]") : null;
    if (!b || (b.type && b.type !== "submit")) return;
    var f = b.form || b.closest("form");
    if (isTrial(f)) f.noValidate = true;
  }, true);
  document.addEventListener("submit", function (e) {
    var f = e.target;
    if (!isTrial(f)) return;
    var email = f.querySelector('[name="email"]'), domain = f.querySelector('[name="domain"]'),
        consent = f.querySelector('input[type="checkbox"][name="consent"]');
    var v = ((email && email.value) || "").trim().toLowerCase(), problem = null, field = null;
    if (!EMAIL.test(v)) { problem = "email"; field = email; }
    else if (domain && domain.type !== "hidden" && !domain.value.trim() && FREE.indexOf(v.split("@").pop()) >= 0) { problem = "domain"; field = domain; }
    else if (consent && !consent.checked) { problem = "consent"; field = consent; }
    [email, domain, consent].forEach(function (x) { if (x) x.removeAttribute("aria-invalid"); });
    if (problem) {
      e.preventDefault();
      var el = box(f);
      el.textContent = MSG[problem];
      el.hidden = false;
      if (field) {
        field.setAttribute("aria-invalid", "true");
        try { field.focus({ preventScroll: true }); } catch (x) { field.focus(); }
        (field.closest("label, p, div") || field).scrollIntoView({ block: "center", behavior: "smooth" });
        if (problem === "consent") {
          var label = field.closest("label") || field.parentNode;
          label.style.outline = "2px solid #ff6b6b"; label.style.outlineOffset = "4px"; label.style.borderRadius = "4px";
        }
      }
      ev("trial_invalid", f, REASON[problem] || problem);
      return;
    }
    var old = f.querySelector(".trial-error");
    if (old) old.hidden = true;
    ev("trial_submit", f);
  }, true);
  document.addEventListener("change", function (e) {
    var t = e.target;
    if (t && t.name === "consent" && t.checked && isTrial(t.form)) {
      var label = t.closest("label") || t.parentNode;
      label.style.outline = "";
      t.removeAttribute("aria-invalid");
    }
  }, true);
})();
