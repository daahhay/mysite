export function validate(definition, input) {
  for (const field of definition.fields) {
    const value = input[field.id];
    if (value == null || value === '') {
      if (field.optional) continue;
      return 'Complete ' + field.label.toLowerCase() + '.';
    }
    if (!Number.isFinite(value)) return 'Enter a valid value for ' + field.label + '.';
    if (field.options && !field.options.some(option => option.value === value)) return 'Choose ' + field.label + '.';
    if (field.type === 'number' && (value < field.min || value > field.max || (field.step === 1 && !Number.isInteger(value)))) {
      return field.label + ' must be ' + (field.step === 1 ? 'a whole number ' : '') + 'between ' + field.min + ' and ' + field.max + '.';
    }
  }
  if (definition.slug === 'hfa-peff' && !definition.fields.some(field => field.optional && input[field.id] != null)) {
    return 'Enter at least one echocardiographic or biomarker measurement.';
  }
  return '';
}

function total(rows, category, detail, maximum) {
  return {score: rows.reduce((sum, row) => sum + row.points, 0), category, detail, maximum, rows};
}
const row = (label, points) => ({label, points});

export function calculate(slug, v) {
  let rows, score;
  switch (slug) {
    case 'coapt': {
      rows = [row('COPD',v.copd),row('AF / flutter',v.af),row('NYHA III / IVa',+(v.nyha >= 2)),
        row('Kidney function',v.egfr),row('LVEF',v.lvef),row('LVESD ≥5.5 cm',v.lvesd),
        row('RVSP >45 mmHg',v.rvsp),row('TR ≥moderate',v.tr > 0 ? 2 : 0)];
      score = rows.reduce((sum,r)=>sum+r.points,0);
      // Observed 2-year rates from the Mount Sinai / Shah reference calculator.
      // Columns: death, HF hospitalization, death or HF hospitalization.
      // Rows: baseline score ≤2, 3, 4, 5, 6, 7, 8, 9, ≥10. No treatment subtraction.
      const medical = [[23.3,27.9,37.0],[23.3,48.4,51.9],[20.8,41.6,51.7],
        [33.8,44.3,60.6],[40.8,55.0,65.7],[59.4,83.1,89.2],
        [61.0,62.5,78.2],[62.6,75.9,80.4],[72.7,84.2,91.2]];
      const teer = [[11.5,19.5,24.8],[14.5,35.6,40.0],[26.2,22.5,34.8],
        [25.0,27.2,39.0],[27.9,27.2,37.5],[28.8,45.1,57.8],
        [42.5,45.7,55.4],[48.5,57.3,72.0],[49.0,67.4,70.4]];
      const index = Math.max(0,Math.min(8,score-2));
      return {...total(rows,'Two-year outcome estimates',
        'Observed COAPT trial rates by baseline score. TEER results reflect MitraClip plus guideline-directed medical therapy.',15),
        scoreGroup: score <= 2 ? '0–2' : score >= 10 ? '≥10' : String(score),
        outcomes: ['Death','HF hospitalization','Death or HF hospitalization'].map((label,i)=>
          ({label,medical:medical[index][i],teer:teer[index][i]}))};
    }
    case 'cha2ds2-vasc':
      rows = [row('Age', v.age >= 75 ? 2 : v.age >= 65 ? 1 : 0), row('Female sex', v.female),
        row('Heart failure', v.hf), row('Hypertension', v.htn), row('Diabetes', v.diabetes),
        row('Prior stroke / TIA / embolism', 2 * v.stroke), row('Vascular disease', v.vascular)];
      return total(rows, 'Stroke risk factor score', 'Interpret with current AF guidance. Female sex alone is a risk modifier; treatment decisions require clinical assessment.', 9);
    case 'h2fpef':
      rows = [row('BMI >30', v.bmi > 30 ? 2 : 0), row('AF history', 3 * v.af), row('Age >60', +(v.age > 60)),
        row('At least two antihypertensives', v.htn2), row('PASP >35', +(v.pasp > 35)), row('E/e′ >9', +(v.ee > 9))];
      score = rows.reduce((sum, r) => sum + r.points, 0);
      return {...total(rows, score <= 1 ? 'Low HFpEF likelihood' : score <= 5 ? 'Intermediate HFpEF likelihood' : 'High HFpEF likelihood',
        score >= 2 && score <= 5 ? 'Additional diagnostic testing is needed.' : 'Interpret in adults with unexplained dyspnea and preserved EF.', 9),
        // Approximate readings from Reddy et al., Circulation 2018, Figure 1.
        // The nomogram ends at 20% and 95%; do not extrapolate beyond it.
        estimatedProbability: ['<20%', '≈23%', '≈39%', '≈56%', '≈72%', '≈83%', '≈91%', '≈95%', '>95%', '>95%'][score]};
    case 'hfpef-aba': {
      const logOdds = -7.788751 + 0.062564 * v.age + 0.135149 * v.bmi + 2.040806 * v.af;
      return {score: 100 / (1 + Math.exp(-logOdds)), probability: true, category: 'Estimated HFpEF probability',
        detail: 'Continuous screening estimate. Confirm the clinical context and evaluate with echocardiography.',
        rows: [row('Age contribution', 0.062564 * v.age), row('BMI contribution', 0.135149 * v.bmi), row('AF contribution', 2.040806 * v.af), row('Intercept', -7.788751)], logOdds};
    }
    case 'revised-geneva':
    case 'simplified-geneva': {
      const simple = slug === 'simplified-geneva';
      rows = [row('Age >65', +(v.age > 65)), row('Heart rate', v.hr >= 95 ? (simple ? 2 : 5) : v.hr >= 75 ? (simple ? 1 : 3) : 0),
        ...[['vte','Prior DVT / PE',3],['surgery','Surgery / fracture',2],['cancer','Active malignancy',2],
          ['pain','Unilateral pain',3],['hemoptysis','Hemoptysis',2],['signs','Tenderness and edema',4]]
          .map(([id,label,weight]) => row(label, v[id] * (simple ? 1 : weight)))];
      score = rows.reduce((sum, r) => sum + r.points, 0);
      const low = simple ? 1 : 3, high = simple ? 5 : 11, likely = simple ? 3 : 6;
      return total(rows, score <= low ? 'Low pretest probability' : score >= high ? 'High pretest probability' : 'Intermediate pretest probability',
        'Two-level classification: PE ' + (score >= likely ? 'likely' : 'unlikely') + '. Apply within a PE diagnostic pathway.', simple ? 9 : 22);
    }
    case 'pesi':
      rows = [row('Age in years',v.age),row('Male sex',v.female === 0 ? 10 : 0),row('Cancer',30*v.cancer),
        row('Heart failure',10*v.hf),row('Lung disease',10*v.lung),row('Heart rate ≥110',v.hr>=110?20:0),
        row('Systolic BP <100',v.sbp<100?30:0),row('Respiratory rate ≥30',v.rr>=30?20:0),
        row('Temperature <36°C',v.temp<36?20:0),row('Altered mental status',60*v.mental),row('Oxygen saturation <90%',v.sat<90?20:0)];
      score=rows.reduce((sum,r)=>sum+r.points,0);
      const index=[65,85,105,125,Infinity].findIndex(limit=>score<=limit);
      return total(rows, 'Class '+['I','II','III','IV','V'][index]+' · '+['Very low','Low','Intermediate','High','Very high'][index]+' risk',
        'Observed 30-day mortality across derivation and validation cohorts: '+['0–1.6%','1.7–3.5%','3.2–7.1%','4.0–11.4%','10.0–24.5%'][index]+'. Cohort estimates are not an individual prognosis.');
    case 'spesi':
      rows=[row('Age >80',+(v.age>80)),row('Cancer',v.cancer),row('Cardiopulmonary disease',v.cardiopulmonary),
        row('Heart rate ≥110',+(v.hr>=110)),row('Systolic BP <100',+(v.sbp<100)),row('Oxygen saturation <90%',+(v.sat<90))];
      score=rows.reduce((sum,r)=>sum+r.points,0);
      return total(rows,score===0?'Lower 30-day mortality risk':'Elevated 30-day mortality risk',
        'For confirmed PE. Assess hemodynamic stability and other clinical factors before disposition decisions.',6);
    case 'hfa-peff':
      return hfaPeff(v);
    default:
      throw new Error('Unknown calculator');
  }
}

function hfaPeff(v) {
  const has = key => v[key] != null && v[key] !== '';
  const above = (key, n) => has(key) && v[key] > n;
  const atLeast = (key, n) => has(key) && v[key] >= n;
  const below = (key, n) => has(key) && v[key] < n;
  const between = (key,a,b) => has(key) && v[key]>=a && v[key]<=b;
  const domains = [
    {label:'Functional', keys:['septal','lateral','ee','tr','pasp','gls'], criteria:[
      ['Age-adjusted low septal e′',below('septal',v.age>=75?5:7),2],
      ['Age-adjusted low lateral e′',below('lateral',v.age>=75?7:10),2],
      ['E/e′ ≥15',atLeast('ee',15),2],['TR velocity >2.8 m/s or PASP >35 mmHg',above('tr',2.8)||above('pasp',35),2],
      ['E/e′ ≥9 and <15',atLeast('ee',9)&&below('ee',15),1],['Absolute GLS <16%',below('gls',16),1]]},
    {label:'Morphological', keys:['lavi','lvmi','rwt','wall'], criteria:[
      ['LAVI above rhythm-specific major threshold',above('lavi',v.af?40:34),2],
      ['LVMI ≥149 (male) / ≥122 (female) and RWT >0.42',atLeast('lvmi',v.female?122:149)&&above('rwt',.42),2],
      ['LAVI in minor range',between('lavi',v.af?34:29,v.af?40:34),1],
      ['LVMI >115 (male) / >95 (female)',above('lvmi',v.female?95:115),1],
      ['RWT >0.42',above('rwt',.42),1],['Wall thickness ≥12 mm',atLeast('wall',12),1]]},
    {label:'Biomarker',keys:['nt','bnp'],criteria:[
      ['NT-proBNP above major threshold',above('nt',v.af?660:220),2],
      ['BNP above major threshold',above('bnp',v.af?240:80),2],
      ['NT-proBNP in minor range',between('nt',v.af?365:125,v.af?660:220),1],
      ['BNP in minor range',between('bnp',v.af?105:35,v.af?240:80),1]]}
  ];
  const rows=domains.map(d=>{
    const matched=d.criteria.filter(c=>c[1]);
    return {label:d.label,points:Math.max(0,...matched.map(c=>c[2])), explanation:matched.map(c=>c[0]).join('; ') || 'No criterion documented',missing:d.keys.filter(k=>!has(k) && !(k==='tr'&&has('pasp')) && !(k==='pasp'&&has('tr')))};
  });
  const score=rows.reduce((sum,r)=>sum+r.points,0);
  // BNP and NT-proBNP are alternatives. A single measured peptide is sufficient.
  const incomplete=rows.some((r,i)=>r.points<2 && (i===2 ? !has('nt')&&!has('bnp') : r.missing.length>0));
  return {score,maximum:6,rows,category:score>=5?'Findings support HFpEF':incomplete?'Incomplete assessment':score>=2?'Intermediate score':'HFpEF unlikely',
    detail:incomplete?'Minimum documented score. Missing measurements can raise the result; complete the assessment before using a low score to exclude HFpEF.':
      score>=5?'In the appropriate clinical setting, this resting score supports HFpEF.':score>=2?'Proceed to functional testing within the HFA–PEFF pathway.':'Investigate alternative causes in the appropriate clinical setting.',
    incomplete};
}
