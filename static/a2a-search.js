(function () {
  var commandSearch = document.querySelector("[data-qa-command-search]");
  if (commandSearch) {
    var commandRoot = document.getElementById("command-root");
    var syncCommandSearch = function () {
      var target = commandRoot.querySelector("#workspace-content > .content");
      if (target && target.firstElementChild !== commandSearch) {
        target.prepend(commandSearch);
      }
      commandSearch.hidden = Boolean(target && !target.querySelector(":scope > .qa-hero-modular-glass"));
      commandSearch.querySelectorAll("[data-qa-agent-bar]").forEach(function (bar) {
        bar.hidden = bar.getAttribute("data-lang") !== document.documentElement.lang;
      });
    };
    var observer = new MutationObserver(syncCommandSearch);
    observer.observe(commandRoot, { childList: true, subtree: true });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
    syncCommandSearch();
  }

  document.querySelectorAll("[data-qa-agent-bar]").forEach(initSearch);

  function initSearch(bar) {
    var form = bar.querySelector("[data-qa-agent-form]");
    var input = bar.querySelector("[data-qa-input]");
    var submitBtn = bar.querySelector("[data-qa-submit]");
    var suggestions = bar.querySelector("[data-qa-suggestions]");
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
    var activeRequest = null;
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
        metaPrefix: "A2A 0.3.0 · معرّف الرد",
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
        metaPrefix: "A2A 0.3.0 · Antwort-ID",
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
        metaPrefix: "A2A 0.3.0 · Reply ID",
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
      metaPrefix: "A2A 0.3.0 · Reply ID",
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
      metaEl.textContent = L.metaPrefix + (tid ? " · " + tid : "");
    }

    function queryAgent(text, extraData, isScan) {
      var clean = String(text || "").trim();
      if (!clean || activeRequest) return;
      var controller = new AbortController();
      activeRequest = controller;
      var timeout = setTimeout(function () { controller.abort(); }, 55000);
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
        signal: controller.signal,
      })
        .then(function (r) {
          if (!r.ok) throw new Error("Search HTTP " + r.status);
          return r.json();
        })
        .then(function (json) {
          if (activeRequest !== controller) return;
          if (json && json.result) {
            renderReply(json.result, clean);
          } else {
            answerEl.textContent = L.error;
          }
        })
        .catch(function () {
          if (activeRequest === controller) answerEl.textContent = L.error;
        })
        .finally(function () {
          clearTimeout(timeout);
          if (activeRequest !== controller) return;
          activeRequest = null;
          submitBtn.disabled = false;
        });
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      queryAgent(input.value, null, false);
    });

    bar.querySelectorAll("[data-qa-prompt]").forEach(function (chip) {
      chip.addEventListener("click", function () {
        if (activeRequest) return;
        var prompt = chip.getAttribute("data-qa-prompt") || "";
        input.value = prompt;
        suggestions.open = false;
        input.focus({ preventScroll: true });
        queryAgent(prompt, null, false);
      });
    });

    function closePanel() {
      if (activeRequest) {
        activeRequest.abort();
        activeRequest = null;
        submitBtn.disabled = false;
      }
      panel.hidden = true;
      input.focus();
    }

    closeBtn.addEventListener("click", closePanel);

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
      if (e.defaultPrevented || bar.closest("[hidden], [inert]")) return;
      if (e.key === "Escape" && !panel.hidden && bar.contains(document.activeElement)) {
        closePanel();
      } else if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        var tag = (document.activeElement && document.activeElement.tagName || "").toLowerCase();
        if (tag !== "input" && tag !== "textarea" && tag !== "select" && !(document.activeElement && document.activeElement.isContentEditable)) {
          e.preventDefault();
          input.focus();
        }
      }
    });
  }
})();
