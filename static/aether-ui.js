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
  const close = () => {
    nav.classList.remove('is-open');
    toggle.setAttribute('aria-expanded', 'false');
  };
  toggle.addEventListener('click', () => {
    const open = nav.classList.toggle('is-open');
    toggle.setAttribute('aria-expanded', String(open));
  });
  const resources = document.querySelector('.nav-resources');
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    if (resources?.open) { resources.open = false; resources.querySelector('summary').focus(); }
    else if (nav.classList.contains('is-open')) { close(); toggle.focus(); }
  });
  document.addEventListener('click', event => {
    if (resources?.open && !resources.contains(event.target)) resources.open = false;
    if (!header.contains(event.target)) close();
  });
})();
