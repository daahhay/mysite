#!/usr/bin/env python3
"""Build static blog documents for GitHub Pages. No runtime service or dependencies."""
import argparse
import html
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import shutil
from datetime import date
from urllib.parse import urlsplit, parse_qs, urlencode, unquote, quote

ORIGIN = 'https://tamerlanerdniev.ru'


def esc(value):
    return html.escape(str(value or ''), quote=True)


def safe_url(value, media=False):
    value = str(value or '').strip()
    if not value or re.search(r'[\x00-\x20\\]', value):
        return ''
    parsed = urlsplit(value)
    if parsed.scheme in (('https',) if media else ('https', 'http')) and parsed.hostname and not parsed.username:
        return value
    if not media and parsed.scheme == 'mailto':
        return value
    if value.startswith('/') and not value.startswith('//') and '..' not in parsed.path.split('/'):
        return value
    if not media and value.startswith('#'):
        return value
    return ''


class ArticleHTML(HTMLParser):
    """Render only a small, safe formatting vocabulary from the visual editor."""
    allowed = set('p br span strong b em i u s del h1 h2 h3 h4 ul ol li blockquote a img hr figure figcaption pre code table thead tbody tr th td sup sub'.split())
    void = {'br', 'img', 'hr'}
    blocked = {'script', 'style', 'iframe', 'object', 'svg', 'math', 'template'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.stack, self.toc, self.words = [], [], [], []
        self.suppressed = []
        self.heading = None

    def handle_starttag(self, tag, attrs):
        if self.suppressed:
            if tag in self.blocked:
                self.suppressed.append(tag)
            return
        if tag in self.blocked:
            self.suppressed.append(tag)
            return
        if tag not in self.allowed:
            return
        attrs = dict(attrs)
        rendered = ''
        if tag == 'span':
            # Only retain an explicit HEX foreground color from rich HTML.
            for declaration in (attrs.get('style') or '').split(';'):
                match = re.fullmatch(r'\s*color\s*:\s*(#[0-9a-f]{6}|#[0-9a-f]{3})\s*', declaration, re.I)
                if match:
                    rendered = f' style="color:{match[1]}"'
        elif tag == 'a':
            url = safe_url(attrs.get('href'))
            if url:
                rendered = f' href="{esc(url)}"'
        elif tag == 'img':
            url = safe_url(attrs.get('src'), media=True)
            if not url:
                return
            rendered = f' src="{esc(url)}" alt="{esc(attrs.get("alt"))}" loading="lazy" decoding="async"'
        elif tag in ('h1', 'h2', 'h3'):
            heading_id = f'section-{len(self.toc) + 1}'
            self.toc.append([heading_id, '', int(tag[1])])
            self.heading = len(self.toc) - 1
            rendered = f' id="{heading_id}"'
        if tag == 'table':
            self.parts.append('<div class="table-wrap">')
        self.parts.append(f'<{tag}{rendered}>')
        if tag not in self.void:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.void:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.suppressed:
            if tag == self.suppressed[-1]:
                self.suppressed.pop()
            return
        if tag not in self.stack:
            return
        while self.stack:
            current = self.stack.pop()
            self.parts.append(f'</{current}>')
            if current == 'table':
                self.parts.append('</div>')
            if current in ('h1', 'h2', 'h3'):
                self.heading = None
            if current == tag:
                break

    def handle_data(self, data):
        if self.suppressed:
            return
        # The hosted editor preserves plain-text color runs on subsequent edits.
        pattern = r'\[color=(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})\](.*?)\[/color\]'
        start = 0
        for match in re.finditer(pattern, data, re.DOTALL):
            self.parts.append(esc(data[start:match.start()]))
            self.parts.append(f'<span style="color:{match[1]}">{esc(match[2])}</span>')
            start = match.end()
        self.parts.append(esc(data[start:]))
        data = re.sub(pattern, lambda match: match[2], data, flags=re.DOTALL)
        self.words.extend(data.split())
        if self.heading is not None:
            self.toc[self.heading][1] += data

    def finish(self):
        self.close()
        while self.stack:
            self.handle_endtag(self.stack[-1])
        return ''.join(self.parts)


def introduction(value):
    # Older articles store literal text. Make their existing web references clickable.
    if not re.search(r'<(?:p|a|strong|em|div|span|br|h[1-6])\b', value, re.I):
        parts = []
        start = 0
        for match in re.finditer(r"""https?://[^\s<>"']+""", value):
            url = match.group().rstrip('.,;:!?')
            if not safe_url(url):
                continue
            parts.extend([esc(value[start:match.start()]), f'<a href="{esc(url)}">{esc(url)}</a>'])
            start = match.start() + len(url)
        parts.append(esc(value[start:]))
        return '<p>' + ''.join(parts) + '</p>', value
    parser = ArticleHTML()
    parser.allowed = {'p', 'br', 'a', 'strong', 'b', 'em', 'i', 'u', 's'}
    parser.feed(value)
    rendered = parser.finish()
    description = html.unescape(re.sub(r'<[^>]+>', '', rendered.replace('</p>', ' ').replace('<br>', ' '))).strip()
    return rendered, description


def video_block(url, caption=''):
    url = safe_url(url, media=True)
    if not url:
        return ''
    parsed = urlsplit(url)
    host, path = (parsed.hostname or '').lower(), parsed.path
    video_id, embed = '', ''
    if host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com'):
        if path == '/watch':
            video_id = parse_qs(parsed.query).get('v', [''])[0]
        elif path.startswith(('/embed/', '/shorts/', '/live/')):
            video_id = path.split('/')[2]
    elif host == 'youtu.be':
        video_id = path.strip('/')
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        embed = 'https://www.youtube-nocookie.com/embed/' + video_id
    elif host in ('vimeo.com', 'www.vimeo.com', 'player.vimeo.com'):
        parts = path.strip('/').split('/')
        candidate = parts[1] if parts[0] == 'video' and len(parts) > 1 else parts[0]
        if candidate.isdigit():
            embed = 'https://player.vimeo.com/video/' + candidate
            # Preserve Vimeo's unlisted-video privacy hash when supplied.
            privacy = parse_qs(parsed.query).get('h', [''])[0]
            if len(parts) > 1 and parts[0] != 'video':
                privacy = parts[1]
            if re.fullmatch(r'[a-zA-Z0-9]+', privacy):
                embed += '?h=' + privacy
    if embed:
        media = f'<iframe src="{esc(embed)}" title="{esc(caption or "Video")}" loading="lazy" allow="fullscreen; picture-in-picture; encrypted-media" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>'
    elif path.lower().endswith(('.mp4', '.webm')):
        media = f'<video controls preload="metadata" playsinline src="{esc(url)}"><a href="{esc(url)}">Watch video</a></video>'
    else:
        media = f'<a class="video-link" href="{esc(url)}">Watch video ↗</a>'
    return f'<div class="video-block">{media}' + (f'<p>{esc(caption)}</p>' if caption else '') + '</div>'


def frame(title, description, path, content, lang='en', noindex=False):
    section_link = '<a href="/blog/">Blog ↗</a>' if path.startswith('/calculators/') else '<a href="/calculators/">Calculators ↗</a>'
    return f'''<!doctype html>
<html lang="{esc(lang)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | Tamerlan Erdniev</title><meta name="description" content="{esc(description)}">
<link rel="canonical" href="{ORIGIN}{path}"><meta name="robots" content="noindex">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}"><meta property="og:url" content="{ORIGIN}{path}"><meta property="og:type" content="{'article' if path not in ('/blog/', '/blog/edit/') else 'website'}">
<link rel="shortcut icon" href="/blog/favicon.ico?v=20261104-3"><link rel="icon" type="image/x-icon" sizes="16x16 32x32 48x48 96x96" href="/blog/favicon.ico?v=20261104-3"><link rel="icon" type="image/png" sizes="16x16" href="/blog/favicon-16.png?v=20261104-3"><link rel="icon" type="image/png" sizes="32x32" href="/blog/favicon-32.png?v=20261104-3"><link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png"><link rel="manifest" href="/site.webmanifest"><meta name="theme-color" content="#f7f6f0"><meta name="apple-mobile-web-app-title" content="Tamerlan"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-status-bar-style" content="default"><link rel="stylesheet" href="/styles.css"><link rel="stylesheet" href="/blog/blog.css">
</head><body><a class="skip" href="#main">Skip to content</a>
<header class="blog-header"><div class="wordmark" aria-label="Tamerlan Erdniev"><span class="brand"><img src="/logo.svg" alt="Tamerlan Erdniev logo" width="31.53515625" height="46" style="display:block"></span><span class="owner-name">Tamerlan Erdniev</span></div><nav class="section-navigation" aria-label="Explore">{section_link}</nav></header>
<main class="blog-main" id="main">{content}</main>
<footer class="blog-footer"><span>Tamerlan Erdniev</span><a href="/blog/edit/">Manage blog ↗</a></footer>
</body></html>'''


def post_url(post):
    return '/blog/' + post['slug'] + '/'


def labels(value):
    """Accept editor lists and older comma-separated values; deduplicate labels."""
    if isinstance(value, str):
        value = value.split(',')
    if value is None:
        value = []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError('Topics and tags must be lists of text labels')
    result, seen = [], set()
    for item in value:
        item = ' '.join(item.split()).lstrip('#').strip()
        if item and item.lower() not in seen:
            result.append(item)
            seen.add(item.lower())
    return result


def taxonomy_links(post):
    links = []
    for kind, values in (('topic', post['topics']), ('tag', post['tags'])):
        for label in values:
            url = '/blog/?' + urlencode({kind: label})
            prefix = '#' if kind == 'tag' else ''
            links.append(f'<a class="taxonomy-chip {kind}-chip" href="{esc(url)}" aria-label="Find articles with {kind}: {esc(label)}">{prefix}{esc(label)}</a>')
    return '<div class="taxonomy-links" aria-label="Topics and tags">' + ''.join(links) + '</div>'


def load_posts(root, include_drafts=False):
    posts, slugs = [], set()
    for file in sorted((root / 'content/blog').glob('*.json')):
        try:
            post = json.loads(file.read_text(encoding='utf-8'))
            if not isinstance(post, dict):
                raise ValueError('Article must be an object')
            if post.get('published') is not True and not include_drafts:
                continue
            for field in ('title', 'slug', 'date', 'excerpt'):
                if not isinstance(post.get(field), str) or not post[field].strip():
                    raise ValueError(f'{field} is required')
            post['excerpt_html'], post['excerpt_text'] = introduction(post['excerpt'])
            slug = post['slug']
            if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or slug in ('edit',):
                raise ValueError('Page address must contain only lowercase English letters, numbers and single hyphens; "edit" is reserved')
            if slug in slugs:
                raise ValueError(f'Duplicate page address: {slug}')
            slugs.add(slug)
            post['date_object'] = date.fromisoformat(post['date'])
            post['language'] = post.get('language') or 'en'
            if post['language'] not in ('en', 'ru'):
                raise ValueError('Language must be en or ru')
            new_topics = labels(post.get('new_topics'))
            post['category'] = post.get('category') or next(iter(new_topics or labels(post.get('topics'))), 'Notes')
            post['topics'] = labels([str(post['category'])] + labels(post.get('topics')) + new_topics)
            post['tags'] = labels(post.get('tags'))
            for field in ('sections', 'references', 'attachments'):
                post[field] = post.get(field) or []
                if not isinstance(post[field], list) or not all(isinstance(x, dict) for x in post[field]):
                    raise ValueError(f'{field} must be a list')
            if post.get('cover') and not safe_url(post['cover'], media=True):
                raise ValueError('Cover image must be an HTTPS URL or a path beginning with /')
            parser = ArticleHTML()
            parser.feed(str(post.get('body') or ''))
            for section in post['sections']:
                if section.get('title'):
                    parser.feed(f'<h2>{esc(section["title"])}</h2>')
                parser.feed(str(section.get('body') or ''))
                video = section.get('video_url') or section.get('video_file')
                if video:
                    if not safe_url(video, media=True):
                        raise ValueError('Video links must use HTTPS or a path beginning with /')
                    parser.parts.append(video_block(video, section.get('video_caption', '')))
            for ref in post['references']:
                if not ref.get('title') or not safe_url(ref.get('url')):
                    raise ValueError('Every reference needs a title and a valid URL')
            post['body_html'] = parser.finish()
            post['toc'] = parser.toc
            post['minutes'] = max(1, math.ceil(len(parser.words) / 200))
            posts.append(post)
        except (ValueError, TypeError, KeyError) as error:
            raise ValueError(f'{file.name}: {error}') from error
    return sorted(posts, key=lambda p: (p['date'], p['slug']), reverse=True)


def translation_pairs(posts):
    # Only published entries are passed in production. Draft/deleted targets have no link.
    by_slug = {post['slug']: post for post in posts}
    pairs = {}
    for post in posts:
        target_slug = post.get('translation_of')
        if not target_slug:
            continue
        if not isinstance(target_slug, str):
            raise ValueError(f"{post['slug']}: Translation of must be one article")
        target = by_slug.get(target_slug)
        if not target:
            continue
        if target['language'] == post['language']:
            raise ValueError(f"{post['slug']}: Select a translation in the other language")
        for source, other in ((post, target), (target, post)):
            existing = pairs.get(source['slug'])
            if existing and existing['slug'] != other['slug']:
                raise ValueError(f"{source['slug']}: More than one translation is linked; keep one per language")
            pairs[source['slug']] = other
    return pairs


def language_switcher(post, translation):
    if not translation:
        return ''
    versions = {p['language']: p for p in (post, translation)}
    label = 'Язык статьи' if post['language'] == 'ru' else 'Article language'
    links = []
    for lang, name in (('en', 'English'), ('ru', 'Русский')):
        current = ' aria-current="page"' if lang == post['language'] else ''
        links.append(f'<a href="{post_url(versions[lang])}" lang="{lang}" hreflang="{lang}"{current}>{name}</a>')
    return f'<nav class="article-languages" aria-label="{label}"><span>{label}</span>{"".join(links)}</nav>'


def display_date(post):
    d = post['date_object']
    return f'{d.day} {d.strftime("%B")} {d.year}'


def card(post):
    url, title = post_url(post), esc(post['title'])
    category = esc(post.get('category') or 'Notes')
    image = (f'<img src="{esc(safe_url(post["cover"], media=True))}" alt="{esc(post.get("cover_alt"))}" loading="lazy" width="800" height="450">' if post.get('cover') else f'<div class="cover-type" aria-hidden="true"><span>{category.upper()}</span><strong>te.</strong><span>FROM THE NOTEBOOK</span></div>')
    return f'''<article class="post-card" data-language="{post['language']}" data-topics="{esc(json.dumps(post['topics'], ensure_ascii=False))}" data-tags="{esc(json.dumps(post['tags'], ensure_ascii=False))}"><a class="post-cover" href="{url}" aria-label="{title}">{image}</a>
<div class="post-meta"><span class="topic">{category}</span><span>·</span><time datetime="{post['date']}">{display_date(post)}</time><span>· {post['minutes']} min read</span></div>
<h2 lang="{post['language']}"><a href="{url}">{title}</a></h2><div class="introduction" lang="{post['language']}">{post['excerpt_html']}</div>{taxonomy_links(post)}<a class="read-link" href="{url}" aria-label="Read {title}">Read article <span aria-hidden="true">↗</span></a></article>'''


def index_page(posts):
    hero = '''<section class="blog-hero"><div><div class="eyebrow"><span class="dot"></span> THE NOTEBOOK</div><h1>Blog.</h1><p>Notes, perspectives, and a closer look at cardiology and clinical research.</p></div><div class="blog-note">A place to explore<br>ideas in more depth.<span>THE BLOG OF TAMERLAN ERDNIEV</span></div></section>'''
    if not posts:
        body = '''<section class="blog-empty"><div class="empty-mark" aria-hidden="true">01</div><div><div class="eyebrow">A NEW CHAPTER</div><h2>The notebook is open.</h2><p>New articles will appear here.</p></div></section>'''
    else:
        topics = sorted(labels([t for p in posts for t in p['topics']]), key=str.lower)
        tags = sorted(labels([t for p in posts for t in p['tags']]), key=str.lower)
        options = ''.join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in topics)
        tag_options = ''.join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in tags)
        body = f'''<div class="blog-toolbar"><label for="article-search">SEARCH <input id="article-search" type="search" placeholder="Articles, topics, tags…" autocomplete="off"></label><label for="article-topic">TOPIC <select id="article-topic"><option value="">All topics</option>{options}</select></label><label for="article-tag">TAG <select id="article-tag"><option value="">All tags</option>{tag_options}</select></label><label for="article-language">LANGUAGE <select id="article-language"><option value="">All languages</option><option value="en">English</option><option value="ru">Русский</option></select></label><button class="reset-filters" id="clear-filters" type="button">Clear filters</button></div>
<p class="result-count" id="result-count" role="status">{len(posts)} articles</p><div class="post-grid">{''.join(card(p) for p in posts)}</div>
<div class="no-results" id="no-results" hidden><h2>No matching articles</h2><p>Try another search, topic, tag or language, or clear the filters above.</p></div><script src="/blog/blog.js" defer></script>'''
    return frame('Blog', 'Notes, perspectives and articles by Tamerlan Erdniev.', '/blog/', hero + body)


def attachment_links(items, is_ru):
    if not items:
        return ''
    links = []
    for item in items:
        path = unquote(str(item.get('file') or ''))
        kind = Path(path).suffix.lower()
        if not path.startswith('/media/blog/') or '..' in path.split('/') or kind not in ('.pdf', '.pptx'):
            raise ValueError('Choose a PDF or PPTX attachment from the blog media library')
        url = quote(path, safe='/')
        label = item.get('title') or Path(path).name
        links.append(f'<li><a download href="{esc(url)}"><span class="file-icon">{kind[1:].upper()}</span>{esc(label)}</a></li>')
    heading = 'Скачать материалы' if is_ru else 'Download materials'
    return f'<section class="attachments"><h2>{heading}</h2><ul>{"".join(links)}</ul></section>'


def article_page(post, newer=None, older=None, preview=False, translation=None):
    is_ru = post['language'] == 'ru'
    toc_label = 'В ЭТОЙ СТАТЬЕ' if is_ru else 'IN THIS ARTICLE'
    refs_label = 'Источники и ссылки' if is_ru else 'References & further reading'
    meta = f'<div class="post-meta"><span class="topic">{esc(post.get("category") or "Notes")}</span><span>·</span><time datetime="{post["date"]}">{display_date(post)}</time><span>· {post["minutes"]} min read</span></div>'
    title = f'''<div class="breadcrumb"><a href="/blog/">← All articles</a></div><div class="article-head">{language_switcher(post, translation)}{meta}<h1>{esc(post['title'])}</h1><div class="article-deck introduction">{post['excerpt_html']}</div>{taxonomy_links(post)}</div>'''
    cover = ''
    if post.get('cover'):
        cover = f'<figure class="article-cover"><img src="{esc(safe_url(post["cover"], media=True))}" alt="{esc(post.get("cover_alt"))}">' + (f'<figcaption>{esc(post["cover_caption"])}</figcaption>' if post.get('cover_caption') else '') + '</figure>'
    toc_links = ''.join(f'<li class="toc-level-{level}"><a href="#{anchor}">{esc(label)}</a></li>' for anchor, label, level in post['toc'])
    references = ''
    if post['references']:
        toc_links += f'<li class="toc-level-2"><a href="#references">{refs_label}</a></li>'
        references = f'<section class="references" id="references"><h2>{refs_label}</h2><ol>' + ''.join(f'<li><a href="{esc(safe_url(r["url"]))}">{esc(r["title"])}</a></li>' for r in post['references']) + '</ol></section>'
    toc = f'<aside class="article-toc" aria-label="Article contents"><h2>{toc_label}</h2><ol>{toc_links}</ol></aside>' if toc_links else '<div></div>'
    body = f'<div class="reading-layout">{toc}<article class="article-body">{post["body_html"]}{references}</article></div>'
    navigation = '<nav class="post-navigation" aria-label="More articles">'
    navigation += (f'<a href="{post_url(newer)}"><span>← NEWER ARTICLE</span>{esc(newer["title"])}</a>' if newer else '<div></div>')
    navigation += (f'<a href="{post_url(older)}"><span>OLDER ARTICLE →</span>{esc(older["title"])}</a>' if older else '<a href="/blog/"><span>KEEP EXPLORING</span>All articles →</a>')
    navigation += '</nav>'
    banner = '<div class="draft-banner">LOCAL PREVIEW · This draft is not published</div>' if preview and not post.get('published') else ''
    page = frame(post['title'], post['excerpt_text'], post_url(post), banner + title + cover + attachment_links(post["attachments"], is_ru) + body + navigation, lang=post['language'], noindex=preview)
    if translation:
        alternates = ''.join(f'<link rel="alternate" hreflang="{p["language"]}" href="{ORIGIN}{post_url(p)}">' for p in (post, translation))
        page = page.replace('</head>', alternates + '</head>')
    return page


def palette_panel():
    colors = [('Graphite', '#363A38'), ('Slate', '#526778'), ('Brown', '#795643'),
              ('Coral', '#A54436'), ('Amber', '#926214'), ('Olive', '#596D35'),
              ('Forest', '#286047'), ('Teal', '#236968'), ('Blue', '#305E9C'),
              ('Indigo', '#554A94'), ('Plum', '#774878'), ('Rose', '#984A69')]
    swatches = ''.join(f'<button type="button" class="swatch" style="--swatch:{value}" '
                       f'data-color="{value}" title="{name} ({value})" aria-label="{name} {value}" '
                       f'aria-pressed="false"></button>' for name, value in colors)
    return f'''<section class="palette" id="palette" aria-labelledby="palette-heading">
<h2 id="palette-heading">Text color</h2>
<p>Enter the words to color, choose a swatch or enter a HEX value, then copy the result into the article’s visual editor. The color appears on the published page.</p>
<label>Text to color<input id="color-text" type="text" placeholder="A word or phrase"></label>
<div class="swatches" role="group" aria-label="Text color presets">{swatches}</div>
<label>Custom HEX<input id="color-hex" value="#286047" maxlength="7" spellcheck="false"></label>
<div class="color-preview" id="color-preview">Sample text</div>
<button class="button" type="button" id="color-copy">Copy for article</button>
<p id="color-status" role="status"></p><textarea id="color-manual" aria-label="Formatted text to copy" readonly hidden></textarea>
</section><script defer src="/blog/palette.js"></script>'''


def editor_page():
    return frame('Manage your blog', 'Write, illustrate and publish your articles.', '/blog/edit/', '''<section class="editor-intro"><a class="eyebrow" href="/blog/">← BACK TO THE BLOG</a><h1>Your writing desk.</h1><p>Write an article, add pictures and videos, then publish when you’re ready.</p><a class="button" href="https://app.pagescms.org/">Open visual editor <span>↗</span></a>''' + palette_panel() + '''<ol class="editor-steps"><li><h2>Connect once</h2><p>Sign in to Pages CMS with GitHub. Install its GitHub app for <strong>daahhay/mysite</strong>, then open that repository and choose <strong>main</strong>. The article editor is already configured.</p></li><li><h2>Write & illustrate</h2><p>Open <strong>Blog articles</strong>, then add an article or edit the draft template. Enter a title, page address and short introduction. Use the formatting toolbar for headings, links and pictures. Add video links or upload short MP4/WebM clips under <strong>Additional sections & videos</strong>. Add sources under <strong>References & useful links</strong>.</p></li><li><h2>Add a translation</h2><p>Create a separate article with a unique page address (for example, arterial-lines-ru). Set <strong>Article language</strong> to the other language, write the translated title, introduction and article, then choose the original in <strong>Translation of</strong>. Link once only. When both versions are published, an <strong>English / Русский</strong> switcher appears above the title on both pages. Each version can have its own pictures, attachments and references.</p></li><li><h2>Save a draft or publish</h2><p>Keep <strong>Publish on website</strong> off while writing. Turn it on and save when ready. Your article appears at <strong>/blog/your-page-address/</strong> after deployment finishes, usually within a few minutes. Turn it off and save to remove the article from the website.</p></li></ol><div class="editor-note"><strong>Drafts & media</strong><p>Drafts stay off the website, but this GitHub repository is public: draft files and uploaded media can be read there. Use YouTube or Vimeo links for large videos. Article dates are display dates, not a publishing schedule.</p></div><p><a href="https://github.com/daahhay/mysite/actions">Check publishing status ↗</a> · <a href="https://pagescms.org/docs/quick-start/">Editor setup help ↗</a></p></section>''', noindex=True)


IMAGE_LOADER = """<style>
#image-loader {position:fixed;inset:0;margin:auto;padding:0;border:0;outline:0;box-shadow:none;overflow:visible;background:transparent;color:#111}
#image-loader::backdrop {background:var(--paper,#f7f6f0)}
#image-loader svg {display:block;width:65px;height:72px;animation:heart-beat 1s ease-in-out infinite}
#image-loader .fill {clip-path:inset(6% 0 0);transition:clip-path .2s linear}
#image-loader[open]:not(.ready) .fill {animation:heart-loading 1.8s linear both}
#image-loader.ready .fill {clip-path:inset(0)}
@keyframes heart-beat {0%,40%,100% {transform:scale(1)} 10% {transform:scale(1.09)} 20% {transform:scale(1.015)} 29% {transform:scale(1.055)}}
@keyframes heart-loading {from {clip-path:inset(100% 0 0)} to {clip-path:inset(6% 0 0)}}
@media (prefers-reduced-motion:reduce) {#image-loader svg,#image-loader[open] .fill {animation:none!important;transition:none}}
</style>
<dialog id="image-loader" aria-label="Loading images">
<svg viewBox="184 113 1234 1375" aria-hidden="true" fill="none" stroke-linecap="round" stroke-linejoin="round">
<defs>
  <g id="heart-ink" stroke-width="70">
    <path d="M375 545V208h157l3 302M527 507c3-150 121-269 275-269 97 0 185 39 239 120M680 252l-25-74m145 54v-80m111 91 27-65"/>
    <path d="M704 585c15-63 2-116 42-158 40-43 80-20 123-17 64 6 125-23 189-44l168-53 43 121-182 66c-38 14-67 20-99 23M1191 557l142-47 45 120-88 29"/>
    <path d="M672 807c65-123 150-266 305-282 188-24 329 127 328 289 0 216-225 467-541 635C471 1287 220 1031 222 813c2-170 134-290 286-290 108 0 205 54 251 147"/>
  </g>
</defs>
<g class="fill" fill="#c52c40">
  <path d="M375 558V208h157l3 191Q633 238 802 238c97 0 185 39 239 120l185-45 43 121-180 66q65 15 102 57l142-47 45 120-88 29q16 75 15 155c0 216-225 467-541 635C471 1287 220 1031 222 813q0-163 153-255Z"/>
</g>
<use href="#heart-ink" stroke="currentColor"/>
</svg></dialog>
<script>
(() => {
  const loader = document.getElementById('image-loader');
  if (!loader.showModal) return;
  const reveal = () => loader.remove();
  loader.showModal();
  loader.addEventListener('cancel', event => event.preventDefault());
  const minimumFill = new Promise(resolve => setTimeout(resolve, 1800));
  document.addEventListener('DOMContentLoaded', async () => {
    const images = Array.from(document.images);
    await Promise.all(images.map(async image => {
      image.loading = 'eager';
      try {
        if (image.decode) await image.decode();
        else if (!image.complete) await new Promise(resolve => {
          image.addEventListener('load', resolve, {once:true});
          image.addEventListener('error', resolve, {once:true});
        });
      } catch { /* A missing picture should not block the page. */ }
    }));
    await minimumFill;
    loader.classList.add('ready');
    setTimeout(reveal, 200);
  }, {once:true});
})();
</script>"""


def build(root, output, include_drafts=False):
    root, output = root.resolve(), output.resolve()
    if output == root or output in root.parents:
        raise ValueError('Output must not overwrite source')
    posts = load_posts(root, include_drafts)
    translations = translation_pairs(posts)
    if output.exists():
        if not (output / '.blog-generated').exists():
            raise ValueError('Refusing to replace a directory not created by this builder')
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / '.blog-generated').touch()
    for pattern in ('*.html', '*.css', '*.js', '*.svg', '*.ico', '*.png', '*.webmanifest', 'CNAME', 'robots.txt'):
        for source in root.glob(pattern):
            if source.is_file():
                shutil.copy2(source, output / source.name)
    for directory in ('Pics', 'media'):
        if (root / directory).exists():
            shutil.copytree(root / directory, output / directory)
    blog = output / 'blog'
    blog.mkdir()
    for source in (root / 'blog').glob('*'):
        if source.is_file():
            shutil.copy2(source, blog / source.name)
    for name in ('favicon.ico', 'favicon-16.png', 'favicon-32.png'):
        if (root / name).exists():
            shutil.copy2(root / name, blog / name)
    (blog / 'index.html').write_text(index_page(posts), encoding='utf-8')
    (blog / 'edit').mkdir()
    (blog / 'edit/index.html').write_text(editor_page(), encoding='utf-8')
    for index, post in enumerate(posts):
        target = blog / post['slug']
        target.mkdir()
        newer = posts[index - 1] if index else None
        older = posts[index + 1] if index + 1 < len(posts) else None
        (target / 'index.html').write_text(article_page(post, newer, older, include_drafts, translations.get(post['slug'])), encoding='utf-8')
    if (root / 'calculators/data.json').exists():
        import runpy
        calculator_builder = runpy.run_path(str(root / 'scripts/build_calculators.py'))
        calculator_builder['build_calculators'](root, output, frame)
    for page in output.rglob('*.html'):
        html = page.read_text(encoding='utf-8')
        if '</head>' in html and 'rel="icon"' not in html:
            html = html.replace('</head>', '<link rel="shortcut icon" href="/favicon.ico?v=20261104-2"><link rel="icon" type="image/x-icon" sizes="16x16 32x32 48x48 96x96" href="/favicon.ico?v=20261104-2"><link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png?v=20261104-2"><link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png?v=20261104-2"></head>', 1)
        if '<body>' in html and 'http-equiv="refresh"' not in html.lower():
            html = html.replace('<body>', '<body>' + IMAGE_LOADER, 1)
        page.write_text(html, encoding='utf-8')
    urls = ['/', '/main_ru.html']
    sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{ORIGIN}{u}</loc></url>' for u in urls) + '</urlset>'
    (output / 'sitemap.xml').write_text(sitemap, encoding='utf-8')
    (output / '.nojekyll').touch()
    print(f'Built {len(posts)} article(s) in {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', action='store_true', help='Include draft articles locally in _preview, never _site')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    build(root, root / ('_preview' if args.preview else '_site'), args.preview)
