/* Arithmetic only. No drug dose is inferred from article text. */
function calculateDrugDose({low, high=low, weight, perKg, unit, time, concentration, concentrationUnit}) {
  const positive = x => typeof x==='number' && Number.isFinite(x) && x>0;
  if(!positive(low)||!positive(high)||high<low) throw Error('dose');
  if(!['mg','mcg','units'].includes(unit)||!['dose','hour','minute'].includes(time)) throw Error('unit');
  if(perKg && !positive(weight)) throw Error('weight');
  const total=[low,high].map(x=>x*(perKg?weight:1)*(time==='minute'?60:1));
  let volume=null;
  if(concentration!==null && concentration!==undefined){
    if(!positive(concentration)) throw Error('concentration');
    if(!['mg','mcg','units'].includes(concentrationUnit) || (unit==='units')!==(concentrationUnit==='units')) throw Error('incompatible');
    const factors={mg:1,mcg:0.001,units:1};
    volume=total.map(x=>x*factors[unit]/factors[concentrationUnit]/concentration);
  }
  if([...total,...(volume||[])].some(x=>!Number.isFinite(x)||x<=0)) throw Error('range');
  return {total,volume,perHour:time!=='dose'};
}
if(typeof module!=='undefined') module.exports={calculateDrugDose};
if(typeof document!=='undefined') document.querySelectorAll('.dose-calculator').forEach(root=>{
  const ru=root.dataset.language==='ru';
  const t=(en,rus)=>ru?rus:en;
  const units={mg:t('mg','мг'),mcg:t('mcg','мкг'),units:t('units','ЕД')};
  let regimens=[];try{regimens=JSON.parse(root.dataset.regimens).filter(x=>x&&x.label);}catch{}
  const options=(values)=>values.map(([value,label])=>'<option value="'+value+'">'+label+'</option>').join('');
  const unitOptions=options(Object.entries(units));
  const numeric=(id,label,extra='')=>'<label>'+label+'<input id="dose-'+id+'" type="text" inputmode="decimal" autocomplete="off" '+extra+'></label>';
  root.innerHTML='<div class="dose-form"><div class="dose-inputs">'+
    '<label class="dose-wide">'+t('Regimen','Режим')+'<select id="dose-regimen"><option value="">'+t('Manual calculation','Ручной расчёт')+'</option></select></label>'+
    '<label>'+t('Dose basis','Основа дозирования')+'<select id="dose-basis">'+options([['kg',t('Per kg','На кг')],['fixed',t('Fixed dose','Фиксированная доза')]])+'</select></label>'+
    numeric('weight',t('Weight, kg','Масса, кг'))+
    numeric('low',t('Dose / lower end','Доза / нижняя граница'))+numeric('high',t('Upper end (optional)','Верхняя граница (необязательно)'))+
    '<label>'+t('Dose unit','Единица дозы')+'<select id="dose-unit">'+unitOptions+'</select></label>'+
    '<label>'+t('Time basis','Время введения')+'<select id="dose-time">'+options([['dose',t('Single dose','Разовая доза')],['hour',t('Per hour','В час')],['minute',t('Per minute','В минуту')]])+'</select></label>'+
    numeric('concentration',t('Final concentration (optional)','Конечная концентрация (необязательно)'))+
    '<label>'+t('Concentration unit','Единица концентрации')+'<select id="dose-concentration-unit">'+options(Object.entries(units).map(([v,l])=>[v,l+t('/mL','/мл')]))+'</select></label>'+
    '<div class="dose-wide"><button class="dose-reset" type="button">'+t('Clear values','Очистить значения')+'</button></div></div>'+
    '<div class="dose-result" role="status" aria-live="polite" aria-atomic="true"></div></div><p class="dose-note"></p><a class="dose-source" hidden></a><p class="dose-caution">'+t('Converts the entered dose into an amount and volume. It does not select a dose, check patient eligibility or apply maximum-dose limits. Verify the regimen, route, units and final concentration.','Пересчитывает введённую дозу в количество и объём. Не подбирает дозу, не проверяет показания и не применяет ограничения максимальной дозы. Проверьте режим, путь введения, единицы и конечную концентрацию.')+'</p>';
  const get=id=>root.querySelector('#dose-'+id);
  const fields=['weight','low','high','unit','basis','time','concentration','concentration-unit'];
  const result=root.querySelector('.dose-result'),note=root.querySelector('.dose-note'),source=root.querySelector('.dose-source');
  regimens.forEach((r,i)=>{const option=document.createElement('option');option.value=String(i);option.textContent=r.label;get('regimen').append(option);});
  const number=value=>{const s=String(value).trim().replace(',','.');return /^(?:\d+(?:\.\d*)?|\.\d+)$/.test(s)?Number(s):NaN;};
  const fmt=n=>new Intl.NumberFormat(ru?'ru-RU':'en-US',{maximumSignificantDigits:6,useGrouping:false}).format(n);
  const range=values=>values[0]===values[1]?fmt(values[0]):fmt(values[0])+'–'+fmt(values[1]);
  function render(){
    const perKg=get('basis').value==='kg'; get('weight').disabled=!perKg;
    const doseUnit=units[get('unit').value];
    const basis=doseUnit+(perKg?t('/kg','/кг'):'')+(get('time').value==='minute'?t('/min','/мин'):get('time').value==='hour'?t('/h','/ч'):'');
    if(!get('low').value.trim() || (perKg&&!get('weight').value.trim())){result.textContent=t('Enter the dose and, for weight-based dosing, the patient’s weight.','Введите дозу и, при расчёте на кг, массу пациента.');return;}
    try{
      const low=number(get('low').value),high=get('high').value.trim()?number(get('high').value):low;
      const concentration=get('concentration').value.trim()?number(get('concentration').value):null;
      const output=calculateDrugDose({low,high,weight:number(get('weight').value),perKg,unit:get('unit').value,time:get('time').value,concentration,concentrationUnit:get('concentration-unit').value});
      const suffix=output.perHour?t('/h','/ч'):'';
      result.innerHTML='<span class="dose-result-label">'+t('Calculated amount','Результат расчёта')+'</span><strong>'+range(output.total)+' '+doseUnit+suffix+'</strong>'+(output.volume?'<strong class="dose-volume">'+range(output.volume)+' '+t('mL','мл')+suffix+'</strong>':'<p>'+t('Enter a concentration to calculate volume.','Введите концентрацию для расчёта объёма.')+'</p>')+'<p>'+range([low,high])+' '+basis+(perKg?' × '+fmt(number(get('weight').value))+' '+t('kg','кг'):'')+(get('time').value==='minute'?' × 60':'')+'</p><p>'+t('Rounded to 6 significant digits.','Округлено до 6 значащих цифр.')+'</p>';
    }catch(error){
      const messages={dose:t('Enter a positive dose; the upper end must not be below the lower end.','Введите положительную дозу; верхняя граница должна быть не ниже нижней.'),weight:t('Enter a positive weight in kg.','Введите положительную массу в кг.'),concentration:t('Enter a positive final concentration.','Введите положительную конечную концентрацию.'),incompatible:t('Units cannot be converted to mg or mcg. Match the dose and concentration units.','ЕД нельзя перевести в мг или мкг. Согласуйте единицы дозы и концентрации.'),unit:t('Choose valid dose units and time basis.','Выберите допустимые единицы и время.'),range:t('Values are outside the calculable range.','Значения выходят за пределы вычислимого диапазона.')};
      result.innerHTML='<p class="dose-error"></p>';result.firstChild.textContent=messages[error.message]||t('Check the entered values.','Проверьте введённые значения.');
    }
  }
  function selectRegimen(){
    const r=get('regimen').value===''?null:regimens[Number(get('regimen').value)];
    get('low').value=r?.dose_min??'';get('high').value=r?.dose_max??'';
    get('unit').value=r?.dose_unit||'mg';get('basis').value=r?.per_kg===false?'fixed':'kg';get('time').value=r?.time||'dose';
    get('concentration').value=r?.concentration??'';get('concentration-unit').value=r?.concentration_unit||'mg';
    ['low','high'].forEach(id=>get(id).readOnly=!!r);
    ['unit','basis','time'].forEach(id=>get(id).disabled=!!r);
    note.textContent=r?.notes||'';source.hidden=true;source.removeAttribute('href');
    if(r?.source){try{const u=new URL(r.source);if(['http:','https:'].includes(u.protocol)){source.href=u.href;source.textContent=t('Regimen source','Источник режима');source.hidden=false;}}catch{}}
    render();
  }
  fields.forEach(id=>get(id).addEventListener('input',render));
  get('regimen').addEventListener('change',selectRegimen);
  root.querySelector('.dose-reset').addEventListener('click',()=>{get('regimen').value='';get('weight').value='';selectRegimen();});
  selectRegimen();
});
