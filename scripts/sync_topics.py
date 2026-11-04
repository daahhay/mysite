"""Add topics from saved articles, including drafts, to the CMS suggestions."""
import hashlib
import json
from pathlib import Path

from build_blog import labels


def sync_topics(root):
    library = root / 'content/topics'
    library.mkdir(parents=True, exist_ok=True)
    known = set()
    for path in library.glob('*.json'):
        topic = json.loads(path.read_text(encoding='utf-8'))
        known.update(name.casefold() for name in labels([topic.get('title') or '']))
    added = 0
    for path in sorted((root / 'content/blog').glob('*.json')):
        article = json.loads(path.read_text(encoding='utf-8'))
        topics = labels([str(article.get('category') or '')] +
                        labels(article.get('topics')) + labels(article.get('new_topics')))
        for name in topics:
            key = name.casefold()
            if key in known:
                continue
            filename = hashlib.sha256(key.encode('utf-8')).hexdigest() + '.json'
            target = library / filename
            with target.open('x', encoding='utf-8') as output:
                output.write(json.dumps({'title': name}, ensure_ascii=False, indent=2) + '\n')
            known.add(key)
            added += 1
    return added


if __name__ == '__main__':
    print(f'Added {sync_topics(Path(__file__).resolve().parents[1])} topic suggestions')
