import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('blog', Path(__file__).resolve().parents[1] / 'scripts/build_blog.py')
blog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(blog)


class BlogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'source'
        (self.root / 'content/blog').mkdir(parents=True)
        (self.root / 'blog').mkdir()
        (self.root / 'Pics').mkdir()
        (self.root / 'Pics/avatar.jpg').write_bytes(b'portrait')
        (self.root / 'index.html').write_text('Existing CV remains intact')
        self.out = Path(self.temp.name) / 'output'

    def write_post(self, name='one', **overrides):
        post = dict(title='A clinical note', slug=name, published=True, date='2026-10-31', excerpt='A short introduction', category='Cardiology', body='<h2>Overview</h2><p>A paragraph with an <a href="https://example.org/">external link</a>.</p><img src="/media/blog/figure.png" alt="Figure">', sections=[], references=[])
        post.update(overrides)
        (self.root / 'content/blog' / (name + '.json')).write_text(json.dumps(post))
        return post

    def test_builds_real_documents_and_preserves_cv(self):
        self.write_post(references=[{'title': 'Reference', 'url': 'https://example.org/research'}])
        self.write_post('older', date='2026-09-01')
        blog.build(self.root, self.out)
        self.assertEqual((self.out / 'index.html').read_text(), 'Existing CV remains intact')
        page = (self.out / 'blog/one/index.html').read_text()
        self.assertIn('id="section-1"', page)
        self.assertIn('href="#section-1"', page)
        self.assertIn('/blog/older/', page)
        self.assertIn('https://example.org/research', page)
        self.assertIn('https://tamerlanerdniev.ru/blog/one/', page)
        self.assertNotIn('/blog/', (self.out / 'sitemap.xml').read_text())
        self.assertIn('value="Cardiology"', (self.out / 'blog/index.html').read_text())
        self.assertTrue((self.out / 'Pics/avatar.jpg').exists())

    def test_drafts_excluded_from_all_public_output_and_unpublish_cleans(self):
        self.write_post('private-draft', published=False, title='Draft marker')
        self.write_post()
        blog.build(self.root, self.out)
        self.assertFalse((self.out / 'blog/private-draft').exists())
        self.assertFalse((self.out / 'content').exists())
        self.assertNotIn('Draft marker', (self.out / 'blog/index.html').read_text())
        self.assertNotIn('private-draft', (self.out / 'sitemap.xml').read_text())
        self.write_post(published=False)
        blog.build(self.root, self.out)
        self.assertFalse((self.out / 'blog/one').exists())
        self.assertIn('The notebook is open.', (self.out / 'blog/index.html').read_text())

    def test_draft_preview_explicit_and_not_indexable(self):
        self.write_post(published=False)
        blog.build(self.root, self.out, include_drafts=True)
        page = (self.out / 'blog/one/index.html').read_text()
        self.assertIn('LOCAL PREVIEW', page)
        self.assertIn('name="robots" content="noindex"', page)

    def test_rich_html_strips_active_content_and_keeps_formatting(self):
        parser = blog.ArticleHTML()
        parser.feed('<h2>Safe <em>title</em></h2><script>alert(1)</script><img src="javascript:alert(1)" onerror="alert(2)"><a href="jav&#97;script:alert(3)">bad link</a><p style="color:red" onclick="alert(4)">Text</p><iframe src="https://evil.example">evil</iframe><table><tr><td>cell</td></tr></table>')
        result = parser.finish()
        for bad in ('<script', 'alert(', 'onerror', 'onclick', 'javascript:', '<iframe', 'style=', 'evil'):
            self.assertNotIn(bad, result)
        self.assertIn('<em>title</em>', result)
        self.assertIn('<div class="table-wrap"><table>', result)
        self.assertEqual(parser.toc, [['section-1', 'Safe title', 2]])

    def test_media_embeds_and_untrusted_provider_fallback(self):
        self.assertIn('youtube-nocookie.com/embed/abcdefghijk', blog.video_block('https://youtu.be/abcdefghijk'))
        self.assertIn('youtube-nocookie.com/embed/abcdefghijk', blog.video_block('https://www.youtube.com/watch?v=abcdefghijk&t=20'))
        self.assertIn('player.vimeo.com/video/12345?h=abc123', blog.video_block('https://vimeo.com/12345/abc123'))
        self.assertIn('<video controls', blog.video_block('https://example.org/movie.mp4'))
        self.assertIn('Watch video', blog.video_block('https://example.org/video'))
        self.assertNotIn('<iframe', blog.video_block('https://youtube.com.evil.example/watch?v=abcdefghijk'))
        self.assertEqual(blog.video_block('javascript:alert(1)'), '')
        self.assertEqual(blog.safe_url('//evil.example/image.jpg', media=True), '')

    def test_rejects_invalid_slugs_duplicate_addresses_and_dates(self):
        for invalid in ('../escape', 'edit', 'two words', 'Uppercase'):
            self.write_post(slug=invalid)
            with self.assertRaises(ValueError):
                blog.load_posts(self.root)
        self.write_post(date='not-a-date')
        with self.assertRaises(ValueError):
            blog.load_posts(self.root)
        self.write_post()
        self.write_post('two', slug='one')
        with self.assertRaises(ValueError):
            blog.load_posts(self.root)

    def test_escapes_metadata_and_embeds_multiple_sections(self):
        self.write_post(title='<script>bad()</script>', sections=[{'title': 'A video', 'video_url': 'https://youtu.be/abcdefghijk', 'video_caption': '<script>unsafe</script>'}, {'title': 'Another section', 'body': '<p>More text</p>'}])
        blog.build(self.root, self.out)
        page = (self.out / 'blog/one/index.html').read_text()
        self.assertNotIn('<script>bad', page)
        self.assertIn('&lt;script&gt;bad()', page)
        self.assertIn('youtube-nocookie.com/embed/abcdefghijk', page)
        self.assertIn('href="#section-3"', page)
        self.assertIn('More text', page)

    def test_uploaded_video_and_image_paths(self):
        self.write_post(cover='/media/blog/cover.jpg', cover_alt='Cover description', sections=[{'title': 'A clip', 'video_file': '/media/blog/clip.mp4'}])
        blog.build(self.root, self.out)
        page = (self.out / 'blog/one/index.html').read_text()
        self.assertIn('src="/media/blog/cover.jpg" alt="Cover description"', page)
        self.assertIn('playsinline src="/media/blog/clip.mp4"', page)

    def test_heading_one_is_preserved_and_linked_in_contents(self):
        self.write_post(body='<h1>Major <em>heading</em></h1><p>Text</p><h2>Smaller heading</h2>')
        post = blog.load_posts(self.root)[0]
        self.assertIn('<h1 id="section-1">Major <em>heading</em></h1>', post['body_html'])
        self.assertEqual(post['toc'], [['section-1', 'Major heading', 1], ['section-2', 'Smaller heading', 2]])

    def test_colored_words_and_three_level_contents(self):
        self.write_post(body='<h1>First</h1><h2>Second</h2><h3>[color=#357]Third[/color]</h3><p>Before [color=#305E9C]blue &amp; safe[/color] after.</p><span style="color:#abc;background:url(evil)">More</span>')
        post = blog.load_posts(self.root)[0]
        page = blog.article_page(post)
        self.assertEqual([entry[2] for entry in post['toc']], [1, 2, 3])
        self.assertIn('<li class="toc-level-3"><a href="#section-3">Third</a>', page)
        self.assertIn('Before <span style="color:#305E9C">blue &amp; safe</span> after.', page)
        self.assertIn('<span style="color:#abc">More</span>', page)
        self.assertNotIn('url(evil)', page)
        self.assertIn('id="palette"', blog.editor_page())

    def test_topics_and_tags_round_trip_and_old_articles_still_work(self):
        self.write_post(topics=[' Critical care ', 'cardiology', 'Critical care'], tags=['echo', '#ultrasound', 'ECHO', 'Русский тег'])
        self.write_post('legacy')
        posts = blog.load_posts(self.root)
        post = next(p for p in posts if p['slug'] == 'one')
        self.assertEqual(post['topics'], ['Cardiology', 'Critical care'])
        self.assertEqual(post['tags'], ['echo', 'ultrasound', 'Русский тег'])
        legacy = next(p for p in posts if p['slug'] == 'legacy')
        self.assertEqual(legacy['topics'], ['Cardiology'])
        self.assertEqual(legacy['tags'], [])
        blog.build(self.root, self.out)
        index = (self.out / 'blog/index.html').read_text()
        page = (self.out / 'blog/one/index.html').read_text()
        self.assertIn('id="article-tag"', index)
        self.assertIn('value="Critical care"', index)
        self.assertIn('value="ultrasound"', index)
        self.assertIn('/blog/?topic=Critical+care', page)
        self.assertIn('/blog/?tag=ultrasound', page)
        self.assertIn('data-tags=', index)

    def test_taxonomy_is_escaped_and_accepts_comma_separated_legacy_input(self):
        self.write_post(tags='echo, ultrasound, echo', topics=['<script>alert(1)</script>'])
        post = blog.load_posts(self.root)[0]
        self.assertEqual(post['tags'], ['echo', 'ultrasound'])
        rendered = blog.index_page([post])
        self.assertNotIn('<script>alert', rendered)
        self.assertIn('&lt;script&gt;', rendered)


if __name__ == '__main__':
    unittest.main()
