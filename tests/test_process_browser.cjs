/* Real browser acceptance of D01 against a running offline service. */
'use strict';
const assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const {chromium}=require(process.env.LAB_PLAYWRIGHT||'playwright');
const base=process.env.LAB_TEST_URL||'http://127.0.0.1:8765';
async function api(p,body){const r=await fetch(base+'/api/process/'+p,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const x=await r.json();assert(r.ok,JSON.stringify(x));return x;}
async function waitFor(fn){for(let i=0;i<180;i++){const x=await fn();if(x)return x;await new Promise(r=>setTimeout(r,300));}throw Error('Timed out waiting for state');}
(async()=>{
 if(process.argv.includes('--check-persistence')){const p=JSON.parse(fs.readFileSync('/tmp/lab-process-e2e.json'));const d=await api('drafts/'+p.draft);assert.equal(d.version,2);assert(d.stale);assert((await api('documents/'+p.doc)).document.deleted);console.log('D01 persistence verified after container restart.');return;}
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});const page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const artifact='/tmp/lab-browser-artifacts';fs.mkdirSync(artifact,{recursive:true});
 try{
  await require('./test_process_bootstrap.cjs')(browser,base,artifact);
  const go=async(route)=>{await page.goto(base+'/demos/02-process-rag/#'+route);await page.locator('#rag-view h1').waitFor();};
  await go('upload');await page.getByLabel('资料名称',{exact:true}).fill('浏览器验收工艺卡');await page.getByLabel('适用材料',{exact:true}).fill('铌钛合金');
  await page.locator('input[type=file]').setInputFiles({name:'acceptance.md',mimeType:'text/markdown',buffer:Buffer.from('铌钛合金 QXTRACER 声发射检测规范。检验前确认量具校准状态，检验后记录批次与结果。')});
  await page.getByRole('button',{name:'上传并建立索引',exact:true}).click();await page.waitForURL(/#jobs$/);
  const doc=await waitFor(async()=>{const s=await api('workspace');return s.documents.find(d=>d.title==='浏览器验收工艺卡'&&d.status==='ready');});
  await go('search');await page.locator('[name=query]').fill('QXTRACER');await page.getByLabel('材料范围').selectOption('铌钛合金');await page.getByRole('button',{name:'检索资料',exact:true}).click();
  await page.getByRole('heading',{name:'QXTRACER',exact:true}).waitFor();assert((await page.locator('.source-text').first().textContent()).includes('QXTRACER'));
  await page.locator('.source-card h3 a').first().click();await page.locator('.requested-page mark').waitFor();assert((await page.locator('.requested-page mark').textContent()).includes('QXTRACER'));
  await go('search');await page.locator('[name=query]').fill('QXTRACER');await page.getByRole('button',{name:'检索资料',exact:true}).click();await page.locator('#generate-form').waitFor();await page.getByRole('button',{name:'生成待审核草案',exact:true}).click();await page.waitForURL(/#jobs$/);
  const draft=await waitFor(async()=>{const s=await api('workspace');return s.drafts.find(d=>d.title==='QXTRACER');});
  await go('draft/'+draft.id);await page.locator('#review-form [name=actor]').fill('浏览器验收记录人');await page.getByRole('button',{name:'确认核对通过',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#review-form .form-message').textContent.includes('逐工序'));
  for(const box of await page.locator('#review-form [name=confirmed]').all())await box.check();await page.getByRole('button',{name:'确认核对通过',exact:true}).click();await page.locator('.draft-bar .state-approved').waitFor();
  const operation=page.locator('[name=operation]').first();await operation.fill((await operation.inputValue())+' 人工复查适用范围。');await page.getByRole('button',{name:'保存为新版本',exact:true}).click();await page.waitForURL(/version=2$/);await page.locator('.draft-bar .state-pending').waitFor();
  const downloadPromise=page.waitForEvent('download');await page.getByRole('link',{name:'导出 JSON',exact:true}).click();const dl=await downloadPromise;const exported=JSON.parse(fs.readFileSync(await dl.path(),'utf8'));assert.equal(exported.version,2);assert(exported.data.sources.some(s=>s.document_id===doc.id));
  await page.locator('#process-toast').waitFor({state:'hidden'});await page.screenshot({path:artifact+'/d01-draft-desktop.png',fullPage:true});
  const other=await browser.newContext();const second=await other.newPage();await second.goto(base+'/demos/02-process-rag/#draft/'+draft.id);await second.getByRole('heading',{name:'QXTRACER',exact:true}).waitFor();assert((await second.locator('.draft-bar').textContent()).includes('历史版本'));await other.close();
  await go('document/'+doc.id);await page.locator('.replace-document summary').click();await page.locator('.replace-document input[type=file]').setInputFiles({name:'revision.txt',mimeType:'text/plain',buffer:Buffer.from('铌钛合金新版本包装检查规范。保留批次更新记录。')});await page.getByRole('button',{name:'上传新版本并重建索引'}).click();await page.waitForURL(/#jobs$/);
  await waitFor(async()=>(await api('workspace')).documents.find(d=>d.id===doc.id&&d.version===2));
  await go('draft/'+draft.id);assert.notEqual(await page.locator('#review-form fieldset').getAttribute('disabled'),null);assert((await page.locator('.draft-bar').textContent()).includes('来源已变化'));
  await go('document/'+doc.id);await page.getByRole('button',{name:'从有效资料库删除'}).click();await page.getByRole('button',{name:'确认删除',exact:true}).click();await page.waitForURL(/#documents$/);assert((await api('search',{query:'QXTRACER'})).refused);
  await go('overview');await page.locator('#process-toast').waitFor({state:'hidden'});await page.screenshot({path:artifact+'/d01-overview-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});for(const r of ['overview','documents','search','history','drafts','jobs','settings','guide']){await go(r);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Horizontal overflow on '+r);}
  await page.locator('#process-toast').waitFor({state:'hidden'});await page.screenshot({path:artifact+'/d01-mobile.png',fullPage:true});await page.getByRole('button',{name:'选题介绍',exact:true}).click();assert(await page.locator('#topic-dialog').isVisible());await page.keyboard.press('Escape');assert(!(await page.locator('#topic-dialog').isVisible()));
  await go('draft/'+draft.id);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Mobile draft overflow');await page.screenshot({path:artifact+'/d01-draft-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);fs.writeFileSync('/tmp/lab-process-e2e.json',JSON.stringify({doc:doc.id,draft:draft.id}));console.log('PASS: D01 real browser upload/index/search/source/draft/review/edit/export/cross-browser/replace/delete/mobile/dialog flow');
 }catch(error){fs.writeFileSync(artifact+'/failure.html',await page.content());await page.screenshot({path:artifact+'/failure.png',fullPage:true});throw error;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
