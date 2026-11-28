(function () {
  var activeCh = "all";
  var autoOn = true;
  var secLeft = 15;
  var data = null;

  var tsEl = document.getElementById("server-ts");
  var cdEl = document.getElementById("countdown");
  var dotEl = document.getElementById("live-dot");
  var kpiEl = document.getElementById("kpi-strip");
  var feedEl = document.getElementById("event-feed");
  var evCountEl = document.getElementById("ev-count");
  var timerEl = document.getElementById("timer-list");
  var tmCountEl = document.getElementById("tm-count");
  var pillsEl = document.getElementById("filter-pills");
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
        { l: "الوكلاء النشطون 24/7", v: k.active_agents || 0, s: data.app_active ? "الخادم: متصل 🟢" : "الخادم: متوقف 🔴" },
        { l: "الزوار البشر اليوم", v: k.human_today || 0, s: "مشاهدات: " + (k.human_pvs_today || 0) + " · أمس: " + (k.human_yesterday || 0) },
        { l: "نشاط X · Moltbook · AB", v: xPosts + xReplies + mbAct + abAct, s: "X: " + xPosts + " نشر/" + xReplies + " رد · MB: " + mbAct + " · AB: " + abAct },
        { l: "مؤشر MCP واستدعاءاته", v: k.mcp_calls_24h || 0, s: "آخر 24س · مقاس: " + (idx.measured || 0) + " (" + (idx.pq_pct || 0) + "% PQ)" },
        { l: "A2A و MSP Pilot", v: (k.a2a_ok || 0) + "/" + (k.a2a_total || 0), s: "A2A 200 OK · رسائل MSP (14ي): " + (k.msp_sent_14d || 0) },
        { l: "الإيرادات والتجارب", v: (k.paid_orders || 0) + " + " + (k.x402_paid || 0), s: "مدفوع + x402 · تجارب نشطة: " + (k.active_trials || 0) }
      ];
      kpiEl.innerHTML = cards.map(function (c) {
        return '<div class="kpi"><div class="kpi-label">' + esc(c.l) + '</div><div class="kpi-val">' + esc(c.v) + '</div><div class="kpi-sub">' + esc(c.s) + '</div></div>';
      }).join("");
    }

    var evs = (data.events || []).filter(function (e) { return activeCh === "all" || e.channel === activeCh; });
    if (evCountEl) evCountEl.textContent = evs.length + " حدث";
    if (feedEl) {
      feedEl.innerHTML = evs.length ? evs.map(function (e) {
        var lnk = e.url ? '<a href="' + esc(e.url) + '" target="_blank" rel="noopener">فتح ↗</a>' : "";
        return '<div class="ev">' +
          '<span class="tag ' + esc(e.channel) + '">' + esc(e.badge) + '</span>' +
          '<div><div class="ev-title">' + esc(e.title) + '</div>' +
          '<div class="ev-detail">' + esc(e.detail) + '</div>' +
          '<div class="ev-meta"><span>' + esc(e.ts) + '</span>' + lnk + '</div></div></div>';
      }).join("") : '<div class="ev-detail">لا توجد أحداث في هذا الفلتر بعد.</div>';
    }

    var tms = data.timers || [];
    if (tmCountEl) tmCountEl.textContent = tms.length + " مؤقّت";
    if (timerEl) {
      timerEl.innerHTML = tms.length ? tms.map(function (t) {
        var stCls = t.state === "paused" ? "st-pause" : "st-ok";
        var stTxt = t.state === "paused" ? "⏸ متوقّف" : "● شغّال";
        return '<div class="tm"><div><div class="tm-name">' + esc(t.label) + '</div>' +
          '<div class="tm-sub">' + esc(t.group) + ' · <span dir="ltr">' + esc(t.unit) + '</span></div></div>' +
          '<div class="tm-right"><div class="' + stCls + '">' + stTxt + ' · ' + esc(t.left) + '</div>' +
          '<div class="tm-sub">آخر تشغيل: ' + esc(t.passed) + '</div></div></div>';
      }).join("") : '<div class="ev-detail">لا توجد مؤقّتات معروضة.</div>';
    }
  }

  function applyDomFilterOnly() {
    if (!feedEl) return;
    var items = feedEl.querySelectorAll(".ev");
    var shown = 0;
    items.forEach(function (el) {
      var ch = el.getAttribute("data-ch") || "";
      var ok = activeCh === "all" || ch === activeCh;
      el.style.display = ok ? "" : "none";
      if (ok) shown += 1;
    });
    if (evCountEl) evCountEl.textContent = shown + " حدث";
  }

  function refresh() {
    if (cdEl) cdEl.textContent = "جارٍ التحديث...";
    fetch("/admin/agents-live/feed", { credentials: "same-origin", cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (d) { data = d; secLeft = 15; render(); if (cdEl) cdEl.textContent = "تحديث خلال 15ث"; })
      .catch(function () { if (cdEl) cdEl.textContent = "تعذّر التحديث — إعادة المحاولة..."; });
  }

  if (pillsEl) {
    pillsEl.addEventListener("click", function (e) {
      var b = e.target.closest(".pill");
      if (!b) return;
      activeCh = b.getAttribute("data-ch") || "all";
      pillsEl.querySelectorAll(".pill").forEach(function (p) { p.classList.toggle("active", p === b); });
      if (data) render();
      else applyDomFilterOnly();
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

  // Hydrate initial JSON on load and then poll every 15s
  refresh();
  setInterval(function () {
    if (!autoOn) return;
    secLeft -= 1;
    if (secLeft <= 0) refresh();
    else if (cdEl) cdEl.textContent = "تحديث خلال " + secLeft + "ث";
  }, 1000);
})();
