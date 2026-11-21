// 2026-11-21: links to #buy open the (collapsed) purchase card before scrolling to it.
document.addEventListener("click", function (e) {
  var a = e.target.closest && e.target.closest('a[href="#buy"]');
  var buy = document.getElementById("buy");
  if (!a || !buy) return;
  e.preventDefault();
  buy.open = true;
  buy.scrollIntoView({ behavior: "smooth", block: "start" });
  var box = document.getElementById("consent");
  if (box) setTimeout(function () { box.focus({ preventScroll: true }); }, 400);
});
// Result page (2026-11-14): one POST per page view; the server probes www/api/mail/auth/login once per scan and caches it.
(function () {
  var box = document.getElementById("common-hosts");
  if (!box) return;
  var msg = JSON.parse(box.dataset.msg), list = box.querySelector(".ins-hosts"), alertEl = box.querySelector(".ins-alert");
  var tries = 0;
  function iso(text) { return "\u2068" + text + "\u2069"; }  // keep LTR names intact inside Arabic sentences
  function fill(text, d) {
    return text.replace(/\{(\w+)\}/g, function (_, k) { return d[k] === undefined || d[k] === null ? "" : d[k]; });
  }
  function tabs(d) {
    var why = document.getElementById("why");
    if (!why || !d.stack) return;
    var match = why.querySelector('.fix-tab[data-stack="' + d.stack + '"]');
    if (!match) return;
    why.querySelectorAll(".fix-tab").forEach(function (el) { el.open = el === match; });
    match.parentNode.insertBefore(match, match.parentNode.firstChild);
    var det = why.querySelector(".ins-detected");
    det.textContent = fill(det.dataset.msg, { name: iso((d.fix && d.fix.name) || d.stack), server: iso(d.server || "") });
    det.hidden = false;
  }
  function show(d) {
    list.textContent = "";
    var classical = [], seen = 0;
    (d.hosts || []).forEach(function (h) {
      var li = document.createElement("li"), name = document.createElement("strong"), st = document.createElement("span");
      li.className = "host-" + h.status;
      name.textContent = h.host;
      st.textContent = " — " + (msg.st[h.status] || h.status) + (h.group ? " (" + h.group + ")" : "");
      li.appendChild(name); li.appendChild(st); list.appendChild(li);
      if (h.status !== "none") seen++;
      if (h.status === "not_pq") classical.push(h.host);
    });
    if (classical.length) {
      alertEl.textContent = fill(box.dataset.gradeA ? msg.alert_a : msg.alert, { domain: iso(box.dataset.domain), hosts: classical.map(iso).join(document.documentElement.lang === "ar" ? "، " : ", ") });
      alertEl.className = "ins-alert warn";
    } else {
      alertEl.textContent = seen ? msg.all_ok : msg.nothing;
      alertEl.className = "ins-alert";
    }
    tabs(d);
  }
  function load() {
    fetch(box.dataset.api, { method: "POST", credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.state === "busy" && ++tries < 6) { setTimeout(load, 2500); return; }
        if (d.state !== "done") { alertEl.textContent = msg.failed; return; }
        show(d);
        var qes = document.getElementById("exposure");
        if (qes && d.exposure_html) qes.innerHTML = d.exposure_html;  // server-rendered, now including subdomains
      })
      .catch(function () { alertEl.textContent = msg.failed; });
  }
  // only one stack tab open at a time
  document.querySelectorAll("#why .fix-tab").forEach(function (el) {
    el.addEventListener("toggle", function () {
      if (el.open) document.querySelectorAll("#why .fix-tab").forEach(function (o) { if (o !== el) o.open = false; });
    });
  });
  load();
})();
