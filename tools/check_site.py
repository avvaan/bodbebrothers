#!/usr/bin/env python3
"""Проверка собранного сайта (запускайте после tools/build.py).

    python3 tools/check_site.py             # проверить public/
    python3 tools/check_site.py --external  # заодно проверить внешние ссылки (нужен интернет)

Проверяет: битые внутренние ссылки и якоря, пустые или отсутствующие alt,
незаполненные поля в data/site.json, lang и noindex на каждой странице,
robots.txt, вес главной страницы, контраст цветов палитры. Грузинских надписей
на сайте быть не должно: найденные считаются ошибкой.
Код выхода 1, если есть ошибки (предупреждения не считаются).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public"
DATA = ROOT / "data" / "site.json"

HTML_BUDGET = 60 * 1024          # сама страница
INITIAL_BUDGET = 900 * 1024      # страница + CSS + шрифты + картинки (мобильный вариант)

GEORGIAN = re.compile(r"[Ⴀ-ჿᲐ-Ჿ]+(?:\s+[Ⴀ-ჿᲐ-Ჿ]+)*")


class Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []   # (attr, url)
        self.imgs: list[dict] = []
        self.ids: set[str] = set()
        self.html_lang = None
        self.robots = None
        self.text: list[str] = []
        self.picture_sources: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "html":
            self.html_lang = a.get("lang")
        if tag == "meta" and a.get("name") == "robots":
            self.robots = a.get("content", "")
        if tag == "a" and "href" in a:
            self.links.append(("href", a["href"]))
        if tag == "link" and "href" in a and a.get("rel") not in ("alternate",):
            self.links.append(("href", a["href"]))
        if tag in ("img", "audio", "source", "script") and "src" in a:
            self.links.append(("src", a["src"]))
        if tag in ("img", "source") and "srcset" in a:
            for part in a["srcset"].split(","):
                self.links.append(("srcset", part.strip().split()[0]))
        if tag == "source" and "srcset" in a:
            self.picture_sources.append(a["srcset"])
        if tag == "img":
            self.imgs.append(a)
        for k in ("aria-label", "alt", "title"):
            if k in a:
                self.text.append(a[k])

    def handle_data(self, data):
        self.text.append(data)


def contrast(c1: str, c2: str) -> float:
    def lum(hexc):
        hexc = hexc.lstrip("#")
        rgb = [int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    l1, l2 = sorted((lum(c1), lum(c2)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def walk_data(node, path=""):
    """Возвращает список путей к полям со значением null."""
    nulls = []
    if isinstance(node, dict):
        for k, v in node.items():
            if not k.startswith("_"):
                nulls += walk_data(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            nulls += walk_data(v, f"{path}.{i}")
    elif node is None:
        nulls.append(path)
    return nulls


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--external", action="store_true", help="проверить внешние ссылки по сети")
    args = ap.parse_args()

    errors: list[str] = []
    warns: list[str] = []
    info: list[str] = []
    externals: set[str] = set()
    georgian: dict[str, set[str]] = {}

    if not OUT.exists():
        print("Нет папки public/. Сначала: python3 tools/build.py")
        return 1

    data = json.loads(DATA.read_text(encoding="utf-8"))
    pages = sorted(OUT.rglob("*.html"))
    for page in pages:
        rel = page.relative_to(OUT)
        html = page.read_text(encoding="utf-8")
        c = Collector()
        c.feed(html)

        if 'class="pv' in html:
            errors.append(f"{rel}: в странице остались пометки предпросмотра — пересоберите без --preview")
        if c.html_lang != "en":
            errors.append(f"{rel}: нет или неверный lang у <html> ({c.html_lang!r})")
        if not c.robots or "noindex" not in c.robots:
            errors.append(f"{rel}: нет <meta name=robots content=noindex>")

        for img in c.imgs:
            alt = img.get("alt")
            if alt is None or not alt.strip():
                if img.get("role") != "presentation":
                    errors.append(f"{rel}: пустой или отсутствующий alt у {img.get('src')}")

        for attr, url in c.links:
            if url.startswith(("http://", "https://")):
                externals.add(url)
                continue
            if url.startswith(("tel:", "mailto:")):
                continue
            if url.startswith("#"):
                if url[1:] and url[1:] not in c.ids:
                    errors.append(f"{rel}: якорь {url} не найден")
                continue
            target = (page.parent / url.split("#")[0]).resolve()
            if url.endswith("/") or target.is_dir():
                target = target / "index.html"
            if not target.exists():
                errors.append(f"{rel}: битая ссылка {attr}={url}")

        for chunk in c.text:
            for m in GEORGIAN.findall(chunk):
                georgian.setdefault(m, set()).add(str(rel))

        if rel.name == "index.html" and len(rel.parts) == 1:
            size_html = len(html.encode("utf-8"))
            css = OUT / "assets" / "style.css"
            fonts = sum(f.stat().st_size for f in (OUT / "assets" / "fonts").glob("*.woff2"))
            # картинки: самый маленький вариант каждой <img> (как на телефоне)
            imgs = 0
            for img in c.imgs:
                cand = [img.get("src")]
                p = OUT / cand[0]
                if p.exists():
                    imgs += p.stat().st_size
            total = size_html + css.stat().st_size + fonts + imgs
            info.append(f"Главная: HTML {size_html / 1024:.0f} КБ, CSS {css.stat().st_size / 1024:.0f} КБ, "
                        f"шрифты {fonts / 1024:.0f} КБ, картинки (мобильные) {imgs / 1024:.0f} КБ, "
                        f"итого ≈ {total / 1024:.0f} КБ")
            if size_html > HTML_BUDGET:
                warns.append(f"HTML главной {size_html / 1024:.0f} КБ > {HTML_BUDGET // 1024} КБ")
            if total > INITIAL_BUDGET:
                warns.append(f"Вес главной ≈ {total / 1024:.0f} КБ > {INITIAL_BUDGET // 1024} КБ")

    robots = OUT / "robots.txt"
    if not robots.exists() or "Disallow: /" not in robots.read_text():
        errors.append("robots.txt отсутствует или не закрывает сайт")

    # данные
    nulls = walk_data(data)

    # контраст палитры (значения из src/style.css)
    css_src = (ROOT / "src" / "style.css").read_text(encoding="utf-8")
    tokens = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", css_src))
    pairs = [("cream", "espresso"), ("muted", "espresso"), ("espresso", "gold"), ("gold", "espresso"),
             ("cream", "wine"), ("gold-hi", "wine"), ("cream", "vine"), ("gold-hi", "vine"),
             ("ink", "stone"), ("muted", "cocoa"), ("gold", "walnut")]
    for fg, bg in pairs:
        if fg in tokens and bg in tokens:
            r = contrast(tokens[fg], tokens[bg])
            line = f"контраст {fg} на {bg}: {r:.1f}:1"
            if r < 4.5:
                (warns if fg == "gold" and bg == "walnut" else errors).append(line + " (< 4.5, ниже AA)")
            else:
                info.append(line)

    if args.external:
        for url in sorted(externals):
            try:
                req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "site-check"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    if r.status >= 400:
                        errors.append(f"внешняя ссылка {url}: HTTP {r.status}")
            except Exception as e:  # noqa: BLE001
                warns.append(f"внешняя ссылка {url}: {e}")

    print(f"Проверено страниц: {len(pages)}")
    for line in info:
        print("  ·", line)
    if nulls:
        print(f"\nНезаполненные поля в data/site.json ({len(nulls)}), на сайте показана заглушка:")
        for n in nulls:
            print("  ·", n)
    for g, where in georgian.items():
        errors.append(f"грузинская надпись «{g}» ({', '.join(sorted(where))}) — на сайте их быть не должно")
    if externals and not args.external:
        print(f"\nВнешних ссылок: {len(externals)} (не проверялись; добавьте --external)")
    if warns:
        print("\nПредупреждения:")
        for w in warns:
            print("  !", w)
    if errors:
        print("\nОШИБКИ:")
        for e in errors:
            print("  ✗", e)
        return 1
    print("\nОшибок нет.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
