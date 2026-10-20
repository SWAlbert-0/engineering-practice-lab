'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),pw=require(process.env.LAB_PLAYWRIGHT||'playwright');
const base=process.env.LAB_TEST_URL||'http://127.0.0.1:8765',art='/tmp/lab-browser-artifacts';
const projects=[['01-repair-agent','D11','overview','repositories'],['02-process-rag','D01','overview','upload'],['03-mlops','D02','overview','datasets'],['04-video-understanding','D12','studio','studio'],['05-requirements','D09','overview','import'],['06-literature','D13','overview','new']];
(async()=>{
 const name=process.env.LAB_BROWSER||'chromium',browser=await pw[name].launch({headless:true,executablePath:process.env.LAB_BROWSER_EXECUTABLE||undefined,args:name==='chromium'?['--no-sandbox']:[]});
 const ctx=await browser.newContext({viewport:{width:1440,height:1000}}),page=await ctx.newPage(),errors=[];let posts=0;
 page.on('pageerror',error=>errors.push(error.message));page.on('request',request=>{if(request.method()==='POST')posts++;});fs.mkdirSync(art,{recursive:true});
 if(process.env.LAB_TEST_FONT){const b64=fs.readFileSync(process.env.LAB_TEST_FONT).toString('base64');await ctx.addInitScript(font=>document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent='@font-face{font-family:GuideTest;src:url(data:font/otf;base64,'+font+')}body,.experience-guide,.research-desk-main h2{font-family:GuideTest,sans-serif!important}';document.head.append(s);}),b64);}
 const ready=async()=>page.waitForFunction(()=>{const view=document.querySelector('#workspace-view,#rag-view,#view');return view&&!view.inert&&view.getAttribute('aria-busy')!=='true'&&document.querySelector('#experience-guide');});
 const click=action=>page.locator('[data-experience="'+action+'"]').click();
 const shot=async label=>{await page.evaluate(()=>document.fonts.ready);await page.locator('#experience-guide').scrollIntoViewIfNeeded();await page.screenshot({path:art+'/'+label+'.png',fullPage:true});};
 try{
  for(const [folder,id,home,target] of projects){
   await page.setViewportSize({width:1440,height:1000});await page.goto(base+'/demos/'+folder+'/#'+home);await ready();
   const guide=page.locator('#experience-guide');assert(await guide.isVisible());assert((await guide.textContent()).includes('功能体验引导'));
   await click('start');assert((await guide.textContent()).includes('应该看到什么'));
   const count=posts;await click('go');await page.waitForFunction(expected=>location.hash==='#'+expected,target);await ready();await click('locate');await page.locator('.experience-target').first().waitFor();assert.equal(posts,count,'Guide must not execute business operations');
   await shot(id.toLowerCase()+'-experience-desktop');
   if(!await guide.locator('details').evaluate(el=>el.open))await guide.locator('summary').click();await guide.locator('[data-experience-step="2"]').click();assert((await guide.textContent()).includes('第 3 /'));
   await click('pause');await page.reload();await ready();assert((await guide.textContent()).includes('继续体验'));await click('start');assert((await guide.textContent()).includes('第 3 /'));assert((await guide.textContent()).includes('已自行确认 0 步'),'Opening routes must not manufacture completion');
   await click('pause');await click('reset');assert((await guide.textContent()).includes('第 1 /'));await click('next');assert((await guide.textContent()).includes('已自行确认 1 步'));
   await page.setViewportSize({width:390,height:844});await shot(id.toLowerCase()+'-experience-mobile');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Mobile overflow '+id);
   await click('pause');assert.equal(await page.locator('.experience-target').count(),0);
  }
  // Follow the actual D11 tutorial into one real offline task, not just route clicks.
  await page.setViewportSize({width:1440,height:1000});await page.goto(base+'/demos/01-repair-agent/#overview');await ready();await click('reset');await click('next');await click('go');await page.waitForSelector('#task-form');
  await page.locator('#task-form [name="title"]').fill('功能教学引导 / 失败后修订');await page.locator('#task-form [name="candidate"]').selectOption('progressive');await page.locator('#task-form [name="max_attempts"]').selectOption('2');await page.locator('#task-form button[type="submit"]').click();
  await page.waitForFunction(()=>location.hash.startsWith('#task/'));const id=await page.evaluate(()=>location.hash.slice(1).split('/')[1].split('?')[0]);
  for(let i=0;i<180;i++){const r=await fetch(base+'/api/repair-workspace/tasks/'+id),task=await r.json();if(task.status==='succeeded'){assert.equal(task.attempts.length,2);break;}if(i===179)throw Error('Tutorial task did not finish');await new Promise(resolve=>setTimeout(resolve,200));}
  await click('next');await page.waitForFunction(id=>document.querySelector('[data-experience="go"]').getAttribute('href').startsWith('#task/'+id),id);await click('go');await ready();await page.getByRole('link',{name:'测试变化',exact:true}).click();await page.locator('.test-changes').waitFor();await shot('d11-experience-actual-task');
  assert.deepEqual(errors,[]);console.log('PASS six project experience guides: visible entry, actual routes and highlights, no automatic business operations, manual progress/reload/reset, 390px layouts and real D11 two-round task.');
 }catch(error){await page.screenshot({path:art+'/experience-failure.png',fullPage:true});fs.writeFileSync(art+'/experience-failure.html',await page.content());throw error;}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
