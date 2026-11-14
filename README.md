# bodbebrothers.com

Статический сайт мужского певческого клуба Bodbe Brothers при храме святой Нины в Орландо.

**Статус:** шаг 2 из 4, на согласовании первый экран и раздел «Что это». Полный README (как поменять расписание, добавить песню и аудио, как опубликовать в Cloudflare Pages) будет на шаге 3.

## Открыть локально

```bash
python3 tools/build.py --serve
```

Потом откройте http://localhost:8000/. Нужен только Python 3.8+, без зависимостей.

С пометками незаполненных полей:

```bash
python3 tools/build.py --preview --serve
```

## Где что

- `data/site.json`: все тексты (EN и RU), расписание, контакты
- `src/style.css`, `src/nina-cross.svg`: стили и крест святой Нины
- `assets/`: шрифты (OFL), изображения (сгенерированы в Higgsfield), аудио
- `tools/build.py`: сборка в `public/`
- `DESIGN.md`, `PLAN.md`, `QUESTIONS.md`
