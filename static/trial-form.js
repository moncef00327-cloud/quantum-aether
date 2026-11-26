/* Trial forms (any form posting to /monitoring/trial, including the home page app):
   check email, domain and consent before sending and say clearly what is missing, in the page language.
   The browser's own bubbles were easy to miss (consent box sits below the button), so clicks never became requests.
   The server checks everything again; this only explains. No text the visitor typed is sent to analytics. */
(function () {
  var lang = (document.documentElement.lang || "en").slice(0, 2);
  var ALL = {
    en: { empty: "Email required: enter your email (work or personal) to receive your monitoring activation link.",
          emptyDom: "Email required: enter your email (work or personal) to receive your monitoring activation link for {domain}.",
          email: "Please enter a valid email address, for example security@company.com.",
          domain: "Personal mailboxes are welcome: please also enter the domain to monitor (for example company.com).",
          consent: "Accept the Terms and Privacy Policy to start your free trial." },
    de: { empty: "E-Mail-Adresse fehlt: Geben Sie Ihre E-Mail-Adresse (geschäftlich oder privat) ein, um den Aktivierungslink für die Überwachung zu erhalten.",
          emptyDom: "E-Mail-Adresse fehlt: Geben Sie Ihre E-Mail-Adresse (geschäftlich oder privat) ein, um den Aktivierungslink für die Überwachung von {domain} zu erhalten.",
          email: "Bitte geben Sie eine gültige E-Mail-Adresse ein, z. B. security@firma.at.",
          domain: "Private Adressen sind willkommen: Bitte geben Sie zusätzlich die zu überwachende Domain ein (z. B. firma.at).",
          consent: "Bestätigen Sie die AGB und die Datenschutzerklärung, um den kostenlosen Test zu starten." },
    ar: { empty: "البريد مطلوب: أدخل بريدك الإلكتروني (عمل أو شخصي) لإرسال رابط تفعيل المراقبة.",
          emptyDom: "البريد مطلوب: أدخل بريدك الإلكتروني (عمل أو شخصي) لإرسال رابط تفعيل المراقبة لـ {domain}.",
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
    "article.card.is-plan-selected,.price-box.is-plan-selected{border-color:#67e8f9!important;box-shadow:0 0 0 1px rgba(103,232,249,.35)}" +
    ".qa-multi-scan-nudge{margin:0 0 .9rem;padding:11px 14px;border-radius:12px;border:1px solid rgba(103,232,249,.55);background:rgba(103,232,249,.12);color:#e2f8ff;font-size:.93rem;line-height:1.5}" +
    ".qa-multi-scan-nudge strong{color:#67e8f9}" +
    ".qa-multi-scan-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}" +
    ".qa-multi-scan-chip{display:inline-block;padding:2px 8px;border-radius:999px;background:rgba(15,23,42,.65);border:1px solid rgba(103,232,249,.35);font-size:.8rem;font-family:monospace;direction:ltr}" +
    ".qa-empty-alt{display:block;margin-top:6px;font-size:.85rem;font-weight:500;color:#cbd5e1}" +
    ".qa-empty-alt a{color:#67e8f9;text-decoration:underline}" +
    ".trial-form input[name='email']:focus{border-color:#67e8f9!important;box-shadow:0 0 0 3px rgba(103,232,249,.22)!important}";
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
    var slot = form.querySelector("[data-trial-email-error]");
    var el = (isGuide && slot) ? slot : (form.querySelector(".trial-error") || slot);
    if (!el) {
      el = document.createElement("p");
      el.className = "trial-error";
      el.id = (form.id || ("trial-form-" + Math.random().toString(36).slice(2, 8))) + "-msg";
      form.insertBefore(el, form.firstChild);
    }
    // Missing email: show the message right under the email box (not above the label), so it is seen with the field.
    // Prefer a reserved slot already under the field (survives React re-renders on the home app).
    if (isGuide && field && field.name === "email") {
      var row = field.closest(".scan-row, .qa-email-row") || field;
      if (!el.hasAttribute("data-trial-email-error") && row.nextSibling !== el) row.parentNode.insertBefore(el, row.nextSibling);
      field.setAttribute("aria-describedby", el.id);
    }
    el.classList.toggle("form-error", !isGuide);
    el.setAttribute("role", "alert");
    // Missing email (2026-11-21): a clear error box under the field, not a soft cyan hint (6 empty submits that day,
    // 5 of them on /pricing, and nobody retried).
    el.style.cssText = isGuide
      ? "display:block;color:#fef3c7;background:rgba(245,158,11,.15);border:1px solid rgba(251,191,36,.62);padding:10px 13px;border-radius:12px;font-weight:600;margin:.45rem 0 .75rem"
      : "color:#ff6b6b;font-weight:600;margin:0 0 .6rem";
    return el;
  }
  // Auto-focus email field cleanly when landing directly on /monitoring with a prefilled domain or #trial-form hash.
  try {
    if (location.pathname === "/monitoring" && (location.hash === "#trial-form" || location.hash === "#trial" || new URLSearchParams(location.search).get("domain"))) {
      var monEmail = document.getElementById("trial-form-email");
      if (monEmail && !monEmail.value) {
        setTimeout(function () { try { monEmail.focus({ preventScroll: true }); } catch (e) {} }, 120);
      }
    }
  } catch (e) {}
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
      if (isGuide && document.getElementById("alert")) {
        var altWrap = document.createElement("span");
        altWrap.className = "qa-empty-alt";
        var altLink = document.createElement("a");
        altLink.href = "#alert";
        altLink.textContent = lang === "ar"
          ? "تفضّل تنبيهاً مجانياً لتغيّر هذا النطاق فقط؟ انتقل للتنبيه السريع ↓"
          : (lang === "de" ? "Lieber nur kostenlose Änderungs-Warnung für 1 Domain? ↓"
            : "Prefer a free single-domain change alert instead? Jump to quick alert ↓");
        altWrap.appendChild(altLink);
        el.appendChild(altWrap);
      }
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
  // Repeat-scanner incentive: remember recent scanned domains in localStorage (browser-only, max 10)
  // and offer to monitor all of them together in one 14-day free trial.
  function initMultiScanNudge() {
    var KEY = "qa_recent_scans";
    var list = [];
    try { list = JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { list = []; }
    if (!Array.isArray(list)) list = [];
    function normDom(s) {
      return String(s || "").trim().toLowerCase().replace(/^https?:\/\//, "").split("/")[0].split(":")[0].replace(/^www\./, "");
    }
    var cur = "";
    var ch = document.getElementById("common-hosts");
    if (ch && ch.getAttribute("data-domain")) cur = normDom(ch.getAttribute("data-domain"));
    else if (location.pathname.indexOf("/scan/") === 0) {
      var h1 = document.querySelector("h1.domain");
      if (h1) cur = normDom(h1.textContent);
    }
    if (cur && /^[a-z0-9][a-z0-9.-]+\.[a-z]{2,}$/.test(cur)) {
      list = [cur].concat(list.filter(function (d) { return d && d !== cur; })).slice(0, 10);
      try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) {}
    }
    if (list.length < 2) return;
    var forms = document.querySelectorAll('form[action*="/monitoring/trial"]');
    if (!forms.length) return;
    var NUDGE = {
      en: "You've checked {n} domains in this session — instead of re-scanning manually, monitor all {n} daily for free (14-day trial, no card, instant silent-downgrade alerts). Enter your email below and we'll add them all automatically:",
      ar: "فحصت للتو {n} نطاقات في هذه الجلسة — بدل إعادة الفحص يدويًا، راقبها جميعًا يوميًا مجانًا لمدة 14 يومًا (بلا بطاقة، وتنبيه فوري عند أي تراجع صامت). أدخل بريدك أدناه وسنضيفها كلها تلقائيًا:",
      de: "Sie haben in dieser Sitzung {n} Domains geprüft — überwachen Sie alle {n} täglich kostenlos (14 Tage Test, keine Karte, sofortige Downgrade-Warnungen). E-Mail unten eingeben, alle Domains werden automatisch hinzugefügt:"
    };
    forms.forEach(function (f) {
      if (f.querySelector(".qa-multi-scan-nudge")) return;
      var domInput = f.querySelector('[name="domain"]');
      var primary = normDom(domInput ? domInput.value : cur);
      if (!primary && domInput && domInput.type !== "hidden") {
        primary = list[0];
        domInput.value = primary;
      }
      var extras = list.filter(function (d) { return d !== primary; }).slice(0, primary ? 9 : 10);
      var allDoms = (primary ? [primary] : []).concat(extras);
      if (allDoms.length < 2) return;
      var hidden = f.querySelector('input[name="extra_domains"]');
      if (!hidden) {
        hidden = document.createElement("input");
        hidden.type = "hidden";
        hidden.name = "extra_domains";
        f.appendChild(hidden);
      }
      hidden.value = extras.join(",");
      var banner = document.createElement("div");
      banner.className = "qa-multi-scan-nudge";
      banner.setAttribute("role", "status");
      var total = allDoms.length;
      var p = document.createElement("div");
      p.textContent = (NUDGE[lang] || NUDGE.en).replace(/\{n\}/g, String(total));
      banner.appendChild(p);
      var chips = document.createElement("div");
      chips.className = "qa-multi-scan-chips";
      allDoms.slice(0, 6).forEach(function (d) {
        var chip = document.createElement("span");
        chip.className = "qa-multi-scan-chip";
        chip.textContent = d;
        chips.appendChild(chip);
      });
      if (total > 6) {
        var more = document.createElement("span");
        more.className = "qa-multi-scan-chip";
        more.textContent = "+" + (total - 6);
        chips.appendChild(more);
      }
      banner.appendChild(chips);
      f.insertBefore(banner, f.firstChild);
      ev("multi_scan_nudge", f, String(total));
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initMultiScanNudge);
  else initMultiScanNudge();
  // Inline trial forms (pricing/monitoring/business) render the email field with no cursor in it, so a first
  // click can land on the button while the field is still empty (8 such empty submits in two days, none retried).
  // On a real pointer device, drop the cursor into the required email field once it scrolls fully into view, so
  // typing starts right away. Skipped on touch (never force the mobile keyboard open), when the visitor is already
  // typing somewhere, when the field is prefilled, and when the page opened straight to a form (#hash handles that).
  function initTrialEmailAutofocus() {
    if (location.hash) return;
    if (!("IntersectionObserver" in window)) return;
    var finePointer = false;
    try { finePointer = window.matchMedia("(pointer:fine)").matches && !window.matchMedia("(hover:none)").matches; } catch (e) {}
    if (!finePointer) return;  // desktop/mouse only: do not pop the mobile keyboard or scroll the page
    var fields = [];
    document.querySelectorAll('form[action*="/monitoring/trial"] input[name="email"]').forEach(function (el) {
      if (el.type !== "hidden" && !el.value) fields.push(el);
    });
    if (!fields.length) return;
    var done = false;
    function busy() {
      var a = document.activeElement;
      return !!(a && a !== document.body && a !== document.documentElement && a.tagName !== "A");
    }
    var io = new IntersectionObserver(function (entries) {
      if (done) { io.disconnect(); return; }
      entries.forEach(function (entry) {
        if (done) return;
        var el = entry.target;
        if (entry.isIntersecting && entry.intersectionRatio >= 0.9 && !el.value && !busy()) {
          done = true;
          try { el.focus({ preventScroll: true }); } catch (x) { el.focus(); }
          io.disconnect();
        }
      });
    }, { threshold: [0.9] });
    fields.forEach(function (el) { io.observe(el); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initTrialEmailAutofocus);
  else initTrialEmailAutofocus();
})();
