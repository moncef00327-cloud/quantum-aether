(function () {
  // إحصاء الزيارات: يُرسَل من المتصفح فقط، فالروبوتات التي لا تشغّل JavaScript لا تُحسب.
  try {
    var pv = JSON.stringify({ path: location.pathname, search: location.search, ref: document.referrer });
    if (navigator.sendBeacon) navigator.sendBeacon("/api/pv", pv);
    else fetch("/api/pv", { method: "POST", body: pv, keepalive: true });
  } catch (e) { /* الإحصاء ليس ضرورياً */ }
  // أحداث داخل الصفحة: نعرف هل يحاول الزائر الفحص (لا كوكيز، لا نص مكتوب، اسم الحدث فقط).
  var sent = {};
  function ev(name) {
    if (sent[name]) return;
    sent[name] = true;
    try {
      var body = JSON.stringify({ name: name, page: location.pathname, lang: document.documentElement.lang });
      if (navigator.sendBeacon) navigator.sendBeacon("/api/ev", body);
      else fetch("/api/ev", { method: "POST", body: body, keepalive: true });
    } catch (e) { /* ليس ضرورياً */ }
  }
  document.querySelectorAll('form input[name="domain"]').forEach(function (input) {
    input.addEventListener("focus", function () { ev("focus"); });
    input.addEventListener("input", function () { ev("type"); });
  });
  document.querySelectorAll("form[data-busy]").forEach(function (form) {
    form.addEventListener("submit", function () { ev("submit"); });
  });
  document.querySelectorAll("[data-ev]").forEach(function (el) {
    el.addEventListener("click", function () { ev(el.dataset.ev); });
  });
  document.querySelectorAll("nav a.lang").forEach(function (a) {
    a.addEventListener("click", function () { ev("lang"); });
  });
  if (document.querySelector("[data-ev-load]")) ev(document.querySelector("[data-ev-load]").dataset.evLoad);
  // كل نموذج فحص (data-busy): عطّل الزر وأظهر رسالة الانتظار، فالفحص قد يستغرق حتى 20 ثانية.
  document.querySelectorAll("form[data-busy]").forEach(function (form) {
    form.addEventListener("submit", function () {
      if (form.hasAttribute('data-async-scan') && window.fetch && window.AbortController) return;
      var button = form.querySelector("button");
      if (button) button.disabled = true;
      var busy = form.querySelector(".form-busy");
      if (busy) busy.hidden = false;
    });
  });
  window.addEventListener('pageshow', function (event) {
    if (!event.persisted) return;
    document.querySelectorAll('form[data-busy]').forEach(function (form) {
      form.querySelectorAll('button').forEach(function (button) { button.disabled = false; });
      var busy = form.querySelector('.form-busy');
      if (busy) busy.hidden = true;
    });
  });
  // أزرار النسخ: data-copy يشير إلى عنصر، والنص يُنسخ إلى الحافظة.
  document.querySelectorAll(".copy-btn").forEach(function (button) {
    button.addEventListener("click", function () {
      var target = document.querySelector(button.dataset.copy);
      if (!target || !navigator.clipboard) return;
      navigator.clipboard.writeText(target.textContent.trim()).then(function () {
        var original = button.textContent;
        button.textContent = button.dataset.done || "✓";
        setTimeout(function () { button.textContent = original; }, 1500);
      });
    });
  });
    // أمثلة قابلة للنقر: تملأ الخانة وتبدأ الفحص بنقرة واحدة.
  document.querySelectorAll(".example-link").forEach(function (link) {
    link.addEventListener("click", function () {
      ev("example");
      var form = document.querySelector(".scan-form");
      if (!form) return;
      var src = form.querySelector('input[name="src"]');
      if (src) src.value = "example";
      form.querySelector('input[name="domain"]').value = link.dataset.domain;
      if (form.requestSubmit) form.requestSubmit(); else form.submit();
    });
  });
    var printButton = document.querySelector(".print-button");
  if (printButton) {
    printButton.addEventListener("click", function () { window.print(); });
  }
})();
