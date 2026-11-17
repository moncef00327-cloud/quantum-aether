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
  var PLAN_CSS = ".trial-plan-switch{display:flex;gap:.5rem;flex-wrap:wrap;margin:.25rem 0 1rem}" +
    ".trial-plan-pill{flex:1 1 140px;display:inline-flex;align-items:center;justify-content:center;gap:.35rem;" +
    "padding:.6rem .9rem;border-radius:999px;border:1px solid rgba(148,130,200,.4);background:rgba(16,11,28,.55);" +
    "color:#d8d4e8;font-size:.95rem;font-weight:600;cursor:pointer;transition:border-color .15s,background .15s,color .15s,box-shadow .15s}" +
    ".trial-plan-pill small{font-weight:400;opacity:.82;font-size:.82em}" +
    ".trial-plan-pill.is-active,.trial-plan-pill[aria-pressed='true']{border-color:#67e8f9;background:rgba(103,232,249,.16);color:#fff;box-shadow:0 0 0 1px rgba(103,232,249,.4)}" +
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
