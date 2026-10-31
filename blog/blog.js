(() => {
  const search = document.querySelector('#article-search');
  const topic = document.querySelector('#article-topic');
  const tag = document.querySelector('#article-tag');
  if (!search || !topic || !tag) return;
  const normalize = value => value.trim().toLocaleLowerCase();
  const cards = [...document.querySelectorAll('.post-card')].map(element => ({
    element,
    topics: JSON.parse(element.dataset.topics || '[]').map(normalize),
    tags: JSON.parse(element.dataset.tags || '[]').map(normalize),
    text: normalize(element.textContent)
  }));
  const count = document.querySelector('#result-count');
  const empty = document.querySelector('#no-results');
  function filter() {
    const words = normalize(search.value).split(/\s+/).filter(Boolean);
    let shown = 0;
    for (const card of cards) {
      const matches = words.every(word => card.text.includes(word)) &&
        (!topic.value || card.topics.includes(normalize(topic.value))) &&
        (!tag.value || card.tags.includes(normalize(tag.value)));
      card.element.hidden = !matches;
      if (matches) shown++;
    }
    count.textContent = `${shown} ${shown === 1 ? 'article' : 'articles'}`;
    empty.hidden = shown > 0;
    const url = new URL(location.href);
    for (const [key, value] of [['q', search.value.trim()], ['topic', topic.value], ['tag', tag.value]]) {
      if (value) url.searchParams.set(key, value);
      else url.searchParams.delete(key);
    }
    history.replaceState(null, '', url);
  }
  function restore() {
    const params = new URLSearchParams(location.search);
    search.value = params.get('q') || '';
    for (const [select, key] of [[topic, 'topic'], [tag, 'tag']]) {
      const requested = params.get(key) || '';
      const found = [...select.options].find(option => normalize(option.value) === normalize(requested));
      // Preserve a removed/renamed label as an explicit no-results filter.
      if (!found && requested) select.add(new Option(requested, requested));
      select.value = found ? found.value : requested;
    }
    filter();
  }
  search.addEventListener('input', filter);
  topic.addEventListener('change', filter);
  tag.addEventListener('change', filter);
  window.addEventListener('popstate', restore);
  document.querySelector('#clear-filters').addEventListener('click', () => {
    search.value = ''; topic.value = ''; tag.value = ''; filter(); search.focus();
  });
  restore();
})();
