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
  var printButton = document.querySelector(".print-button");
  if (printButton) {
    printButton.addEventListener("click", function () { window.print(); });
  }
})();
