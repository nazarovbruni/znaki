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
    W: WORKS, P: PEOPLE,
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
    if w > 1000:
        im.resize((800, round(h * 800 / w)), Image.LANCZOS).save(
            os.path.join(OUT, base + '-800.webp'), 'WEBP', quality=80, method=6)
        out.append((base + '-800.webp', 800))
    out.append((base + '.webp', w))
    return out

SIZES = {'works': '(max-width: 620px) 100vw, (max-width: 960px) 50vw, 400px',
         'artists': '(max-width: 620px) 50vw, (max-width: 960px) 50vw, 400px'}
def to_picture(m):
    tag, rel = m.group(0), m.group(1)
    kind = rel.split('/')[1]
    srcset = ', '.join(f'{f} {w}w' for f, w in webp_variants(rel))
    return f'<picture><source type="image/webp" srcset="{srcset}" sizes="{SIZES[kind]}">{tag}</picture>'
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
W, P = res['W'], res['P']
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
    d = {'@type': 'Person', '@id': URL + '#artist-' + str(i + 1), 'name': p['n'],
         'description': strip_tags(p['lead']),
         'memberOf': {'@id': URL + '#msh'}, 'jobTitle': 'Художник'}
    if p.get('photo'):
        d['image'] = URL + p['photo']
    links = [m for k, v in p['rows'] for m in re.findall(r'href="([^"]+)"', v)]
    if links:
        d['sameAs'] = links
    persons.append(d)
pid = {p['name']: p['@id'] for p in persons}
artworks = []
for i, w in enumerate(W):
    if w.get('empty') or not (w.get('img') or w.get('video')):
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
    for w in W if w.get('img'))
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
         'Формат: виртуальная выставка, вход свободный', '',
         '## О проекте', '', manifest_text(), '',
         '## Работы', '']
for i, w in enumerate(W):
    if w.get('empty'):
        continue
    line = f'- №{i + 1:02d}. Знак «{w["t"]}» — {w["a"]}'
    if w.get('means'):
        line += '. ' + strip_tags(w['means'])
    lines.append(line)
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
