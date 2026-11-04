# og_image.py
# صور المعاينة (Open Graph، 1200×630) عند مشاركة رابط في لينكدإن وX وSlack وواتساب.
# المنصات لا تقبل SVG، لذلك نرسم PNG بـ Pillow ونحفظه على القرص (المفتاح يتضمن الدرجة والتاريخ،
# فتتغير الصورة تلقائياً حين تتغير النتيجة). النص لاتيني فقط: الخط وحده لا يرسم العربية متصلة.
import hashlib
import os

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # Pillow غير مثبت: لا صور، والصفحات تعمل كما هي
    Image = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_BOLD = os.path.join(BASE_DIR, "data", "fonts", "DejaVuSans-Bold.ttf")
FONT_REGULAR = os.path.join(BASE_DIR, "data", "fonts", "DejaVuSans.ttf")
W, H = 1200, 630
BG, CARD, LINE, TEXT, MUTED, ACCENT = "#0f172a", "#1e293b", "#334155", "#f8fafc", "#94a3b8", "#38bdf8"
GRADE_COLORS = {"A": "#4ade80", "B": "#f59e0b", "C": "#f87171", "F": "#ef4444"}


def available():
    return Image is not None and os.path.exists(FONT_BOLD)


def _font(path, size):
    return ImageFont.truetype(path, size)


def _fit(draw, text, path, size, max_width):
    """أكبر حجم خط (حتى size) يجعل النص يتسع لـ max_width (النطاقات الطويلة)."""
    while size > 28:
        font = _font(path, size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 4
    return _font(path, size)


def _frame(draw):
    draw.rectangle([0, 0, W, 10], fill=ACCENT)
    # شعار بسيط: ثلاث مدارات + نواة (كما في favicon)
    cx, cy = 92, 92
    for angle in (0, 60, 120):
        import math
        pts = []
        for t in range(0, 361, 4):
            r = math.radians(t)
            x, y = 34 * math.cos(r), 13 * math.sin(r)
            a = math.radians(angle)
            pts.append((cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)))
        draw.line(pts, fill=ACCENT, width=4)
    draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill="#4ade80")
    draw.text((146, 68), "Quantum Aether", font=_font(FONT_BOLD, 40), fill=TEXT)
    draw.text((60, H - 70), "ather-quatum.cloud", font=_font(FONT_REGULAR, 30), fill=MUTED)


def render_result(domain, grade, pq, unsure=False, day=""):
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    _frame(draw)
    draw.text((60, 170), "Post-quantum TLS readiness", font=_font(FONT_REGULAR, 34), fill=MUTED)
    draw.text((60, 222), domain, font=_fit(draw, domain, FONT_BOLD, 76, 800), fill=TEXT)
    if unsure:
        verdict, color = "Undetermined: our probe was blocked", MUTED
    elif pq:
        verdict, color = "Uses post-quantum key exchange", GRADE_COLORS["A"]
    else:
        verdict, color = "No post-quantum key exchange", GRADE_COLORS["C"]
    draw.text((60, 340), verdict, font=_fit(draw, verdict, FONT_BOLD, 44, 800), fill=color)
    if day:
        draw.text((60, 410), f"Checked {day} · X25519MLKEM768 (ML-KEM, FIPS 203)", font=_font(FONT_REGULAR, 28), fill=MUTED)
    # دائرة الدرجة
    g = grade or "?"
    gc = GRADE_COLORS.get(g, MUTED)
    draw.ellipse([900, 170, 1140, 410], fill=CARD, outline=gc, width=12)
    font = _font(FONT_BOLD, 150)
    box = draw.textbbox((0, 0), g, font=font)
    draw.text((1020 - (box[2] - box[0]) / 2 - box[0], 290 - (box[3] - box[1]) / 2 - box[1]), g, font=font, fill=gc)
    draw.text((W - 60 - draw.textlength("Check your site free →", font=_font(FONT_BOLD, 30)), H - 70),
              "Check your site free →", font=_font(FONT_BOLD, 30), fill=ACCENT)
    return image


def render_country(name, pct, rank, total, delta_pp=None, week=""):
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    _frame(draw)
    draw.text((60, 170), "Post-quantum TLS: country ranking", font=_font(FONT_REGULAR, 34), fill=MUTED)
    draw.text((60, 222), name, font=_fit(draw, name, FONT_BOLD, 76, 760), fill=TEXT)
    line = f"{pct:g}% of its top sites are post-quantum ready"
    draw.text((60, 340), line, font=_fit(draw, line, FONT_BOLD, 40, 800), fill=GRADE_COLORS["A"] if pct >= 50 else GRADE_COLORS["B"])
    sub = f"Week {week}" + (f" · {'▲' if delta_pp > 0 else '▼' if delta_pp < 0 else '•'} {delta_pp:+g} pp vs last week"
                            if delta_pp is not None else "")
    draw.text((60, 410), sub, font=_font(FONT_REGULAR, 28), fill=MUTED)
    draw.ellipse([900, 170, 1140, 410], fill=CARD, outline=ACCENT, width=12)
    big = f"#{rank}"
    font = _font(FONT_BOLD, 100 if len(big) <= 2 else 76)
    box = draw.textbbox((0, 0), big, font=font)
    draw.text((1020 - (box[2] - box[0]) / 2 - box[0], 275 - (box[3] - box[1]) / 2 - box[1]), big, font=font, fill=TEXT)
    of = f"of {total}"
    f2 = _font(FONT_REGULAR, 30)
    draw.text((1020 - draw.textlength(of, font=f2) / 2, 340), of, font=f2, fill=MUTED)
    draw.text((W - 60 - draw.textlength("Where does your country rank? →", font=_font(FONT_BOLD, 30)), H - 70),
              "Where does your country rank? →", font=_font(FONT_BOLD, 30), fill=ACCENT)
    return image


def render_default():
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    _frame(draw)
    draw.text((60, 190), "Is your website ready", font=_font(FONT_BOLD, 72), fill=TEXT)
    draw.text((60, 280), "for quantum computers?", font=_font(FONT_BOLD, 72), fill=TEXT)
    draw.text((60, 400), "Free 10-second check for post-quantum TLS (X25519MLKEM768)", font=_font(FONT_REGULAR, 32), fill=MUTED)
    draw.text((W - 60 - draw.textlength("Scan free →", font=_font(FONT_BOLD, 30)), H - 70),
              "Scan free →", font=_font(FONT_BOLD, 30), fill=ACCENT)
    return image


def cached_png(cache_dir, key, build):
    """يعيد مسار PNG مخزّناً (يبنيه مرة واحدة). key يجب أن يتغير حين يتغير المحتوى."""
    os.makedirs(cache_dir, exist_ok=True)
    name = hashlib.sha256(key.encode()).hexdigest()[:32] + ".png"
    path = os.path.join(cache_dir, name)
    if not os.path.exists(path):
        tmp = path + f".{os.getpid()}.tmp"
        build().save(tmp, "PNG", optimize=True)
        os.replace(tmp, path)
    return path
