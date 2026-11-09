"""Сборка сайта ЗНАКИ: site/index.html (исходник) -> out/ (то, что лежит на GitHub).

1. оборачивает исходник в полноценный HTML;
2. открывает страницу в браузере и забирает готовую разметку работ и авторов,
   чтобы она была в HTML сразу (для Яндекса, Алисы и ИИ без выполнения скриптов);
3. добавляет JSON-LD, размеры картинок, sitemap.xml, robots.txt, llms.txt, манифест.
"""
import json, os, re, shutil, subprocess, sys, datetime
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, 'site')
OUT = os.path.join(ROOT, 'out')
URL = 'https://nazarovbruni.github.io/znaki/'
SECTION_URL = 'https://artanum.ru/examination/index.php?id=26'
MSH_URL = 'https://artanum.ru/'

os.makedirs(OUT, exist_ok=True)

# 1. обёртка
src = open(os.path.join(SITE, 'index.html'), encoding='utf-8').read()
head, rest = src.split('</style>', 1)
page = ('<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        + head + '</style>\n</head>\n<body>\n' + rest.lstrip() + '\n</body>\n</html>\n')

# статика
for name in ['favicon.ico', 'favicon.svg', 'icon-192.png', 'icon-512.png', 'apple-touch-icon.png']:
    shutil.copy(os.path.join(SITE, name), os.path.join(OUT, name))
if os.path.exists(os.path.join(OUT, 'img')):
    shutil.rmtree(os.path.join(OUT, 'img'))
shutil.copytree(os.path.join(SITE, 'img'), os.path.join(OUT, 'img'),
                ignore=shutil.ignore_patterns('znak-*.jpg', 'yulia-nazar.jpg'))

tmp = os.path.join(OUT, '_render.html')
open(tmp, 'w', encoding='utf-8').write(page)

# 2. пререндер
js = r"""
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1366, height: 900 } });
  await p.goto('file://' + process.argv[2]);
  await p.waitForTimeout(300);
  const r = await p.evaluate(() => ({
    works: document.getElementById('works').innerHTML,
    people: document.getElementById('people').innerHTML,
    series: document.getElementById('series').innerHTML,
    bu: document.getElementById('bu-grid').innerHTML,
    W: WORKS, P: PEOPLE, SER: SERIES, SER_A: SERIES_AUTHOR, BU: BU,
  }));
  console.log(JSON.stringify(r));
  await b.close();
})();
"""
jsf = os.path.join(OUT, '_render.js')
open(jsf, 'w').write(js)
res = json.loads(subprocess.check_output(['node', jsf, tmp], cwd=ROOT).decode())
os.remove(jsf); os.remove(tmp)

def clean(h):
    h = re.sub(r'\s+is-in', '', h)
    return re.sub(r'\n\s*\n', '\n', h).strip()

page = page.replace('<ul class="grid" id="works"></ul>',
                    '<ul class="grid" id="works">\n' + clean(res['works']) + '\n</ul>', 1)
page = page.replace('<ol class="digital__signs" id="series"></ol>',
                    '<ol class="digital__signs" id="series">\n' + clean(res['series']) + '\n</ol>', 1)
page = page.replace('<ol class="bu__grid" id="bu-grid"></ol>',
                    '<ol class="bu__grid" id="bu-grid">\n' + clean(res['bu']) + '\n</ol>', 1)
page = page.replace('<ul class="people" id="people"></ul>',
                    '<ul class="people" id="people">\n' + clean(res['people']) + '\n</ul>', 1)

# WebP-версии работ и фото (полная и 800px) + <picture>
def webp_variants(rel):
    src_path = os.path.join(SITE, rel)
    base = os.path.splitext(rel)[0]
    im = Image.open(src_path).convert('RGB')
    w, h = im.size
    out = []
    im.save(os.path.join(OUT, base + '.webp'), 'WEBP', quality=80, method=6)
    if 600 < w <= 1000:
        im.resize((480, round(h * 480 / w)), Image.LANCZOS).save(
            os.path.join(OUT, base + '-480.webp'), 'WEBP', quality=80, method=6)
        out.append((base + '-480.webp', 480))
    if w > 1000:
        im.resize((800, round(h * 800 / w)), Image.LANCZOS).save(
            os.path.join(OUT, base + '-800.webp'), 'WEBP', quality=80, method=6)
        out.append((base + '-800.webp', 800))
    if w > 1700:
        im.resize((1400, round(h * 1400 / w)), Image.LANCZOS).save(
            os.path.join(OUT, base + '-1400.webp'), 'WEBP', quality=80, method=6)
        out.append((base + '-1400.webp', 1400))
    out.append((base + '.webp', w))
    return out

SIZES = {'works': '(max-width: 620px) 100vw, (max-width: 960px) 50vw, 400px',
         'artists': '(max-width: 620px) 50vw, (max-width: 960px) 50vw, 380px'}
def to_picture(m):
    tag, rel = m.group(0), m.group(1)
    kind = rel.split('/')[1]
    srcset = ', '.join(f'{f} {w}w' for f, w in webp_variants(rel))
    sizes = '(max-width: 960px) 100vw, 1240px' if 'data-wide' in tag else SIZES[kind]
    return f'<picture><source type="image/webp" srcset="{srcset}" sizes="{sizes}">{tag}</picture>'
page = re.sub(r'<img src="(img/(?:works|artists)/[^"]+\.jpg)"[^>]*>', to_picture, page)

# WebP для всех картинок работ и фото (их открывают и во всплывающем окне)
for kind in ('works', 'artists'):
    for f in sorted(os.listdir(os.path.join(SITE, 'img', kind))):
        if f.endswith('.jpg') and not os.path.exists(os.path.join(OUT, 'img', kind, f[:-4] + '.webp')):
            webp_variants('img/%s/%s' % (kind, f))

# размеры картинок (против прыжков вёрстки)
def add_size(m):
    tag, src_ = m.group(0), m.group(1)
    if 'width=' in tag:
        return tag
    path = os.path.join(SITE, src_)
    if not os.path.exists(path):
        return tag
    w, h = Image.open(path).size
    return tag[:-1] + f' width="{w}" height="{h}">'
page = re.sub(r'<img src="(img/[^"]+)"[^>]*>', add_size, page)

# 3. JSON-LD
W, P, SER, SER_A, BU = res['W'], res['P'], res['SER'], res['SER_A'], res['BU']
BUIMG = lambda slug: 'img/works/bukheevy-bulkin-mikheeva-%s-moskovskiy-soyuz-khudozhnikov.jpg' % slug
SIGN = lambda x: 'img/works/mamchur-yuriy-%s-moskovskiy-soyuz-khudozhnikov.png' % x['slug']
SCENE = lambda x: 'img/works/mamchur-yuriy-%s-sreda-moskovskiy-soyuz-khudozhnikov.jpg' % x['slug']
COVER = 'img/works/mamchur-yuriy-znaki-tsifrovogo-antropogeneza-moskovskiy-soyuz-khudozhnikov.jpg'
BOX = 'img/works/mamchur-yuriy-znaki-tsifrovogo-antropogeneza-korobka-moskovskiy-soyuz-khudozhnikov.jpg'
def strip_tags(t):
    return re.sub(r'<[^>]+>', '', t)

section = {'@type': 'Organization', '@id': URL + '#section',
           'name': 'Секция плаката РОО «Московский союз художников»', 'url': SECTION_URL,
           'parentOrganization': {'@type': 'Organization', '@id': URL + '#msh',
                                  'name': 'Московский союз художников', 'alternateName': 'МСХ',
                                  'url': MSH_URL, 'logo': URL + 'img/msh-logo.png'}}
persons = []
for i, p in enumerate(P):
    if p.get('empty'):
        continue
    if p.get('group'):
        d = {'@type': 'Organization', '@id': URL + '#artist-' + str(i + 1), 'name': p['n'],
             'alternateName': 'Бухеевы', 'description': strip_tags(p['lead']),
             'member': [{'@type': 'Person', 'name': m_, 'jobTitle': 'Художник', 'memberOf': {'@id': URL + '#msh'}} for m_ in p['group']]}
    else:
        d = {'@type': 'Person', '@id': URL + '#artist-' + str(i + 1), 'name': p['n'],
             'description': strip_tags(p['lead']),
             'memberOf': {'@id': URL + '#msh'}, 'jobTitle': 'Художник'}
    if p.get('photo'):
        d['image'] = URL + p['photo']
    links = [m for k, v in p['rows'] for m in re.findall(r'href="([^"]+)"', v) if 'artanum.ru' not in m and m.startswith('http')]
    if links:
        d['sameAs'] = links
    persons.append(d)
pid = {p['name']: p['@id'] for p in persons}
artworks = []
for i, w in enumerate(W):
    if w.get('empty') or w.get('series') or not (w.get('img') or w.get('video')):
        continue
    a = {'@type': 'VisualArtwork', '@id': URL + '#znak-%02d' % (i + 1),
         'name': 'Знак «%s»' % w['t'], 'url': URL + '#znak-%02d' % (i + 1),
         'creator': {'@id': pid.get(w['a'])} if w['a'] in pid else {'@type': 'Person', 'name': w['a']},
         'artform': 'Плакат', 'inLanguage': 'ru',
         'isPartOf': {'@id': URL + '#exhibition'}}
    if w.get('img'):
        a['image'] = [URL + w['card'], URL + w['img']] if w.get('card') else URL + w['img']
    if w.get('means'):
        a['description'] = strip_tags(w['means'])
    artworks.append(a)

ser_parts = []
for i, x in enumerate(SER):
    ser_parts.append({'@type': 'VisualArtwork', '@id': URL + '#digital-%d' % (i + 1),
        'name': 'Знак «%s»' % x['t'], 'alternateName': x['en'], 'url': URL + '#digital-%d' % (i + 1),
        'creator': {'@id': pid.get(SER_A)}, 'artform': 'Графика', 'inLanguage': 'ru',
        'image': [URL + SIGN(x), URL + SCENE(x)], 'description': x['concept'] + ' ' + x['depth']})
series_node = {'@type': 'CreativeWorkSeries', '@id': URL + '#digital', 'name': 'Знаки цифрового антропогенеза',
    'creator': {'@id': pid.get(SER_A)}, 'dateCreated': '2026', 'url': URL + '#digital',
    'image': [URL + COVER, URL + BOX], 'isPartOf': {'@id': URL + '#exhibition'},
    'hasPart': [{'@id': x['@id']} for x in ser_parts],
    'description': 'Графическое исследование тектонических сдвигов в человеческой природе: серия из пяти знаков о новом виде человека, изменённого интерфейсами, алгоритмами и цифровой средой.'}
artworks += [series_node] + ser_parts
bu_parts = []
for i, b in enumerate(BU):
    imgs_ = [URL + BUIMG(f) for f in b['frames']] if b.get('frames') else URL + BUIMG(b['slug'])
    bu_parts.append({'@type': 'VisualArtwork', '@id': URL + '#bukhei-%d' % (i + 1), 'name': 'Знак «%s»' % b['t'],
        'url': URL + '#bukhei-%d' % (i + 1), 'creator': {'@id': pid.get('БУ ХЕЕВЫ')}, 'artform': 'Плакат', 'inLanguage': 'ru',
        'image': imgs_, 'description': strip_tags(b['means'])})
artworks += [{'@type': 'CreativeWorkSeries', '@id': URL + '#bukhei', 'name': 'Бухейпроект',
    'alternateName': 'Постероконцептуализм', 'creator': {'@id': pid.get('БУ ХЕЕВЫ')}, 'url': URL + '#bukhei',
    'image': URL + 'img/artists/bukheevy-bulkin-sergey-mikheeva-evgeniya-moskovskiy-soyuz-khudozhnikov.jpg',
    'isPartOf': {'@id': URL + '#exhibition'}, 'hasPart': [{'@id': x['@id']} for x in bu_parts],
    'description': 'Спецпроект арт-группы БУ ХЕЕВЫ (Сергей Булкин и Евгения Михеева): 16 знаков-идеограмм в духе постероконцептуализма — теории, по которой плакат одновременно самодостаточен, становится частью общей картины, обретает значимость через тиражирование и переходит из плоскости в объём.'}] + bu_parts

desc = re.search(r'<meta name="description" content="([^"]+)"', page).group(1)
title = re.search(r'<title>([^<]+)</title>', page).group(1)
graph = [
    {'@type': 'WebSite', '@id': URL + '#site', 'url': URL, 'name': 'ЗНАКИ', 'inLanguage': 'ru',
     'description': desc, 'publisher': {'@id': URL + '#section'}},
    {'@type': 'WebPage', '@id': URL + '#page', 'url': URL, 'name': title, 'description': desc,
     'inLanguage': 'ru', 'isPartOf': {'@id': URL + '#site'},
     'primaryImageOfPage': URL + 'img/og-znaki.jpg', 'about': {'@id': URL + '#exhibition'}},
    {'@type': 'ExhibitionEvent', '@id': URL + '#exhibition', 'name': 'ЗНАКИ',
     'alternateName': 'Виртуальная выставка «ЗНАКИ»', 'description': desc, 'url': URL,
     'image': URL + 'img/og-znaki.jpg', 'inLanguage': 'ru',
     'startDate': '2026-12-01', 'endDate': '2026-12-31',
     'eventStatus': 'https://schema.org/EventScheduled',
     'eventAttendanceMode': 'https://schema.org/OnlineEventAttendanceMode',
     'location': {'@type': 'VirtualLocation', 'url': URL},
     'isAccessibleForFree': True,
     'organizer': [{'@id': URL + '#section'}, {'@type': 'Person', 'name': 'Юлия Назар',
                                               'jobTitle': 'Куратор', 'url': 'https://julianazar.ru'}],
     'performer': [{'@id': p['@id']} for p in persons],
     'sponsor': {'@type': 'Organization', 'name': 'Галерея «Глубина»', 'alternateName': 'Glubina Gallery', 'url': 'https://galleryglubina.ru'},
     'workFeatured': [{'@id': a['@id']} for a in artworks]},
    section, *persons, *artworks,
]
ld = json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False, indent=1)
page = page.replace('<!--JSONLD-->', '<script type="application/ld+json">\n' + ld + '\n</script>', 1)

open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(page)

# sitemap с картинками
today = datetime.date.today().isoformat()
imgs = ''.join(
    f'\n    <image:image><image:loc>{URL}{w["img"]}</image:loc><image:title>Знак «{w["t"]}», {w["a"]}, Московский союз художников</image:title></image:image>'
    for w in W if w.get('img') and not w.get('series'))
imgs += ''.join(
    f'\n    <image:image><image:loc>{URL}{u}</image:loc><image:title>{t}</image:title></image:image>'
    for x in SER for u, t in ((SIGN(x), f'Знак «{x["t"]}», {SER_A}, Московский союз художников'),
                              (SCENE(x), f'Знак «{x["t"]}» в среде, {SER_A}, Московский союз художников')))
imgs += ''.join(
    f'\n    <image:image><image:loc>{URL}{u}</image:loc><image:title>Знаки цифрового антропогенеза, {SER_A}, Московский союз художников</image:title></image:image>'
 for u in ())
imgs += ''.join(
    f'\n    <image:image><image:loc>{URL}{BUIMG(f)}</image:loc><image:title>Знак «{b["t"]}», БУ ХЕЕВЫ (Сергей Булкин, Евгения Михеева), Московский союз художников</image:title></image:image>'
    for b in BU for f in (b.get('frames') or [b['slug']]))
imgs += ''.join(
    f'\n    <image:image><image:loc>{URL}{u}</image:loc><image:title>{t}</image:title></image:image>'
    for u, t in ((BUIMG('vybor-1987-plakat'), 'Плакат «Выбор», 1987, БУ ХЕЕВЫ'), (BUIMG('vybor-1997-tarart'), 'Объёмный «Выбор», Тарарт, 1997, БУ ХЕЕВЫ'),
                 (BUIMG('kontur-vybora-2008-ekspozitsiya'), 'Проект «Контур выбора», 2008, БУ ХЕЕВЫ'), (BUIMG('bukheyproekt-seriya'), 'Бухейпроект, БУ ХЕЕВЫ')))
imgs += ''.join(
    f'\n    <image:image><image:loc>{URL}{u}</image:loc><image:title>Знаки цифрового антропогенеза, {SER_A}, Московский союз художников</image:title></image:image>'
    for u in (COVER, BOX, 'img/works/mamchur-yuriy-znaki-tsifrovogo-antropogeneza-seriya-moskovskiy-soyuz-khudozhnikov.jpg'))
imgs += ''.join(
    f'\n    <image:image><image:loc>{URL}{w["card"]}</image:loc><image:title>Знак «{w["t"]}», {w["a"]}, Московский союз художников</image:title></image:image>'
    for w in W if w.get('card'))
imgs += ''.join(
    f'\n    <image:image><image:loc>{URL}{p["photo"]}</image:loc><image:title>{p["n"]}, художник, Московский союз художников</image:title></image:image>'
    for p in P if p.get('photo'))
open(os.path.join(OUT, 'sitemap.xml'), 'w', encoding='utf-8').write(
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
    'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
    f'  <url>\n    <loc>{URL}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>1.0</priority>{imgs}\n  </url>\n'
    '</urlset>\n')

open(os.path.join(OUT, 'robots.txt'), 'w').write(
    'User-agent: *\nAllow: /\n\nSitemap: ' + URL + 'sitemap.xml\n')

open(os.path.join(OUT, 'site.webmanifest'), 'w', encoding='utf-8').write(json.dumps({
    'name': 'ЗНАКИ — виртуальная выставка', 'short_name': 'ЗНАКИ', 'lang': 'ru',
    'start_url': './', 'display': 'standalone', 'background_color': '#ffffff', 'theme_color': '#ffffff',
    'icons': [{'src': 'icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
              {'src': 'icon-512.png', 'sizes': '512x512', 'type': 'image/png'}]},
    ensure_ascii=False, indent=1))

# llms.txt — краткое описание для ИИ-ассистентов
def manifest_text():
    m = re.search(r'<div class="manifest__body">(.*?)</div>', page, re.S).group(1)
    return '\n\n'.join(strip_tags(x).strip() for x in re.findall(r'<p[^>]*>(.*?)</p>', m, re.S))
lines = ['# ЗНАКИ — виртуальная выставка', '',
         '> ' + desc, '',
         f'Адрес: {URL}',
         'Организатор: Секция плаката РОО «Московский союз художников» (МСХ)',
         'Куратор: Юлия Назар (https://julianazar.ru)',
         'При поддержке галереи «Глубина» (https://galleryglubina.ru)',
         'Даты: декабрь 2026',
         'Формат: виртуальная выставка, вход свободный', '',
         '## О проекте', '', manifest_text(), '',
         '## Работы', '']
for i, w in enumerate(W):
    if w.get('empty'):
        continue
    if w.get('series'):
        lines.append(f'- №{i + 1:02d}. Серия «{w["t"]}» — {w["a"]}, {w["series"]} знаков (см. раздел «Спецпроект» ниже)')
        continue
    line = f'- №{i + 1:02d}. Знак «{w["t"]}» — {w["a"]}'
    if w.get('means'):
        line += '. ' + strip_tags(w['means'])
    lines.append(line)
lines += ['', f'## Спецпроект: «Знаки цифрового антропогенеза» — {SER_A}, 2026', '',
          f'Адрес: {URL}#digital', '',
          'Графическое исследование тектонических сдвигов в человеческой природе. Серия фиксирует появление нового вида человека, изменённого интерфейсами, алгоритмами и цифровой средой. Знаки построены на языке системной графики, дорожных стандартов и интерфейсов. Визуализации выполнены с применением инструментов генеративного искусства и цифрового монтажа.', '']
for i, x in enumerate(SER):
    lines.append(f'- {i + 1}. «{x["t"]}»' + (f' ({x["sub"]})' if x['sub'] else '') + f' / {x["en"]}. Концепт: {x["concept"]} Смысл: {x["depth"]}')
lines += ['', '## Спецпроект: «Бухейпроект» — БУ ХЕЕВЫ (Сергей Булкин и Евгения Михеева)', '',
          f'Адрес: {URL}#bukhei', '',
          'Постероконцептуализм (post — после, постер — плакат) — термин авторов: произведение создаётся как самодостаточное; одновременно может стать частью общей картины или новой смысловой мозаики; может обрести новую значимость через тиражирование; может перейти из плоскости в объём. Направление «Тарарт» — объёмный плакат. Знак «Выбор» (1987) представлен шестью вариантами, сменяющими друг друга.', '']
for i, b in enumerate(BU):
    lines.append(f'- {i + 1}. «{b["t"]}». Обозначает: {strip_tags(b["means"])} Почему: {strip_tags(b["why"])}')
lines += ['', '## Художники', '']
for p in P:
    if p.get('empty'):
        continue
    lines.append(f'- {p["n"]}. ' + strip_tags(p['lead']) + ' ' +
                 '; '.join(f'{k}: {strip_tags(v)}' for k, v in p['rows']))
sec = re.search(r'<div class="section-msh__body">(.*?)<div class="links">', page, re.S).group(1)
lines += ['', '## Секция плаката МСХ', '',
          '\n\n'.join(strip_tags(x).strip() for x in re.findall(r'<p>(.*?)</p>', sec, re.S)),
          '', f'Страница секции: {SECTION_URL}', f'Московский союз художников: {MSH_URL}',
          '', '## Контакты', '', 'Телефон: +7 495 995-06-13', 'Почта: gallery@glubinagallery.ru', '']
open(os.path.join(OUT, 'llms.txt'), 'w', encoding='utf-8').write('\n'.join(lines))

print('ok:', len(page) // 1024, 'KB;', len(persons), 'artists;', len(artworks), 'artworks')
