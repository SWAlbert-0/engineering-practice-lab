/* Verify the redesigned entry points and review navigation against real APIs. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const playwright=require(process.env.LAB_PLAYWRIGHT||'playwright');
const browserName=process.env.LAB_BROWSER||'chromium';
const base=process.env.LAB_TEST_URL||'http://127.0.0.1:8765';
const artifact='/tmp/lab-browser-artifacts';
async function api(path){const r=await fetch(base+path);const body=await r.json();assert(r.ok,JSON.stringify(body));return body;}
async function waitFor(fn){for(let n=0;n<160;n++){const value=await fn();if(value)return value;await new Promise(r=>setTimeout(r,250));}throw Error('Design flow did not finish');}
(async()=>{
 const browser=await playwright[browserName].launch({headless:true,executablePath:process.env.LAB_BROWSER_EXECUTABLE||undefined,args:browserName==='chromium'?['--no-sandbox']:[]});
 const page=await browser.newPage({viewport:{width:1536,height:1040}});const errors=[];page.on('pageerror',e=>errors.push(e.message));fs.mkdirSync(artifact,{recursive:true});
 try{
  await page.goto(base+'/demos/02-process-rag/#overview');await page.locator('#search-form').waitFor();
  const material=await page.locator('.material-tabs a').nth(1).textContent();await page.locator('.material-tabs a').nth(1).click();await page.waitForFunction(m=>decodeURIComponent(location.hash).includes('material='+m),material);
  await page.waitForFunction(m=>[...document.querySelectorAll('.document-card .material-tag')].length>0&&[...document.querySelectorAll('.document-card .material-tag')].every(n=>n.textContent===m),material);
  await page.locator('.material-tabs a').first().click();await page.waitForFunction(()=>document.querySelector('.material-tabs a.active')?.textContent==='全部');
  await page.screenshot({path:artifact+'/d01-design-home-desktop.png',fullPage:true});
  await page.getByRole('button',{name:'量具校准',exact:true}).click();assert.equal(await page.locator('#rag-query').inputValue(),'量具校准');await page.getByRole('button',{name:'检索资料',exact:true}).click();await page.locator('.source-card').first().waitFor();assert((await page.locator('#rag-view').textContent()).includes('量具校准'));
  await page.setViewportSize({width:390,height:844});await page.goto(base+'/demos/02-process-rag/#overview');await page.locator('#search-form').waitFor();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:artifact+'/d01-design-home-mobile.png',fullPage:true});

  await page.setViewportSize({width:1536,height:1040});await page.goto(base+'/demos/05-requirements/#overview');await page.locator('#import-form').waitFor();await page.screenshot({path:artifact+'/d09-design-home-desktop.png',fullPage:true});
  const title='首页入口与用例目录验收';const source='用户只能查看本人订单。\n用户可以取消尚未发货的本人订单。\n管理员可以查看审计记录。';
  await page.getByLabel('需求名称',{exact:true}).fill(title);await page.locator('#source-file').setInputFiles({name:'review.md',mimeType:'text/markdown',buffer:Buffer.from(source)});await page.waitForFunction(()=>document.querySelector('#import-form [name=text]').value.includes('取消尚未发货'));
  assert.equal(await page.locator('#file-name').textContent(),'review.md');await page.getByRole('button',{name:'保存需求原文',exact:true}).click();await page.locator('#analyze-form').waitFor();const docId=page.url().split('#document/')[1];
  await page.getByRole('button',{name:'分析并生成用例集',exact:true}).click();const suite=await waitFor(async()=>(await api('/api/requirements-workspace/workspace')).sets.find(s=>s.document_id===docId));
  await page.goto(base+'/demos/05-requirements/#suite/'+suite.id);await page.locator('.outline-case').nth(1).waitFor();const first=await page.locator('.case-id').textContent();
  await page.getByLabel('用例标题',{exact:true}).fill('目录切换应先保存当前用例');await page.locator('.outline-case').nth(1).click();await page.waitForFunction(id=>document.querySelector('.case-id')?.textContent!==id,first);assert.notEqual(await page.locator('.case-id').textContent(),first);
  await page.locator('.outline-case').first().click();await page.waitForFunction(id=>document.querySelector('.case-id')?.textContent===id,first);assert.equal(await page.getByLabel('用例标题',{exact:true}).inputValue(),'目录切换应先保存当前用例');
  await page.getByRole('button',{name:'选择全部',exact:true}).click();const count=await page.locator('[name=review-case]').count();assert.equal(await page.locator('[name=review-case]:checked').count(),count);assert((await page.locator('#review-selected-count').textContent()).includes(String(count)));await page.getByRole('button',{name:'选择全部',exact:true}).click();assert.equal(await page.locator('[name=review-case]:checked').count(),0);
  await page.locator('#toast').waitFor({state:'hidden'});await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:artifact+'/d09-design-review-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:artifact+'/d09-design-review-mobile.png',fullPage:true});
  await page.goto(base+'/demos/05-requirements/#overview');await page.locator('#import-form').waitFor();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:artifact+'/d09-design-home-mobile.png',fullPage:true});assert.deepEqual(errors,[]);
  console.log('PASS: redesigned D01 homepage search/material filters, D09 homepage file import/case outline/autosave/select-all, desktop and 390px layouts');
 }catch(error){await page.screenshot({path:artifact+'/design-failure.png',fullPage:true});throw error;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
