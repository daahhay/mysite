"""Build the CMS-managed drug library without publishing draft source files."""
import html
import json
import re
import shutil
from urllib.parse import quote

SECTIONS = [["renal","Kidney impairment"],["hepatic","Liver impairment"],["special_populations","Obesity / older adults / other populations"],["administration","Administration / preparation / storage"],["contraindications","Contraindications"],["warnings","Warnings / precautions"],["adverse_effects","Adverse effects"],["interactions","Drug interactions"],["pregnancy","Pregnancy / breastfeeding"],["monitoring","Monitoring"],["mechanism","Mechanism of action"],["pharmacokinetics","Pharmacokinetics"],["counseling","Patient counseling"]]

def esc(value):
    return html.escape(str(value or ''), quote=True)

def folders(values):
    result = []
    for value in values or []:
        parts = [p.strip() for p in value.split('/') if p.strip()]
        if parts:
            result.append(' / '.join(parts))
    return sorted(set(result), key=str.casefold)

def load_drugs(root, preview=False):
    entries, seen = [], set()
    for source in sorted((root / 'content/drugs').glob('*.json')):
        d = json.loads(source.read_text())
        if d.get('published') is not True and not preview:
            continue
        slug = d.get('slug', '')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or slug in ('edit',) or slug in seen:
            raise ValueError('Invalid or duplicate drug slug: ' + slug)
        if not str(d.get('title', '')).strip():
            raise ValueError('Missing drug name: ' + slug)
        seen.add(slug)
        d['categories'] = folders(d.get('categories', []))
        entries.append(d)
    return sorted(entries, key=lambda d:d['title'].casefold())


RU = {
    'Overview':'Обзор', 'Dosing guidance':'Общие рекомендации по дозированию',
    'Dosing by condition':'Дозирование по показаниям', 'Off-label use':'Применение вне зарегистрированных показаний',
    'Kidney impairment':'Нарушение функции почек', 'Liver impairment':'Нарушение функции печени',
    'Obesity / older adults / other populations':'Ожирение / пожилой возраст / особые группы',
    'Administration / preparation / storage':'Введение / приготовление / хранение',
    'Contraindications':'Противопоказания', 'Warnings / precautions':'Предупреждения и меры предосторожности',
    'Adverse effects':'Нежелательные реакции', 'Drug interactions':'Лекарственные взаимодействия',
    'Pregnancy / breastfeeding':'Беременность и грудное вскармливание', 'Monitoring':'Мониторинг',
    'Mechanism of action':'Механизм действия', 'Pharmacokinetics':'Фармакокинетика',
    'Patient counseling':'Информация для пациента', 'Downloads':'Материалы для скачивания',
    'References':'Источники', 'All drugs':'Все препараты', 'CONTENTS':'СОДЕРЖАНИЕ',
    'Last reviewed: ':'Дата проверки: ', 'Drug information':'Информация о препарате',
    'Draft preview · not published':'Черновик · не опубликован'
}

def drug_versions(drug, preview=False):
    original = dict(drug)
    original['language'] = drug.get('language') or 'en'
    if original['language'] not in ('en','ru'):
        raise ValueError('Invalid drug language: ' + original['language'])
    versions = [original]
    translation = drug.get('translation') or {}
    if translation and (translation.get('published') is True or preview) and str(translation.get('title') or '').strip():
        other = 'ru' if original['language']=='en' else 'en'
        # Keep clinical text separate: never fill missing translations with original doses.
        translated = {k:v for k,v in translation.items() if k not in ('language','categories','slug','published')}
        translated.update(language=other, categories=original['categories'],
                          slug=translation.get('slug') or original['slug']+'-'+other,
                          published=original.get('published') is True and translation.get('published') is True)
        versions.append(translated)
    elif translation.get('published') is True and not str(translation.get('title') or '').strip():
        raise ValueError('Published translation needs a drug name: ' + original['slug'])
    for version in versions:
        version['group'] = original['slug']
        version['versions'] = [{'title':v['title'],'slug':v['slug'],'language':v['language']} for v in versions]
    return versions

def build_drugs(root, output, frame, parser_type, safe_url, preview=False):
    target = output / 'drugs'
    target.mkdir()
    for name in ('drugs.css', 'drugs.js'):
        shutil.copy2(root / 'drugs' / name, target / name)
    def page(title, path, body, description='Drug information library.', lang='en'):
        result = frame(title, description, path, body, lang=lang)
        result = result.replace('</head>', '<link rel="stylesheet" href="/drugs/drugs.css"></head>')
        result = result.replace('<a href="/blog/edit/">Manage blog ↗</a>', '<a href="/drugs/edit/">Manage drugs</a>')
        return result.replace('</body>', '<script src="/drugs/drugs.js" defer></script></body>')
    entries = load_drugs(root, preview)
    versions = [v for d in entries for v in drug_versions(d, preview)]
    seen_slugs = set()
    for v in versions:
        slug = v['slug']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or slug=='edit' or slug in seen_slugs:
            raise ValueError('Invalid or duplicate drug version address: ' + slug)
        seen_slugs.add(slug)
    category_paths = set()
    for d in entries:
        for category in d['categories']:
            parts = category.split(' / ')
            category_paths.update(' / '.join(parts[:i]) for i in range(1,len(parts)+1))
    folder_links = ''.join('<li><a class="drug-folder" href="?category='+quote(c)+'" data-folder="'+esc(c)+'" style="--depth:'+str(c.count(' / '))+'">'+esc(c.split(' / ')[-1])+'</a></li>' for c in sorted(category_paths,key=str.casefold))
    rows = []
    letters = set()
    for d in versions:
        letter = d['title'][0].upper()
        letter = letter if letter.isalpha() else '#'
        letters.add(letter)
        search = ' '.join([d['title'], ' '.join((d.get('aliases') or [])), ' '.join(d['categories']), d.get('summary','')])
        alternate = d['slug'] != d['group']
        switch = ' '.join('<a lang="'+v['language']+'" href="/drugs/'+v['slug']+'/">'+('Русский' if v['language']=='ru' else 'English')+'</a>' for v in d['versions']) if len(d['versions'])>1 else ''
        rows.append('<li class="drug-row"'+(' hidden' if alternate else '')+' data-group="'+esc(d['group'])+'" data-language="'+d['language']+'" data-letter="'+esc(letter)+'" data-search="'+esc(search)+'" data-categories="'+esc(json.dumps(d['categories']))+'"><a href="/drugs/'+d['slug']+'/">'+esc(d['title'])+'<span class="drug-type">: '+('Информация о препарате' if d['language']=='ru' else 'Drug information')+'</span></a><p>'+esc(' · '.join(d['categories']))+'</p><div class="drug-version-links">'+switch+'</div></li>')
    alphabet = ''.join('<button type="button" data-letter-filter="'+esc(l)+'">'+esc(l)+'</button>' for l in sorted(letters))
    body = '''<section class="drug-hero"><h1>Drugs</h1><p>Browse drug information by name or category.</p></section>
<div class="drug-library"><aside class="drug-folders" aria-label="Drug categories"><h2>Categories</h2><ul><li><a class="drug-folder" href="/drugs/" data-folder="">All drugs</a></li>'''+folder_links+'''</ul></aside>
<section aria-label="Drug list"><label class="drug-search">Find a drug<input id="drug-search" type="search" placeholder="Drug name, brand or category…" autocomplete="off"></label>
<label class="drug-language-filter">Language<select id="drug-language"><option value="">All languages</option><option value="en">English</option><option value="ru">Русский</option></select></label>\n<div class="drug-alphabet" aria-label="Filter by initial"><button type="button" data-letter-filter="">All</button>'''+alphabet+'''</div>
<div class="drug-list-status"><p id="drug-count" role="status">'''+str(len(entries))+''' drugs</p><button id="drug-clear" type="button">Clear filters</button></div><ul class="drug-list">'''+''.join(rows)+'''</ul>
<p id="drug-empty"'''+(' hidden' if entries else '')+'''>'''+('No matching drugs. Try another search or category.' if entries else 'No drug pages have been published yet.')+'''</p></section></div>'''
    (target/'index.html').write_text(page('Drugs','/drugs/',body))
    for d in versions:
        tr = lambda label: RU.get(label,label) if d['language']=='ru' else label
        raw = ''
        def section(title, value):
            return '<h2>'+esc(tr(title))+'</h2>'+str(value) if value and str(value).strip() not in ('<p></p>','<p><br></p>') else ''
        raw += section('Overview', d.get('overview'))
        raw += section('Dosing guidance', d.get('dosing_guidance'))
        if d.get('doses'):
            raw += '<h2>'+esc(tr('Dosing by condition'))+'</h2>'
            for dose in d['doses']:
                raw += '<h3>'+esc(dose.get('condition'))+'</h3>'
                metadata = [dose.get('population'),dose.get('route'), tr('Off-label use') if dose.get('off_label') else '']
                raw += '<p><strong>'+esc(' · '.join(x for x in metadata if x))+'</strong></p>'+str(dose.get('body') or '')
        for key, title in SECTIONS:
            raw += section(title, d.get(key))
        for s in (d.get('sections') or []):
            raw += section(s.get('title',''),s.get('body'))
        links = []
        for item in (d.get('attachments') or []):
            url = safe_url(item.get('file'))
            if url and url.lower().endswith(('.pdf','.pptx')):
                links.append('<li><a href="'+esc(url)+'" download>'+esc(item.get('title') or url.rsplit('/',1)[-1])+'</a></li>')
        if links:
            raw += section('Downloads','<ul>'+''.join(links)+'</ul>')
        refs = []
        for ref in (d.get('references') or []):
            url = safe_url(ref.get('url'))
            if url:
                refs.append('<li><a href="'+esc(url)+'">'+esc(ref.get('title') or url)+'</a></li>')
        if refs:
            raw += section('References','<ol>'+''.join(refs)+'</ol>')
        parser = parser_type()
        parser.feed(raw)
        content = parser.finish()
        toc = ''.join('<li class="toc-level-'+str(level)+'"><a href="#'+anchor+'">'+esc(title)+'</a></li>' for anchor,title,level in parser.toc)
        category_links = ' '.join('<a class="drug-category" href="/drugs/?category='+quote(c)+'">'+esc(c)+'</a>' for c in d['categories'])
        body = '<a class="back-link" href="/drugs/">'+tr('All drugs')+'</a>'
        if len(d['versions'])>1:
            body += '<nav class="drug-language-switch" aria-label="Drug language">' + ''.join('<a lang="'+v['language']+'" hreflang="'+v['language']+'" href="/drugs/'+v['slug']+'/"'+(' aria-current="page"' if v['slug']==d['slug'] else '')+'>'+('Русский' if v['language']=='ru' else 'English')+'</a>' for v in d['versions'])+'</nav>'
        body += '<div class="drug-heading">'
        if not d.get('published'):
            body += '<p class="drug-draft">'+tr('Draft preview · not published')+'</p>'
        body += '<h1>'+esc(d['title'])+'</h1><p>'+esc(' · '.join((d.get('aliases') or [])))+'</p><div>'+category_links+'</div>'
        if d.get('summary'):
            body += '<p>'+esc(d['summary'])+'</p>'
        if d.get('reviewed'):
            body += '<p class="muted">'+tr('Last reviewed: ')+esc(d['reviewed'])+'</p>'
        body += '</div><div class="reading-layout"><aside class="article-toc" aria-label="Drug contents"><h2>'+tr('CONTENTS')+'</h2><ol>'+toc+'</ol></aside><article class="article-body drug-body">'+content+'</article></div>'
        folder = target/d['slug']; folder.mkdir()
        (folder/'index.html').write_text(page(d['title']+' | '+tr('Drug information'),'/drugs/'+d['slug']+'/',body,d.get('summary') or d['title'],lang=d['language']))
    editor = target/'edit'; editor.mkdir()
    guide = '''<section class="drug-hero"><h1>Manage drugs</h1><p>Add and update drug information with the visual editor.</p><a class="button" href="https://app.pagescms.org/daahhay/mysite/main">Open Pages CMS</a></section>'''
    (editor/'index.html').write_text(page('Manage drugs','/drugs/edit/',guide))
