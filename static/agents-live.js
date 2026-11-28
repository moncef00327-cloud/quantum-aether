(function () {
  var activeCh = "all";
  var activeTier = "all";
  var activeCat = "all";
  var activeGrp = "all";
  var autoOn = true;
  var secLeft = 15;
  var data = null;

  var tsEl = document.getElementById("server-ts");
  var cdEl = document.getElementById("countdown");
  var dotEl = document.getElementById("live-dot");
  var kpiEl = document.getElementById("kpi-strip");
  var protoEl = document.getElementById("proto-list");
  var mcpToolsBody = document.getElementById("mcp-tools-body");
  var ucpCatalogBody = document.getElementById("ucp-catalog-body");
  var a2uiListEl = document.getElementById("a2ui-list");
  var feedEl = document.getElementById("event-feed");
  var evCountEl = document.getElementById("ev-count");
  var timerEl = document.getElementById("timer-list");
  var tmCountEl = document.getElementById("tm-count");
  var pillsEl = document.getElementById("filter-pills");
  var deckTabsEl = document.getElementById("deck-tabs");
  var mcpTierPills = document.getElementById("mcp-tier-pills");
  var ucpCatPills = document.getElementById("ucp-cat-pills");
  var timerGrpPills = document.getElementById("timer-group-pills");
  var btnRefresh = document.getElementById("btn-refresh");
  var btnToggle = document.getElementById("btn-toggle");

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function render() {
    if (!data) return;
    var k = data.kpis || {};
    var pc = k.platform_counts || {};
    var xPosts = ((pc.x || {}).daily_post || 0) + ((pc.x || {}).manual_post || 0);
    var xReplies = (pc.x || {}).mention_reply || 0;
    var mbAct = ((pc.moltbook || {}).daily_digest || 0) + ((pc.moltbook || {}).intro || 0) + ((pc.moltbook || {}).comment_reply || 0);
    var abAct = ((pc.agentboard || {}).daily_digest || 0) + ((pc.agentboard || {}).reply || 0);
    var idx = k.mcp_index || {};

    if (tsEl) tsEl.textContent = data.server_time_utc || "";
    if (kpiEl) {
      var cards = [
        { l: "الوكلاء والبروتوكولات النشطة 24/7", v: k.active_agents || 0, s: "مجدول: " + (k.active_timers || 0) + " · بروتوكولات حية: " + (k.live_protocols || 0) },
        { l: "مركز MCP الرئيسي (v1.8)", v: (k.mcp_tools_total || 18) + " أداة", s: "استدعاءات 24س: " + (k.mcp_calls_24h || 0) + " · موارد: " + (k.mcp_resources_total || 0) + " · قوالب: " + (k.mcp_prompts_total || 0) },
        { l: "تجارة UCP و x402", v: (k.ucp_skus_total || 9) + " SKUs", s: "أدوات x402 بـ MCP: " + (k.mcp_x402_tools || 5) + " · طلبات UCP 24س: " + (k.ucp_calls_24h || 0) },
        { l: "A2UI v0.8 (Flutter) و A2A", v: (k.a2a_ok || 0) + "/" + (k.a2a_total || 0), s: "A2UI 24س: " + (k.a2ui_calls_24h || 0) + " · MCP Index: " + (idx.measured || 0) + " (" + (idx.pq_pct || 0) + "% PQ)" },
        { l: "الزوار البشر اليوم", v: k.human_today || 0, s: "مشاهدات: " + (k.human_pvs_today || 0) + " · أمس: " + (k.human_yesterday || 0) },
        { l: "نشاط X · Moltbook · AB", v: xPosts + xReplies + mbAct + abAct, s: "X: " + xPosts + "/" + xReplies + " · MB: " + mbAct + " · AB: " + abAct },
        { l: "فحوصات وإيصالات Ed25519", v: k.scans_24h || 0, s: "إيصالات موقّعة 24س: " + (k.receipts_24h || 0) },
        { l: "الإيرادات والتجارب و MSP", v: (k.paid_orders || 0) + " + " + (k.x402_paid || 0), s: "تجارب: " + (k.active_trials || 0) + " · MSP (14ي): " + (k.msp_sent_14d || 0) }
      ];
      kpiEl.innerHTML = cards.map(function (c) {
        return '<div class="kpi"><div class="kpi-label">' + esc(c.l) + '</div><div class="kpi-val">' + esc(c.v) + '</div><div class="kpi-sub">' + esc(c.s) + '</div></div>';
      }).join("");
    }

    if (protoEl && Array.isArray(data.protocols)) {
      protoEl.innerHTML = data.protocols.map(function (p) {
        var stCls = p.state === "active" ? "st-ok" : "st-pause";
        var stTxt = p.state === "active" ? "● نشط 24/7" : "⏸ متوقف";
        var secLink = p.secondary_url ? '<a href="' + esc(p.secondary_url) + '" target="_blank" rel="noopener">' + esc(p.secondary_label) + ' ↗</a>' : "";
        return '<article class="item-card">' +
          '<div class="item-top"><span class="tag ' + esc(p.id) + '">' + esc(p.badge) + '</span><span class="' + stCls + '">' + stTxt + '</span></div>' +
          '<div class="item-title">' + esc(p.name) + '</div>' +
          '<div class="item-desc">' + esc(p.role) + '</div>' +
          '<div class="item-meta">' + esc(p.detail) + '</div>' +
          '<div class="item-foot"><span class="metric-chip">24س: ' + esc(p.calls_24h) + '</span>' +
          '<div class="item-links"><a href="' + esc(p.endpoint) + '" target="_blank" rel="noopener">فحص JSON ↗</a>' + secLink + '</div></div></article>';
      }).join("");
    }

    if (mcpToolsBody && Array.isArray(data.mcp_tools)) {
      var tools = data.mcp_tools.filter(function (t) { return activeTier === "all" || t.tier === activeTier; });
      mcpToolsBody.innerHTML = tools.map(function (t) {
        var cls = t.tier === "x402" ? "x402" : (t.tier === "commerce" ? "msp" : "mcp");
        return '<tr data-tier="' + esc(t.tier) + '">' +
          '<td data-label="الأداة" dir="ltr" class="mono cell-primary">' + esc(t.name) + '</td>' +
          '<td data-label="الوظيفة" class="cell-desc">' + esc(t.title) + '</td>' +
          '<td data-label="التصنيف"><span class="tag ' + cls + '">' + esc(t.price_label) + '</span></td>' +
          '<td data-label="الوضع">' + (t.read_only ? "قراءة فقط" : "تنفيذ حي") + '</td>' +
          '<td data-label="استدعاءات 24س" dir="ltr" class="mono num">' + esc(t.calls_24h) + '</td></tr>';
      }).join("");
    }

    if (ucpCatalogBody && Array.isArray(data.ucp_catalog)) {
      var items = data.ucp_catalog.filter(function (it) { return activeCat === "all" || it.category === activeCat; });
      ucpCatalogBody.innerHTML = items.map(function (it) {
        return '<tr data-cat="' + esc(it.category) + '">' +
          '<td data-label="SKU" dir="ltr" class="mono cell-primary">' + esc(it.id) + '</td>' +
          '<td data-label="المنتج" class="cell-desc">' + esc(it.title) + '</td>' +
          '<td data-label="السعر" dir="ltr" class="mono num">' + esc(it.price) + ' ' + esc(it.currency) + '</td>' +
          '<td data-label="أداة MCP" dir="ltr" class="mono">' + esc(it.mcp_tool || "—") + '</td>' +
          '<td data-label="الدفع" dir="ltr">' + esc((it.payment_methods || []).join(", ")) + '</td>' +
          '<td data-label="رابط"><a href="' + esc(it.checkout_url) + '" target="_blank" rel="noopener">فتح ↗</a></td></tr>';
      }).join("");
    }

    if (a2uiListEl && data.a2ui && Array.isArray(data.a2ui.sample_domains)) {
      a2uiListEl.innerHTML = data.a2ui.sample_domains.map(function (d) {
        return '<article class="item-card">' +
          '<div class="item-top"><span class="tag a2ui">A2UI v0.8</span><span class="st-ok">● جاهز للعرض</span></div>' +
          '<div class="item-title" dir="ltr">' + esc(d.domain) + '</div>' +
          '<div class="item-desc">surfaceUpdate · dataModelUpdate · beginRendering</div>' +
          '<div class="item-foot"><div class="item-links">' +
          '<a href="' + esc(d.json_ar) + '" target="_blank" rel="noopener">JSON عربي ↗</a>' +
          '<a href="' + esc(d.json_en) + '" target="_blank" rel="noopener">EN ↗</a>' +
          '<a href="' + esc(d.jsonl) + '" target="_blank" rel="noopener">JSONL ↗</a>' +
          '</div></div></article>';
      }).join("");
    }

    var evs = (data.events || []).filter(function (e) { return activeCh === "all" || e.channel === activeCh; });
    if (evCountEl) evCountEl.textContent = evs.length + " حدث";
    if (feedEl) {
      feedEl.innerHTML = evs.length ? evs.map(function (e) {
        var lnk = e.url ? '<a href="' + esc(e.url) + '" target="_blank" rel="noopener">فتح ↗</a>' : "";
        return '<div class="ev" data-ch="' + esc(e.channel) + '">' +
          '<span class="tag ' + esc(e.channel) + '">' + esc(e.badge) + '</span>' +
          '<div><div class="ev-title">' + esc(e.title) + '</div>' +
          '<div class="ev-detail">' + esc(e.detail) + '</div>' +
          '<div class="ev-meta"><span>' + esc(e.ts) + '</span>' + lnk + '</div></div></div>';
      }).join("") : '<div class="ev-detail">لا توجد أحداث في هذا الفلتر بعد.</div>';
    }

    var tms = (data.timers || []).filter(function (t) { return activeGrp === "all" || t.group === activeGrp; });
    if (tmCountEl) tmCountEl.textContent = tms.length + " مؤقّت";
    if (timerEl) {
      timerEl.innerHTML = tms.length ? tms.map(function (t) {
        var stCls = t.state === "paused" ? "st-pause" : "st-ok";
        var stTxt = t.state === "paused" ? "⏸ متوقّف" : "● شغّال";
        return '<div class="tm" data-grp="' + esc(t.group) + '"><div><div class="tm-name">' + esc(t.label) + '</div>' +
          '<div class="tm-sub">' + esc(t.group) + ' · <span dir="ltr">' + esc(t.unit) + '</span></div></div>' +
          '<div class="tm-right"><div class="' + stCls + '">' + stTxt + ' · ' + esc(t.left) + '</div>' +
          '<div class="tm-sub">آخر تشغيل: ' + esc(t.passed) + '</div></div></div>';
      }).join("") : '<div class="ev-detail">لا توجد مؤقّتات في هذا التصنيف.</div>';
    }
  }

  function filterDom(container, selector, attr, val, countEl, suffix) {
    if (!container) return;
    var shown = 0;
    container.querySelectorAll(selector).forEach(function (el) {
      var ok = val === "all" || (el.getAttribute(attr) || "") === val;
      el.classList.toggle("is-hidden", !ok);
      if (ok) shown += 1;
    });
    if (countEl) countEl.textContent = shown + " " + suffix;
  }

  function refresh() {
    if (cdEl) cdEl.textContent = "جارٍ التحديث...";
    fetch("/admin/agents-live/feed", { credentials: "same-origin", cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (d) { data = d; secLeft = 15; render(); if (cdEl) cdEl.textContent = "تحديث خلال 15ث"; })
      .catch(function () { if (cdEl) cdEl.textContent = "تعذّر التحديث — إعادة المحاولة..."; });
  }

  if (deckTabsEl) {
    deckTabsEl.addEventListener("click", function (e) {
      var btn = e.target.closest(".tab-btn");
      if (!btn) return;
      var target = btn.getAttribute("data-tab");
      deckTabsEl.querySelectorAll(".tab-btn").forEach(function (b) { b.classList.toggle("active", b === btn); });
      document.querySelectorAll(".tab-pane").forEach(function (p) {
        p.classList.toggle("is-hidden", p.getAttribute("data-pane") !== target);
      });
    });
  }

  if (mcpTierPills) {
    mcpTierPills.addEventListener("click", function (e) {
      var b = e.target.closest(".pill");
      if (!b) return;
      activeTier = b.getAttribute("data-tier") || "all";
      mcpTierPills.querySelectorAll(".pill").forEach(function (p) { p.classList.toggle("active", p === b); });
      if (data) render();
      else filterDom(mcpToolsBody, "tr", "data-tier", activeTier, null, "");
    });
  }

  if (ucpCatPills) {
    ucpCatPills.addEventListener("click", function (e) {
      var b = e.target.closest(".pill");
      if (!b) return;
      activeCat = b.getAttribute("data-cat") || "all";
      ucpCatPills.querySelectorAll(".pill").forEach(function (p) { p.classList.toggle("active", p === b); });
      if (data) render();
      else filterDom(ucpCatalogBody, "tr", "data-cat", activeCat, null, "");
    });
  }

  if (timerGrpPills) {
    timerGrpPills.addEventListener("click", function (e) {
      var b = e.target.closest(".pill");
      if (!b) return;
      activeGrp = b.getAttribute("data-grp") || "all";
      timerGrpPills.querySelectorAll(".pill").forEach(function (p) { p.classList.toggle("active", p === b); });
      if (data) render();
      else filterDom(timerEl, ".tm", "data-grp", activeGrp, tmCountEl, "مؤقّت");
    });
  }

  if (pillsEl) {
    pillsEl.addEventListener("click", function (e) {
      var b = e.target.closest(".pill");
      if (!b) return;
      activeCh = b.getAttribute("data-ch") || "all";
      pillsEl.querySelectorAll(".pill").forEach(function (p) { p.classList.toggle("active", p === b); });
      if (data) render();
      else filterDom(feedEl, ".ev", "data-ch", activeCh, evCountEl, "حدث");
    });
  }

  if (btnRefresh) btnRefresh.addEventListener("click", refresh);
  if (btnToggle) {
    btnToggle.addEventListener("click", function () {
      autoOn = !autoOn;
      btnToggle.textContent = autoOn ? "إيقاف التحديث" : "استئناف التحديث";
      if (dotEl) dotEl.classList.toggle("is-paused", !autoOn);
    });
  }

  refresh();
  setInterval(function () {
    if (!autoOn) return;
    secLeft -= 1;
    if (secLeft <= 0) refresh();
    else if (cdEl) cdEl.textContent = "تحديث خلال " + secLeft + "ث";
  }, 1000);
})();
