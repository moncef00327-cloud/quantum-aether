(function () {
  var form = document.querySelector(".scan-form");
  if (form) {
    form.addEventListener("submit", function () {
      var button = form.querySelector("button");
      button.disabled = true;
      form.querySelector(".form-busy").hidden = false;
    });
  }
  var printButton = document.querySelector(".print-button");
  if (printButton) {
    printButton.addEventListener("click", function () { window.print(); });
  }
})();
