# bodbebrothers.com

Статический сайт мужского певческого клуба **Bodbe Brothers** при храме святой Нины
(Saint Nina Orthodox Church, Орландо). Одна страница на английском.

Сайт собирается из одного файла данных `data/site.json` маленьким скриптом на Python.
Без фреймворков, без npm, без зависимостей, без трекеров и внешних шрифтов.

## Открыть локально

Нужен Python 3.8 или новее (на Mac и Linux обычно уже есть).

```bash
python3 tools/build.py --serve
```

Откройте http://localhost:8000/. Остановить сервер: Ctrl+C.

Предпросмотр с пометками: незаполненные поля выделены розовым, непереведённые синим.

```bash
python3 tools/build.py --preview --serve
```

Проверка перед публикацией: ссылки, alt, переводы, вес страницы, контраст, грузинские надписи.

```bash
python3 tools/build.py && python3 tools/check_site.py
```

## Как поменять расписание

Откройте `data/site.json`, найдите блок `"schedule"`:

```json
"schedule": {
  "next_meeting": null,
  "time": "19:00",
  "regular": { "en": "Tuesdays", "ru": "По вторникам" },
  "room": { "en": null, "ru": null }
}
```

- **Дата ближайшей встречи**: вместо `null` напишите дату в кавычках в формате ГГГГ-ММ-ДД, например `"next_meeting": "2026-12-01"`. Сайт сам напишет «Tuesday, December 1». Пока там `null`, на кнопке показывается регулярное расписание («Tuesdays · 7 pm»).
- **Время**: 24-часовой формат, `"19:00"`. На сайте получится «7 pm».
- **День**: `"regular"`. Английский текст в `"en"`.
- **Помещение** (трапезная, зал): `"room"`, например `{ "en": "Parish hall", "ru": "Трапезная" }`.

Сохраните файл и пересоберите (`python3 tools/build.py`). Если сайт опубликован в Cloudflare Pages
и подключён к GitHub, достаточно сохранить изменение в репозитории: сборка запустится сама.

`null` означает «пока неизвестно»: на сайте вместо значения стоит понятная заглушка
(«date coming soon», «We'll answer this one soon»). Не подставляйте примерные значения:
человек придёт по выдуманному расписанию к закрытой двери.

## Как добавить песню

В `data/site.json`, блок `"songs"` → `"items"`, добавьте ещё один элемент по образцу:

```json
{
  "title": { "en": "Song title", "ru": "Название" },
  "note":  { "en": "Subtitle or original title", "ru": "" },
  "text":  { "en": "One or two sentences about the song.", "ru": "..." },
  "audio": null
}
```

Не забудьте запятую между элементами списка. `note` можно оставить `null`.
Заголовок раздела «The first four songs» тоже лежит в данных (`songs.title`), поменяйте число.

## Как добавить аудио для разучивания

1. Положите файл в `assets/audio/`, например `assets/audio/many-years.mp3`. Формат MP3, моно, 96–128 кбит/с: так файл весит 1–2 МБ.
2. У нужной песни напишите `"audio": "many-years.mp3"`.
3. Пересоберите. Плеер появится только если файл действительно лежит в папке; нет файла, нет плеера.

Только свои записи. Чужие записи на сайт не кладём.

## Как заменить фотографии

Сейчас все фото сгенерированы в Higgsfield и помечены на странице как иллюстрации.
Когда появятся настоящие снимки (только с согласия людей на них), подготовьте WebP
с теми же именами и размерами в `assets/img/`:

| Файл | Где | Размеры |
|---|---|---|
| `hero-1200.webp`, `hero-1920.webp` | первый экран, компьютер | 16:9 |
| `hero-m-600.webp`, `hero-m-900.webp` | первый экран, телефон | 4:5 |
| `table-720.webp`, `table-1200.webp` | «A club, not a choir loft» | 3:2 |
| `singing-720.webp`, `singing-1200.webp` | «Three steps» | 3:2 |

Поправьте тексты `image_alt` в данных и уберите `footer.images_note`.

## Русская версия

Сейчас собирается только английская. Русские тексты в `data/site.json` сохранены.
Чтобы включить версию `/ru/`, поменяйте `"languages": ["en"]` на `"languages": ["en", "ru"]`:
появятся страница `/ru/` и переключатель языка в шапке.

## Публикация в Cloudflare Pages

> **Не публиковать без слова «публикуй» от о. Андрея.** Ниже только инструкция.
> Домен `bodbebrothers.com` уже в Cloudflare. Записи DNS руками не трогать: Pages добавит их сам.

1. Cloudflare → **Workers & Pages** → **Create** → **Pages** → **Connect to Git** → репозиторий `bodbebrothers`.
2. Настройки сборки:
   - Framework preset: **None**
   - Build command: `python3 tools/build.py`
   - Build output directory: `public`
   - Production branch: та ветка, в которую сольют эту работу (например `main`).
3. **Save and Deploy**. Сайт появится на адресе вида `bodbebrothers.pages.dev`; проверьте его с телефона.
4. Проект → **Custom domains** → **Set up a custom domain** → `bodbebrothers.com` (и при желании `www.bodbebrothers.com`). Cloudflare сам создаст нужные записи, потому что домен в том же аккаунте.

Пока клуб не начался, сайт закрыт от поисковиков тремя способами:
`<meta name="robots" content="noindex">` на странице, `robots.txt` с `Disallow: /`
и заголовок `X-Robots-Tag` в `public/_headers`. Когда решите открыть сайт:
уберите строку с `robots` в `tools/build.py` (функция `head`), поменяйте `robots.txt`
и `_headers` в функции `build`.

## Где что лежит

```
data/site.json        все тексты, расписание, контакты, песни
src/style.css         стили
src/nina-cross.svg    крест святой Нины из лозы (из Higgsfield)
assets/fonts/         Alegreya, Alegreya Sans, Noto Serif Georgian (SIL OFL, лицензии рядом)
assets/img/           изображения (WebP) и favicon
assets/audio/         записи для разучивания (пока пусто)
tools/build.py        сборка в public/
tools/check_site.py   проверка
DESIGN.md             дизайн: палитра, шрифты, сетка
PLAN.md               план страницы
QUESTIONS.md          вопросы к о. Андрею
```

Папка `public/` создаётся сборкой и в репозиторий не попадает.
