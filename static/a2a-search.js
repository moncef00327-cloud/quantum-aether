(function () {
  var bar = document.querySelector("[data-qa-agent-bar]");
  if (!bar) return;

  // On the React-hydrated Command homepage (AR/EN), mount cleanly at the top of .content after hydration
  if (bar.getAttribute("data-qa-mount") === "command-top") {
    var placeInCommandTop = function () {
      var target = document.querySelector("#workspace-content > .content") || document.querySelector("#command-root .content");
      if (target && bar.parentNode !== target) {
        target.insertBefore(bar, target.firstChild);
      }
    };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", placeInCommandTop);
    }
    placeInCommandTop();
    setTimeout(placeInCommandTop, 120);
    setTimeout(placeInCommandTop, 450);
    var rootEl = document.getElementById("command-root");
    if (rootEl && typeof MutationObserver !== "undefined") {
      var mo = new MutationObserver(function () {
        var target = document.querySelector("#workspace-content > .content") || document.querySelector("#command-root .content");
        if (target && bar.parentNode !== target) {
          target.insertBefore(bar, target.firstChild);
        }
      });
      mo.observe(rootEl, { childList: true, subtree: true });
      setTimeout(function () { mo.disconnect(); }, 4000);
    }
  }

  var form = bar.querySelector("[data-qa-agent-form]");
  var input = bar.querySelector("#qa-agent-input");
  var submitBtn = bar.querySelector("[data-qa-submit]");
  var panel = bar.querySelector("[data-qa-panel]");
  var answerEl = bar.querySelector("[data-qa-answer]");
  var pointsEl = bar.querySelector("[data-qa-points]");
  var codeWrap = bar.querySelector("[data-qa-code-wrap]");
  var codeLabel = bar.querySelector("[data-qa-code-label]");
  var codeEl = bar.querySelector("[data-qa-code]");
  var copyBtn = bar.querySelector("[data-qa-copy]");
  var actionsEl = bar.querySelector("[data-qa-actions]");
  var metaEl = bar.querySelector("[data-qa-meta]");
  var closeBtn = bar.querySelector("[data-qa-close]");

  var lang = bar.getAttribute("data-lang") || "en";
  var endpoint = bar.getAttribute("data-endpoint") || "/a2a";
  var contactHref = bar.getAttribute("data-contact") || "mailto:info@ather-quantum.com";
  var busy = false;
  var reqSeq = 0;

  var L = {
    ar: {
      thinking: "جارٍ البحث والاستعلام من وكيل A2A...",
      scanning: "جارٍ فحص النطاق مباشرة (قد يستغرق بضع ثوانٍ)...",
      error: "تعذّر الاتصال بوكيل A2A حالياً. حاول مرة أخرى بعد لحظة.",
      copied: "تم النسخ ✓",
      copy: "نسخ",
      scanNow: "فحص مباشر الآن",
      contact: "إرسال استفسار مباشر للفريق",
      ask: "اسأل",
      metaPrefix: "A2A 0.3.0 · إجابة فورية موثّقة",
    },
    de: {
      thinking: "A2A-Assistent sucht die Antwort...",
      scanning: "Live-TLS-Prüfung läuft (einige Sekunden)...",
      error: "Verbindung zum A2A-Assistenten fehlgeschlagen. Bitte erneut versuchen.",
      copied: "Kopiert ✓",
      copy: "Kopieren",
      scanNow: "Jetzt live prüfen",
      contact: "Direkt an das Team schreiben",
      ask: "Fragen",
      metaPrefix: "A2A 0.3.0 · Live-Antwort",
    },
    en: {
      thinking: "Querying the Quantum Aether A2A agent...",
      scanning: "Running live TLS scan (a few seconds)...",
      error: "Could not reach the A2A agent right now. Please try again.",
      copied: "Copied ✓",
      copy: "Copy",
      scanNow: "Run live scan now",
      contact: "Email our team",
      ask: "Ask",
      metaPrefix: "A2A 0.3.0 · Verified live answer",
    },
  }[lang] || {
    thinking: "Querying the Quantum Aether A2A agent...",
    scanning: "Running live TLS scan (a few seconds)...",
    error: "Could not reach the A2A agent right now. Please try again.",
    copied: "Copied ✓",
    copy: "Copy",
    scanNow: "Run live scan now",
    contact: "Email our team",
    ask: "Ask",
    metaPrefix: "A2A 0.3.0 · Verified live answer",
  };

  function clearEl(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  function showLoading(isScan) {
    panel.hidden = false;
    answerEl.textContent = isScan ? L.scanning : L.thinking;
    pointsEl.hidden = true;
    clearEl(pointsEl);
    codeWrap.hidden = true;
    actionsEl.hidden = true;
    clearEl(actionsEl);
    metaEl.textContent = "";
  }

  function addActionLink(label, url, primary) {
    if (!url || (!url.startsWith("/") && !url.startsWith("https://") && !url.startsWith("http://") && !url.startsWith("mailto:"))) {
      return;
    }
    var a = document.createElement("a");
    a.className = "qa-agent-action" + (primary ? " is-primary" : "");
    a.href = url;
    a.textContent = label;
    actionsEl.appendChild(a);
  }

  function addActionButton(label, onClick, primary) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "qa-agent-action" + (primary ? " is-primary" : "");
    btn.textContent = label;
    btn.addEventListener("click", onClick);
    actionsEl.appendChild(btn);
  }

  function renderReply(result, askedText) {
    var parts = (result && Array.isArray(result.parts)) ? result.parts : [];
    var textPart = parts.find(function (p) { return p && p.kind === "text"; });
    var dataPart = parts.find(function (p) { return p && p.kind === "data"; });
    var data = (dataPart && dataPart.data && typeof dataPart.data === "object") ? dataPart.data : {};

    answerEl.textContent = (textPart && textPart.text) ? textPart.text : L.error;

    clearEl(pointsEl);
    if (Array.isArray(data.points) && data.points.length) {
      data.points.forEach(function (pt) {
        var li = document.createElement("li");
        li.textContent = String(pt);
        pointsEl.appendChild(li);
      });
      pointsEl.hidden = false;
    } else {
      pointsEl.hidden = true;
    }

    if (data.code && typeof data.code === "string") {
      codeLabel.textContent = data.code_label || "TLS Config";
      codeEl.textContent = data.code;
      copyBtn.textContent = L.copy;
      codeWrap.hidden = false;
    } else {
      codeWrap.hidden = true;
    }

    clearEl(actionsEl);
    var actions = Array.isArray(data.actions) ? data.actions : [];
    actions.forEach(function (act, idx) {
      if (!act || !act.label) return;
      if (act.scan_domain) {
        addActionButton(act.label, function () {
          queryAgent("scan " + act.scan_domain, { skill: "tls-scan", domain: act.scan_domain, lang: lang, ui: "top-search" }, true);
        }, idx === 0);
      } else if (act.prompt) {
        addActionButton(act.label, function () {
          input.value = act.prompt;
          queryAgent(act.prompt, { lang: lang, ui: "top-search" }, false);
        }, false);
      } else if (act.url) {
        addActionLink(act.label, act.url, idx === 0);
      }
    });

    if (data.state === "not_scanned" && data.domain && !actions.some(function (a) { return a && a.scan_domain; })) {
      addActionButton(L.scanNow + " (" + data.domain + ")", function () {
        queryAgent("scan " + data.domain, { skill: "tls-scan", domain: data.domain, lang: lang, ui: "top-search" }, true);
      }, true);
    }

    if (data.scan_id && !actions.some(function (a) { return a && a.url && a.url.indexOf("/scan/") !== -1; })) {
      addActionLink(lang === "ar" ? "فتح تقرير الفحص ↗" : (lang === "de" ? "Prüfbericht öffnen ↗" : "Open scan report ↗"), "/scan/" + encodeURIComponent(data.scan_id) + "?lang=" + encodeURIComponent(lang), true);
    } else if (data.verification_url && !actions.length) {
      addActionLink(lang === "ar" ? "صفحة التحقق ↗" : (lang === "de" ? "Verifizierungsseite ↗" : "Verification page ↗"), data.verification_url, true);
    }

    if (data.allow_contact) {
      var subj = encodeURIComponent("Quantum Aether Inquiry: " + (askedText || "").slice(0, 80));
      addActionLink(L.contact, contactHref + "?subject=" + subj, false);
    }

    actionsEl.hidden = actionsEl.childNodes.length === 0;

    var tid = result && result.messageId ? String(result.messageId).slice(0, 12) : "";
    metaEl.textContent = L.metaPrefix + (tid ? " · task " + tid : "");
  }

  function queryAgent(text, extraData, isScan) {
    var clean = String(text || "").trim();
    if (!clean || busy) return;
    busy = true;
    reqSeq += 1;
    submitBtn.disabled = true;
    showLoading(Boolean(isScan));

    var payloadData = Object.assign({ lang: lang, ui: "top-search" }, extraData || {});
    var body = {
      jsonrpc: "2.0",
      id: "web-" + reqSeq,
      method: "message/send",
      params: {
        message: {
          role: "user",
          messageId: "ui-" + Date.now() + "-" + reqSeq,
          parts: [
            { kind: "text", text: clean },
            { kind: "data", data: payloadData },
          ],
        },
      },
    };

    fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(body),
    })
      .then(function (r) { return r.json(); })
      .then(function (json) {
        if (json && json.result) {
          renderReply(json.result, clean);
        } else {
          answerEl.textContent = (json && json.error && json.error.message) ? json.error.message : L.error;
        }
      })
      .catch(function () {
        answerEl.textContent = L.error;
      })
      .finally(function () {
        busy = false;
        submitBtn.disabled = false;
      });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    queryAgent(input.value, null, false);
  });

  bar.querySelectorAll("[data-qa-prompt]").forEach(function (chip) {
    chip.addEventListener("click", function () {
      var prompt = chip.getAttribute("data-qa-prompt") || "";
      input.value = prompt;
      queryAgent(prompt, null, false);
    });
  });

  if (closeBtn) {
    closeBtn.addEventListener("click", function () {
      panel.hidden = true;
    });
  }

  if (copyBtn) {
    copyBtn.addEventListener("click", function () {
      if (!navigator.clipboard || !codeEl.textContent) return;
      navigator.clipboard.writeText(codeEl.textContent).then(function () {
        copyBtn.textContent = L.copied;
        setTimeout(function () { copyBtn.textContent = L.copy; }, 1600);
      }).catch(function () {});
    });
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !panel.hidden) {
      panel.hidden = true;
    } else if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) {
      var tag = (document.activeElement && document.activeElement.tagName || "").toLowerCase();
      if (tag !== "input" && tag !== "textarea" && tag !== "select" && !document.activeElement.isContentEditable) {
        e.preventDefault();
        input.focus();
      }
    }
  });
})();
