# Исходники сайта ЗНАКИ

- `site/index.html` — исходник страницы. Данные работ и художников — массивы `WORKS` и `PEOPLE` в скрипте внизу.
- `build.py` — сборка: `python3 build.py` (Python + Pillow, Node + Playwright). Делает готовый `index.html` с вписанными работами и авторами, JSON-LD, `sitemap.xml`, `robots.txt`, `llms.txt` в папку `out/`.
- Картинки: `site/img/works/` — работы, `site/img/artists/` — фото художников. Имена: `фамилия-имя-название-moskovskiy-soyuz-khudozhnikov.jpg`.
