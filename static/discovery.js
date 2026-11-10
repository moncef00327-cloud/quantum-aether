// كشف النطاقات الفرعية في صفحة النتيجة: يبدأ عند الضغط فقط، ويعرض الأعداد (لا الأسماء).
(function () {
  var box = document.getElementById("discovery");
  if (!box) return;
  var api = box.dataset.api, msg = JSON.parse(box.dataset.msg);
  var button = box.querySelector(".disc-start"), status = box.querySelector(".disc-status");
  var request = box.querySelector(".disc-request"), tries = 0;
  function fill(text, d) {
    return text.replace(/\{(\w+)\}/g, function (_, k) { return d[k] === undefined || d[k] === null ? "" : d[k]; });
  }
  function show(d) {
    if (d.state === "rate_limited" || d.state === "busy") { status.textContent = msg[d.state]; button.disabled = false; return; }
    if (d.status === "RUNNING") {
      status.textContent = msg.running;
      if (++tries < 40) setTimeout(poll, 3000); else { status.textContent = msg.failed; button.disabled = false; }
      return;
    }
    if (d.status === "FAILED") { status.textContent = msg.failed; button.disabled = false; return; }
    if (d.status === "DONE") {
      if (!d.responding) { status.textContent = fill(msg.none, d); return; }
      status.textContent = fill(msg.result, d);
      request.hidden = false;
    }
  }
  function poll() {
    fetch(api, { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(show)
      .catch(function () { status.textContent = msg.failed; button.disabled = false; });
  }
  button.addEventListener("click", function () {
    button.disabled = true; tries = 0; status.textContent = msg.running;
    fetch(api, { method: "POST", credentials: "same-origin" }).then(function (r) { return r.json(); }).then(show)
      .catch(function () { status.textContent = msg.failed; button.disabled = false; });
  });
  // نتيجة محفوظة (آخر 24 ساعة) تظهر مباشرة دون تشغيل جديد
  fetch(api, { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (d) {
    if (d.status === "DONE") { button.hidden = true; show(d); }
  }).catch(function () {});
})();
