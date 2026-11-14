#!/usr/bin/env python3
"""Сборка сайта Bodbe Brothers из data/site.json.

    python3 tools/build.py            # обычная сборка в public/
    python3 tools/build.py --preview  # пометить незаполненные поля
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

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def esc(s: str) -> str:
    return html.escape(s, quote=True)


class Page:
    def __init__(self, data: dict, preview: bool):
        self.d = data
        self.preview = preview
        self.missing: list[str] = []

    # ---- доступ к данным -------------------------------------------------
    def raw(self, path: str):
        node = self.d
        for key in path.split("."):
            node = node[int(key)] if isinstance(node, list) else node.get(key)
            if node is None:
                return None
        return node

    def t(self, path: str, placeholder: str | None = None) -> str:
        """Текст из данных, уже экранированный. null → заглушка."""
        val = self.raw(path)
        if val is None:
            self.missing.append(path)
            ph = placeholder if placeholder is not None else self.t("ui.coming_soon")
            if self.preview:
                return f'<mark class="pv pv-null" title="Не заполнено: {esc(path)}">{ph}</mark>'
            return ph
        return esc(str(val))

    def n(self, path: str) -> int:
        return len(self.raw(path) or [])

    # ---- форматирование --------------------------------------------------
    @staticmethod
    def fmt_date(iso: str) -> str:
        d = dt.date.fromisoformat(iso)
        return f"{WEEKDAYS[d.weekday()]}, {MONTHS[d.month - 1]} {d.day}"

    @staticmethod
    def fmt_time(hhmm: str) -> str:
        h, m = (int(x) for x in hhmm.split(":"))
        suffix = "am" if h < 12 else "pm"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {suffix}" if m else f"{h12} {suffix}"

    def time_str(self) -> str:
        time = self.raw("schedule.time")
        return esc(self.fmt_time(time)) if time else self.t("schedule.time", self.t("ui.time_soon"))

    def schedule_line(self) -> str:
        """«1st & 3rd Tuesday of the month · 7 pm»."""
        return f"{self.t('schedule.regular')}&nbsp;· {self.time_str()}"

    def next_date(self) -> str:
        date = self.raw("schedule.next_meeting")
        if date:
            return esc(self.fmt_date(date))
        return self.t("schedule.next_meeting", self.t("ui.date_soon"))

    def img(self, base: str, widths: list[int], alt_path: str, sizes: str, cls: str = "",
            ratio: tuple[int, int] = (3, 2)) -> str:
        srcset = ", ".join(f"assets/img/{base}-{w}.webp {w}w" for w in widths)
        return (f'<img class="{cls}" src="assets/img/{base}-{widths[0]}.webp" srcset="{srcset}" '
                f'sizes="{sizes}" width="{ratio[0] * 100}" height="{ratio[1] * 100}" '
                f'alt="{self.t(alt_path)}" loading="lazy" decoding="async">')

    # ---- части страницы --------------------------------------------------
    def head(self) -> str:
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{self.t('ui.site_title')}</title>
<meta name="description" content="{self.t('ui.meta_description')}">
<meta name="theme-color" content="#140b00">
<link rel="icon" href="assets/img/favicon.svg" type="image/svg+xml">
<link rel="preload" href="assets/fonts/alegreya-latin-700-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="assets/style.css">
</head>"""

    def header(self) -> str:
        return f"""<a class="skip" href="#main">{self.t('ui.skip_link')}</a>
<header class="topbar">
  <div class="wrap topbar__in">
    <a class="brand" href="./">Bodbe Brothers</a>
  </div>
</header>"""

    def hero(self) -> str:
        if self.raw("schedule.next_meeting"):
            label = self.t("hero.cta_prefix")
            value = f"{self.next_date()}&nbsp;· {self.time_str()}"
        else:
            label = self.t("hero.cta_prefix_regular")
            value = self.schedule_line()
        return f"""<section class="hero" aria-labelledby="hero-title">
  <picture class="hero__media">
    <source media="(min-width: 900px)" srcset="assets/img/hero-1200.webp 1200w, assets/img/hero-1920.webp 1920w" sizes="100vw">
    <img src="assets/img/hero-m-600.webp" srcset="assets/img/hero-m-600.webp 600w, assets/img/hero-m-900.webp 900w" sizes="100vw" width="900" height="1125" alt="{self.t('hero.image_alt')}" fetchpriority="high">
  </picture>
  <div class="wrap hero__in">
    <div class="hero__text">
      <p class="eyebrow">{self.t('hero.eyebrow')}</p>
      <h1 id="hero-title" class="hero__title">{self.t('hero.title')}</h1>
      <p class="hero__tagline">{self.t('hero.tagline')}</p>
      <p class="hero__lead">{self.t('hero.lead')}</p>
      <a class="btn btn--gold" href="#when">
        <span class="btn__text"><span class="btn__label">{label}:</span> <span class="btn__value">{value}</span></span>
        <span class="btn__arrow" aria-hidden="true">↓</span>
      </a>
    </div>
  </div>
</section>"""

    def about(self) -> str:
        nots = "\n".join(
            f"        <li><strong>{self.t(f'about.nots.{i}.title')}</strong> {self.t(f'about.nots.{i}.text')}</li>"
            for i in range(self.n("about.nots")))
        photo = self.img("table", [720, 1200], "about.image_alt", "(min-width: 900px) 40vw, 100vw", cls="photo")
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

    def how(self) -> str:
        steps = []
        for i in range(self.n("how.steps")):
            tm = self.time_str() if i == 0 else self.t(f"how.steps.{i}.time")
            steps.append(f"""      <li class="step">
        <span class="step__num" aria-hidden="true">{i + 1}</span>
        <div>
          <h3>{self.t(f'how.steps.{i}.label')} <span class="step__time">{tm}</span></h3>
          <p>{self.t(f'how.steps.{i}.text')}</p>
        </div>
      </li>""")
        photo = self.img("singing", [720, 1200], "how.image_alt", "(min-width: 900px) 45vw, 100vw",
                         cls="photo photo--wide")
        return f"""<section class="section how" id="how" aria-labelledby="how-title">
  <div class="wrap how__grid">
    <div>
      <p class="kicker">{self.t('how.kicker')}</p>
      <h2 id="how-title">{self.t('how.title')}</h2>
      <ol class="steps">
{chr(10).join(steps)}
      </ol>
    </div>
    <figure class="how__figure">{photo}</figure>
  </div>
</section>"""

    def bodbe(self) -> str:
        paras = "\n".join(f"      <p>{self.t(f'bodbe.paras.{i}')}</p>" for i in range(self.n("bodbe.paras")))
        photo = self.img("kakheti", [900, 1600], "bodbe.image_alt", "(min-width: 900px) 45vw, 100vw",
                         cls="photo photo--wide", ratio=(16, 9))
        return f"""<section class="section band band--wine bodbe" id="bodbe" aria-labelledby="bodbe-title">
  <div class="wrap bodbe__grid">
    <div class="bodbe__text">
      <p class="kicker">{self.t('bodbe.kicker')}</p>
      <h2 id="bodbe-title">{self.t('bodbe.title')}</h2>
{paras}
    </div>
    <figure class="bodbe__figure">{photo}</figure>
  </div>
</section>"""

    def audio(self, i: int) -> str:
        name = self.raw(f"songs.items.{i}.audio")
        if name and (ASSETS / "audio" / name).is_file():
            return f'<audio controls preload="none" src="assets/audio/{esc(name)}"></audio>'
        if self.preview:
            return f'<p><mark class="pv pv-null">{self.t("ui.audio_soon")}</mark></p>'
        return ""

    def songs(self) -> str:
        items = []
        for i in range(self.n("songs.items")):
            note = self.raw(f"songs.items.{i}.note")
            note_html = f' <span class="song__note">{esc(note)}</span>' if note else ""
            items.append(f"""      <li class="song">
        <h3>{self.t(f'songs.items.{i}.title')}{note_html}</h3>
        <p>{self.t(f'songs.items.{i}.text')}</p>
        {self.audio(i)}
      </li>""")
        return f"""<section class="section songs" id="songs" aria-labelledby="songs-title">
  <div class="wrap">
    <p class="kicker">{self.t('songs.kicker')}</p>
    <h2 id="songs-title">{self.t('songs.title')}</h2>
    <p class="lead">{self.t('songs.intro')}</p>
    <ol class="song-list">
{chr(10).join(items)}
    </ol>
  </div>
</section>"""

    def goals(self) -> str:
        items = "\n".join(f"""      <li class="goal">
        <p class="goal__when">{self.t(f'goals.items.{i}.when')}</p>
        <h3>{self.t(f'goals.items.{i}.title')}</h3>
        <p>{self.t(f'goals.items.{i}.text')}</p>
      </li>""" for i in range(self.n("goals.items")))
        return f"""<section class="section goals" id="goals" aria-labelledby="goals-title">
  <div class="wrap">
    <p class="kicker">{self.t('goals.kicker')}</p>
    <h2 id="goals-title">{self.t('goals.title')}</h2>
    <ul class="goal-list">
{items}
    </ul>
  </div>
</section>"""

    def when(self) -> str:
        room_val = self.t("schedule.room")  # учитывается в отчёте, даже если не показан
        room = f"<br>{room_val}" if self.raw("schedule.room") or self.preview else ""
        parking_val = self.t("when.parking")
        parking = f'<p class="muted">{parking_val}</p>' if self.raw("when.parking") or self.preview else ""
        return f"""<section class="section band band--vine when" id="when" aria-labelledby="when-title">
  <div class="wrap">
    <p class="kicker">{self.t('when.kicker')}</p>
    <h2 id="when-title">{self.t('when.title')}</h2>
    <dl class="facts">
      <div class="fact">
        <dt>{self.t('when.day_label')}</dt>
        <dd class="fact__big">{self.schedule_line()}</dd>
      </div>
      <div class="fact">
        <dt>{self.t('when.next_label')}</dt>
        <dd>{self.next_date()}</dd>
      </div>
      <div class="fact">
        <dt>{self.t('when.where_label')}</dt>
        <dd>{self.t('venue.name')}<br>{self.t('venue.address_line1')}<br>{self.t('venue.address_line2')}{room}</dd>
      </div>
    </dl>
    {parking}
    <a class="btn btn--gold" href="{self.t('venue.maps_url')}" rel="noopener">
      <span class="btn__text">{self.t('when.map_button')}</span>
      <span class="btn__arrow" aria-hidden="true">↗</span>
    </a>
  </div>
</section>"""

    def faq(self) -> str:
        items = "\n".join(f"""      <details class="qa">
        <summary>{self.t(f'faq.items.{i}.q')}</summary>
        <p>{self.t(f'faq.items.{i}.a', self.t('ui.answer_soon'))}</p>
      </details>""" for i in range(self.n("faq.items")))
        return f"""<section class="section band band--stone faq" id="faq" aria-labelledby="faq-title">
  <div class="wrap">
    <p class="kicker">{self.t('faq.kicker')}</p>
    <h2 id="faq-title">{self.t('faq.title')}</h2>
    <div class="qa-list">
{items}
    </div>
  </div>
</section>"""

    def join(self) -> str:
        cards = []
        for i in range(self.n("join.ways")):
            key = self.raw(f"join.ways.{i}.key")
            extra = ""
            if key == "visit":
                extra = (f'<p class="way__extra">{self.schedule_line()}<br>'
                         f'{self.t("venue.address_line1")}, {self.t("venue.address_line2")}</p>')
            elif key == "phone":
                extra = (f'<p class="way__extra"><a class="way__link" href="tel:{self.t("venue.phone_tel")}">'
                         f'{self.t("venue.phone")}</a></p>')
            cards.append(f"""      <li class="way">
        <h3>{self.t(f'join.ways.{i}.title')}</h3>
        <p>{self.t(f'join.ways.{i}.text')}</p>
        {extra}
      </li>""")
        email = self.raw("contact.signup_email")
        if email:
            cards.append(f'      <li class="way"><h3>Email</h3><p class="way__extra">'
                         f'<a class="way__link" href="mailto:{esc(email)}">{esc(email)}</a></p></li>')
        else:
            ph = self.t("contact.signup_email")
            if self.preview:
                cards.append(f'      <li class="way"><h3>Email</h3><p>{ph}</p></li>')
        return f"""<section class="section join" id="join" aria-labelledby="join-title">
  <div class="wrap">
    <p class="kicker">{self.t('join.kicker')}</p>
    <h2 id="join-title">{self.t('join.title')}</h2>
    <ul class="ways">
{chr(10).join(cards)}
    </ul>
  </div>
</section>"""

    def footer(self) -> str:
        return f"""<footer class="footer">
  <div class="wrap footer__in">
    <div>
      <p class="footer__brand">Bodbe Brothers</p>
      <p>{self.t('footer.note')}</p>
      <p class="footer__small">{self.t('footer.images_note')}</p>
    </div>
    <div class="footer__venue">
      <p>{self.t('footer.venue_link')}: <a href="{self.t('venue.website')}" rel="noopener">{self.t('venue.website_label')}</a></p>
      <p>{self.t('venue.name')}<br>{self.t('venue.address_line1')}, {self.t('venue.address_line2')}<br>
      <a href="tel:{self.t('venue.phone_tel')}">{self.t('venue.phone')}</a></p>
    </div>
  </div>
</footer>"""

    def render(self) -> str:
        return "\n".join([
            self.head(),
            f'<body class="{"preview" if self.preview else ""}">',
            self.header(),
            '<main id="main">',
            self.hero(), self.about(), self.how(), self.bodbe(), self.songs(),
            self.goals(), self.when(), self.faq(), self.join(),
            "</main>",
            self.footer(),
            "</body>\n</html>\n",
        ])


def build(preview: bool) -> Page:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ASSETS, OUT / "assets", ignore=shutil.ignore_patterns("README*", ".gitkeep"))
    shutil.copy(SRC / "style.css", OUT / "assets" / "style.css")
    page = Page(data, preview)
    (OUT / "index.html").write_text(page.render(), encoding="utf-8")
    (OUT / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (OUT / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow\n", encoding="utf-8")
    return page


def report(page: Page, preview: bool) -> None:
    print(f"Собрано в public/ ({'предпросмотр' if preview else 'обычная сборка'})")
    miss = sorted(set(page.missing))
    print(f"  не заполнено (показана заглушка): {len(miss)}")
    for m in miss:
        print(f"      · {m}")


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
    ap.add_argument("--preview", action="store_true", help="пометить незаполненные поля")
    ap.add_argument("--serve", action="store_true", help="после сборки запустить локальный сервер")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    page = build(args.preview)
    report(page, args.preview)
    if args.serve:
        serve(args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
