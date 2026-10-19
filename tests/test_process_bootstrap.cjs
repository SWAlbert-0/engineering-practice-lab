/* Upgrade compatibility and startup recovery, using the screenshot's exact URL. */
'use strict';
const assert=require('node:assert/strict');
module.exports=async function checkBootstrap(browser,base,artifact){
 const url=base+'/demos/02-process-rag/index.html';
 const context=await browser.newContext();const page=await context.newPage();
 const ready=()=>page.getByRole('heading',{name:'工艺资料工作台',exact:true}).waitFor();
 const entry='**/demos/02-process-rag/workspace.js?*';
 try{
  // Cached legacy product.js must never be requested by the new HTML.
  let legacyRequests=0;
  await page.route('**/demos/02-process-rag/product.js',route=>{legacyRequests++;return route.fulfill({contentType:'application/javascript',body:'const K=P;'});});
  await page.goto(url);await ready();assert.equal(legacyRequests,0);
  await page.unroute('**/demos/02-process-rag/product.js');

  // A failed script download leaves an actionable HTML page; retry recovers.
  await page.route(entry,route=>route.abort());await page.goto(url);
  await page.locator('#boot-error').waitFor();assert((await page.locator('#boot-error').textContent()).includes('页面文件未能下载'));
  assert(await page.getByRole('link',{name:'返回项目总览',exact:true}).isVisible());
  await page.screenshot({path:artifact+'/d01-loading-recovery.png',fullPage:true});
  await page.unroute(entry);await page.getByRole('button',{name:'重新加载',exact:true}).click();await ready();

  // Reproduce the old bundle's actual missing dependency, rather than assuming
  // a fresh browser can cover upgrades from the previous implementation.
  const startupErrors=[];page.on('pageerror',error=>startupErrors.push(error.message));
  await page.route(entry,route=>route.fulfill({contentType:'application/javascript',body:"'use strict';const K=P;"}));
  await page.goto(url);await page.locator('#boot-error').waitFor();
  assert(startupErrors.some(message=>message.includes('P is not defined')));
  assert((await page.locator('#boot-status').textContent()).includes('页面暂未能打开'));
  await page.unroute(entry);await page.getByRole('button',{name:'重新加载',exact:true}).click();await ready();

  const endpoint=base+'/api/process/workspace';
  for(const fault of ['old-server','wrong-shape','disconnected']){
   await page.route(endpoint,route=>fault==='disconnected'?route.abort():route.fulfill(fault==='old-server'?{status:404,contentType:'text/html',body:'<!doctype html><h1>Not found</h1>'}:{contentType:'application/json',body:'{"status":"ok"}'}));
   await page.goto(url);await page.locator('#process-error').waitFor();
   assert(await page.getByRole('heading',{name:'暂时无法读取资料库',exact:true}).isVisible());
   assert(await page.getByRole('link',{name:'资料目录',exact:true}).isVisible());
   const message=await page.locator('#process-error-message').textContent();
   assert(message.includes(fault==='disconnected'?'无法连接资料服务':'更新项目并重启服务'),message);
   await page.unroute(endpoint);await page.getByRole('button',{name:'重新读取',exact:true}).click();await ready();
  }
 }catch(error){await page.screenshot({path:artifact+'/bootstrap-failure.png',fullPage:true});throw error;}finally{await context.close();}
 const noJS=await browser.newContext({javaScriptEnabled:false});
 try{const page=await noJS.newPage();await page.goto(url);assert(await page.getByRole('heading',{name:'工艺资料工作区',exact:true}).isVisible());assert(await page.locator('noscript').isVisible());}finally{await noJS.close();}
 console.log('PASS: D01 exact index URL, legacy cache isolation, script failure, startup exception, API recovery and disabled JavaScript');
};
