const papers=[
['2026','May','Left ventricular ejection fraction changes after an episode of decompensated acute heart failure: a three-year follow-up','10.15829/1728-8800-2026-4764'],
['2026','May','Echocardiographically occult nonbacterial thrombotic endocarditis with tumor cell-containing valvular vegetations in metastatic breast cancer','10.1186/s40959-026-00498-8'],
['2026','Apr','Prognostic value of microRNA-143-3p and -451a levels at five year follow up in patients with coronary atherosclerosis','10.18786/2072-0505-2025-53-027'],
['2026','Apr','New Risk Factor-Weighted Clinical Likelihood (RF-CL) in Diagnosis of Chronic Coronary Syndrome in Men and Women: Our First Impressions About the Differences and Opportunities','10.3390/jcm15082923'],
['2025','Dec','Botulism Sequelae: A Systematic Review','10.1093/ofid/ofaf773'],
['2024','Nov','Cardiomyopathy associated with the use of anabolic androgenic steroids. Case report','10.26442/20751753.2024.10.202890'],
['2024','Oct','Venous Excess Ultrasound Score Is Associated with Worsening Renal Function and Reduced Natriuretic Response in Patients with Acute Heart Failure','10.3390/jcm13206272'],
['2024','Sep','Threonine In Different Phenotypes Of Chronic Heart Failure With Preserved Ejection Fraction','10.15275/rusomj.2024.0304'],
['2024','Aug','Hematologic mask of infective endocarditis as a cause of fever of unknown origin: a case report','10.15829/1728-8800-2024-4070']];
const russian=location.pathname.endsWith('main_ru.html');
if(russian){document.documentElement.lang='ru';document.title='Тамерлан Эрдниев — Кардиология и исследования';document.querySelectorAll('[data-ru]').forEach(el=>el.innerHTML=el.dataset.ru);document.querySelector('[aria-current]').removeAttribute('aria-current');document.querySelector('.languages [lang="ru"]').setAttribute('aria-current','page');document.querySelector('.skip').textContent='К содержанию';}
let lastYear='';const months={May:'Май',Apr:'Апр',Dec:'Дек',Nov:'Ноя',Oct:'Окт',Sep:'Сен',Aug:'Авг'};
document.getElementById('articles').innerHTML=papers.map(([year,month,title,doi])=>{const heading=year!==lastYear?`<h3 class="year">${year}</h3>`:'';lastYear=year;return `${heading}<a class="article" href="https://doi.org/${doi}"><div><h3 lang="en">${title}</h3><div class="meta"><span>${russian?months[month]:month} ${year}</span><span>·</span><span>${russian?'Читать статью':'Read article'}</span></div></div><span class="arrow" aria-hidden="true">↗</span></a>`}).join('');
