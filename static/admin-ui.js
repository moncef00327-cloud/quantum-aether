(function () {
  var bar = document.getElementById("adm-tabs");
  if (!bar) return;
  var tabs = Array.prototype.slice.call(bar.querySelectorAll(".adm-tab"));
  var panels = Array.prototype.slice.call(document.querySelectorAll(".adm-panel[data-panel]"));

  function activate(key) {
    tabs.forEach(function (t) {
      var on = t.getAttribute("data-tab") === key;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    panels.forEach(function (p) {
      var show = key === "all" || p.getAttribute("data-panel") === key;
      p.classList.toggle("is-hidden", !show);
    });
    try { sessionStorage.setItem("qa_admin_tab", key); } catch (e) {}
  }

  bar.addEventListener("click", function (e) {
    var btn = e.target.closest(".adm-tab");
    if (!btn) return;
    activate(btn.getAttribute("data-tab") || "overview");
  });

  var initial = "overview";
  try {
    var saved = sessionStorage.getItem("qa_admin_tab");
    if (saved && tabs.some(function (t) { return t.getAttribute("data-tab") === saved; })) {
      initial = saved;
    }
  } catch (e) {}
  if (location.hash === "#audit-orders" || location.hash === "#billing-records") initial = "sales";
  activate(initial);
})();
