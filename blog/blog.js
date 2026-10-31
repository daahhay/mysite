(() => {
  const search = document.querySelector('#article-search');
  const topic = document.querySelector('#article-topic');
  if (!search || !topic) return;
  const cards = [...document.querySelectorAll('.post-card')];
  const count = document.querySelector('#result-count');
  const empty = document.querySelector('#no-results');
  function filter() {
    const query = search.value.trim().toLocaleLowerCase();
    let shown = 0;
    for (const card of cards) {
      const matches = (!query || card.textContent.toLocaleLowerCase().includes(query)) && (!topic.value || card.dataset.topic === topic.value);
      card.hidden = !matches;
      if (matches) shown++;
    }
    count.textContent = `${shown} ${shown === 1 ? 'article' : 'articles'}`;
    empty.hidden = shown > 0;
  }
  search.addEventListener('input', filter);
  topic.addEventListener('change', filter);
  document.querySelector('#clear-filters').addEventListener('click', () => {
    search.value = ''; topic.value = ''; filter(); search.focus();
  });
  filter();
})();
