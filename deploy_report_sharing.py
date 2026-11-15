"""Guarded production patch for shareable monthly research reports."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


TARGET = Path('/var/www/quantum_saas')
EXPECTED = {
    'quantum_saas_app.py': '03e8926a7a71dfc49a8ac725665d6836644e268609ac212040f1047fea144836',
    'og_image.py': 'a1bf8ebcb9c1bc25368df83a1153f6fd82239d069f1debb42cc0b5c295d49c87',
    'i18n.py': 'a1346b6503bf55f0894b62d75ba63cbaf0ac02ae08a57404d8097b71eb227df6',
    'templates/monthly_report.html': 'e35f30e1707d30c95c43159c688351da1e8be58b09cacfcbec9ba8583d576087',
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(content: str, before: str, after: str, label: str) -> str:
    if content.count(before) != 1:
        raise RuntimeError(f'Expected exactly one insertion point for {label}')
    return content.replace(before, after, 1)


for name, expected in EXPECTED.items():
    if digest(TARGET / name) != expected:
        raise RuntimeError(f'Production file changed since review: {name}')

app_path = TARGET / 'quantum_saas_app.py'
app = app_path.read_text()
app_anchor = '''@bp.get("/og/default.png")
def og_default():
    return _og_response("default", og_image.render_default)


@bp.get("/og/site/<domain>.png")'''
app_insert = '''@bp.get("/og/default.png")
def og_default():
    return _og_response("default", og_image.render_default)


@bp.get("/og/report/<report_id>.png")
def og_report(report_id):
    r = _report_or_404(report_id)
    top = r.get("top1000") or {}
    if top.get("pct") is None:
        abort(404)
    pct, measured, week = top["pct"], top.get("reachable", 0), r.get("week", "")
    return _og_response(f"report|{report_id}|{pct}|{measured}|{week}",
                        lambda: og_image.render_report(pct, measured, week))


@bp.get("/og/site/<domain>.png")'''
app = replace_once(app, app_anchor, app_insert, 'report preview route')

image_path = TARGET / 'og_image.py'
image = image_path.read_text()
image_anchor = '\ndef cached_png(cache_dir, key, build):'
image_insert = '''
def render_report(pct, measured, week):
    """Branded, report-specific preview for sharing monthly research."""
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    _frame(draw)
    draw.text((60, 170), "Post-quantum TLS adoption", font=_font(FONT_REGULAR, 36), fill=MUTED)
    headline = f"{pct}% of responding top-1,000 sites are ready"
    draw.text((60, 235), headline, font=_fit(draw, headline, FONT_BOLD, 52, 790), fill=TEXT)
    draw.text((60, 315), f"Sites responding on HTTPS: {measured:,}", font=_font(FONT_REGULAR, 30), fill=MUTED)
    draw.text((60, 365), f"Weekly research · {week}", font=_font(FONT_REGULAR, 30), fill=MUTED)
    draw.ellipse([900, 170, 1140, 410], fill=CARD, outline=ACCENT, width=12)
    big = f"{pct}%"
    font = _font(FONT_BOLD, 78)
    box = draw.textbbox((0, 0), big, font=font)
    draw.text((1020 - (box[2] - box[0]) / 2 - box[0], 290 - (box[3] - box[1]) / 2 - box[1]),
              big, font=font, fill=ACCENT)
    cta = "Read the open report →"
    draw.text((W - 60 - draw.textlength(cta, font=_font(FONT_BOLD, 30)), H - 70),
              cta, font=_font(FONT_BOLD, 30), fill=ACCENT)
    return image


def cached_png(cache_dir, key, build):'''
image = replace_once(image, image_anchor, image_insert, 'report preview renderer')

i18n_path = TARGET / 'i18n.py'
i18n = i18n_path.read_text()
for language, cite, values in [
    ('English', '    "rep_cite": "How to cite",', '    "rep_copy": "Copy citation", "rep_copied": "Copied",\n    "rep_share_title": "Share this report",'),
    ('Arabic', '    "rep_cite": "طريقة الاقتباس",', '    "rep_copy": "انسخ الاقتباس", "rep_copied": "تم النسخ",\n    "rep_share_title": "شارك هذا التقرير",'),
    ('German', '    "rep_cite": "Zitierweise",', '    "rep_copy": "Zitat kopieren", "rep_copied": "Kopiert",\n    "rep_share_title": "Diesen Bericht teilen",'),
]:
    i18n = replace_once(i18n, cite, cite + '\n' + values, f'{language} report labels')

template_path = TARGET / 'templates/monthly_report.html'
template = template_path.read_text()
template = replace_once(
    template,
    '{% block description %}{{ facts[0] if facts else t.rep_meta }}{% endblock %}\n',
    '{% block description %}{{ facts[0] if facts else t.rep_meta }}{% endblock %}\n'
    "{% block og_image %}{{ abs_url('site.og_report', report_id=r.id) }}{% endblock %}\n",
    'report social image metadata',
)
template = replace_once(
    template,
    '</pre>\n  <p><a href="{{ url_for(\'site.report_json\', report_id=r.id) }}">',
    '''</pre>
  <p><button type="button" class="copy-btn" data-copy="#cite" data-done="{{ t.rep_copied }}">{{ t.rep_copy }}</button></p>
  <h2>{{ t.rep_share_title }}</h2>
  {% set share_url = abs_url('site.monthly_report', report_id=r.id, lang=lang) %}
  {% set share_text = t.rep_title.format(month=month_name) ~ ' — ' ~ (facts[0] if facts else '') %}
  <p>
    <a class="button-link" target="_blank" rel="noopener" href="https://www.linkedin.com/sharing/share-offsite/?url={{ (share_url|utm('linkedin', 'report-' ~ r.id)) | urlencode }}">LinkedIn</a>
    <a class="button-link" target="_blank" rel="noopener" href="https://twitter.com/intent/tweet?text={{ share_text | urlencode }}&url={{ (share_url|utm('x', 'report-' ~ r.id)) | urlencode }}">X</a>
    <a class="button-link" target="_blank" rel="noopener" href="https://wa.me/?text={{ (share_text ~ ' ' ~ (share_url|utm('whatsapp', 'report-' ~ r.id))) | urlencode }}">WhatsApp</a>
  </p>
  <p><a href="{{ url_for('site.report_json', report_id=r.id) }}">''',
    'report share actions',
)

updated = {
    'quantum_saas_app.py': app.encode(),
    'og_image.py': image.encode(),
    'i18n.py': i18n.encode(),
    'templates/monthly_report.html': template.encode(),
}
backup = Path(tempfile.mkdtemp(prefix='report-sharing-', dir='/root/backups'))
for name in EXPECTED:
    saved = backup / name
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TARGET / name, saved)


def atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_name(path.name + '.report-share-new')
    temporary.write_bytes(content)
    os.chmod(temporary, 0o644)
    os.replace(temporary, path)


def restart() -> None:
    subprocess.run(['systemctl', 'restart', 'quantum_saas'], check=True)
    subprocess.run(['systemctl', 'is-active', '--quiet', 'quantum_saas'], check=True)


try:
    for name, content in updated.items():
        atomic_write(TARGET / name, content)
    restart()
    print(f'PUBLISHED; service active; guarded backup: {backup}')
except BaseException:
    for name in EXPECTED:
        shutil.copy2(backup / name, TARGET / name)
    restart()
    raise
