"""Сборка сайта ЗНАКИ: site/index.html (исходник) -> out/ (то, что лежит на GitHub).

1. оборачивает исходник в полноценный HTML;
2. открывает страницу в браузере и забирает готовую разметку работ и авторов,
   чтобы она была в HTML сразу (для Яндекса, Алисы и ИИ без выполнения скриптов);
3. добавляет JSON-LD, размеры картинок, sitemap.xml, robots.txt, llms.txt, манифест.
"""
import json, os, re, shutil, subprocess, sys, datetime
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from halls import HALLS, SPEC, ROUTE_TITLE, ROUTE_INTRO, shape_svg

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
for name in ['404.html', 'favicon.ico', 'favicon.svg', 'icon-192.png', 'icon-512.png', 'apple-touch-icon.png']:
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
    if '--fd:' in tag:                      # кадры анимации «Выбор»
        sizes = '(max-width: 620px) 80vw, 460px'
    elif ', БУ ХЕЕВЫ (' in tag:              # плитки знаков БУ ХЕЕВЫХ
        sizes = '(max-width: 620px) 45vw, (max-width: 960px) 30vw, 220px'
    elif ', БУ ХЕЕВЫ"' in tag:               # миниатюры во входе на главной
        sizes = '64px'
    elif 'data-thumb' in tag:                # миниатюры залов
        sizes = '72px'
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

# 2а. залы: маршрут в фойе, шапки и переходы
W0 = res['W']
def plural(n, one, few, many):
    n10, n100 = n % 10, n % 100
    return one if n10 == 1 and n100 != 11 else few if 2 <= n10 <= 4 and not 12 <= n100 <= 14 else many
def hall_works(n):
    return [(i, w) for i, w in enumerate(W0) if w.get('hall') == n and not w.get('series')]
def hall_count(n):
    c = len(hall_works(n)) + (len(res['SER']) if n == 3 else 0)
    return f'{c} {plural(c, "знак", "знака", "знаков")}'
def thumbs(n):
    out = []
    for i, w in hall_works(n)[:3]:
        src = w.get('card') or w.get('img')
        if src:
            out.append(f'<li><img src="{src}" alt="Знак «{w["t"]}», {w["a"]}" loading="lazy" decoding="async" data-thumb></li>')
    return ''.join(out)
def rcard(h, go, tag='a'):
    spec = h is SPEC
    k = 'Спецпроект · 16 знаков' if spec else f'Зал {h["roman"]} · {hall_count(h["n"])}'
    th = ''.join(f'<li><img src="{u}" alt="" loading="lazy" decoding="async" data-thumb></li>' for u in h['thumbs']) if spec else thumbs(h['n'])
    return (f'<a class="rcard{" rcard--spec" if spec else ""}" href="{h["slug"]}">'
            + shape_svg(h['shape'], h['roman'] if not spec else '')
            + f'<span class="rcard__k">{k}</span><span class="rcard__t">{h["title"]}</span>'
            + f'<span class="rcard__line">{h["line"]}</span>'
            + f'<ul class="rcard__thumbs" aria-hidden="true">{th}</ul>'
            + f'<span class="rcard__go"><span>{h["sub"]}</span><em>{go}<b aria-hidden="true">→</b></em></span></a>')
total_signs = len([w for w in W0 if not w.get('series')]) + len(res['SER']) + len(res['BU'])
route_html = ('<section class="route" id="gallery" aria-labelledby="g-h">\n  <div class="wrap">\n'
    f'    <div class="sec-head"><h2 id="g-h">{ROUTE_TITLE}</h2><p>Три зала и спецпроект. Нажмите на зал, чтобы войти.</p></div>\n'
    f'    <p class="route__intro">{ROUTE_INTRO}</p>\n    <ol class="route__list">\n'
    + ''.join(f'      <li>{rcard(h, "Войти в зал")}</li>\n' for h in HALLS)
    + f'      <li>{rcard(SPEC, "Открыть спецпроект")}</li>\n    </ol>\n  </div>\n</section>')
def hall_artists(n):
    cnt = {}
    for i, w in hall_works(n):
        cnt[w['a']] = cnt.get(w['a'], 0) + 1
    if n == 3:
        cnt[res['SER_A']] = len(res['SER'])
    return ''.join(f'<li><a href="./#authors"><strong>{a}</strong><span>{c} {plural(c, "знак", "знака", "знаков")}</span></a></li>' for a, c in cnt.items())
def all_halls(cur, nxt=None):
    items = [(x['slug'], shape_svg(x['shape'], x['roman'], 'hshape'), f'Зал {x["roman"]}', x['title'], x is cur, x is nxt) for x in HALLS]
    items.append((SPEC['slug'], shape_svg(SPEC['shape'], '', 'hshape'), 'Спецпроект', SPEC['title'], SPEC is cur, SPEC is nxt))
    out = ''.join(
        (f'<li><span class="hall-mini is-here" aria-current="page">{sv}<span><em>{k}</em><strong>{t}</strong><i>Вы здесь</i></span></span></li>' if here else
         f'<li><a class="hall-mini{" is-next" if nx else ""}" href="{sl}">{sv}<span><em>{k}</em><strong>{t}</strong><i>{"Следующий зал →" if nx else "Перейти →"}</i></span></a></li>')
        for sl, sv, k, t, here, nx in items)
    return f'<div class="hall-all"><p class="hall-all__t">Куда дальше · все залы выставки</p><ol>{out}<li><a class="hall-mini hall-mini--home" href="./"><span class="hall-mini__home" aria-hidden="true">⌂</span><span><em>Фойе</em><strong>Маршрут</strong><i>Перейти →</i></span></a></li></ol></div>'
def grid_fill(h):
    n = h['n']
    k = len(hall_works(n))
    slots = (3 - k % 3) % 3
    nxt = HALLS[n] if n < 3 else SPEC
    cards = [(nxt['slug'], shape_svg(nxt['shape'], nxt['roman'] if nxt is not SPEC else ''), 'Дальше', (f'Зал {nxt["roman"]} · ' if nxt is not SPEC else '') + nxt['title'], nxt['sub']),
             ('./#gallery', '<span class="gnav__home" aria-hidden="true">⌂</span>', 'Все залы', 'Маршрут выставки', 'Фойе и карта залов')]
    return ''.join(f'<li class="card card--gnav"><a class="card__link" href="{u}"><div class="plate gnav">{sv}</div>'
                   f'<div class="card__cap"><span class="card__title">{k}: {t}</span><span class="card__author">{s}</span><span class="card__hint">Перейти →</span></div></a></li>'
                   for u, sv, k, t, s in cards[:slots])
def hall_top(h):
    sw = ''.join(f'<li><a href="{x["slug"]}" aria-label="Зал {x["roman"]} · {x["title"]}"{' aria-current="page"' if x is h else ''}>{x["roman"]}</a></li>' for x in HALLS)
    sw += f'<li><a href="{SPEC["slug"]}" aria-label="Спецпроект «Бухейпроект»">◆</a></li>'
    concept = ''.join(f'<p>{p}</p>' for p in h['concept'])
    return (f'<nav class="hbar" aria-label="Залы выставки"><div class="wrap">'
            f'<a class="crumbs__back" href="./"><b aria-hidden="true">←</b>Фойе</a><ol class="hswitch">{sw}</ol></div></nav>\n'
            f'<header class="hallhead"><div class="wrap">{shape_svg(h["shape"], h["roman"])}<div class="hallhead__text">'
            f'<p class="hallhead__k">Зал {h["roman"]} · {hall_count(h["n"])}</p><h1>{h["title"]}</h1>'
            f'<p class="hallhead__sub">{h["sub"]}</p><p class="hallhead__lead">{h["lead"]}</p>{concept}'
            f'<p class="hallhead__who">Художники зала</p><ul class="hall-artists">{hall_artists(h["n"])}</ul></div></div></header>')
def hall_next(h):
    n = h['n']
    nxt = HALLS[n] if n < 3 else SPEC
    prev = HALLS[n - 2] if n > 1 else None
    eyebrow = 'Следующий зал' if n < 3 else 'Дальше — спецпроект'
    go = f'Перейти в Зал {nxt["roman"]}' if n < 3 else 'Открыть спецпроект'
    more = (f'<a href="{prev["slug"]}">← Зал {prev["roman"]} · {prev["title"]}</a>' if prev else '') + \
           '<a href="./">Фойе</a><a href="./#authors">Авторы</a><a href="./#curator">От куратора</a>'
    more = '<a href="./#authors">Авторы</a><a href="./#curator">От куратора</a>'
    return (f'<section class="hnext" aria-label="Переход между залами"><div class="wrap">'
            f'{all_halls(h, nxt)}<div class="hnext__more">{more}</div></div></section>')
snip = {'ROUTE': route_html}
for h in HALLS:
    snip['TOP%d' % h['n']] = hall_top(h)
    snip['NEXT%d' % h['n']] = hall_next(h)
for k in snip:
    v = re.sub(r'<img src="(img/(?:works|artists)/[^"]+\.jpg)"[^>]*>', to_picture, snip[k])
    snip[k] = re.sub(r'<img src="(img/[^"]+)"[^>]*>', add_size, v)

# 2б. страницы из одного исходника
BU_URL = URL + 'bukhei.html'
def cut(h, tag):
    return re.sub(r'<!--%s-->.*?<!--/%s-->\n?' % (tag, tag), '', h, flags=re.S)
def unmark(h):
    return re.sub(r'<!--/?(MAIN|BU|HALL|DIGITAL|HALLTOP|HALLNEXT)-->\n?', '', h)
def localize(h):
    ids = set(re.findall(r'id="([^"]+)"', h))
    h = re.sub(r'href="#([^"]+)"', lambda m: m.group(0) if m.group(1) in ids else 'href="./#%s"' % m.group(1), h)
    h = h.replace('<a class="nav__mark" href="#top">', '<a class="nav__mark" href="./" aria-label="ЗНАКИ — в фойе выставки">')
    h = h.replace('<ol>\n      <li><a href="./#manifest">', '<ol>\n      <li><a href="./">← Фойе</a></li>\n      <li><a href="./#manifest">', 1)
    return h
def current(h, slug):
    return h.replace(f'<a href="{slug}">', f'<a href="{slug}" aria-current="page">')
main_page = unmark(cut(cut(page, 'BU'), 'HALL')).replace('<!--ROUTE-->', snip['ROUTE'], 1)
main_page = main_page.replace('<a href="./"><i aria-hidden="true">⌂</i>', '<a href="./" aria-current="page"><i aria-hidden="true">⌂</i>', 1)
# блок «Секция плаката МСХ» — в конце залов и спецпроекта, перед подвалом
SEC_BLOCK = re.search(r'\n  <section class="section-msh" id="section".*?\n  </section>\n', page, re.S).group(0)
def add_section(h):
    return h.replace('</main>', SEC_BLOCK + '</main>', 1)
bu_page = add_section(unmark(cut(cut(page, 'MAIN'), 'HALL')))
hall_base = cut(cut(page, 'MAIN'), 'BU')
hall_of = {i + 1: w.get('hall') for i, w in enumerate(W0)}
def top_menu(h):
    items = '<li><a href="./">← Фойе</a></li>' + ''.join(f'<li><a href="{x["slug"]}">Зал {x["roman"]} · {x["title"]}</a></li>' for x in HALLS) + f'<li><a href="{SPEC["slug"]}">{SPEC["title"]}</a></li>'
    return re.sub(r'(<nav aria-label=")Разделы(">\s*<ul>).*?(</ul>)', lambda m: m.group(1) + 'Залы выставки' + m.group(2) + items + m.group(3), h, count=1, flags=re.S)
CTA_NEXT = {1: ('Зал II · Вокруг', 'Зал II'), 2: ('Зал III · Время', 'Зал III'), 3: ('Спецпроект «Бухейпроект»', 'Дальше')}
hall_pages = {}
for h in HALLS:
    n = h['n']
    hp = hall_base
    if n != 3:
        hp = cut(hp, 'DIGITAL')
    hp = hp.replace('<!--HALLTOP-->', snip['TOP%d' % n], 1).replace('<!--HALLNEXT-->', snip['NEXT%d' % n], 1)
    hp = re.sub(r'<li class="card[^"]*" id="znak-(\d+)".*?</li>\n?',
                lambda m: m.group(0) if hall_of.get(int(m.group(1))) == n and 'card--series' not in m.group(0)[:80] else '', hp, flags=re.S)
    hp = hp.replace('<section class="gallery" id="gallery"', '<section class="gallery" id="znaki-zala"', 1)
    hp = top_menu(hp)
    hp = hp.replace('<main id="top">', f'<main id="top" data-hall="{n}">', 1)
    nxt = HALLS[n]['slug'] if n < 3 else SPEC['slug']
    lng, sh = CTA_NEXT[n]
    hp = re.sub(r'<a class="cta" id="cta" href="[^"]*">.*?</a>',
        f'<a class="cta" href="{nxt}"><b aria-hidden="true">→</b><span><span class="cta__long">{lng}</span><span class="cta__short">{sh}</span></span></a>', hp, count=1, flags=re.S)
    hp = current(localize(unmark(add_section(hp))), h['slug'])
    hall_pages[n] = hp
# на странице спецпроекта ссылки на разделы главной ведут на главную
bu_page = localize(bu_page)
bu_page = re.sub(r'<a class="cta" id="cta" href="[^"]*">.*?</a>',
    '<a class="cta" href="./#gallery"><b aria-hidden="true">←</b><span><span class="cta__long">Вернуться на выставку</span><span class="cta__short">Выставка</span></span></a>', bu_page, count=1, flags=re.S)
bu_page = current(top_menu(bu_page), 'bukhei.html')
bu_page = bu_page.replace('<h2 id="bu-h">Бухейпроект</h2>', '<h1 id="bu-h">Бухейпроект</h1>', 1)
# главное фото спецпроекта — сразу, без ленивой загрузки
bu_page = re.sub(r'(<img src="img/artists/bukheevy-bulkin-sergey[^>]*?) loading="lazy"', r'\1 fetchpriority="high"', bu_page, count=1)
BU_TITLE = 'Бухейпроект — спецпроект БУ ХЕЕВЫХ на выставке «ЗНАКИ» Секции плаката МСХ'
BU_DESC = 'Спецпроект арт-группы БУ ХЕЕВЫ (Сергей Булкин и Евгения Михеева) на виртуальной выставке «ЗНАКИ», декабрь 2026: 16 знаков постероконцептуализма — «Выбор», «Мы», «Победа», «Конформизм» и другие.'
BU_IMG = URL + 'img/og-bukheyproekt-znaki-moskovskiy-soyuz-khudozhnikov.jpg'
def set_head(h, title, desc, url, img):
    t0 = re.search(r'<title>([^<]+)</title>', h).group(1)
    d0 = re.search(r'<meta name="description" content="([^"]+)"', h).group(1)
    h = h.replace(t0, title).replace(d0, desc)
    h = h.replace('<link rel="canonical" href="%s">' % URL, '<link rel="canonical" href="%s">' % url)
    h = h.replace('<meta property="og:url" content="%s">' % URL, '<meta property="og:url" content="%s">' % url)
    h = h.replace(URL + 'img/og-znaki.jpg', img)
    h = re.sub(r'<meta property="og:image:(width|height)"[^>]*>\n', '', h)
    h = h.replace('<meta property="og:image:alt" content="ЗНАКИ — виртуальная выставка Секции плаката МСХ">',
                  '<meta property="og:image:alt" content="БУ ХЕЕВЫ — Евгения Михеева и Сергей Булкин в объёмных плакатах «Выбор»">')
    return h
bu_page = set_head(bu_page, BU_TITLE, BU_DESC, BU_URL, BU_IMG)
bu_page = bu_page.replace('<meta property="og:image" content="%s">' % BU_IMG,
    '<meta property="og:image" content="%s">\n<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">' % BU_IMG, 1)

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
                                  'name': 'Московский союз художников', 'alternateName': ['МСХ', 'МОСХ', 'РОО «Московский союз художников»'],
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
    links = [m for k, v in p['rows'] for m in re.findall(r'href="([^"]+)"', v) if 'artanum.ru' not in m and m.rstrip('/') != 'https://tcxp.ru' and m.startswith('http')]
    if links:
        d['sameAs'] = links
    persons.append(d)
pid = {p['name']: p['@id'] for p in persons}
# куратор: связать с личным сайтом и с «Глубиной»
for d in persons:
    if d['name'] == 'Юлия Назар':
        d['jobTitle'] = ['Художник', 'Куратор']
        d['url'] = 'https://julianazar.ru'
        d['memberOf'] = [{'@id': URL + '#msh'},
                         {'@type': 'Organization', 'name': 'Творческий союз художников России',
                          'alternateName': 'ТСХР', 'url': 'https://tcxp.ru/'}]
        d['sameAs'] = sorted(set(d.get('sameAs', []) + ['https://julianazar.ru']))
glubina = {'@type': ['ArtGallery', 'Organization'], '@id': URL + '#glubina',
           'name': 'Галерея «Глубина»',
           'alternateName': ['Галерея GLUBINA', 'GLUBINA', 'Арт-сообщество «Глубина»', 'Glubina Gallery'],
           'description': 'Арт-сообщество и галерея, созданные художницами и кураторами Светланой Дёминой и Юлией Назар в 2022 году.',
           'url': 'https://galleryglubina.ru', 'foundingDate': '2022',
           'founder': [{'@id': pid[n]} for n in ('Светлана Дёмина', 'Юлия Назар') if n in pid],
           'address': {'@type': 'PostalAddress', 'addressLocality': 'Москва', 'streetAddress': 'Фрунзенская наб., 46', 'addressCountry': 'RU'},
           'logo': URL + 'img/glubina-gallery-logo.png'}
H3_URL = URL + HALLS[2]['slug']
artworks = []
for i, w in enumerate(W):
    if w.get('empty') or w.get('series') or not (w.get('img') or w.get('video')):
        continue
    hu = URL + HALLS[w['hall'] - 1]['slug']
    a = {'@type': 'VisualArtwork', '@id': hu + '#znak-%02d' % (i + 1),
         'name': 'Знак «%s»' % w['t'], 'url': hu + '#znak-%02d' % (i + 1), '_hall': w['hall'],
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
    ser_parts.append({'@type': 'VisualArtwork', '@id': H3_URL + '#digital-%d' % (i + 1),
        'name': 'Знак «%s»' % x['t'], 'alternateName': x['en'], 'url': H3_URL + '#digital-%d' % (i + 1), '_hall': 3,
        'creator': {'@id': pid.get(SER_A)}, 'artform': 'Графика', 'inLanguage': 'ru',
        'image': [URL + SIGN(x), URL + SCENE(x)], 'description': x['concept'] + ' ' + x['depth']})
series_node = {'@type': 'CreativeWorkSeries', '@id': H3_URL + '#digital', 'name': 'Знаки цифрового антропогенеза', '_hall': 3,
    'creator': {'@id': pid.get(SER_A)}, 'dateCreated': '2026', 'url': H3_URL + '#digital',
    'image': [URL + COVER, URL + BOX], 'isPartOf': {'@id': URL + '#exhibition'},
    'hasPart': [{'@id': x['@id']} for x in ser_parts],
    'description': 'Графическое исследование тектонических сдвигов в человеческой природе: серия из пяти знаков о новом виде человека, изменённого интерфейсами, алгоритмами и цифровой средой.'}
artworks += [series_node] + ser_parts
bu_parts = []
for i, b in enumerate(BU):
    imgs_ = [URL + BUIMG(f) for f in b['frames']] if b.get('frames') else URL + BUIMG(b['slug'])
    bu_parts.append({'@type': 'VisualArtwork', '@id': BU_URL + '#bukhei-%d' % (i + 1), 'name': 'Знак «%s»' % b['t'],
        'url': BU_URL + '#bukhei-%d' % (i + 1), 'creator': {'@id': pid.get('БУ ХЕЕВЫ')}, 'artform': 'Плакат', 'inLanguage': 'ru',
        'image': imgs_, 'description': strip_tags(b['means'])})
artworks += [{'@type': 'CreativeWorkSeries', '@id': BU_URL + '#bukhei', 'name': 'Бухейпроект',
    'alternateName': 'Постероконцептуализм', 'creator': {'@id': pid.get('БУ ХЕЕВЫ')}, 'url': BU_URL,
    'image': URL + 'img/artists/bukheevy-bulkin-sergey-mikheeva-evgeniya-moskovskiy-soyuz-khudozhnikov.jpg',
    'isPartOf': {'@id': URL + '#exhibition'}, 'hasPart': [{'@id': x['@id']} for x in bu_parts],
    'description': 'Спецпроект арт-группы БУ ХЕЕВЫ (Сергей Булкин и Евгения Михеева): 16 знаков-идеограмм в духе постероконцептуализма — теории, по которой плакат одновременно самодостаточен, становится частью общей картины, обретает значимость через тиражирование и переходит из плоскости в объём.'}] + bu_parts

desc = re.search(r'<meta name="description" content="([^"]+)"', main_page).group(1)
title = re.search(r'<title>([^<]+)</title>', main_page).group(1)
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
     'organizer': [{'@id': URL + '#section'}, {'@id': pid.get('Юлия Назар')}],
     'performer': [{'@id': p['@id']} for p in persons],
     'sponsor': {'@id': URL + '#glubina'},
     'workFeatured': [{'@id': a['@id']} for a in artworks]},
    section, glubina, *persons, *artworks,
]
hall_nodes = {h['n']: [x for x in artworks if x.get('_hall') == h['n']] for h in HALLS}
for x in artworks:
    x.pop('_hall', None)
ld = json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False, indent=1)
page = main_page.replace('<!--JSONLD-->', '<script type="application/ld+json">\n' + ld + '\n</script>', 1)
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(page)

bu_nodes = [x for x in artworks if x['@id'].startswith(BU_URL)]
bu_group = [x for x in persons if x['name'] == 'БУ ХЕЕВЫ']
bu_graph = [
    {'@type': 'WebPage', '@id': BU_URL + '#page', 'url': BU_URL, 'name': BU_TITLE, 'description': BU_DESC,
     'inLanguage': 'ru', 'isPartOf': {'@type': 'WebSite', '@id': URL + '#site', 'url': URL, 'name': 'ЗНАКИ'},
     'primaryImageOfPage': BU_IMG, 'about': {'@id': BU_URL + '#bukhei'}, 'breadcrumb': {'@id': BU_URL + '#crumbs'}},
    {'@type': 'BreadcrumbList', '@id': BU_URL + '#crumbs', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': 'ЗНАКИ', 'item': URL},
        {'@type': 'ListItem', 'position': 2, 'name': 'Залы', 'item': URL + '#gallery'},
        {'@type': 'ListItem', 'position': 3, 'name': 'Бухейпроект', 'item': BU_URL}]},
    {'@type': 'ExhibitionEvent', '@id': URL + '#exhibition', 'name': 'ЗНАКИ', 'url': URL,
     'startDate': '2026-12-01', 'endDate': '2026-12-31',
     'eventAttendanceMode': 'https://schema.org/OnlineEventAttendanceMode',
     'location': {'@type': 'VirtualLocation', 'url': URL}, 'organizer': {'@id': URL + '#section'}},
    section, *bu_group, *bu_nodes]
ld_bu = json.dumps({'@context': 'https://schema.org', '@graph': bu_graph}, ensure_ascii=False, indent=1)
bu_page = bu_page.replace('<!--JSONLD-->', '<script type="application/ld+json">\n' + ld_bu + '\n</script>', 1)
open(os.path.join(OUT, 'bukhei.html'), 'w', encoding='utf-8').write(bu_page)

# страницы залов
for h in HALLS:
    n, hu = h['n'], URL + h['slug']
    og = URL + 'img/og-zal-%d-%s-znaki-moskovskiy-soyuz-khudozhnikov.jpg' % (n, h['slug'].split('-')[2].split('.')[0])
    hp = set_head(hall_pages[n], h['seo_title'], h['seo_desc'], hu, og)
    hp = hp.replace('<meta property="og:image:alt" content="БУ ХЕЕВЫ — Евгения Михеева и Сергей Булкин в объёмных плакатах «Выбор»">',
                    f'<meta property="og:image:alt" content="Зал {h["roman"]} «{h["title"]}» — {h["sub"].lower()}, выставка «ЗНАКИ»">')
    hp = hp.replace('<meta property="og:image" content="%s">' % og,
        '<meta property="og:image" content="%s">\n<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">' % og, 1)
    nodes = hall_nodes[n]
    creators = {x['creator'].get('@id') for x in nodes if isinstance(x.get('creator'), dict)}
    hg = [
        {'@type': 'CollectionPage', '@id': hu + '#page', 'url': hu, 'name': h['seo_title'], 'description': h['seo_desc'],
         'inLanguage': 'ru', 'isPartOf': {'@type': 'WebSite', '@id': URL + '#site', 'url': URL, 'name': 'ЗНАКИ'},
         'primaryImageOfPage': og, 'breadcrumb': {'@id': hu + '#crumbs'},
         'about': {'@id': URL + '#exhibition'}, 'hasPart': [{'@id': x['@id']} for x in nodes]},
        {'@type': 'BreadcrumbList', '@id': hu + '#crumbs', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'ЗНАКИ', 'item': URL},
            {'@type': 'ListItem', 'position': 2, 'name': 'Залы', 'item': URL + '#gallery'},
            {'@type': 'ListItem', 'position': 3, 'name': f'Зал {h["roman"]} «{h["title"]}»', 'item': hu}]},
        {'@type': 'ExhibitionEvent', '@id': URL + '#exhibition', 'name': 'ЗНАКИ', 'url': URL,
         'startDate': '2026-12-01', 'endDate': '2026-12-31',
         'eventAttendanceMode': 'https://schema.org/OnlineEventAttendanceMode',
         'location': {'@type': 'VirtualLocation', 'url': URL}, 'organizer': {'@id': URL + '#section'}},
        section, *[p for p in persons if p['@id'] in creators], *nodes]
    ldh = json.dumps({'@context': 'https://schema.org', '@graph': hg}, ensure_ascii=False, indent=1)
    hp = hp.replace('<!--JSONLD-->', '<script type="application/ld+json">\n' + ldh + '\n</script>', 1)
    open(os.path.join(OUT, h['slug']), 'w', encoding='utf-8').write(hp)

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
bu_imgs = ''.join(
    f'\n    <image:image><image:loc>{URL}{BUIMG(f)}</image:loc><image:title>Знак «{b["t"]}», БУ ХЕЕВЫ (Сергей Булкин, Евгения Михеева), Московский союз художников</image:title></image:image>'
    for b in BU for f in (b.get('frames') or [b['slug']]))
bu_imgs += ''.join(
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
# картинки работ — в адресах залов, на главной остаются фото авторов
def itag(u, t):
    return f'\n    <image:image><image:loc>{URL}{u}</image:loc><image:title>{t}</image:title></image:image>'
hall_imgs = {h['n']: '' for h in HALLS}
for w in W:
    if w.get('series') or not w.get('img'):
        continue
    t = f'Знак «{w["t"]}», {w["a"]}, Московский союз художников'
    hall_imgs[w['hall']] += (itag(w['card'], t) if w.get('card') else '') + itag(w['img'], t)
hall_imgs[3] += ''.join(itag(u, t) for x in SER for u, t in (
    (SIGN(x), f'Знак «{x["t"]}», {SER_A}, Московский союз художников'),
    (SCENE(x), f'Знак «{x["t"]}» в среде, {SER_A}, Московский союз художников')))
hall_imgs[3] += ''.join(itag(u, f'Знаки цифрового антропогенеза, {SER_A}, Московский союз художников')
    for u in (COVER, BOX, 'img/works/mamchur-yuriy-znaki-tsifrovogo-antropogeneza-seriya-moskovskiy-soyuz-khudozhnikov.jpg'))
imgs = ''.join(itag(p['photo'], f'{p["n"]}, художник, Московский союз художников') for p in P if p.get('photo'))
hall_urls = ''.join(
    f'  <url>\n    <loc>{URL}{h["slug"]}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.9</priority>{hall_imgs[h["n"]]}\n  </url>\n'
    for h in HALLS)
open(os.path.join(OUT, 'sitemap.xml'), 'w', encoding='utf-8').write(
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
    'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
    f'  <url>\n    <loc>{URL}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>1.0</priority>{imgs}\n  </url>\n'
    + hall_urls +
    f'  <url>\n    <loc>{BU_URL}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.8</priority>{bu_imgs}\n  </url>\n'
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
         'Куратор: Юлия Назар (https://julianazar.ru), член Московского союза художников (МСХ) и Творческого союза художников России (ТСХР), сооснователь арт-сообщества «Глубина»',
         'При поддержке галереи и арт-сообщества «Глубина» (GLUBINA, https://galleryglubina.ru), созданного Светланой Дёминой и Юлией Назар',
         'Даты: декабрь 2026',
         'Формат: виртуальная выставка, вход свободный', '',
         '## О проекте', '', manifest_text(), '',
         '## Залы', '', ROUTE_INTRO, '']
for h in HALLS:
    lines += [f'### Зал {h["roman"]} «{h["title"]}» — {h["sub"]}', '', f'Страница: {URL}{h["slug"]}', '',
              h['lead'], '', *[c for c in h['concept']], '']
lines += ['## Работы по залам', '']
cur_h = None
for i, w in enumerate(W):
    if w.get('empty'):
        continue
    if w.get('hall') != cur_h:
        cur_h = w.get('hall'); hh = HALLS[cur_h - 1]
        lines += ['', f'Зал {hh["roman"]} «{hh["title"]}» ({URL}{hh["slug"]}):']
    if w.get('series'):
        lines.append(f'- №{i + 1:02d}. {"Спецпроект" if w.get("label") else "Серия знаков"} «{w["t"]}» — {w["a"]}, {w["series"]} знаков (см. ниже)')
        continue
    line = f'- №{i + 1:02d}. Знак «{w["t"]}» — {w["a"]}'
    if w.get('means'):
        line += '. ' + strip_tags(w['means'])
    lines.append(line)
lines += ['', f'## Спецпроект: «Знаки цифрового антропогенеза» — {SER_A}, 2026', '',
          f'Адрес: {URL}{HALLS[2]["slug"]}#digital (финал Зала III)', '',
          'Графическое исследование тектонических сдвигов в человеческой природе. Серия фиксирует появление нового вида человека, изменённого интерфейсами, алгоритмами и цифровой средой. Знаки построены на языке системной графики, дорожных стандартов и интерфейсов. Визуализации выполнены с применением инструментов генеративного искусства и цифрового монтажа.', '']
for i, x in enumerate(SER):
    lines.append(f'- {i + 1}. «{x["t"]}»' + (f' ({x["sub"]})' if x['sub'] else '') + f' / {x["en"]}. Концепт: {x["concept"]} Смысл: {x["depth"]}')
lines += ['', '## Спецпроект: «Бухейпроект» — БУ ХЕЕВЫ (Сергей Булкин и Евгения Михеева)', '',
          f'Отдельная страница: {BU_URL}', '',
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

print('ok:', len(page) // 1024, 'KB +', len(bu_page) // 1024, 'KB bukhei;', len(persons), 'artists;', len(artworks), 'artworks')
