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

def build_drugs(root, output, frame, parser_type, safe_url, preview=False):
    target = output / 'drugs'
    target.mkdir()
    for name in ('drugs.css', 'drugs.js'):
        shutil.copy2(root / 'drugs' / name, target / name)
    def page(title, path, body, description='Drug information library.'):
        result = frame(title, description, path, body)
        result = result.replace('</head>', '<link rel="stylesheet" href="/drugs/drugs.css"></head>')
        result = result.replace('<a href="/blog/edit/">Manage blog ↗</a>', '<a href="/drugs/edit/">Manage drugs</a>')
        return result.replace('</body>', '<script src="/drugs/drugs.js" defer></script></body>')
    entries = load_drugs(root, preview)
    category_paths = set()
    for d in entries:
        for category in d['categories']:
            parts = category.split(' / ')
            category_paths.update(' / '.join(parts[:i]) for i in range(1,len(parts)+1))
    folder_links = ''.join('<li><a class="drug-folder" href="?category='+quote(c)+'" data-folder="'+esc(c)+'" style="--depth:'+str(c.count(' / '))+'">'+esc(c.split(' / ')[-1])+'</a></li>' for c in sorted(category_paths,key=str.casefold))
    rows = []
    letters = set()
    for d in entries:
        letter = d['title'][0].upper()
        letter = letter if letter.isalpha() else '#'
        letters.add(letter)
        search = ' '.join([d['title'], ' '.join((d.get('aliases') or [])), ' '.join(d['categories']), d.get('summary','')])
        rows.append('<li class="drug-row" data-letter="'+esc(letter)+'" data-search="'+esc(search)+'" data-categories="'+esc(json.dumps(d['categories']))+'"><a href="/drugs/'+d['slug']+'/">'+esc(d['title'])+'<span class="drug-type">: Drug information</span></a><p>'+esc(' · '.join(d['categories']))+'</p></li>')
    alphabet = ''.join('<button type="button" data-letter-filter="'+esc(l)+'">'+esc(l)+'</button>' for l in sorted(letters))
    body = '''<section class="drug-hero"><h1>Drugs</h1><p>Browse drug information by name or category.</p></section>
<div class="drug-library"><aside class="drug-folders" aria-label="Drug categories"><h2>Categories</h2><ul><li><a class="drug-folder" href="/drugs/" data-folder="">All drugs</a></li>'''+folder_links+'''</ul></aside>
<section aria-label="Drug list"><label class="drug-search">Find a drug<input id="drug-search" type="search" placeholder="Drug name, brand or category…" autocomplete="off"></label>
<div class="drug-alphabet" aria-label="Filter by initial"><button type="button" data-letter-filter="">All</button>'''+alphabet+'''</div>
<div class="drug-list-status"><p id="drug-count" role="status">'''+str(len(entries))+''' drugs</p><button id="drug-clear" type="button">Clear filters</button></div><ul class="drug-list">'''+''.join(rows)+'''</ul>
<p id="drug-empty"'''+(' hidden' if entries else '')+'''>'''+('No matching drugs. Try another search or category.' if entries else 'No drug pages have been published yet.')+'''</p></section></div>'''
    (target/'index.html').write_text(page('Drugs','/drugs/',body))
    for d in entries:
        raw = ''
        def section(title, value):
            return '<h2>'+esc(title)+'</h2>'+str(value) if value and str(value).strip() not in ('<p></p>','<p><br></p>') else ''
        raw += section('Overview', d.get('overview'))
        raw += section('Dosing guidance', d.get('dosing_guidance'))
        if d.get('doses'):
            raw += '<h2>Dosing by condition</h2>'
            for dose in d['doses']:
                raw += '<h3>'+esc(dose.get('condition'))+'</h3>'
                metadata = [dose.get('population'),dose.get('route'), 'Off-label use' if dose.get('off_label') else '']
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
        body = '<a class="back-link" href="/drugs/">All drugs</a><div class="drug-heading">'
        if not d.get('published'):
            body += '<p class="drug-draft">Draft preview · not published</p>'
        body += '<h1>'+esc(d['title'])+'</h1><p>'+esc(' · '.join((d.get('aliases') or [])))+'</p><div>'+category_links+'</div>'
        if d.get('summary'):
            body += '<p>'+esc(d['summary'])+'</p>'
        if d.get('reviewed'):
            body += '<p class="muted">Last reviewed: '+esc(d['reviewed'])+'</p>'
        body += '</div><div class="reading-layout"><aside class="article-toc" aria-label="Drug contents"><h2>CONTENTS</h2><ol>'+toc+'</ol></aside><article class="article-body drug-body">'+content+'</article></div>'
        folder = target/d['slug']; folder.mkdir()
        (folder/'index.html').write_text(page(d['title']+' | Drug information','/drugs/'+d['slug']+'/',body,d.get('summary') or d['title']+' drug information.'))
    editor = target/'edit'; editor.mkdir()
    guide = '''<section class="drug-hero"><h1>Manage drugs</h1><p>Add and update drug information with the visual editor.</p><a class="button" href="https://app.pagescms.org/daahhay/mysite/main">Open Pages CMS</a></section>
<article class="article-body"><h2>Create a drug page</h2><ol><li>Open Pages CMS and choose <strong>Drugs</strong>, then create an entry.</li><li>Enter the drug name and a permanent page address, such as <strong>norepinephrine</strong>.</li><li>Add other names and categories. Type a new category directly; use <strong>Cardiovascular / Vasopressors</strong> to create a nested folder. You can assign multiple folders.</li><li>Under <strong>Dosing by condition</strong>, add an entry for each condition or population. Enter the route and format doses, titration and notes with the rich-text toolbar.</li><li>Fill the relevant information sections. Empty sections are omitted. Add more sections, pictures, tables, source links or downloadable documents as needed.</li><li>Review the content, set the review date, turn on <strong>Publish on website</strong>, and save. The website rebuilds automatically.</li></ol><h2>Drafts and folders</h2><p>Drafts are hidden from the live library. Source files remain visible in the public GitHub repository. Categories appear automatically when their drugs are published. Moving a drug between categories does not change its page address.</p><h2>Starter entry</h2><p>An unpublished Norepinephrine entry provides example condition headings. Enter and review your content before publishing. No doses have been filled in automatically.</p></article>'''
    (editor/'index.html').write_text(page('Manage drugs','/drugs/edit/',guide))
