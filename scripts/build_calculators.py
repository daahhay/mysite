"""Build the separate calculator directory and individual static documents."""
import html
import json
import shutil

def build_calculators(root, output, frame):
    source = root / 'calculators'
    definitions = json.loads((source / 'data.json').read_text())
    target = output / 'calculators'
    target.mkdir()
    for name in ('app.js','engine.mjs','calculators.css'):
        shutil.copy2(source / name, target / name)
    def esc(value):
        return html.escape(str(value),quote=True)
    def page(title, slug, body):
        url = '/calculators/' + (slug + '/' if slug else '')
        rendered = frame(title, 'Clinical calculators for cardiology and pulmonary embolism.',url,body)
        rendered = rendered.replace('<link rel="stylesheet" href="/blog/blog.css">','<link rel="stylesheet" href="/blog/blog.css"><link rel="stylesheet" href="/calculators/calculators.css">')
        rendered = rendered.replace('<a href="/blog/edit/">Manage blog ↗</a>','<span>Clinical tools · Sources reviewed 4 November 2026</span>')
        return rendered.replace('</body>','<script type="module" src="/calculators/app.js"></script></body>')
    rows = ''.join(f'<li class="calculator-row" data-category="{esc(d["category"])}" data-search="{esc(d["title"]+" "+d["slug"]+" "+d["summary"]+" "+d["category"])}"><a href="/calculators/{d["slug"]}/"><span class="row-number">{i+1:02}</span><div><h2>{esc(d["title"])}</h2><p>{esc(d["summary"])}</p><span class="category">{esc(d["category"])}</span></div><span class="row-arrow" aria-hidden="true">↗</span></a></li>' for i,d in enumerate(definitions))
    categories=''.join(f'<option>{esc(c)}</option>' for c in dict.fromkeys(d['category'] for d in definitions))
    body=f'''<section class="calc-hero"><div class="eyebrow"><span class="dot"></span> CLINICAL TOOLS</div><h1>Medical calculators.</h1><p>A focused collection for cardiology and pulmonary embolism.</p></section>
<div class="library-controls"><label>Find a calculator<input id="calculator-search" type="search" placeholder="Search name, condition or specialty…" autocomplete="off"></label><label>Clinical area<select id="calculator-category"><option value="">All areas</option>{categories}</select></label></div>
<p id="library-count" class="muted" role="status">{len(definitions)} calculators</p><ol class="calculator-list">{rows}</ol><p id="library-empty" hidden>No matching calculators. Try another name or clinical area.</p>
<p class="clinical-note">For clinical decision support in adults. Interpret results alongside the full clinical assessment and the cited sources.</p>'''
    (target/'index.html').write_text(page('Medical calculators','',body))
    for d in definitions:
        fields=[]
        for f in d['fields']:
            help_text=f.get('help','')
            if f.get('optional'):
                help_text='Optional · leave blank if not measured.'
            hint=f'<p id="help-{f["id"]}" class="field-help">{esc(help_text)}</p>' if help_text else ''
            described=f' aria-describedby="help-{f["id"]}"' if help_text else ''
            if f.get('type')=='number':
                required='' if f.get('optional') else ' required'
                control=f'<label for="field-{f["id"]}">{esc(f["label"])}</label>{hint}<div class="number-control"><input id="field-{f["id"]}" name="{f["id"]}" type="number" min="{f["min"]}" max="{f["max"]}" step="{f["step"]}" inputmode="decimal"{required}{described}><span>{esc(f["unit"])}</span></div>'
                fields.append('<div class="field">'+control+'</div>')
            else:
                options=''.join(f'<label class="choice"><input type="radio" name="{f["id"]}" value="{o["value"]}" required{described}><span>{esc(o["label"])}</span></label>' for o in f['options'])
                fields.append(f'<fieldset class="field"><legend>{esc(f["label"])}</legend>{hint}<div class="choices">{options}</div></fieldset>')
        refs=''.join(f'<li><a href="{esc(r["url"])}" target="_blank" rel="noopener noreferrer">{esc(r["label"])} ↗</a></li>' for r in d['references'])
        payload=json.dumps(d,ensure_ascii=False).replace('<','\u003c')
        body=f'''<a class="back-link" href="/calculators/">← All calculators</a>
<section class="calculator-heading"><div class="eyebrow">{esc(d["category"])}</div><h1>{esc(d["title"])}</h1><p>{esc(d["summary"])}</p></section>
<p class="clinical-note">{esc(d["note"])}</p>
<div class="calculator-layout"><form id="calculator-form" novalidate><div class="form-heading"><h2>Patient inputs</h2><button type="reset" class="reset-button">Reset</button></div><p class="muted">Complete each required input. Results are calculated in this browser.</p>
{''.join(fields)}<p id="form-error" class="form-error" role="alert" tabindex="-1"></p><button type="submit" class="calculate-button">Calculate result <span aria-hidden="true">↗</span></button></form>
<aside class="result-panel" aria-label="Calculator result"><div id="calculator-result" aria-live="polite"><span class="eyebrow">RESULT</span><h2>Ready when you are.</h2><p>Enter patient information and select Calculate result.</p></div></aside></div>
<section class="calculator-evidence"><h2>How it works</h2><p>{esc(d["method"])}</p><h2>Sources</h2><ul>{refs}</ul><p class="muted">Reviewed 4 November 2026. Supports clinical reasoning; confirm findings and use current local guidance.</p></section>
<script type="application/json" id="calculator-definition">{payload}</script><noscript><p>Enable JavaScript to calculate results.</p></noscript>'''
        folder=target/d['slug'];folder.mkdir()
        (folder/'index.html').write_text(page(d['title'],d['slug'],body))
