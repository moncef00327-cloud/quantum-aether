/* Progressive scanner enhancement. States reflect requests, never invented TLS stages. */
(() => {
  if (!window.fetch || !window.AbortController) return;
  const forms = [...document.querySelectorAll('form[data-async-scan]')];
  function domainFrom(raw) {
    const value = raw.trim().replace(/^[`"'<>([\s]+|[`"'<>)\],;\s]+$/g, '');
    if (!value || /[\s\\\u0000-\u001f\u007f]/u.test(value)) throw new Error('invalid_domain');
    const url = new URL(value.includes('://') ? value : `https://${value}`);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.port === '0') throw new Error('invalid_domain');
    const host = url.hostname.toLowerCase().replace(/\.$/, '');
    const labels = host.split('.');
    if (host.length > 253 || labels.length < 2 || /^\d+$/.test(labels.at(-1)) ||
        !labels.every(label => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) throw new Error('invalid_domain');
    return host;
  }
  function restore(form) {
    form.dataset.state = 'idle';
    form.setAttribute('aria-busy', 'false');
    form.querySelectorAll('button').forEach(button => { button.disabled = false; });
    const status = form.querySelector('.form-busy');
    if (status) status.hidden = true;
  }
  forms.forEach(form => {
    const input = form.querySelector('input[name="domain"]');
    const error = form.querySelector('[data-scan-error]');
    const status = form.querySelector('.form-busy');
    if (!input || !error || !status) return;
    let messages = {};
    try { messages = JSON.parse(form.dataset.errors || '{}'); } catch { /* localized fallback below */ }
    restore(form);
    input.addEventListener('input', () => input.removeAttribute('aria-invalid'));
    input.addEventListener('paste', event => {
      const text = event.clipboardData?.getData('text');
      if (!text) return;
      try {
        const clean = domainFrom(text);
        event.preventDefault();
        input.value = clean;
        input.removeAttribute('aria-invalid');
        error.hidden = true;
      } catch { /* let default paste happen so user can edit */ }
    });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (form.dataset.state === 'submitted') return;
      error.hidden = true;
      input.removeAttribute('aria-invalid');
      let domain;
      try { domain = domainFrom(input.value); }
      catch {
        error.textContent = form.dataset.invalid;
        error.hidden = false;
        input.setAttribute('aria-invalid', 'true');
        input.focus();
        return;
      }
      input.value = domain;
      form.dataset.state = 'submitted';
      form.setAttribute('aria-busy', 'true');
      form.querySelectorAll('button').forEach(button => { button.disabled = true; });
      status.textContent = form.dataset.waiting;
      status.hidden = false;
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 45000);
      const slow = setTimeout(() => { status.textContent = form.dataset.slow; }, 12000);
      try {
        const response = await fetch('/api/scan', {
          method: 'POST', headers: {'Content-Type': 'application/json'}, credentials: 'same-origin',
          signal: controller.signal,
          body: JSON.stringify({domain, source: form.querySelector('[name="src"]')?.value || 'home'})
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          if (data.error === 'invalid_domain') input.setAttribute('aria-invalid', 'true');
          throw new Error(response.status === 429 ? form.dataset.rate : messages[data.error] || form.dataset.failed);
        }
        if (!data.scan_url) throw new Error(form.dataset.failed);
        const destination = new URL(data.scan_url, location.origin);
        if (destination.origin !== location.origin || !/^\/scan\/[a-zA-Z0-9_-]+$/.test(destination.pathname)) throw new Error(form.dataset.failed);
        destination.searchParams.set('lang', document.documentElement.lang);
        form.dataset.state = 'complete';
        location.assign(destination.href);
      } catch (failure) {
        restore(form);
        form.dataset.state = 'error';
        error.textContent = failure.name === 'AbortError' || failure instanceof TypeError ? form.dataset.network : failure.message;
        error.hidden = false;
        error.focus();
      } finally {
        clearTimeout(timeout);
        clearTimeout(slow);
      }
    });
  });
  window.addEventListener('pageshow', event => { if (event.persisted) forms.forEach(restore); });
})();
