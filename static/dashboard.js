// لوحة المراقبة: زر الطباعة وتأكيد الإلغاء (بلا سكربت داخلي بسبب سياسة CSP).
(function () {
  var printButton = document.getElementById("print-report");
  if (printButton) printButton.addEventListener("click", function () { window.print(); });
  var cancelForm = document.getElementById("cancel-form");
  if (cancelForm) cancelForm.addEventListener("submit", function (event) {
    if (!window.confirm(cancelForm.dataset.confirm)) event.preventDefault();
  });
})();
