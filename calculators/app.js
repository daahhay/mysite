import {calculate, validate} from './engine.mjs?v=20261110';

const normalize = text => text.normalize('NFKD').toLowerCase().replace(/[^a-z0-9]+/g,' ');
const search = document.querySelector('#calculator-search');
if (search) {
  const category = document.querySelector('#calculator-category');
  const rows = [...document.querySelectorAll('.calculator-row')];
  function filter() {
    const terms = normalize(search.value).trim().split(/\s+/).filter(Boolean);
    let count = 0;
    for (const row of rows) {
      const matches = terms.every(term => normalize(row.dataset.search).includes(term)) &&
        (!category.value || row.dataset.category === category.value);
      row.hidden = !matches;
      if (matches) count++;
    }
    document.querySelector('#library-count').textContent = count + (count === 1 ? ' calculator' : ' calculators');
    document.querySelector('#library-empty').hidden = count !== 0;
  }
  search.addEventListener('input', filter);
  category.addEventListener('change', filter);
}
const form = document.querySelector('#calculator-form');
if (form) {
  const definition = JSON.parse(document.querySelector('#calculator-definition').textContent);
  const result = document.querySelector('#calculator-result');
  const error = document.querySelector('#form-error');
  const initial = result.innerHTML;
  const add = (parent, tag, text, className) => {
    const element = document.createElement(tag);
    element.textContent = text;
    if (className) element.className = className;
    parent.append(element);
    return element;
  };
  function clear() {result.innerHTML = initial; error.textContent = '';}
  form.addEventListener('input', clear);
  form.addEventListener('reset', clear);
  form.addEventListener('submit', event => {
    event.preventDefault();
    const data = new FormData(form);
    const values = Object.fromEntries(definition.fields.map(field => {
      const value = data.get(field.id);
      return [field.id, value === null || value.trim() === '' ? null : Number(value)];
    }));
    const message = validate(definition, values);
    if (message || !form.checkValidity()) {
      result.innerHTML = initial;
      error.textContent = message || 'Check the highlighted inputs.';
      form.reportValidity();
      error.focus();
      return;
    }
    const answer = calculate(definition.slug, values);
    error.textContent = '';
    result.replaceChildren();
    add(result,'span', answer.incomplete ? 'DOCUMENTED RESULT' : 'RESULT','eyebrow');
    add(result,'div',answer.probability ? answer.score.toFixed(1)+'%' : String(answer.score),'score');
    if (answer.maximum) add(result,'p','of '+answer.maximum+' points','score-unit');
    if (answer.estimatedProbability) {
      add(result,'div',answer.estimatedProbability,'probability-estimate');
      add(result,'p','Estimated HFpEF probability','probability-label');
      const note = add(result,'p','Approximate reading from the original study’s probability chart. ','field-help');
      const source = add(note,'a','View source');
      source.href = 'https://pmc.ncbi.nlm.nih.gov/articles/PMC6202181/#F1';
    }
    add(result,'h2',answer.category);
    add(result,'p',answer.detail);
    if (answer.outcomes) {
      add(result,'p','Baseline score group: '+answer.scoreGroup,'field-help');
      const comparison = add(result,'div','','outcome-comparison');
      for (const outcome of answer.outcomes) {
        const section = add(comparison,'section','','outcome');
        add(section,'h3',outcome.label);
        for (const [label,value,kind] of [['Medical therapy alone',outcome.medical,'medical'],['TEER + medical therapy',outcome.teer,'teer']]) {
          const line = add(section,'div','','outcome-line');
          add(line,'span',label);
          add(line,'strong',value.toFixed(1)+'%');
          const track = add(section,'div','','outcome-track');
          track.setAttribute('aria-hidden','true');
          const bar = add(track,'div','',kind);
          bar.style.width = value+'%';
        }
      }
      add(result,'p','Trial averages do not guarantee an individual treatment benefit.','field-help');
    }
    const details = add(result,'details','');
    add(details,'summary',answer.probability ? 'Model contributions' : 'Score breakdown');
    for (const row of answer.rows) {
      const line = add(details,'div','','breakdown-row');
      add(line,'span',row.label);
      add(line,'strong',answer.probability ? row.points.toFixed(4) : String(row.points));
      if (row.explanation) add(details,'p',row.explanation,'field-help');
    }
    if (answer.probability) add(details,'p','Log odds = '+answer.logOdds.toFixed(6),'field-help');
    result.tabIndex = -1;
    result.focus({preventScroll:true});
    if (matchMedia('(max-width: 850px)').matches) result.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth',block:'start'});
  });
}
