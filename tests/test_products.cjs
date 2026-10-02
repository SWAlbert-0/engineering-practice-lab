/* Product flows tested with a minimal DOM adapter, real engine results, and
 * in-memory LocalStorage. Browser rendering is intentionally not simulated. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),read=p=>fs.readFileSync(path.join(root,p),'utf8');
const python=spawnSync(process.env.PYTHON || 'python',['-c',`import json,server
print(json.dumps({'repair':server.repair.run('boundary','correct'),'wrong':server.repair.run('boundary','wrong'),'rag':server.rag.search('铝合金薄壁精加工','铝合金'),'bad':server.mlops.run(.65,0,True),'unlabeled':server.mlops.run(.65,0,False)}))`],{cwd:root,encoding:'utf8'});
assert.equal(python.status,0,python.stderr);const results=JSON.parse(python.stdout),rendered=[];
class Node {
 constructor(){this.value='';this.innerHTML='';this.textContent='';this.hidden=false;this.listeners={};this.style={};this.classList={toggle(){}};}
 addEventListener(name,fn){this.listeners[name]=fn;}
 setAttribute(){} removeAttribute(){} focus(){this.focused=true;} close(){this.open=false;this.listeners.close?.();} showModal(){this.open=true;}
 querySelector(){return null;}
}
function setup(folder,store=new Map()){
 const elements=new Map(),events={},windowEvents={};let frame=null;
 const el=selector=>{if(!elements.has(selector))elements.set(selector,new Node());return elements.get(selector);};
 const document={body:new Node(),documentElement:{style:{setProperty(){}}},querySelector:selector=>selector==='iframe'?frame:el(selector),querySelectorAll:()=>[],addEventListener:(name,fn)=>{events[name]=fn;},createElement:()=>({click(){}})};
 const context=vm.createContext({document,location:{hash:'',origin:'http://localhost:8765'},localStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)},structuredClone,URLSearchParams,URL,Blob,console,setTimeout:()=>0,clearTimeout(){},FormData,scrollTo(){},addEventListener:(name,fn)=>{windowEvents[name]=fn;},TowerEngine:require('../demos/04-tower-defense/engine.js')});
 vm.runInContext('globalThis.window=globalThis;',context);
 vm.runInContext(read('shared/product/core.js'),context);
 vm.runInContext(read('shared/product/topics.js'),context);
 vm.runInContext(read('shared/product/themes.js'),context);
 vm.runInContext(read('shared/product/guides-data.js'),context);
 vm.runInContext(read('shared/product/guides.js'),context);
 vm.runInContext('const originalStart=P.start;P.start=config=>{globalThis.config=config;originalStart(config);};',context);
 vm.runInContext(read(`demos/${folder}/product.js`),context);
 const c=context.config,p=context.P,s=p.state;
 const render=(page,id)=>{const html=c.render(page,id,s);assert.match(html,/<h1>/,`${folder}/${page} has heading`);assert(!/(?:>undefined<|>NaN<)/.test(html),`Invalid display value ${folder}/${page}`);rendered.push({folder,route:page+(id?'/'+id:''),html});return html;};
 return {c,p,s,context,document,store,render,events,windowEvents,el,frame:f=>{frame=f;}};
}
function routes(app,extra=[]){const queue=app.c.nav.map(n=>n[0]).concat(extra),visited=new Set();for(let i=0;i<queue.length;i++){
 const route=queue[i];if(visited.has(route))continue;visited.add(route);const [page,id]=route.split('?')[0].split('/');if(page==='play')app.context.location.hash='#'+route;
 const html=app.render(page,id);
 assert(!html.includes('<h1>未找到'),`Broken route ${app.c.id}/${route}`);
 for(const match of html.matchAll(/href="#([^"\s]+)"/g)){if(!visited.has(match[1]))queue.push(match[1]);}
 assert(visited.size<120,'Unexpected route recursion');
}return visited.size;}
(async()=>{
 const repair=setup('01-repair-agent'),r=repair.s;
 await repair.c.submit('repo',{name:'local-service',branch:'main',url:'',language:'Python',description:'test'},r);
 await repair.c.submit('task',{title:'New boundary task',repo:r.repos.at(-1).id,case:'boundary',candidate:'correct',note:'Check equality'},r);
 const task=r.tasks[0];assert.equal(task.status,'待运行');
 const frame={contentWindow:{}};repair.frame(frame);
 const message={type:'engineering-result',project:'repair',context:{task:task.id},result:results.repair};
 repair.windowEvents.message({origin:'http://malicious.example',source:frame.contentWindow,data:message});assert.equal(r.runs.length,0);
 repair.windowEvents.message({origin:'http://localhost:8765',source:{},data:message});assert.equal(r.runs.length,0);
 repair.windowEvents.message({origin:'http://localhost:8765',source:frame.contentWindow,data:message});assert.equal(r.runs.length,1);assert.equal(task.status,'已验证');
 await repair.c.action('approve',r.runs[0].id,r);assert.equal(r.runs[0].review,'已认可');
 repair.c.onResult({...message,result:results.wrong},r);assert.equal(task.status,'验收失败');
 assert.throws(()=>repair.c.action('approve',r.runs[0].id,r),/未通过/);
 await repair.c.submit('review-note',{id:r.runs[0].id,comment:'Boundary case missing'},r);
 const repairCount=routes(repair,['new-repo','new-task','run/'+task.id]);
 const reload=setup('01-repair-agent',repair.store);assert.equal(reload.s.tasks[0].id,task.id);assert.equal(reload.s.runs.length,2);

 const rag=setup('02-process-rag'),k=rag.s;
 rag.c.onResult({result:results.rag,context:{query:'铝合金薄壁精加工'}},k);
 await rag.c.action('make-draft',k.searches[0].id,k);const draft=k.drafts[0];assert.equal(draft.sources[0],'AL-02');
 await rag.c.action('approve-draft',draft.id,k);assert.equal(draft.status,'已审核');
 await rag.c.submit('draft-text',{id:draft.id,text:'改写后的内容'},k);assert.equal(draft.status,'待审核');
 await rag.c.submit('document',{title:'<img onerror=x>',material:'通用',version:'1.0',text:'新文档内容',file:null},k);
 assert.equal(k.documents.at(-1).indexed,false);assert.match(rag.render('document',k.documents.at(-1).id),/&lt;img/);
 await assert.rejects(rag.c.submit('document',{title:'x',material:'通用',version:'1',text:'',file:null},k),/粘贴/);
 rag.p.api=async(_path,body)=>({refused:body.query==='量子纠缠实验',hits:[{id:{'铝合金薄壁精加工':'AL-02','不锈钢钻孔':'ST-01','量具校准':'QA-01'}[body.query]}]});
 await rag.c.action('evaluate','',k,{textContent:''});assert.equal(k.evaluations[0].checks.filter(c=>c.pass).length,4);
 const ragCount=routes(rag,['upload']);

 const mlops=setup('03-mlops'),m=mlops.s;
 mlops.c.onResult({result:results.bad},m);assert.equal(m.runs.length,1);assert.equal(m.versions.length,3);assert.equal(m.alerts.length,1);
 const rejected=m.versions.find(v=>v.tag.startsWith('v2'));
 assert.throws(()=>mlops.c.submit('release',{model:rejected.id},m),/可进入审批/);
 mlops.c.onResult({result:results.unlabeled},m);assert.equal(m.versions[0].qualityState,'等待真实标签');assert(!m.versions[0].eligible);
 const accepted=m.versions.find(v=>v.run && v.eligible);
 mlops.c.submit('release',{model:accepted.id,name:'test-release',environment:'staging',traffic:'10',note:'test'},m);
 const release=m.releases[0];assert.equal(release.status,'待审批');
 mlops.c.action('activate',release.id,m);assert.equal(release.status,'模拟发布中');
 mlops.c.action('rollback',release.id,m);assert.equal(release.status,'已模拟回滚');
 mlops.c.submit('resolve-alert',{id:m.alerts[0].id,resolution:'标签回流后复核'},m);assert.equal(m.alerts[0].status,'已处理');
 const mlopsCount=routes(mlops,['new-release','new-experiment']);

 const tower=setup('04-tower-defense'),t=tower.s;
 tower.render('editor');
 const ctx=new Proxy({},{get:(o,k)=>o[k] || (()=>{}),set:(o,k,v)=>{o[k]=v;return true;}});
 const canvas=tower.el('#layout-canvas');canvas.getContext=()=>ctx;canvas.getBoundingClientRect=()=>({left:0,top:0,width:450,height:250});
 tower.el('[name=tool]').value='bolt';tower.el('[name=level]').value='standard';tower.c.afterRender('editor');
 canvas.listeners.click({clientX:95,clientY:30});canvas.listeners.click({clientX:155,clientY:140});
 tower.c.submit('layout',{id:'',name:'New layout',level:'standard'},t);assert.equal(t.layouts[0].towers.length,2);assert.equal(t.layouts[0].towers[0].x,190);
 const play=tower.render('play','standard');assert(play.includes('level=standard'));
 tower.context.location.hash='#play/standard?layout='+t.layouts[0].id;assert.match(tower.render('play','standard'),/layout=%5B%7B/);
 tower.c.onResult({result:{level:'standard',levelName:'标准防线',outcome:'won',wave:5,kills:60,life:12,gold:30,clock:80,towers:t.layouts[0].towers}},t);assert.equal(t.battles.length,1);
 tower.c.submit('game-settings',{speed:'2',preview:'off'},t);assert.equal(t.settings.speed,'2');
 const towerCount=routes(tower);
 for(const app of [repair,rag,mlops,tower]) {
   assert(app.document.body.className.includes('theme-'+app.c.id));
   assert.match(app.document.body.innerHTML,/aria-controls="topic-dialog"/);
   const html=app.p.topicMarkup(),topic=app.context.ProjectTopics[app.c.id];
   const source=JSON.parse(read('report/topics.json')).find(t=>t.id===topic.id);
   for(const field of ['id','teacher','title','difficulty','value','weeks','score','resource','core','risk','upgrade','acceptance']) assert.equal(topic[field],source[field]);
   assert(html.includes(topic.title));assert(html.includes(topic.teacher));assert(html.includes(topic.weeks+' 周'));
   assert.match(html,/aria-labelledby="topic-title"/);assert.match(html,/当前原型已实现/);
   rendered.push({folder:app.c.folder,route:'topic-modal',html});
   const trigger=new Node();trigger.dataset={action:'topic-info'};trigger.isConnected=true;
   await app.events.click({target:{closest:selector=>selector==='[data-action]'?trigger:null}});
   assert(app.el('#topic-dialog').open);assert.equal(app.document.body.style.overflow,'hidden');assert(app.el('#topic-title').focused);
   const close=new Node();close.dataset={action:'topic-close'};
   await app.events.click({target:{closest:selector=>selector==='[data-action]'?close:null}});
   assert(!app.el('#topic-dialog').open);assert(trigger.focused);assert.notEqual(app.document.body.style.overflow,'hidden');
   await app.events.click({target:{closest:selector=>selector==='[data-action]'?trigger:null}});
   const dialog=app.el('#topic-dialog');dialog.getBoundingClientRect=()=>({left:10,right:300,top:10,bottom:300});
   dialog.listeners.click({target:dialog,clientX:50,clientY:50});assert(dialog.open);
   dialog.listeners.click({target:dialog,clientX:1,clientY:1});assert(!dialog.open);
 }
 await rag.c.submit('quick-search',{query:'铝合金薄壁零件'},k);
 assert(rag.context.location.hash.includes('search?query='));
 if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify(rendered,null,2));
 console.log(`Product flows passed; rendered routes: repair ${repairCount}, RAG ${ragCount}, MLOps ${mlopsCount}, tower ${towerCount}.`);
})().catch(error=>{console.error(error);process.exitCode=1;});
