(function () {
  var activeTab = "overview";
  var autoOn = true;
  var secLeft = 15;
  var busy = false;

  function applyTab(key) {
    activeTab = key || "overview";
    var bar = document.getElementById("adm-tabs");
    if (bar) {
      bar.querySelectorAll(".adm-tab").forEach(function (t) {
        var on = t.getAttribute("data-tab") === activeTab;
        t.classList.toggle("is-active", on);
        t.setAttribute("aria-selected", on ? "true" : "false");
      });
    }
    document.querySelectorAll(".adm-panel[data-panel]").forEach(function (p) {
      var show = activeTab === "all" || p.getAttribute("data-panel") === activeTab;
      p.classList.toggle("is-hidden", !show);
    });
    try { sessionStorage.setItem("qa_admin_tab", activeTab); } catch (e) {}
  }

  function updateClock() {
    var ts = document.getElementById("adm-sync-ts");
    if (!ts) return;
    var d = new Date();
    var pad = function (n) { return (n < 10 ? "0" : "") + n; };
    ts.textContent = "آخر تحديث " + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
  }

  function setCountdown(text) {
    var cd = document.getElementById("adm-countdown");
    if (cd) cd.textContent = text;
  }

  function liveRefresh() {
    if (busy) return;
    busy = true;
    setCountdown("جارٍ التحديث...");
    var url = location.pathname + location.search;
    fetch(url, { credentials: "same-origin", cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.text();
      })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, "text/html");
        var freshRoot = doc.getElementById("adm-live-root");
        var curRoot = document.getElementById("adm-live-root");
        if (freshRoot && curRoot) {
          curRoot.innerHTML = freshRoot.innerHTML;
          applyTab(activeTab);
        }
        secLeft = 15;
        updateClock();
        setCountdown(autoOn ? "تحديث خلال 15ث" : "متوقّف مؤقتاً");
      })
      .catch(function () {
        setCountdown("تعذّر التحديث — إعادة المحاولة...");
      })
      .finally(function () {
        busy = false;
      });
  }

  document.addEventListener("click", function (e) {
    var tabBtn = e.target.closest(".adm-tab");
    if (tabBtn) {
      applyTab(tabBtn.getAttribute("data-tab"));
      return;
    }
    if (e.target.closest("#adm-btn-refresh")) {
      liveRefresh();
      return;
    }
    var tog = e.target.closest("#adm-btn-toggle");
    if (tog) {
      autoOn = !autoOn;
      tog.textContent = autoOn ? "إيقاف التحديث" : "استئناف التحديث";
      var dot = document.getElementById("adm-live-dot");
      if (dot) dot.classList.toggle("is-paused", !autoOn);
      setCountdown(autoOn ? ("تحديث خلال " + secLeft + "ث") : "متوقّف مؤقتاً");
    }
  });

  // Restore saved tab or deep-link hash
  try {
    var saved = sessionStorage.getItem("qa_admin_tab");
    if (saved) activeTab = saved;
  } catch (e) {}
  if (location.hash === "#audit-orders" || location.hash === "#billing-records") activeTab = "sales";
  applyTab(activeTab);
  updateClock();

  setInterval(function () {
    if (!autoOn) return;
    secLeft -= 1;
    if (secLeft <= 0) liveRefresh();
    else setCountdown("تحديث خلال " + secLeft + "ث");
  }, 1000);
})();
