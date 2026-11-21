// Partner referral consent (partners.py). Yes -> POST /partners/consent sets the 60-day cookie. No -> nothing stored.
(function () {
  var bar = document.getElementById("ref-bar");
  if (!bar) return;
  function close() { bar.remove(); }
  bar.querySelector(".ref-no").addEventListener("click", close);
  bar.querySelector(".ref-yes").addEventListener("click", function () {
    fetch("/partners/consent", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: bar.dataset.code }) }).finally(close);
  });
})();
