(() => {
  const panel = document.querySelector('#palette');
  if (!panel) return;
  const field = id => panel.querySelector('#color-' + id);
  const words = field('text'), hex = field('hex'), preview = field('preview');
  const copy = field('copy'), status = field('status'), manual = field('manual');
  const swatches = [...panel.querySelectorAll('.swatch')];
  function value() {
    const raw = hex.value.trim().replace(/^#/, '');
    if (!/^(?:[a-f0-9]{3}|[a-f0-9]{6})$/i.test(raw)) return '';
    return '#' + (raw.length === 3 ? [...raw].map(c => c + c).join('') : raw).toUpperCase();
  }
  function refresh() {
    const color = value();
    preview.style.color = color || 'inherit';
    preview.textContent = words.value || 'Sample text';
    hex.setAttribute('aria-invalid', String(!color));
    copy.disabled = !color || !words.value.trim();
    status.textContent = color ? '' : 'Use 3 or 6 hexadecimal digits, for example #286047.';
    manual.hidden = true;
    swatches.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.color === color)));
  }
  swatches.forEach(b => b.addEventListener('click', () => {hex.value = b.dataset.color; refresh();}));
  words.addEventListener('input', refresh); hex.addEventListener('input', refresh);
  copy.addEventListener('click', async () => {
    const result = '[color=' + value() + ']' + words.value + '[/color]';
    try {
      await navigator.clipboard.writeText(result);
      status.textContent = 'Copied. Paste into the article where you want the colored text.';
    } catch {
      manual.value = result; manual.hidden = false; manual.focus(); manual.select();
      status.textContent = 'Copy the selected text, then paste it into your article.';
    }
  });
  refresh();
})();
