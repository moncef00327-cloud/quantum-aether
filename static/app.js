(function () {
  // إحصاء الزيارات: يُرسَل من المتصفح فقط، فالروبوتات التي لا تشغّل JavaScript لا تُحسب.
  try {
    var pv = JSON.stringify({ path: location.pathname, search: location.search, ref: document.referrer });
    if (navigator.sendBeacon) navigator.sendBeacon("/api/pv", pv);
    else fetch("/api/pv", { method: "POST", body: pv, keepalive: true });
  } catch (e) { /* الإحصاء ليس ضرورياً */ }
  // كل نموذج فحص (data-busy): عطّل الزر وأظهر رسالة الانتظار، فالفحص قد يستغرق حتى 20 ثانية.
  document.querySelectorAll("form[data-busy]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var button = form.querySelector("button");
      if (button) button.disabled = true;
      var busy = form.querySelector(".form-busy");
      if (busy) busy.hidden = false;
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
      var form = document.querySelector(".scan-form");
      if (!form) return;
      form.querySelector('input[name="domain"]').value = link.dataset.domain;
      if (form.requestSubmit) form.requestSubmit(); else form.submit();
    });
  });
    var printButton = document.querySelector(".print-button");
  if (printButton) {
    printButton.addEventListener("click", function () { window.print(); });
  }
})();
