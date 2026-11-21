/* Trial forms (any form posting to /monitoring/trial, including the home page app):
   check email, domain and consent before sending and say clearly what is missing, in the page language.
   The browser's own bubbles were easy to miss (consent box sits below the button), so clicks never became requests.
   The server checks everything again; this only explains. No text the visitor typed is sent to analytics. */
(function () {
  var lang = (document.documentElement.lang || "en").slice(0, 2);
  var ALL = {
    en: { empty: "Email required: enter your work email to receive your monitoring activation link.",
          emptyDom: "Email required: enter your work email to receive your monitoring activation link for {domain}.",
          email: "Please enter a valid email address, for example security@company.com.",
          domain: "Personal mailboxes are welcome: please also enter the domain to monitor (for example company.com).",
          consent: "Accept the Terms and Privacy Policy to start your free trial." },
    de: { empty: "E-Mail-Adresse fehlt: Geben Sie Ihre geschäftliche E-Mail-Adresse ein, um den Aktivierungslink für die Überwachung zu erhalten.",
          emptyDom: "E-Mail-Adresse fehlt: Geben Sie Ihre geschäftliche E-Mail-Adresse ein, um den Aktivierungslink für die Überwachung von {domain} zu erhalten.",
          email: "Bitte geben Sie eine gültige E-Mail-Adresse ein, z. B. security@firma.at.",
          domain: "Private Adressen sind willkommen: Bitte geben Sie zusätzlich die zu überwachende Domain ein (z. B. firma.at).",
          consent: "Bestätigen Sie die AGB und die Datenschutzerklärung, um den kostenlosen Test zu starten." },
    ar: { empty: "البريد مطلوب: أدخل بريد العمل لإرسال رابط تفعيل المراقبة.",
          emptyDom: "البريد مطلوب: أدخل بريد العمل لإرسال رابط تفعيل المراقبة لـ {domain}.",
          email: "اكتب بريداً صحيحاً، مثل security@company.com.",
          domain: "البريد الشخصي مقبول: اكتب أيضاً النطاق المراد مراقبته (مثل company.com).",
          consent: "وافق على الشروط وسياسة الخصوصية لبدء التجربة المجانية." }
  };
  var EXTRA = {
    en: { domainOnly: "That looks like a domain. Enter an email address at it, for example {example}.",
          typo: "Did you mean {fix}? Correct it, or press the button again to send it as typed." },
    de: { domainOnly: "Das sieht nach einer Domain aus. Geben Sie eine E-Mail-Adresse dort ein, z. B. {example}.",
          typo: "Meinten Sie {fix}? Korrigieren Sie die Adresse oder klicken Sie erneut, um sie so zu senden." },
    ar: { domainOnly: "هذا يبدو نطاقاً لا بريداً. اكتب بريداً عليه، مثل {example}.",
          typo: "هل تقصد {fix}؟ صحّحه، أو اضغط الزر مرة أخرى للإرسال كما هو." }
  };
  var MSG = ALL[lang] || ALL.en;
  var MORE = EXTRA[lang] || EXTRA.en;
  MSG.domainOnly = MORE.domainOnly; MSG.typo = MORE.typo;
  var REASON = { empty: "empty_email", email: "bad_email", domainOnly: "bad_email", typo: "email_typo",
                 domain: "need_domain", consent: "consent_missing" };
  var TYPO = { "gmial.com": "gmail.com", "gamil.com": "gmail.com", "gmai.com": "gmail.com", "gmail.co": "gmail.com",
               "gmail.con": "gmail.com", "gnail.com": "gmail.com", "hotmial.com": "hotmail.com", "hotmai.com": "hotmail.com",
               "hotmail.co": "hotmail.com", "outlok.com": "outlook.com", "outlook.co": "outlook.com", "yahooo.com": "yahoo.com",
               "yaho.com": "yahoo.com", "icloud.co": "icloud.com", "iclod.com": "icloud.com" };
  // Same clean-up as the server (quantum_saas_app.clean_email): bidi marks and spaces from RTL pages, full-width @.
  function clean(s) {
    return String(s).replace(/[​-‏‪-‮⁦-⁩﻿\s]/g, "").replace(/＠/g, "@")
      .replace(/^mailto:/i, "").replace(/^[<"']+|[>"'.,;:]+$/g, "").toLowerCase();
  }
  // Shape of a rejected address for analytics, never the address itself.
  function shape(s) {
    if (s.indexOf("@") < 0) return /^(https?:\/\/)?[a-z0-9-]+(\.[a-z0-9-]+)+\/?/.test(s) ? "domain_only" : "no_at";
    if (s.split("@").length > 2) return "two_at";
    if (s.split("@").pop().indexOf(".") < 0) return "no_dot";
    return "other";
  }
  var FREE = ("gmail.com googlemail.com outlook.com hotmail.com hotmail.de live.com live.de msn.com yahoo.com yahoo.de " +
    "ymail.com icloud.com me.com mac.com aol.com gmx.at gmx.de gmx.net gmx.ch web.de t-online.de freenet.de aon.at " +
    "chello.at a1.net bluewin.ch proton.me protonmail.com pm.me mail.com mail.ru yandex.com yandex.ru zoho.com " +
    "tutanota.com tuta.io posteo.de mailbox.org outlook.de qq.com 163.com").split(" ");
  var EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  var sent = {};
  var PLAN_CSS = ".trial-plan-switch{display:grid!important;grid-template-columns:1fr 1fr;gap:10px;margin:.5rem 0 1rem}" +
    ".service-content button.trial-plan-pill,.qa-trial button.trial-plan-pill,button.trial-plan-pill{" +
    "display:flex!important;flex-direction:column!important;align-items:center!important;justify-content:center!important;gap:3px!important;" +
    "padding:10px 12px!important;min-height:58px!important;border-radius:16px!important;" +
    "border:1px solid rgba(148,163,184,.32)!important;background:rgba(15,12,28,.78)!important;" +
    "color:#cbd5e1!important;box-shadow:none!important;cursor:pointer;text-align:center!important;line-height:1.3!important;" +
    "transition:border-color .15s,background .15s,color .15s,box-shadow .15s}" +
    "button.trial-plan-pill .trial-plan-main{display:block;font-size:15px;font-weight:700;white-space:nowrap;letter-spacing:.01em;color:inherit}" +
    "button.trial-plan-pill .trial-plan-sub{display:block;font-size:12px;font-weight:500;white-space:nowrap;opacity:.85;color:inherit}" +
    ".service-content button.trial-plan-pill.is-active,.qa-trial button.trial-plan-pill.is-active,button.trial-plan-pill[aria-pressed='true']{" +
    "border:1.5px solid #67e8f9!important;background:rgba(103,232,249,.16)!important;color:#ffffff!important;" +
    "box-shadow:0 0 16px rgba(103,232,249,.22),inset 0 1px 0 rgba(255,255,255,.15)!important}" +
    "button.trial-plan-pill[aria-pressed='true'] .trial-plan-main::before{content:'✓ ';color:#67e8f9}" +
    "article.card[data-select-plan],.price-box[data-select-plan]{cursor:pointer}" +
    "article.card.is-plan-selected,.price-box.is-plan-selected{border-color:#67e8f9!important;box-shadow:0 0 0 1px rgba(103,232,249,.35)}";
  if (typeof document !== "undefined" && !document.getElementById("trial-plan-style")) {
    var st = document.createElement("style");
    st.id = "trial-plan-style";
    st.textContent = PLAN_CSS;
    (document.head || document.documentElement).appendChild(st);
  }
  function selectPlan(plan, price) {
    if (plan !== "starter" && plan !== "business") return;
    if (!price) {
      var ref = document.querySelector('[data-select-plan="' + plan + '"][data-price]');
      if (ref) price = ref.getAttribute("data-price");
      else {
        var sec = document.querySelector("[data-starter-price]");
        if (sec) price = sec.getAttribute(plan === "business" ? "data-business-price" : "data-starter-price");
      }
    }
    if (price) {
      document.querySelectorAll("[data-trial-price]").forEach(function (el) { el.textContent = price; });
    }
    document.querySelectorAll('form[action*="/monitoring/trial"] input[name="plan"]').forEach(function (inp) {
      inp.value = plan;
    });
    document.querySelectorAll(".trial-plan-pill[data-select-plan]").forEach(function (btn) {
      var active = btn.getAttribute("data-select-plan") === plan;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
    document.querySelectorAll("article.card[data-select-plan], .price-box[data-select-plan]").forEach(function (card) {
      card.classList.toggle("is-plan-selected", card.getAttribute("data-select-plan") === plan);
    });
    try { if (price) sessionStorage.setItem("qa_selected_plan", JSON.stringify({ plan: plan, price: price })); } catch (e) {}
  }
  try {
    var qPlan = new URLSearchParams(location.search).get("plan");
    if (qPlan === "starter" || qPlan === "business") {
      selectPlan(qPlan);
    } else {
      var saved = JSON.parse(sessionStorage.getItem("qa_selected_plan") || "null");
      if (saved && (saved.plan === "starter" || saved.plan === "business")) selectPlan(saved.plan, saved.price);
    }
  } catch (e) {}
  document.addEventListener("click", function (e) {
    var target = e.target && e.target.closest ? e.target.closest("[data-select-plan]") : null;
    if (!target) return;
    var plan = target.getAttribute("data-select-plan");
    var price = target.getAttribute("data-price");
    selectPlan(plan, price);
    var link = e.target && e.target.closest ? e.target.closest("a[href*='#trial']") : null;
    if (link) {
      var trialEl = document.getElementById("trial") || document.getElementById("trial-form");
      if (trialEl) {
        e.preventDefault();
        try {
          var u = new URL(window.location.href);
          u.searchParams.set("plan", plan);
          u.hash = "trial";
          window.history.replaceState(null, "", u.pathname + u.search + u.hash);
        } catch (err) {}
        trialEl.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  });
  function ev(name, form, reason) {
    var key = name + ":" + (reason || "");
    if (sent[key]) return;
    sent[key] = true;
    try {
      var src = "";
      if (form) src = form.getAttribute("data-trial-source") || ((form.querySelector('[name="src"]') || {}).value) || "";
      // Pages without an explicit source (e.g. /pricing, /business) are named after the page.
      if (!src) src = (location.pathname.replace(/^\/+/, "").split("/")[0] || "home").toLowerCase();
      // "source|reason" (2026-11-21): the server keeps "|" in event details, so the two parts stay separable.
      var detail = reason ? (src + "|" + reason) : src;
      var body = JSON.stringify({ name: name, page: location.pathname, lang: document.documentElement.lang, detail: detail });
      if (navigator.sendBeacon) navigator.sendBeacon("/api/ev", body);
      else fetch("/api/ev", { method: "POST", body: body, keepalive: true });
    } catch (e) { /* analytics are optional */ }
  }
  function isTrial(form) {
    return !!(form && form.getAttribute && /\/monitoring\/trial/.test(form.getAttribute("action") || ""));
  }
  function box(form, isGuide, field) {
    var el = form.querySelector(".trial-error");
    if (!el) {
      el = document.createElement("p");
      el.className = "trial-error";
      el.id = (form.id || ("trial-form-" + Math.random().toString(36).slice(2, 8))) + "-msg";
      form.insertBefore(el, form.firstChild);
    }
    // Missing email: show the message right under the email box (not above the label), so it is seen with the field.
    if (isGuide && field && field.name === "email") {
      var row = field.closest(".scan-row") || field;
      if (row.nextSibling !== el) row.parentNode.insertBefore(el, row.nextSibling);
      field.setAttribute("aria-describedby", el.id);
    }
    el.classList.toggle("form-error", !isGuide);
    el.setAttribute("role", "alert");
    // Missing email (2026-11-21): a clear error box under the field, not a soft cyan hint (6 empty submits that day,
    // 5 of them on /pricing, and nobody retried).
    el.style.cssText = isGuide
      ? "color:#fecaca;background:rgba(255,107,107,.14);border:1px solid rgba(255,107,107,.6);padding:8px 12px;border-radius:10px;font-weight:600;margin:.4rem 0 .7rem"
      : "color:#ff6b6b;font-weight:600;margin:0 0 .6rem";
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
    var v = clean((email && email.value) || ""), problem = null, field = null, kind = "";
    if (email && email.value !== v) email.value = v;  // pasted RTL marks, spaces, full-width @, mailto:
    var domVal = ((domain && domain.value) || "").trim();
    if (!v) { problem = "empty"; field = email; }
    else if (!EMAIL.test(v)) {
      kind = shape(v);
      var asDomain = v.replace(/^https?:\/\//, "").replace(/^www\./, "").split("/")[0];
      if (kind === "domain_only" && domain && domain.type !== "hidden" && !domVal) domain.value = asDomain;
      problem = kind === "domain_only" ? "domainOnly" : "email"; field = email;
    }
    else if (TYPO[v.split("@").pop()] && !f.getAttribute("data-typo-ok")) {
      kind = "typo"; problem = "typo"; field = email;
      f.setAttribute("data-typo-ok", "1");  // second click sends as typed
    }
    else if (domain && domain.type !== "hidden" && !domVal && FREE.indexOf(v.split("@").pop()) >= 0) { problem = "domain"; field = domain; }
    else if (consent && !consent.checked) { problem = "consent"; field = consent; }
    [email, domain, consent].forEach(function (x) { if (x) { x.removeAttribute("aria-invalid"); x.style.outline = ""; } });
    if (problem) {
      e.preventDefault();
      var isGuide = problem === "empty";
      var el = box(f, isGuide, field);
      var text = (isGuide && domVal) ? MSG.emptyDom.replace("{domain}", function () { return domVal; }) : MSG[problem];
      if (problem === "domainOnly") {
        var d0 = v.replace(/^https?:\/\//, "").replace(/^www\./, "").split("/")[0];
        text = text.replace("{example}", function () { return "security@" + d0; });
      } else if (problem === "typo") {
        var at = v.split("@");
        text = text.replace("{fix}", function () { return at[0] + "@" + TYPO[at[1]]; });
      }
      el.textContent = (isGuide ? "\u26A0 " : "") + text;
      el.setAttribute("data-trial-problem", problem);
      el.hidden = false;
      if (field) {
        if (!isGuide) field.setAttribute("aria-invalid", "true");
        if (isGuide) { field.setAttribute("aria-invalid", "true"); field.style.outline = "2px solid #ff6b6b"; field.style.outlineOffset = "2px"; }
        try { field.focus({ preventScroll: true }); } catch (x) { field.focus(); }
        (field.closest("label, p, div") || field).scrollIntoView({ block: "center", behavior: "smooth" });
        if (problem === "consent") {
          var label = field.closest("label") || field.parentNode;
          label.style.outline = "2px solid #ff6b6b"; label.style.outlineOffset = "4px"; label.style.borderRadius = "4px";
        }
      }
      ev("trial_invalid", f, (REASON[problem] || problem) + (kind ? ":" + kind : ""));
      return;
    }
    var old = f.querySelector(".trial-error");
    if (old) old.hidden = true;
    ev("trial_submit", f);
  }, true);
  // "Start free trial" links only scroll to the form; put the cursor in the email box so the next click is not empty.
  function focusTrialEmail(hash) {
    var target = hash && hash.length > 1 ? document.getElementById(hash.slice(1)) : null;
    var form = target && (target.matches && target.matches("form") ? target : target.querySelector && target.querySelector("form"));
    if (!isTrial(form)) return;
    var email = form.querySelector('[name="email"]');
    if (email && !email.value) { try { email.focus({ preventScroll: true }); } catch (x) { email.focus(); } }
  }
  document.addEventListener("click", function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href*="#"]') : null;
    if (!a) return;
    var url = a.getAttribute("href") || "";
    var path = url.split("#")[0].split("?")[0];
    if (path && path !== location.pathname) return;
    setTimeout(function () { focusTrialEmail("#" + url.split("#").pop()); }, 350);
  });
  if (location.hash) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { focusTrialEmail(location.hash); });
    else focusTrialEmail(location.hash);
  }
  document.addEventListener("input", function (e) {
    var t = e.target;
    if (t && (t.name === "email" || t.name === "domain") && isTrial(t.form)) {
      t.style.outline = "";
      t.removeAttribute("aria-invalid");
      if (t.value.trim()) {
        var message = t.form.querySelector('.trial-error[data-trial-problem="' +
          (t.name === "email" ? "empty" : "domain") + '"]');
        if (message) message.hidden = true;
      }
    }
  }, true);
  document.addEventListener("change", function (e) {
    var t = e.target;
    if (t && t.name === "consent" && t.checked && isTrial(t.form)) {
      var label = t.closest("label") || t.parentNode;
      label.style.outline = "";
      t.removeAttribute("aria-invalid");
      var message = t.form.querySelector('.trial-error[data-trial-problem="consent"]');
      if (message) message.hidden = true;
    }
  }, true);
})();
