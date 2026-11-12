const search = document.querySelector('#drug-search');
if (search) {
  const normalize = value => value.normalize('NFKD').toLocaleLowerCase().replace(/\p{M}/gu,'');
  const rows = [...document.querySelectorAll('.drug-row')];
  const folders = [...document.querySelectorAll('[data-folder]')];
  const letters = [...document.querySelectorAll('[data-letter-filter]')];
  const params = new URLSearchParams(location.search);
  let category = params.get('category') || '', letter = params.get('letter') || '';
  search.value = params.get('q') || '';
  function filter(updateUrl = true) {
    const terms = normalize(search.value).trim().split(/\s+/).filter(Boolean);
    let count = 0;
    for (const row of rows) {
      const categories = JSON.parse(row.dataset.categories);
      row.hidden = !(terms.every(t=>normalize(row.dataset.search).includes(t)) &&
        (!category || categories.some(c=>c===category || c.startsWith(category+' / '))) &&
        (!letter || row.dataset.letter===letter));
      if (!row.hidden) count++;
    }
    document.querySelector('#drug-count').textContent = count + (count===1?' drug':' drugs');
    document.querySelector('#drug-empty').hidden = count>0;
    folders.forEach(a=>{if(a.dataset.folder===category)a.setAttribute('aria-current','true');else a.removeAttribute('aria-current');});
    letters.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.letterFilter===letter)));
    if(updateUrl){
      const query = new URLSearchParams();
      if(category)query.set('category',category);
      if(letter)query.set('letter',letter);
      if(search.value)query.set('q',search.value);
      history.replaceState(null,'',location.pathname+(query.size?'?'+query:''));
    }
  }
  folders.forEach(a=>a.addEventListener('click',e=>{if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();category=a.dataset.folder;filter();}));
  letters.forEach(b=>b.addEventListener('click',()=>{letter=b.dataset.letterFilter;filter();}));
  search.addEventListener('input',()=>filter());
  document.querySelector('#drug-clear').addEventListener('click',()=>{category='';letter='';search.value='';filter();});
  addEventListener('popstate',()=>{const p=new URLSearchParams(location.search);category=p.get('category')||'';letter=p.get('letter')||'';search.value=p.get('q')||'';filter(false);});
  filter(false);
}
