(() => {
  const payload = document.getElementById('qa-home-snapshot');
  const reactRoot = document.getElementById('command-root');
  const root = reactRoot || document;
  if (!payload || !root) return;

  let data = null;
  try { data = JSON.parse(payload.textContent || 'null'); } catch { /* Fall back to the summary endpoint. */ }

  const valid = value => value && Number.isFinite(value.reachable) && Number.isFinite(value.pq)
    && Number.isFinite(value.pct) && value.grades;

  const update = () => {
    if (!valid(data)) return;
    const cards = root.querySelectorAll('.metrics article');
    const en = document.documentElement.lang === 'en';
    if (cards.length >= 4) {
      const labels = en
        ? ['TOP 1,000 DOMAINS · WEEKLY', 'RESPONDED OVER HTTPS', 'OBSERVED PQ ADOPTION', 'LATEST MEASURED WEEK']
        : ['أكبر 1000 نطاق · قياس أسبوعي', 'استجابت عبر HTTPS', 'تبادل مقاوم للكم مرصود', 'أحدث أسبوع مقاس'];
      const notes = en
        ? ['Weekly tracker sample', 'In the latest measured week', `${data.pq} of ${data.reachable} responding domains negotiated hybrid exchange`, data.date]
        : ['عينة المتتبّع الأسبوعي', 'في أحدث أسبوع مقاس', `${data.pq} من ${data.reachable} نطاقاً مستجيباً تفاوضت على التبادل الهجين`, data.date];
      const values = ['1,000', String(data.reachable), `${data.pct}%`, data.week];

      cards.forEach((card, i) => {
        const label = card.querySelector('div');
        const value = card.querySelector('strong span');
        const note = card.querySelector('p');
        if (label?.firstChild && label.firstChild.nodeType === Node.TEXT_NODE && label.firstChild.nodeValue !== labels[i]) label.firstChild.nodeValue = labels[i];
        if (value && value.textContent !== values[i]) value.textContent = values[i];
        if (note && note.textContent !== notes[i]) note.textContent = notes[i];
      });
    }

    const weeklyCopy = root.querySelector('[data-weekly-current]');
    const studyLiveValues = [
      ['[data-live-total]', '1,000'],
      ['[data-live-reachable]', String(data.reachable)],
      ['[data-live-pq]', String(data.pq)],
      ['[data-live-pct]', `${data.pct}%`]
    ];
    studyLiveValues.forEach(([selector, value]) => {
      const target = root.querySelector(selector);
      if (target && target.textContent !== value) target.textContent = value;
    });
    if (weeklyCopy) {
      const lang = document.documentElement.lang;
      const text = lang === 'ar'
        ? `أسبوع ${data.week}: رُصد التبادل الهجين لدى ${data.pq} من ${data.reachable} نطاقاً مستجيباً (${data.pct}%). تاريخ القياس: ${data.date}.`
        : lang === 'de'
          ? `Woche ${data.week}: Hybrider Schlüsselaustausch bei ${data.pq} von ${data.reachable} antwortenden Domains (${data.pct} %). Messdatum: ${data.date}.`
          : `Week ${data.week}: hybrid key exchange was observed on ${data.pq} of ${data.reachable} responding domains (${data.pct}%). Measured ${data.date}.`;
      if (weeklyCopy.textContent !== text) weeklyCopy.textContent = text;
    }

    const panel = root.querySelector('.qa-metrics-card');
    if (!panel) return;
    const headline = panel.querySelector('.qa-metric-big');
    const summary = panel.querySelector('.qa-card-sub');
    const note = panel.querySelector('.qa-card-note');
    const figure = panel.querySelector('.qa-chart');
    if (headline && headline.textContent !== `${data.pct}%`) headline.textContent = `${data.pct}%`;
    const summaryText = en
      ? `${data.pq} / ${data.reachable} responding domains negotiated hybrid key exchange`
      : `من النطاقات المستجيبة تفاوضت على التبادل الهجين: ${data.pq} / ${data.reachable}`;
    if (summary && summary.textContent !== summaryText) summary.textContent = summaryText;
    const noteText = en
      ? `Weekly tracker · ${data.date} · ${data.pq} domains negotiated hybrid exchange; grade distribution covers responding domains.`
      : `المتتبّع الأسبوعي · ${data.date} · تفاوض ${data.pq} نطاقاً على التبادل الهجين؛ توزيع الدرجات للنطاقات المستجيبة.`;
    if (note && note.textContent !== noteText) note.textContent = noteText;
    if (!figure) return;
    const svg = figure.querySelector('svg');
    const grades = ['A', 'B', 'C', 'F'];
    const maximum = Math.max(1, ...grades.map(g => Number(data.grades[g] || 0)));
    if (svg) {
      svg.setAttribute('aria-label', en
        ? `Latest weekly grades for ${data.week}: ${grades.map(g => `${g} ${data.grades[g] || 0}`).join(', ')} of ${data.reachable}`
        : `توزيع الدرجات للأسبوع ${data.week}: ${grades.map(g => `${g} ${data.grades[g] || 0}`).join('، ')} من ${data.reachable}`);
      const groups = svg.querySelectorAll('g');
      groups.forEach((group, i) => {
        const grade = grades[i];
        if (!grade) return;
        const count = Number(data.grades[grade] || 0);
        const x = 8 + i * 58;
        const height = count ? Math.max(3, Math.round(count / maximum * 66)) : 0;
        const top = 84 - height;
        const title = group.querySelector('title');
        const bar = group.querySelector('.qa-bar');
        let value = group.querySelector('.qa-val');
        if (title) title.textContent = `${grade}: ${count} / ${data.reachable}`;
        if (bar) bar.setAttribute('d', `M${x} 84V${top + 4}Q${x} ${top} ${x + 4} ${top}H${x + 36}Q${x + 40} ${top} ${x + 40} ${top + 4}V84Z`);
        if (!value) {
          value = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          value.setAttribute('text-anchor', 'middle');
          value.setAttribute('class', 'qa-val');
          group.appendChild(value);
        }
        value.setAttribute('x', String(x + 20));
        value.setAttribute('y', String(Math.max(9, top - 4)));
        value.textContent = String(count);
      });
    }
    const caption = figure.querySelector('figcaption');
    const captionText = en ? `Grade distribution · ${data.week}` : `توزيع الدرجات · ${data.week}`;
    if (caption && caption.textContent !== captionText) caption.textContent = captionText;
  };

  const refresh = async () => {
    try {
      const response = await fetch('/adoption/summary.json', {cache: 'no-store', credentials: 'same-origin'});
      if (!response.ok) return;
      const latest = await response.json();
      if (!valid(latest)) return;
      if (reactRoot) {
        const signature = value => JSON.stringify([value.week, value.date, value.total, value.reachable, value.pq, value.pct, value.grades]);
        if (data && signature(latest) !== signature(data)) window.location.reload();
        return;
      }
      data = latest;
      update();
    } catch { /* Keep the server-rendered snapshot available offline. */ }
  };
  if (!reactRoot) update();
  void refresh();
  window.setInterval(refresh, 5 * 60 * 1000);
  window.addEventListener('focus', refresh);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) void refresh(); });
})();
