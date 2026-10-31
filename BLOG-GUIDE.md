# Writing on tamerlanerdniev.ru

Blog: https://tamerlanerdniev.ru/blog/

Editor instructions: https://tamerlanerdniev.ru/blog/edit/

## One-time setup

1. Open https://app.pagescms.org/ and sign in with GitHub.
2. Install the Pages CMS GitHub app for **daahhay/mysite** only.
3. Open that repository, choose **main**, and open **Blog articles**.

The `.pages.yml` file already configures the visual editor. No API tokens need to be pasted into the website.

## Add an article

Choose Add/New in Blog articles. Enter a title and a page address such as `arterial-lines`; the resulting URL is `/blog/arterial-lines/`. Keep the page address unchanged after publishing so existing links continue working. Add a date, topic and short introduction. Select English or Russian for the article text.

Use the Article toolbar for headings, bold, italics, lists, pictures and links. Heading 2 entries automatically become an article contents menu. Upload a cover image and give it a description and optional credit. Uploaded images are stored in `media/blog`.

For videos, add an item under Additional sections & videos, optionally with a heading and formatted text. Paste a YouTube or Vimeo URL (including the privacy hash for unlisted Vimeo videos), or a direct HTTPS MP4/WebM URL. The optional **Or upload a short video** field uploads an MP4/WebM clip directly; use hosted video links for larger files. Supported providers appear as responsive players; other HTTPS video links appear as a Watch video button. You can add and reorder multiple sections. Embed code is not needed. For a video near the beginning, keep the main Article field short and put the rest into additional sections.

Add citations under References & useful links. The site creates a reference list automatically.

## Draft and publish

- Keep **Publish on website** off while writing. A ready-to-edit draft template is included.
- Turn it on and save to publish. Every saved change runs the existing GitHub Pages deployment, normally taking a few minutes.
- Turn it off and save to unpublish. Published pages, list entries and sitemap entries are all removed on the next successful deployment.
- The date is a displayed article date, not a schedule. Publishing a future-dated post makes it live immediately.
- Drafts are excluded from website output, but **this repository is public**, so draft source and uploaded images are visible on GitHub. Do not store confidential material in them.
- There is no separate preview website for drafts. The editor shows formatted content. Developers can preview the final layout locally with the command below.

Check publishing at https://github.com/daahhay/mysite/actions. If publishing fails, the last successful website remains live. An invalid page address, missing required field, duplicate address, malformed date or invalid link will be reported in the build log.

## Implementation

- One JSON document per article in `content/blog`.
- `python3 scripts/build_blog.py` builds the CV pages and published blog into `_site`.
- `python3 scripts/build_blog.py --preview` builds a local draft-inclusive version into `_preview`. This is never uploaded by the deployment workflow.
- `python3 -m unittest discover -s tests` verifies draft exclusion, article creation, media handling and unsafe HTML removal.
- The deployment uploads only `_site`, not draft documents, tests, editor configuration or build scripts.
- Root CV pages, portrait and publications are preserved. The blog remains at `/blog/`, unlinked from both CV menus. Its logo is not a link to the main website. Blog pages request search-engine exclusion with `noindex` and are omitted from the sitemap; this is an unlisted public blog, not access control. Each article may be written in English or Russian. Articles are not automatically translated.
- Hosting remains GitHub Pages using the existing domain configuration; no DNS change is needed.
