import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {calculate, validate} from '../calculators/engine.mjs';
const definitions=JSON.parse(readFileSync(new URL('../calculators/data.json',import.meta.url)));
const zero=slug=>Object.fromEntries(definitions.find(d=>d.slug===slug).fields.map(f=>[f.id,f.optional?null:f.options?0:f.min]));
const score=(slug,v)=>calculate(slug,v).score;
let v={...zero('cha2ds2-vasc'),age:64};
assert.equal(score('cha2ds2-vasc',v),0);
assert.equal(score('cha2ds2-vasc',{...v,age:65}),1);
assert.equal(score('cha2ds2-vasc',{...v,age:74}),1);
assert.equal(score('cha2ds2-vasc',{...v,age:75,female:1,hf:1,htn:1,diabetes:1,stroke:1,vascular:1}),9);
v={age:60,bmi:30,af:0,htn2:0,pasp:35,ee:9};
assert.equal(score('h2fpef',v),0);
assert.equal(score('h2fpef',{age:61,bmi:30.1,af:1,htn2:1,pasp:35.1,ee:9.1}),9);
assert.match(calculate('h2fpef',{...v,bmi:31}).category,/Intermediate/);
assert.match(calculate('h2fpef',{...v,bmi:31,af:1,age:61}).category,/High/);
v={age:65,hr:74,vte:0,surgery:0,cancer:0,pain:0,hemoptysis:0,signs:0};
for(const slug of ['revised-geneva','simplified-geneva']) {
 const simple=slug==='simplified-geneva';
 assert.equal(score(slug,v),0);
 assert.equal(score(slug,{...v,hr:75}),simple?1:3);
 assert.equal(score(slug,{...v,hr:94}),simple?1:3);
 assert.equal(score(slug,{...v,hr:95}),simple?2:5);
 assert.equal(score(slug,{age:66,hr:95,vte:1,surgery:1,cancer:1,pain:1,hemoptysis:1,signs:1}),simple?9:22);
}
v={age:65,female:1,cancer:0,hf:0,lung:0,hr:109,sbp:100,rr:29,temp:36,mental:0,sat:90};
for(const [age,category] of [[65,'I'],[66,'II'],[85,'II'],[86,'III'],[105,'III'],[106,'IV'],[125,'IV'],[126,'V']]) {
 assert.equal(calculate('pesi',{...v,age}).category.split(' · ')[0],'Class '+category);
}
assert.equal(score('pesi',{...v,age:80,female:0,cancer:1,hf:1,lung:1,hr:110,sbp:99,rr:30,temp:35.9,mental:1,sat:89}),310);
v={age:80,cancer:0,cardiopulmonary:0,hr:109,sbp:100,sat:90};
assert.equal(score('spesi',v),0);
assert.equal(score('spesi',{age:81,cancer:1,cardiopulmonary:1,hr:110,sbp:99,sat:89}),6);
const aba=calculate('hfpef-aba',{age:70,bmi:30,af:0});
assert.ok(Math.abs(aba.logOdds-0.645199)<1e-9);
assert.ok(Math.abs(aba.score-65.592775658)<0.00001);
v={age:74,female:0,af:0,septal:7,lateral:10,ee:8,tr:2.8,gls:16,lavi:28,lvmi:115,rwt:.42,wall:11,nt:124,bnp:null};
assert.equal(score('hfa-peff',v),0);
assert.equal(calculate('hfa-peff',v).incomplete,false);
assert.equal(score('hfa-peff',{...v,septal:6.9}),2);
assert.equal(score('hfa-peff',{...v,age:75,septal:6.9}),0);
assert.equal(score('hfa-peff',{...v,ee:14.9}),1);
assert.equal(score('hfa-peff',{...v,ee:15}),2);
assert.equal(score('hfa-peff',{...v,lavi:34}),1);
assert.equal(score('hfa-peff',{...v,lavi:34.1}),2);
assert.equal(score('hfa-peff',{...v,af:1,lavi:40,nt:660}),2);
assert.equal(score('hfa-peff',{...v,af:1,lavi:40.1,nt:660.1}),4);
assert.equal(score('hfa-peff',{...v,lvmi:149,rwt:.43}),2);
assert.equal(score('hfa-peff',{...v,female:1,lvmi:122,rwt:.43}),2);
assert.equal(score('hfa-peff',{...v,ee:15,septal:4,tr:3,lavi:50,lvmi:160,rwt:.5,nt:1000,bnp:500}),6);
assert.equal(calculate('hfa-peff',{...v,septal:null}).incomplete,true);
assert.equal(score('hfa-peff',{...zero('hfa-peff'),ee:15}),2);
for(const definition of definitions) {
 assert.notEqual(validate(definition,{}),'');
 const values=zero(definition.slug);
 if(definition.slug==='hfa-peff') values.ee=8;
 assert.equal(validate(definition,values),'');
 if (definition.slug==='coapt') {
  assert.notEqual(validate(definition,{...values,egfr:2}),'');
  assert.notEqual(validate(definition,{...values,tr:4}),'');
  continue;
 }
 assert.notEqual(validate(definition,{...values,age:-1}),'');
 assert.notEqual(validate(definition,{...values,age:NaN}),'');
 assert.notEqual(validate(definition,{...values,age:60.5}),'');
}
assert.notEqual(validate(definitions.find(d=>d.slug==='hfpef-aba'),{age:70,bmi:30,af:null}),'');
console.log('Passed calculator threshold, domain, probability and validation checks.');

// Exercise every achievable H2FPEF total and its nomogram estimate.
const estimates=['<20%','≈23%','≈39%','≈56%','≈72%','≈83%','≈91%','≈95%','>95%','>95%'];
const seen=new Set();
for(let mask=0;mask<64;mask++){
 const result=calculate('h2fpef',{bmi:mask&1?31:30,af:mask&2?1:0,age:mask&4?61:60,htn2:mask&8?1:0,pasp:mask&16?36:35,ee:mask&32?10:9});
 assert.equal(result.estimatedProbability,estimates[result.score]);
 assert.equal(result.maximum,9);
 assert.equal(result.probability,undefined);
 seen.add(result.score);
}
assert.equal(seen.size,10);
console.log('Passed all H2FPEF probability conversions.');

// Check all baseline combinations against the source calculator's grouped rates.
const coapt=definitions.find(d=>d.slug==='coapt');
const referenceMedical=[[23.3,27.9,37],[23.3,48.4,51.9],[20.8,41.6,51.7],[33.8,44.3,60.6],[40.8,55,65.7],[59.4,83.1,89.2],[61,62.5,78.2],[62.6,75.9,80.4],[72.7,84.2,91.2]];
const referenceTeer=[[11.5,19.5,24.8],[14.5,35.6,40],[26.2,22.5,34.8],[25,27.2,39],[27.9,27.2,37.5],[28.8,45.1,57.8],[42.5,45.7,55.4],[48.5,57.3,72],[49,67.4,70.4]];
const totals=new Set();
function checkCoapt(index,values){
 if(index<coapt.fields.length){
  const f=coapt.fields[index];
  for(const option of f.options) checkCoapt(index+1,{...values,[f.id]:option.value});
  return;
 }
 assert.equal(validate(coapt,values),'');
 const expected=values.copd+values.af+(values.nyha>=2?1:0)+values.egfr+values.lvef+values.lvesd+values.rvsp+(values.tr>=1?2:0);
 const result=calculate('coapt',values);
 assert.equal(result.score,expected);
 assert.equal(result.maximum,15);
 const group=expected<3?0:expected>9?8:expected-2;
 assert.deepEqual(result.outcomes.map(o=>o.medical),referenceMedical[group]);
 assert.deepEqual(result.outcomes.map(o=>o.teer),referenceTeer[group]);
 assert.equal(result.scoreGroup,expected<3?'0–2':expected>9?'≥10':String(expected));
 totals.add(expected);
}
checkCoapt(0,{});
assert.equal(totals.size,16);
console.log('Passed COAPT inputs, all 16 scores and both treatment outcome tables.');
