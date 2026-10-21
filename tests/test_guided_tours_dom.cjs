/* DOM integration with real local APIs. This does not assert browser layout. */
'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs'),{webcrypto}=require('node:crypto');
const {JSDOM,VirtualConsole,ResourceLoader}=require(process.env.LAB_JSDOM||path.resolve('data/tour-test-node/node_modules/jsdom'));
const base=process.env.LAB_TEST_URL||'http://127.0.0.1:8766';
const art=path.resolve('data/browser-artifacts/guided-tours-dom');fs.mkdirSync(art,{recursive:true});
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function exercise(folder,id){
 const errors=[],downloads=[],responses=[];let dom,failPost=true,failExport=true;
 const vc=new VirtualConsole();vc.on('jsdomError',e=>{if(!e.message.startsWith('Not implemented: navigation'))errors.push(e.message);});
 const setup=w=>{
  w.fetch=(url,options)=>{const target=new URL(url,w.location.href);if(failPost&&options?.method==='POST'){failPost=false;return Promise.resolve(new Response(JSON.stringify({error:'Integration fixture: temporary failure'}),{status:503,headers:{'Content-Type':'application/json'}}));}if(failExport&&target.pathname.endsWith('/export')){failExport=false;return Promise.resolve(new Response('{}',{status:503}));}return fetch(target,options);};w.TextEncoder=TextEncoder;w.TextDecoder=TextDecoder;w.structuredClone=structuredClone;w.confirm=()=>true;
  Object.defineProperty(w.crypto,'subtle',{value:webcrypto.subtle});
  w.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});w.scrollTo=()=>{};w.scrollBy=()=>{};
  w.HTMLElement.prototype.scrollIntoView=function(){};w.HTMLElement.prototype.scrollBy=function(){};
  w.HTMLElement.prototype.getBoundingClientRect=function(){return {left:100,right:500,top:300,bottom:350,width:400,height:50,x:100,y:300};};
  w.HTMLElement.prototype.getClientRects=function(){return this.hidden?[]:[this.getBoundingClientRect()];};
  w.HTMLDialogElement.prototype.show=function(){this.open=true;};w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){if(this.open){this.open=false;this.dispatchEvent(new w.Event('close'));}};
  const files=new WeakMap();Object.defineProperty(w.HTMLInputElement.prototype,'files',{get(){return files.get(this)||[];},set(v){files.set(this,v);},configurable:true});
  w.DataTransfer=class{constructor(){this.files=[];this.items={add:f=>this.files.push(f)};}};
  w.FormData=class{constructor(form){this.values=[];if(form)for(const el of form.elements){if(!el.name||el.disabled||el.matches('button'))continue;if(['checkbox','radio'].includes(el.type)&&!el.checked)continue;if(el.type==='file'){this.values.push([el.name,el.files[0]||new w.File([],'')]);continue;}if(el.multiple){for(const option of el.selectedOptions)this.values.push([el.name,option.value]);}else this.values.push([el.name,el.value]);}}get(name){return this.values.find(x=>x[0]===name)?.[1]??null;}getAll(name){return this.values.filter(x=>x[0]===name).map(x=>x[1]);}has(name){return this.values.some(x=>x[0]===name);}entries(){return this.values[Symbol.iterator]();}[Symbol.iterator](){return this.entries();}};
  w.URL.createObjectURL=blob=>{const url=URL.createObjectURL(blob);downloads.push({url,blob});return url;};w.URL.revokeObjectURL=URL.revokeObjectURL;
  const click=w.HTMLAnchorElement.prototype.click;w.HTMLAnchorElement.prototype.click=function(){if(this.href.startsWith('blob:'))return;return click.call(this);};
  w.addEventListener('lab:response',e=>{if(e.detail.body)responses.push(e.detail);});
 };
 try{
  class LocalResources extends ResourceLoader{fetch(url){const name=new URL(url).pathname;const result=Promise.resolve(fs.readFileSync(path.resolve('.'+name)));result.abort=()=>{};return result;}}
  dom=new JSDOM(fs.readFileSync('demos/'+folder+'/index.html','utf8'),{url:base+'/demos/'+folder+'/#overview',resources:new LocalResources(),runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse:setup});
  const w=dom.window,doc=w.document;
  const until=async fn=>{const end=Date.now()+90000;while(Date.now()<end){if(errors.length)throw Error(errors.join('\n'));const result=fn();if(result)return result;await delay(80);}throw Error('Timed out at '+doc.querySelector('.guided-tour-card')?.textContent);};
  await until(()=>doc.querySelector('[data-case-fill]'));
  doc.querySelector('[data-case-fill]').click();
  let actions=0,last='',reloadChecked=false,recoveries=0;
  while(actions++<120){
   await until(()=>{const c=doc.querySelector('.guided-tour-card');return c&&!c.hidden&&c.dataset.stage;});
   const c=w.LabGuidedTour.context,stage=c.run.stage;
   if(stage==='complete')break;
   const problem=doc.querySelector('.guided-tour-card .tour-problem');if(problem){assert(/Integration fixture|导出暂时失败/.test(problem.textContent),stage+': '+problem.textContent);assert(++recoveries<=2);doc.querySelector('[data-guided=retry]').click();await delay(180);continue;}
   if(stage!==last){console.log(id,stage);last=stage;}
   if(stage.startsWith('wait-')){await delay(600);continue;}
   const target=await until(()=>{const el=doc.querySelector('[data-guided-target="'+c.run.stage+'"]');const message=doc.querySelector('.guided-tour-card .tour-problem');if(message)throw Error(message.textContent);return el&&!el.disabled&&el;});
   assert(doc.querySelector('.guided-tour-shade')&&!doc.querySelector('.guided-tour-shade').hidden);
   const oldHash=w.location.hash;doc.querySelector('[data-nav]')?.dispatchEvent(new w.MouseEvent('click',{bubbles:true,cancelable:true}));assert.equal(w.location.hash,oldHash,'Masked navigation must be blocked');
   if(id==='D13'&&stage==='project'){const box=doc.querySelector('[name=outline_confirmed]');box.checked=true;}
   if(id==='D02'&&(stage.startsWith('deploy-form')||stage==='rollback'))doc.querySelector('#deploy-form [name=confirmed]').checked=true;
   const before=JSON.stringify(c.run),beforeCount=responses.length,beforeDownloads=downloads.length;
   if(!reloadChecked&&stage==='export'){const pause=doc.querySelector('[data-guided=exit]');pause.click();await until(()=>!c.run.active);await delay(80);doc.querySelector('[data-guided=resume]').click();await until(()=>c.run.active);await delay(120);reloadChecked=true;}
   // JSDOM does not share our synthetic FileList with its native validation.
   // Assert the supplied file, then leave native file validation to browser CI.
   if(target.form?.querySelector('input[type=file][required]')){assert(target.form.querySelector('input[type=file]').files.length);target.form.noValidate=true;}
   target.click();
   await until(()=>JSON.stringify(c.run)!==before||responses.length!==beforeCount||downloads.length!==beforeDownloads||doc.querySelector('.guided-tour-card .tour-problem'));
   await delay(180);
  }
  const c=w.LabGuidedTour.context;assert.equal(c.run.stage,'complete');assert.equal(errors.length,0);
  assert.equal(recoveries,2);assert(downloads.length>=1);const bundle=JSON.parse(await downloads.at(-1).blob.text());
  if(id==='D01'){assert.equal(bundle.version,2);assert(bundle.data.sources.some(s=>s.document_id===c.run.document));assert(bundle.reviews.some(r=>r.decision==='approved'));}
  if(id==='D02'){assert.notEqual(c.run.model1,c.run.model2);assert.equal(c.run.prediction.model_id,c.run.model1);assert.equal(bundle.id,c.run.model1);assert.equal(bundle.artifact.schema,'lab-linear-v1');}
  if(id==='D13'){assert.equal(downloads.length,3);assert.equal(bundle.schema,'d13-release-v1');assert.equal(bundle.version,2);assert.equal(c.run.evidence.length,6);}
  fs.writeFileSync(path.join(art,id+'-result.json'),JSON.stringify({run:c.run,downloads:downloads.length,writes:responses.length},null,2));
  console.log('PASS',id,'real service/DOM flow;',actions,'actions;',downloads.length,'downloads; no layout claim.');
 }catch(e){if(dom)fs.writeFileSync(path.join(art,id+'-failure.html'),dom.serialize());throw e;}finally{dom?.window.close();}
}
(async()=>{for(const [folder,id]of [['02-process-rag','D01'],['06-literature','D13'],['03-mlops','D02']])await exercise(folder,id);})().catch(e=>{console.error(e);process.exitCode=1;});
