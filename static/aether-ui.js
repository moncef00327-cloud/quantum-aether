/* Progressive navigation: links remain available if JavaScript is disabled. */
(() => {
  document.querySelectorAll('table').forEach(table => {
    table.querySelectorAll('th').forEach(th => {
      if (!th.hasAttribute('scope')) th.setAttribute('scope', table.classList.contains('kv') ? 'row' : 'col');
    });
    if (!table.classList.contains('data')) return;
    const first = table.rows[0];
    if (!first || !first.querySelector('th')) return;
    first.dataset.tableHeader = '';
    const headings = [...first.cells].map(cell => cell.textContent.trim());
    table.setAttribute('role', 'table');
    [...table.rows].forEach((row, index) => {
      row.setAttribute('role', 'row');
      [...row.cells].forEach((cell, column) => {
        cell.setAttribute('role', index === 0 ? 'columnheader' : 'cell');
        if (index > 0) cell.dataset.label = headings[column] || '';
      });
    });
  });
  document.querySelectorAll('.bar-row').forEach(row => {
    const bar = row.querySelector('.bar');
    if (!bar) return;
    bar.setAttribute('role', 'img');
    bar.setAttribute('aria-label', row.textContent.trim().replace(/\s+/g, ' '));
  });
  const header = document.querySelector('.site-header');
  const toggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('#primary-nav');
  if (!header || !toggle || !nav) return;
  header.classList.add('has-menu');
  toggle.hidden = false;
  const mobile = window.matchMedia('(max-width: 1100px)');
  const closeButton = nav.querySelector('.nav-close');
  const scrim = document.createElement('div');
  scrim.className = 'nav-scrim'; scrim.hidden = true;
  document.body.append(scrim);
  const background = [...document.querySelectorAll('main, .site-footer, .mobile-dock')];
  let previousOverflow = '';
  const close = (restoreFocus = false) => {
    const wasOpen = nav.classList.contains('is-open');
    nav.classList.remove('is-open'); scrim.hidden = true;
    toggle.setAttribute('aria-expanded', 'false');
    nav.removeAttribute('role'); nav.removeAttribute('aria-modal');
    background.forEach(el => { el.inert = false; });
    if (wasOpen) document.body.style.overflow = previousOverflow;
    if (restoreFocus && wasOpen) toggle.focus();
  };
  toggle.addEventListener('click', () => {
    if (nav.classList.contains('is-open')) { close(true); return; }
    previousOverflow = document.body.style.overflow;
    nav.classList.add('is-open'); toggle.setAttribute('aria-expanded', 'true');
    if (mobile.matches) {
      scrim.hidden = false; document.body.style.overflow = 'hidden';
      nav.setAttribute('role', 'dialog'); nav.setAttribute('aria-modal', 'true');
      background.forEach(el => { el.inert = true; });
      closeButton?.focus();
    }
  });
  closeButton?.addEventListener('click', () => close(true));
  closeButton.hidden = false;
  scrim.addEventListener('click', () => close(true));
  mobile.addEventListener('change', () => close());
  nav.addEventListener('keydown', event => {
    if (event.key !== 'Tab' || !mobile.matches || !nav.classList.contains('is-open')) return;
    const items = [...nav.querySelectorAll('a,button,summary')].filter(el => el.getClientRects().length);
    const first = items[0], last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  const resources = document.querySelector('.nav-resources');
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    if (resources?.open) { resources.open = false; resources.querySelector('summary').focus(); }
    else if (nav.classList.contains('is-open')) { close(true); }
  });
  document.addEventListener('click', event => {
    if (resources?.open && !resources.contains(event.target)) resources.open = false;
    if (!header.contains(event.target)) close();
  });
})();
