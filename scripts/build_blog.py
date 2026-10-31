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
from urllib.parse import urlsplit, parse_qs, urlencode

ORIGIN = 'https://tamerlanerdniev.ru'
AUTHOR = 'Tamerlan Erdniev'


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
    return f'''<!doctype html>
<html lang="{esc(lang)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — Tamerlan Erdniev</title><meta name="description" content="{esc(description)}">
<link rel="canonical" href="{ORIGIN}{path}"><meta name="robots" content="noindex">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}"><meta property="og:url" content="{ORIGIN}{path}"><meta property="og:type" content="{'article' if path not in ('/blog/', '/blog/edit/') else 'website'}">
<link rel="icon" type="image/svg+xml" href="/blog/favicon.svg"><link rel="stylesheet" href="/styles.css"><link rel="stylesheet" href="/blog/blog.css">
</head><body><a class="skip" href="#main">Skip to content</a>
<header class="blog-header"><div class="wordmark" aria-label="Tamerlan Erdniev"><span class="brand">te<span>.</span></span><span class="owner-name">Tamerlan Erdniev</span></div></header>
<main class="blog-main" id="main">{content}</main>
<footer class="blog-footer"><span>Tamerlan Erdniev</span><span>Cardiology · Sechenov University</span><a href="/blog/edit/">Manage blog ↗</a></footer>
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
            post['topics'] = labels([str(post.get('category') or 'Notes')] + labels(post.get('topics')))
            post['tags'] = labels(post.get('tags'))
            for field in ('sections', 'references'):
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


def display_date(post):
    d = post['date_object']
    return f'{d.day} {d.strftime("%B")} {d.year}'


def card(post):
    url, title = post_url(post), esc(post['title'])
    category = esc(post.get('category') or 'Notes')
    image = (f'<img src="{esc(safe_url(post["cover"], media=True))}" alt="{esc(post.get("cover_alt"))}" loading="lazy" width="800" height="450">' if post.get('cover') else f'<div class="cover-type" aria-hidden="true"><span>{category.upper()}</span><strong>te.</strong><span>FROM THE NOTEBOOK</span></div>')
    return f'''<article class="post-card" data-topics="{esc(json.dumps(post['topics'], ensure_ascii=False))}" data-tags="{esc(json.dumps(post['tags'], ensure_ascii=False))}"><a class="post-cover" href="{url}" aria-label="{title}">{image}</a>
<div class="post-meta"><span class="topic">{category}</span><span>·</span><time datetime="{post['date']}">{display_date(post)}</time><span>· {post['minutes']} min read</span></div>
<h2 lang="{post['language']}"><a href="{url}">{title}</a></h2><p lang="{post['language']}">{esc(post['excerpt'])}</p>{taxonomy_links(post)}<a class="read-link" href="{url}" aria-label="Read {title}">Read article <span aria-hidden="true">↗</span></a></article>'''


def index_page(posts):
    hero = '''<section class="blog-hero"><div><div class="eyebrow"><span class="dot"></span> THE NOTEBOOK</div><h1>Blog.</h1><p>Notes, perspectives, and a closer look at cardiology and clinical research.</p></div><div class="blog-note">A place to explore<br>ideas in more depth.<span>THE BLOG OF TAMERLAN ERDNIEV</span></div></section>'''
    if not posts:
        body = '''<section class="blog-empty"><div class="empty-mark" aria-hidden="true">01</div><div><div class="eyebrow">A NEW CHAPTER</div><h2>The notebook is open.</h2><p>New articles will appear here.</p></div></section>'''
    else:
        topics = sorted(labels([t for p in posts for t in p['topics']]), key=str.lower)
        tags = sorted(labels([t for p in posts for t in p['tags']]), key=str.lower)
        options = ''.join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in topics)
        tag_options = ''.join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in tags)
        body = f'''<div class="blog-toolbar"><label for="article-search">SEARCH <input id="article-search" type="search" placeholder="Articles, topics, tags…" autocomplete="off"></label><label for="article-topic">TOPIC <select id="article-topic"><option value="">All topics</option>{options}</select></label><label for="article-tag">TAG <select id="article-tag"><option value="">All tags</option>{tag_options}</select></label><button class="reset-filters" id="clear-filters" type="button">Clear filters</button></div>
<p class="result-count" id="result-count" role="status">{len(posts)} articles</p><div class="post-grid">{''.join(card(p) for p in posts)}</div>
<div class="no-results" id="no-results" hidden><h2>No matching articles</h2><p>Try another search, topic or tag, or clear the filters above.</p></div><script src="/blog/blog.js" defer></script>'''
    return frame('Blog', 'Notes, perspectives and articles by Tamerlan Erdniev.', '/blog/', hero + body)


def article_page(post, newer=None, older=None, preview=False):
    is_ru = post['language'] == 'ru'
    toc_label = 'В ЭТОЙ СТАТЬЕ' if is_ru else 'IN THIS ARTICLE'
    refs_label = 'Источники и ссылки' if is_ru else 'References & further reading'
    meta = f'<div class="post-meta"><span class="topic">{esc(post.get("category") or "Notes")}</span><span>·</span><time datetime="{post["date"]}">{display_date(post)}</time><span>· {post["minutes"]} min read</span></div>'
    title = f'''<div class="breadcrumb"><a href="/blog/">← All articles</a></div><div class="article-head">{meta}<h1>{esc(post['title'])}</h1><p class="article-deck">{esc(post['excerpt'])}</p>{taxonomy_links(post)}<div class="byline"><img src="/Pics/avatar.jpg" alt="" width="38" height="38"><div>{AUTHOR}<br><span>Sechenov University</span></div></div></div>'''
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
    return frame(post['title'], post['excerpt'], post_url(post), banner + title + cover + body + navigation, lang=post['language'], noindex=preview)


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
    return frame('Manage your blog', 'Write, illustrate and publish your articles.', '/blog/edit/', '''<section class="editor-intro"><a class="eyebrow" href="/blog/">← BACK TO THE BLOG</a><h1>Your writing desk.</h1><p>Write an article, add pictures and videos, then publish when you’re ready.</p><a class="button" href="https://app.pagescms.org/">Open visual editor <span>↗</span></a>''' + palette_panel() + '''<ol class="editor-steps"><li><h2>Connect once</h2><p>Sign in to Pages CMS with GitHub. Install its GitHub app for <strong>daahhay/mysite</strong>, then open that repository and choose <strong>main</strong>. The article editor is already configured.</p></li><li><h2>Write & illustrate</h2><p>Open <strong>Blog articles</strong>, then add an article or edit the draft template. Enter a title, page address and short introduction. Use the formatting toolbar for headings, links and pictures. Add video links or upload short MP4/WebM clips under <strong>Additional sections & videos</strong>. Add sources under <strong>References & useful links</strong>.</p></li><li><h2>Save a draft or publish</h2><p>Keep <strong>Publish on website</strong> off while writing. Turn it on and save when ready. Your article appears at <strong>/blog/your-page-address/</strong> after deployment finishes, usually within a few minutes. Turn it off and save to remove the article from the website.</p></li></ol><div class="editor-note"><strong>Drafts & media</strong><p>Drafts stay off the website, but this GitHub repository is public: draft files and uploaded media can be read there. Use YouTube or Vimeo links for large videos. Article dates are display dates, not a publishing schedule.</p></div><p><a href="https://github.com/daahhay/mysite/actions">Check publishing status ↗</a> · <a href="https://pagescms.org/docs/quick-start/">Editor setup help ↗</a></p></section>''', noindex=True)


IMAGE_LOADER = """<style>
#image-loader {position:fixed;inset:0;margin:auto;padding:0;border:0;outline:0;box-shadow:none;overflow:visible;background:transparent;color:#a64750}
#image-loader::backdrop {background:#fff}
#image-loader svg {display:block;width:59px;height:72px}
#image-loader .fill {clip-path:inset(var(--remaining,100%) 0 0);transition:clip-path .18s linear}
@media (prefers-reduced-motion:reduce) {#image-loader .fill {transition:none}}
</style>
<dialog id="image-loader" aria-label="Loading images">
<svg viewBox="3 1 54 66" aria-hidden="true" fill="none" stroke-linecap="round" stroke-linejoin="round">
<defs>
  <path id="loading-heart" d="M11 24 9 10l6-1 2 12 4-2c-1-6 0-10 4-13l-1-3 4-1 2 4 2-1V2h4l1 4 2 1 2-4 4 2-2 5c3 3 4 6 4 10l6-2 2 5-9 5c5 7 7 18 6 30-.2 5-1 8-4 8-10-2-24-8-32-17C5 40 3 31 7 26Z"/>
  <path id="heart-detail" d="M17 21q-5 1-7 7m15-7c-1-5 1-10 5-11 5-2 10 2 10 8m-20 14c4-11 10-16 17-16l10 4m-23 16c4-9 12-12 22-13m-26 8c2 4 6 5 10 7s6 7 7 12l6 9m-12-19 8-3 4-4m-8 15-5 3m7-1 6 2"/>
  <g id="heart-ink"><use href="#loading-heart" stroke-width="1.6"/><use href="#heart-detail" fill="none" stroke-width="1.35"/></g>
</defs>
<use href="#heart-ink" stroke="currentColor"/>
<g class="fill"><use href="#loading-heart" fill="currentColor" stroke="currentColor" stroke-width="1.6"/><use href="#heart-detail" stroke="#fff" stroke-width="1.35"/></g>
</svg></dialog>
<script>
(() => {
  const loader = document.getElementById('image-loader');
  if (!loader.showModal) return;
  const reveal = () => loader.remove();
  loader.showModal();
  document.addEventListener('DOMContentLoaded', async () => {
    const images = Array.from(document.images);
    let remaining = images.length;
    await Promise.all(images.map(async image => {
      image.loading = 'eager';
      try {
        if (image.decode) await image.decode();
        else if (!image.complete) await new Promise(resolve => {
          image.addEventListener('load', resolve, {once:true});
          image.addEventListener('error', resolve, {once:true});
        });
      } catch { /* A missing picture should not block the page. */ }
      remaining -= 1;
      loader.style.setProperty('--remaining', (100 * remaining / images.length) + '%');
    }));
    setTimeout(reveal, images.length && !matchMedia('(prefers-reduced-motion:reduce)').matches ? 190 : 0);
  }, {once:true});
})();
</script>"""


def build(root, output, include_drafts=False):
    root, output = root.resolve(), output.resolve()
    if output == root or output in root.parents:
        raise ValueError('Output must not overwrite source')
    posts = load_posts(root, include_drafts)
    if output.exists():
        if not (output / '.blog-generated').exists():
            raise ValueError('Refusing to replace a directory not created by this builder')
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / '.blog-generated').touch()
    for pattern in ('*.html', '*.css', '*.js', '*.svg', '*.ico', 'CNAME', 'robots.txt'):
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
    (blog / 'index.html').write_text(index_page(posts), encoding='utf-8')
    (blog / 'edit').mkdir()
    (blog / 'edit/index.html').write_text(editor_page(), encoding='utf-8')
    for index, post in enumerate(posts):
        target = blog / post['slug']
        target.mkdir()
        newer = posts[index - 1] if index else None
        older = posts[index + 1] if index + 1 < len(posts) else None
        (target / 'index.html').write_text(article_page(post, newer, older, include_drafts), encoding='utf-8')
    for page in output.rglob('*.html'):
        html = page.read_text(encoding='utf-8')
        if '<body>' in html and 'http-equiv="refresh"' not in html.lower():
            page.write_text(html.replace('<body>', '<body>' + IMAGE_LOADER, 1), encoding='utf-8')
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
