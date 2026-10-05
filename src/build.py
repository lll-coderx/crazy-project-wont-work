#!/usr/bin/env python3
"""Static site builder for the Nitra Jai sleep-clinic demo site.

    python3 src/build.py

Reads   src/pages/*.html   (front matter + HTML fragment per page)
Writes  site/*.html        (full pages: shared header, footer, <head>)

Static files (CSS, fonts, SVG) live directly in site/assets/ and are not
touched by this script. After building, the script validates the output
(internal links, anchors, duplicate ids, one <h1> per page) and exits with
status 1 if anything is wrong.
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "src" / "pages"
OUT = ROOT / "site"

# ---------------------------------------------------------------------------
# Site configuration. Everything that is "sample data" lives here, so it can be
# replaced in one place when the real clinic details are known.
# ---------------------------------------------------------------------------
CONFIG = {
    "CLINIC": "นิทราใจ",
    "CLINIC_FULL": "นิทราใจ คลินิกจิตเวชและการนอนหลับ",
    "CLINIC_TAGLINE": "คลินิกจิตเวชและการนอนหลับ",
    "DOCTOR": "พญ. ปวีณา วงศ์สุริยา",
    "DOCTOR_SHORT": "คุณหมอปวีณา",
    "DOCTOR_ROLE": "จิตแพทย์ผู้ใหญ่ · สนใจด้านโรคนอนไม่หลับ",
    "PHONE": "02-000-0000",
    "PHONE_TEL": "+6620000000",
    "LINE_ID": "@nitrajai-demo",
    "EMAIL": "hello@example.com",
    "ADDRESS": "เลขที่ 123 ถนนตัวอย่าง แขวงตัวอย่าง เขตตัวอย่าง กรุงเทพมหานคร 10000",
}

HOURS = [
    ("จันทร์ – ศุกร์", "10:00 – 19:00"),
    ("เสาร์", "09:00 – 15:00"),
    ("อาทิตย์และวันหยุดนักขัตฤกษ์", "ปิด"),
]

NOINDEX = True  # demo site: ask search engines not to index it

DEMO_NOTICE = (
    "<strong>เว็บไซต์ตัวอย่างเพื่อการสาธิต</strong> · ชื่อคลินิก ชื่อแพทย์ และข้อมูลติดต่อทั้งหมดเป็นข้อมูลสมมติ "
    "ไม่ใช่สถานพยาบาลจริง"
)

# (key, label, href)
NAV = [
    ("home", "หน้าแรก", "index.html"),
    ("about", "เกี่ยวกับ", "about.html"),
    ("services", "บริการ", "services.html"),
    ("conditions", "ปัญหาการนอน", "conditions.html"),
    ("treatment", "การรักษา", "treatment.html"),
    ("articles", "บทความ", "articles.html"),
    ("faq", "คำถามที่พบบ่อย", "faq.html"),
]
NAV_CTA = ("contact", "นัดหมาย", "contact.html")

PARENTS = {"articles": ("บทความ", "articles.html")}

# ---------------------------------------------------------------------------
# Icons (24x24 outline, stroke = currentColor)
# ---------------------------------------------------------------------------
ICONS = {
    "moon": '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/>',
    "clipboard": '<rect x="5" y="4" width="14" height="17" rx="2.5"/><path d="M9 4v-.5A1.5 1.5 0 0 1 10.5 2h3A1.5 1.5 0 0 1 15 3.5V4"/><path d="M8.8 13l2.4 2.4 4.2-4.4"/>',
    "chat": '<path d="M5 5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-6l-4.5 3.5V17H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z"/><path d="M8 10h8M8 13h5"/>',
    "pill": '<g transform="rotate(-40 12 12)"><rect x="2.5" y="8" width="19" height="8" rx="4"/><path d="M12 8v8"/></g>',
    "video": '<rect x="3" y="6" width="13" height="12" rx="2.5"/><path d="M16 10.5l5-3v9l-5-3z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
    "heart": '<path d="M12 20s-7-4.3-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.7-7 10-7 10z"/>',
    "wave": '<path d="M3 12c2-4.5 4-4.5 6 0s4 4.5 6 0 4-4.5 6 0"/><path d="M3 17c2-3 4-3 6 0s4 3 6 0 4-3 6 0" opacity=".55"/>',
    "cloud": '<path d="M7 18a4 4 0 0 1-.6-7.95A5.5 5.5 0 0 1 17 9.2 3.9 3.9 0 0 1 17.5 18H7z"/>',
    "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.2v.1"/>',
    "phone": '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3.5 7.5l8.5 6 8.5-6"/>',
    "pin": '<path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M8 3v4M16 3v4M3.5 10h17"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6L7 7M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4"/>',
    "wind": '<path d="M3 9h10a2.5 2.5 0 1 0-2.5-2.5M3 15h14a2.5 2.5 0 1 1-2.5 2.5M3 12h7"/>',
    "activity": '<path d="M3 12h4l2.5-6 4 12 2.5-6H21"/>',
    "shield": '<path d="M12 3l7.5 3v5.5c0 4.5-3.2 8-7.5 9.5-4.3-1.5-7.5-5-7.5-9.5V6L12 3z"/><path d="M9 12l2.2 2.2L15.2 10"/>',
    "book": '<path d="M5 4.5A2 2 0 0 1 7 3h12v15H7a2 2 0 0 0-2 2V4.5z"/><path d="M5 20a2 2 0 0 1 2-2h12M9.5 8h6M9.5 11.5h4"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "list": '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
    "star": '<path d="M12 3.5l2.4 5.2 5.6.6-4.2 3.8 1.2 5.6L12 15.9 7 18.7l1.2-5.6L4 9.3l5.6-.6z"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.8v.1"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
}


def icon(name: str) -> str:
    if name not in ICONS:
        raise KeyError(f"unknown icon: {name}")
    return (
        '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        + ICONS[name]
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------
TOKEN = re.compile(r"\{\{\s*([A-Za-z_]+)(?::([a-z0-9_-]+))?\s*\}\}")


CTA_HTML = """<section class="section">
  <div class="container">
    <div class="cta-band">
      <div>
        <h2>อยากนอนหลับให้ดีขึ้น เริ่มจากการคุยกับคุณหมอ</h2>
        <p>นัดหมายล่วงหน้าทางโทรศัพท์ LINE หรืออีเมล เจ้าหน้าที่จะช่วยเลือกวันเวลาที่สะดวก</p>
      </div>
      <div class="hero-actions">
        <a class="btn btn-light" href="contact.html">นัดหมายปรึกษา</a>
        <a class="btn btn-outline-light" href="tel:{{PHONE_TEL}}">โทร {{PHONE}}</a>
      </div>
    </div>
  </div>
</section>"""


def hours_rows() -> str:
    return "\n".join(f"<div><dt>{d}</dt><dd>{t}</dd></div>" for d, t in HOURS)


def substitute(text: str, where: str) -> str:
    def repl(m: re.Match) -> str:
        key, arg = m.group(1), m.group(2)
        if key == "icon":
            return icon(arg)
        if key == "hours_rows":
            return hours_rows()
        if key == "cta":
            return substitute(CTA_HTML, where)
        if key in CONFIG and arg is None:
            return CONFIG[key]
        raise KeyError(f"{where}: unknown token {m.group(0)}")

    return TOKEN.sub(repl, text)


def parse_page(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", raw, re.S)
    if not m:
        raise ValueError(f"{path.name}: missing front matter")
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, raw[m.end():]


def esc_attr(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;")


def nav_html(active: str) -> str:
    links = []
    for key, label, href in NAV:
        cur = ' aria-current="page"' if key == active else ""
        links.append(f'<a href="{href}"{cur}>{label}</a>')
    key, label, href = NAV_CTA
    cur = ' aria-current="page"' if key == active else ""
    links.append(f'<a class="nav-cta" href="{href}"{cur}>{label}</a>')
    return "\n        ".join(links)


def inner_hero(meta: dict) -> str:
    crumb = meta.get("crumb") or meta["title"]
    parts = ['<a href="index.html">หน้าแรก</a>', '<span aria-hidden="true">›</span>']
    parent = meta.get("parent")
    if parent:
        label, href = PARENTS[parent]
        parts += [f'<a href="{href}">{label}</a>', '<span aria-hidden="true">›</span>']
    parts.append(f'<span aria-current="page">{crumb}</span>')
    extra = ""
    if meta.get("meta"):
        items = "".join(f"<span>{i.strip()}</span>" for i in meta["meta"].split("|"))
        extra = f'\n      <div class="meta">{items}</div>'
    lead = f'\n      <p class="lead">{meta["lead"]}</p>' if meta.get("lead") else ""
    return f"""<section class="page-hero">
  <div class="stars" aria-hidden="true"></div>
  <div class="container">
    <nav class="crumbs" aria-label="เส้นทางหน้า">{' '.join(parts)}</nav>
    <h1>{meta["h1"]}</h1>{lead}{extra}
  </div>
</section>"""


def footer_html() -> str:
    menu = "\n".join(f'          <li><a href="{h}">{l}</a></li>' for _, l, h in NAV + [NAV_CTA])
    return f"""<footer class="site-footer">
  <div class="container">
    <div class="footer-grid">
      <div>
        <div class="footer-brand"><img src="assets/logo.svg" alt="" width="40" height="40"><strong>{{{{CLINIC}}}}</strong></div>
        <p>{{{{CLINIC_TAGLINE}}}} ให้คำปรึกษาโดยจิตแพทย์ ดูแลปัญหานอนไม่หลับและความผิดปกติของการนอนหลับในผู้ใหญ่</p>
      </div>
      <div>
        <h2>เมนู</h2>
        <ul>
{menu}
        </ul>
      </div>
      <div>
        <h2>ความรู้และเครื่องมือ</h2>
        <ul>
          <li><a href="article-sleep-habits.html">10 นิสัยที่ช่วยให้หลับดีขึ้น</a></li>
          <li><a href="article-when-to-see-doctor.html">นอนไม่หลับแบบไหนควรพบแพทย์</a></li>
          <li><a href="article-cbt-i.html">CBT-I คืออะไร</a></li>
          <li><a href="sleep-diary.html">แบบบันทึกการนอน (พิมพ์ได้)</a></li>
        </ul>
      </div>
      <div>
        <h2>ติดต่อคลินิก</h2>
        <p>{{{{ADDRESS}}}}</p>
        <p><a href="tel:{{{{PHONE_TEL}}}}">{{{{PHONE}}}}</a><br>LINE: {{{{LINE_ID}}}}<br>{{{{EMAIL}}}}</p>
      </div>
    </div>
    <div class="footer-bottom">
      <p><strong>หากมีความคิดอยากทำร้ายตัวเองหรือผู้อื่น</strong> โทรสายด่วนสุขภาพจิต <a href="tel:1323">1323</a> (ตลอด 24 ชั่วโมง) หรือสายด่วนการแพทย์ฉุกเฉิน <a href="tel:1669">1669</a> หรือไปโรงพยาบาลที่ใกล้ที่สุดทันที</p>
      <p>เนื้อหาในเว็บไซต์นี้ให้ความรู้ทั่วไป ไม่ใช่คำวินิจฉัยหรือคำแนะนำทางการแพทย์สำหรับบุคคลใดบุคคลหนึ่ง และไม่สามารถใช้แทนการพบแพทย์ได้</p>
      <p>{DEMO_NOTICE}</p>
    </div>
  </div>
</footer>"""


def render(slug: str, meta: dict, body: str) -> str:
    title = meta["title"]
    full_title = (
        f"{CONFIG['CLINIC_FULL']} | ปรึกษาจิตแพทย์เรื่องการนอนหลับ"
        if meta.get("kind") == "home"
        else f"{title} | {CONFIG['CLINIC']}"
    )
    desc = esc_attr(meta["description"])
    robots = '\n<meta name="robots" content="noindex, nofollow">' if NOINDEX else ""
    hero = "" if meta.get("kind") in ("home", "bare") else inner_hero(meta)
    active = meta.get("nav", "")
    body_cls = f' class="{meta["body_class"]}"' if meta.get("body_class") else ""
    page = f"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc_attr(full_title)}</title>
<meta name="description" content="{desc}">{robots}
<meta name="theme-color" content="#0e1431">
<meta property="og:type" content="website">
<meta property="og:locale" content="th_TH">
<meta property="og:title" content="{esc_attr(full_title)}">
<meta property="og:description" content="{desc}">
<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
<link rel="preload" href="assets/fonts/noto-sans-thai-thai-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="assets/fonts/noto-serif-thai-thai-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="assets/styles.css">
</head>
<body{body_cls}>
<a class="skip-link" href="#main">ข้ามไปยังเนื้อหาหลัก</a>
<div class="demo-bar" role="note">{DEMO_NOTICE}</div>
<header class="site-header">
  <div class="container header-row">
    <a class="brand" href="index.html" aria-label="{{{{CLINIC}}}} หน้าแรก">
      <img src="assets/logo.svg" alt="" width="42" height="42">
      <span class="brand-text"><span class="brand-name">{{{{CLINIC}}}}</span><span class="brand-sub">{{{{CLINIC_TAGLINE}}}}</span></span>
    </a>
    <input type="checkbox" id="nav-toggle" class="nav-toggle">
    <label for="nav-toggle" class="nav-btn"><span class="bars" aria-hidden="true"></span>เมนู</label>
    <nav class="nav" aria-label="เมนูหลัก">
        {nav_html(active)}
    </nav>
  </div>
</header>
<main id="main">
{hero}
{body.strip()}
</main>
{footer_html()}
</body>
</html>
"""
    return substitute(page, slug)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
class Collector(HTMLParser):
    VOID = {"meta", "link", "img", "br", "hr", "input", "source", "col", "area", "base", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.links: list[tuple[str, str]] = []  # (attr, value)
        self.h1 = 0
        self.problems: list[str] = []
        self.stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "h1":
            self.h1 += 1
        if tag == "a" and "href" in a:
            self.links.append(("href", a["href"] or ""))
        if tag in ("link",) and "href" in a:
            self.links.append(("href", a["href"] or ""))
        if tag in ("img", "script", "source") and "src" in a:
            self.links.append(("src", a["src"] or ""))
        if tag == "img" and "alt" not in a:
            self.problems.append("<img> without alt")
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.problems.append(f"unbalanced </{tag}> (open: {self.stack[-3:]})")
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
        else:
            self.stack.pop()

    def close(self):
        super().close()
        if self.stack:
            self.problems.append(f"unclosed tags: {self.stack}")


def validate(files: list[Path]) -> list[str]:
    errors: list[str] = []
    parsed: dict[str, Collector] = {}
    for f in files:
        c = Collector()
        c.feed(f.read_text(encoding="utf-8"))
        c.close()
        parsed[f.name] = c
        if c.h1 != 1:
            errors.append(f"{f.name}: expected exactly 1 <h1>, found {c.h1}")
        dup = {i for i in c.ids if c.ids.count(i) > 1}
        if dup:
            errors.append(f"{f.name}: duplicate ids {sorted(dup)}")
        errors += [f"{f.name}: {p}" for p in c.problems]
    for name, c in parsed.items():
        for attr, value in c.links:
            if re.match(r"^(https?:|mailto:|tel:|data:)", value):
                continue
            if value.startswith("/"):
                errors.append(f"{name}: root-relative {attr} '{value}' will break on GitHub Pages sub-paths")
                continue
            target, _, anchor = value.partition("#")
            if not target:
                if anchor and anchor not in c.ids:
                    errors.append(f"{name}: missing anchor #{anchor}")
                continue
            tp = OUT / target
            if not tp.exists():
                errors.append(f"{name}: broken {attr} '{value}'")
            elif anchor and target.endswith(".html"):
                other = parsed.get(target)
                if other is not None and anchor not in other.ids:
                    errors.append(f"{name}: missing anchor '{value}'")
    return errors


def main() -> int:
    OUT.mkdir(exist_ok=True)
    built: list[Path] = []
    for src in sorted(PAGES.glob("*.html")):
        meta, body = parse_page(src)
        html = render(src.name, meta, substitute(body, src.name))
        dest = OUT / src.name
        dest.write_text(html, encoding="utf-8")
        built.append(dest)
        print(f"built {dest.relative_to(ROOT)}")
    # remove stale pages that no longer have a source
    for old in OUT.glob("*.html"):
        if old not in built:
            old.unlink()
            print(f"removed stale {old.relative_to(ROOT)}")
    errors = validate(built)
    if errors:
        print("\nVALIDATION FAILED:")
        for e in errors:
            print(" -", e)
        return 1
    print(f"\nOK: {len(built)} pages, no broken links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
