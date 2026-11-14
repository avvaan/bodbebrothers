#!/usr/bin/env python3
"""Сборка сайта Bodbe Brothers из data/site.json.

    python3 tools/build.py            # обычная сборка в public/
    python3 tools/build.py --preview  # пометить незаполненные поля и непереведённое
    python3 tools/build.py --serve    # собрать и открыть на http://localhost:8000

Только стандартная библиотека Python 3.8+. Никаких зависимостей.
"""
from __future__ import annotations

import argparse
import datetime as dt
import functools
import html
import http.server
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "site.json"
SRC = ROOT / "src"
ASSETS = ROOT / "assets"
OUT = ROOT / "public"
LANGS = ("en", "ru")

MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
           "августа", "сентября", "октября", "ноября", "декабря"],
}
WEEKDAYS = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "ru": ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"],
}


def esc(s: str) -> str:
    return html.escape(s, quote=True)


class Page:
    """Рендер одной языковой версии. Собирает отчёт о пропусках."""

    def __init__(self, data: dict, lang: str, preview: bool):
        self.d = data
        self.lang = lang
        self.preview = preview
        self.missing: list[str] = []      # поля null
        self.untranslated: list[str] = []  # нет перевода на этот язык

    # ---- доступ к данным -------------------------------------------------
    def get(self, path: str):
        node = self.d
        for key in path.split("."):
            node = node[int(key)] if isinstance(node, list) else node.get(key)
            if node is None:
                return None
        return node

    def t(self, path: str, placeholder: str | None = None) -> str:
        """Текст для текущего языка, уже экранированный HTML."""
        val = self.get(path)
        if isinstance(val, dict) and set(val) & set(LANGS):
            text = val.get(self.lang)
            if text is None:
                other = next((val[l] for l in LANGS if val.get(l)), None)
                if other is not None:
                    self.untranslated.append(path)
                    if self.preview:
                        return f'<mark class="pv pv-tr" title="Нет перевода: {esc(path)}">{esc(other)}</mark>'
                    return esc(other)
                val = None
            else:
                val = text
        if val is None:
            self.missing.append(path)
            ph = placeholder if placeholder is not None else self.ui("coming_soon")
            if self.preview:
                return f'<mark class="pv pv-null" title="Не заполнено: {esc(path)}">{ph}</mark>'
            return ph
        return esc(str(val))

    def ui(self, key: str) -> str:
        return self.t(f"ui.{key}")

    def raw(self, path: str):
        return self.get(path)

    # ---- форматирование --------------------------------------------------
    def fmt_date(self, iso: str) -> str:
        d = dt.date.fromisoformat(iso)
        wd = WEEKDAYS[self.lang][d.weekday()]
        if self.lang == "ru":
            return f"{wd}, {d.day} {MONTHS['ru'][d.month - 1]}"
        return f"{wd}, {MONTHS['en'][d.month - 1]} {d.day}"

    def fmt_time(self, hhmm: str) -> str:
        h, m = (int(x) for x in hhmm.split(":"))
        if self.lang == "ru":
            return f"{h}:{m:02d}"
        suffix = "am" if h < 12 else "pm"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {suffix}" if m else f"{h12} {suffix}"

    def next_meeting(self) -> str:
        date = self.raw("schedule.next_meeting")
        time = self.raw("schedule.time")
        if not date:
            return self.t("schedule.next_meeting", self.ui("date_soon"))
        out = esc(self.fmt_date(date))
        if time:
            out += " · " + esc(self.fmt_time(time))
        else:
            out += " · " + self.t("schedule.time")
        return out

    # ---- части страницы --------------------------------------------------
    def img(self, base: str, widths: list[int], alt_path: str, sizes: str,
            cls: str = "", eager: bool = False, w_h: tuple[int, int] = (3, 2)) -> str:
        srcset = ", ".join(f"{self.prefix}assets/img/{base}-{w}.webp {w}w" for w in widths)
        largest = widths[-1] if widths[-1] > widths[0] else widths[0]
        loading = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
        return (f'<img class="{cls}" src="{self.prefix}assets/img/{base}-{widths[0]}.webp" '
                f'srcset="{srcset}" sizes="{sizes}" width="{w_h[0] * 100}" height="{w_h[1] * 100}" '
                f'alt="{self.t(alt_path)}" {loading}>')

    @property
    def prefix(self) -> str:
        return "" if self.lang == "en" else "../"

    def head(self) -> str:
        other = "ru" if self.lang == "en" else "en"
        here = "/" if self.lang == "en" else "/ru/"
        there = "/ru/" if self.lang == "en" else "/"
        return f"""<!doctype html>
<html lang="{self.lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{self.ui('site_title')}</title>
<meta name="description" content="{self.ui('meta_description')}">
<meta name="theme-color" content="#140b00">
<link rel="alternate" hreflang="{self.lang}" href="{here}">
<link rel="alternate" hreflang="{other}" href="{there}">
<link rel="icon" href="{self.prefix}assets/img/favicon.svg" type="image/svg+xml">
<link rel="preload" href="{self.prefix}assets/fonts/alegreya-latin-500-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{self.prefix}assets/style.css">
</head>"""

    def header(self) -> str:
        switch_href = "ru/" if self.lang == "en" else "../"
        other = "ru" if self.lang == "en" else "en"
        return f"""<a class="skip" href="#main">{self.ui('skip_link')}</a>
<header class="topbar">
  <div class="wrap topbar__in">
    <a class="brand" href="./" aria-label="Bodbe Brothers">
      <span class="brand__cross" aria-hidden="true">{self.cross}</span>
      <span>Bodbe Brothers</span>
    </a>
    <a class="lang" href="{switch_href}" hreflang="{other}" lang="{other}" aria-label="{self.ui('lang_switch_aria')}">{self.ui('lang_switch_label')}</a>
  </div>
</header>"""

    def hero(self) -> str:
        return f"""<section class="hero" aria-labelledby="hero-title">
  <picture class="hero__media">
    <source media="(min-width: 900px)" srcset="{self.prefix}assets/img/hero-1200.webp 1200w, {self.prefix}assets/img/hero-1920.webp 1920w" sizes="100vw">
    <img src="{self.prefix}assets/img/hero-m-600.webp" srcset="{self.prefix}assets/img/hero-m-600.webp 600w, {self.prefix}assets/img/hero-m-900.webp 900w" sizes="100vw" width="900" height="1125" alt="{self.t('hero.image_alt')}" fetchpriority="high">
  </picture>
  <div class="wrap hero__in">
    <div class="hero__text">
      <p class="eyebrow">{self.t('hero.eyebrow')}</p>
      <h1 id="hero-title" class="hero__title">{self.t('hero.title')}</h1>
      <p class="hero__tagline">{self.t('hero.tagline')}</p>
      <p class="hero__lead">{self.t('hero.lead')}</p>
      <a class="btn btn--gold" href="#when">
        <span class="btn__text"><span class="btn__label">{self.t('hero.cta_prefix')}:</span> <span class="btn__value">{self.next_meeting()}</span></span>
        <span class="btn__arrow" aria-hidden="true">↓</span>
      </a>
    </div>
  </div>
</section>"""

    def about(self) -> str:
        nots = "\n".join(
            f"""        <li><strong>{self.t(f'about.nots.{i}.title')}</strong> {self.t(f'about.nots.{i}.text')}</li>"""
            for i in range(len(self.raw("about.nots") or []))
        )
        photo = self.img("table", [720, 1200], "about.image_alt",
                         "(min-width: 900px) 40vw, 100vw", cls="photo")
        return f"""<section class="section about" id="about" aria-labelledby="about-title">
  <div class="wrap about__grid">
    <div class="about__text">
      <p class="kicker">{self.t('about.kicker')}</p>
      <h2 id="about-title">{self.t('about.title')}</h2>
      <p class="lead">{self.t('about.body')}</p>
      <h3 class="about__not-title">{self.t('about.not_title')}</h3>
      <ul class="nots">
{nots}
      </ul>
      <p class="closer">{self.t('about.closer')}</p>
    </div>
    <figure class="about__figure">{photo}</figure>
  </div>
</section>"""

    def stub(self) -> str:
        # Временная заглушка для шага 2: остальные разделы появятся после одобрения дизайна.
        anchor = "when"
        msg = {"en": "The rest of the page is on its way.",
               "ru": "Остальная часть страницы в работе."}[self.lang]
        return f"""<section class="section stub" id="{anchor}">
  <div class="wrap"><p class="kicker">{msg}</p></div>
</section>"""

    def footer(self) -> str:
        return f"""<footer class="footer">
  <div class="wrap footer__in">
    <p class="footer__brand"><span class="brand__cross" aria-hidden="true">{self.cross}</span> Bodbe Brothers</p>
    <p><a href="{self.t('parish.website')}">{self.t('parish.name')}</a><br>
    {self.t('parish.address_line1')}, {self.t('parish.address_line2')}</p>
  </div>
</footer>"""

    def render(self) -> str:
        self.cross = (SRC / "nina-cross.svg").read_text(encoding="utf-8")
        self.cross = self.cross.replace("<title>Grapevine cross of Saint Nina</title>", "")
        body_cls = "preview" if self.preview else ""
        return "\n".join([
            self.head(),
            f'<body class="{body_cls}">',
            self.header(),
            '<main id="main">',
            self.hero(),
            self.about(),
            self.stub(),
            "</main>",
            self.footer(),
            "</body>\n</html>\n",
        ])


def build(preview: bool) -> list[Page]:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ASSETS, OUT / "assets",
                    ignore=shutil.ignore_patterns("README*", ".gitkeep"))
    shutil.copy(SRC / "style.css", OUT / "assets" / "style.css")
    pages = []
    for lang in LANGS:
        page = Page(data, lang, preview)
        target = OUT / ("index.html" if lang == "en" else "ru/index.html")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page.render(), encoding="utf-8")
        pages.append(page)
    (OUT / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (OUT / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow\n", encoding="utf-8")
    return pages


def report(pages: list[Page], preview: bool) -> None:
    print(f"Собрано в {OUT.relative_to(ROOT)}/ ({'предпросмотр' if preview else 'обычная сборка'})")
    for p in pages:
        miss = sorted(set(p.missing))
        untr = sorted(set(p.untranslated))
        print(f"  [{p.lang}] не заполнено: {len(miss)}; без перевода: {len(untr)}")
        for m in miss:
            print(f"      · {m}")
        for u in untr:
            print(f"      ~ {u} (нет перевода)")


def serve(port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Сайт: http://localhost:{port}/   (Ctrl+C — остановить)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preview", action="store_true", help="пометить незаполненные и непереведённые поля")
    ap.add_argument("--serve", action="store_true", help="после сборки запустить локальный сервер")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    pages = build(args.preview)
    report(pages, args.preview)
    if args.serve:
        serve(args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
