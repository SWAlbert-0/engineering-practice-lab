'use strict';
window.P = (() => {
  const h = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const icons = {overview:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',folder:'M3 6h7l2 3h9v11H3z',tasks:'M9 5h12 M9 12h12 M9 19h12 M3 5h1 M3 12h1 M3 19h1',run:'m8 4 12 8-12 8z',file:'M6 3h8l4 4v14H6z M14 3v5h5 M9 12h6 M9 16h6',chart:'M4 3v17h17 M8 15v-4 M13 15V7 M18 15v-8',settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M19 5l-2 2 M7 17l-2 2',help:'M12 16v1 M9 8a3 3 0 1 1 5 2c-2 1-2 2-2 3 M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20',layers:'m12 3 10 5-10 5L2 8z M2 12l10 5 10-5 M2 16l10 5 10-5',alert:'m12 3 10 18H2z M12 9v5 M12 17v1',game:'M7 8h10l4 8-2 3-4-3H9l-4 3-2-3z M7 10v5 M5 12h4 M16 11h1 M18 14h1'};
  const icon = name => `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${icons[name] || icons.file}"/></svg>`;
  let project, state, timer, storageOK = true;
  const key = () => `engineering-product:${project.id}:v1`;
  const uid = prefix => `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,6)}`;
  const date = value => value ? new Date(value).toLocaleString('zh-CN', {hour12:false}) : '—';
  const now = () => new Date().toISOString();
  const badge = (text, kind='') => `<span class="badge ${kind}">${h(text)}</span>`;
  const origin = record => badge(record.sample ? '示例' : record.result ? '本地运行' : '本地记录', record.sample ? '' : 'info');
  const link = (route, text, cls='') => `<a href="#${h(route)}"${cls ? ` class="${cls}"` : ''}>${h(text)}</a>`;
  const button = (action, text, id='', cls='secondary') => `<button type="button" class="${cls}" data-action="${h(action)}" data-id="${h(id)}">${h(text)}</button>`;
  const title = (name,desc='',actions='',crumb='工作区') => `<header class="heading"><div><div class="crumb">${h(project.title)} / ${h(crumb)}</div><h1>${h(name)}</h1><p class="description">${desc}</p></div><div class="actions">${actions}</div></header>`;
  const panel = (name,body,action='') => `<section class="panel"><div class="panel-title"><h2>${h(name)}</h2>${action}</div>${body}</section>`;
  const pad = body => `<div class="pad">${body}</div>`;
  const notice = (headline,body) => `<div class="notice">${icon('help')}<div><strong>${h(headline)}</strong> ${body}</div></div>`;
  const empty = (headline,desc,route='',label='开始') => `<div class="empty"><strong>${h(headline)}</strong>${h(desc)}${route ? '<div>'+link(route,label,'btn')+'</div>' : ''}</div>`;
  const table = (headers,rows,filter=false) => `${filter ? '<div class="toolbar"><input type="search" data-filter placeholder="筛选当前列表…" aria-label="筛选当前列表"><span class="count" data-count>'+rows.length+' 条记录</span></div>' : ''}<div class="table-wrap"><table><thead><tr>${headers.map(x=>`<th>${h(x)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(cell=>`<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table></div>${filter ? '<div class="filter-empty" hidden>没有匹配的记录。</div>' : ''}`;
  const metrics = items => `<div class="metrics">${items.map(([label,value,note])=>`<div class="metric"><span>${h(label)}</span><strong>${h(value)}</strong><small>${h(note)}</small></div>`).join('')}</div>`;
  const kv = entries => `<dl class="kv">${entries.map(([k,v])=>`<dt>${h(k)}</dt><dd>${v}</dd>`).join('')}</dl>`;
  const field = (name,label,value='',hint='',type='text',required=true) => `<div class="field"><label for="f-${h(name)}">${h(label)}</label><input id="f-${h(name)}" name="${h(name)}" type="${type}" autocomplete="off" value="${h(value)}" ${required?'required':''} maxlength="300"><small>${hint}</small></div>`;
  const select = (name,label,options,value='',hint='') => `<div class="field"><label for="f-${h(name)}">${h(label)}</label><select id="f-${h(name)}" name="${h(name)}">${options.map(([v,t])=>`<option value="${h(v)}" ${v===value?'selected':''}>${h(t)}</option>`).join('')}</select><small>${hint}</small></div>`;
  const area = (name,label,value='',hint='',required=true) => `<div class="field"><label for="f-${h(name)}">${h(label)}</label><textarea id="f-${h(name)}" name="${h(name)}" autocomplete="off" ${required?'required':''} maxlength="10000">${h(value)}</textarea><small>${hint}</small></div>`;
  const form = (name,body,submit='保存',cancel='overview') => `<form data-form="${h(name)}" class="panel"><div class="pad">${body}</div><div class="form-footer"><button type="submit">${h(submit)}</button>${link(cancel,'取消','btn secondary')}</div></form>`;
  const steps = (labels,current=0) => `<ol class="steps">${labels.map((l,i)=>`<li class="${i===current?'current':''}"><span>${i+1}</span>${h(l)}</li>`).join('')}</ol>`;
  const timeline = items => `<ol class="timeline">${items.map(([t,d])=>`<li>${h(t)}<small>${h(d)}</small></li>`).join('')}</ol>`;
  const tabs = (items,current) => `<nav class="tabs" aria-label="详情导航">${items.map(([route,label])=>link(route,label,route===current?'active':'')).join('')}</nav>`;
  const progress = items => `<div class="bars">${items.map(([n,v,max,suffix=''])=>`<div class="bar-row"><span>${h(n)}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(0,Math.min(100,v/max*100))}%"></div></div><span class="number">${h(v)}${h(suffix)}</span></div>`).join('')}</div>`;
  function toast(text) { const el=document.querySelector('#toast'); el.textContent=text;el.hidden=false;clearTimeout(timer);timer=setTimeout(()=>{el.hidden=true;},5000); }
  function save() { try {localStorage.setItem(key(),JSON.stringify(state));} catch {storageOK=false;document.querySelector('#storage-warning').hidden=false;toast('保存空间不可用。本次修改仅在当前页面有效，请导出备份。');} }
  function audit(text) { (state.activity ||= []).unshift({at:now(),text});state.activity=state.activity.slice(0,60);save(); }
  function download(data,name) {const a=document.createElement('a'),u=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
  const route = () => location.hash.slice(1).split('?')[0].split('/').map(part=>{try{return decodeURIComponent(part)}catch{return part}});
  function go(target) { if(location.hash==='#'+target) render();else location.hash=target; }
  function render() {
    const [rawPage,id] = route();
    const page = rawPage || 'overview';
    document.querySelectorAll('[data-nav]').forEach(a=>{const active=a.dataset.nav===(project.navActive?.[page] || page);a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
    const content=document.querySelector('#view');
    try { content.innerHTML=project.render(page || 'overview',id,state); }
    catch(error) {console.error(error);content.innerHTML=title('无法显示此页面')+empty('记录可能已被删除','返回列表后重新选择。','overview','返回概览');}
    document.title=`${content.querySelector('h1')?.textContent || project.title} · ${project.title}`;
    project.afterRender?.(page,id,state);
    const frame=content.querySelector('iframe');
    if(frame) frame.addEventListener('load',()=>{
      try {const doc=frame.contentDocument;const resize=()=>{frame.style.height=Math.max(520,doc.documentElement.scrollHeight)+'px';};resize();const observer=new MutationObserver(resize);observer.observe(doc.body,{subtree:true,childList:true,characterData:true,attributes:true});frame._observer=observer;}catch{}
    });
    window.scrollTo(0,0);
    if(page==='guide' && id)window.ProjectGuides?.focus(id);
  }
  function workbench(params={}) {return `<div class="workbench-wrap"><iframe class="workbench" title="${h(project.title)}运行工作台" src="workbench.html?${h(new URLSearchParams(params))}"></iframe></div>`;}
  async function api(path,data) {let response;try{response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});}catch{throw Error('无法连接服务，请启动 python server.py 后重试。');}const result=await response.json();if(!response.ok)throw Error(result.error || '请求失败');return result;}
  function confirmAction(headline,desc,callback) {const dialog=document.querySelector('#confirm');dialog.querySelector('h2').textContent=headline;dialog.querySelector('p').textContent=desc;dialog.querySelector('[data-confirm]').onclick=()=>{dialog.close();callback();};dialog.showModal();}
  function settings(extra='') {return title('工作区设置','管理本地记录与接入计划。')+notice('本地存储','记录保存在当前浏览器中。不会自动同步到其他设备，也不保存访问令牌。')+`<div class="columns">${panel('数据管理',pad(`<p class="description">导出包含本项目的本地配置、操作记录与已保存结果。</p><div class="actions">${button('export-state','导出工作区')}${button('reset-state','重置为示例数据','','danger')}</div>`))}${panel('运行环境',pad(kv([['服务','<code>127.0.0.1:8765</code>'],['环境','<code>engineering-practice-lab</code>'],['存储',storageOK?'浏览器 LocalStorage':'临时内存'],['外部接入','尚未连接外部账号或生产服务']])) )}</div>${extra}`;}
  function guide(items,boundary) {return title('使用指南','按顺序完成一次项目流程。')+panel('建议流程',pad(timeline(items)))+`<section class="section">${notice('当前实现范围',boundary)}</section>`;}
  let topicTrigger, previousOverflow = '';
  function topicMarkup() {
    const t = window.ProjectTopics?.[project.id];
    if (!t) return '';
    return `<dialog id="topic-dialog" class="topic-dialog" aria-modal="true" aria-labelledby="topic-title" aria-describedby="topic-summary">
      <header class="topic-dialog-header"><div class="topic-source">${h(t.teacher)}老师 / ${h(t.id)} / 选题介绍</div>
      <button type="button" class="topic-close" data-action="topic-close" aria-label="关闭选题介绍">×</button>
      <h2 id="topic-title" tabindex="-1">${h(t.title)}</h2><p id="topic-summary">适合方向：${h(t.direction)}</p></header>
      <dl class="topic-facts"><div><dt>实现难度</dt><dd>${t.difficulty} / 5</dd></div><div><dt>简历价值</dt><dd>${t.value} / 5</dd></div><div><dt>预计周期</dt><dd>${h(t.weeks)} 周</dd></div><div><dt>综合评分</dt><dd>${t.score} / 100</dd></div></dl>
      <div class="topic-dialog-content">
        <section><h3>原题要求</h3><p>${h(t.core)}</p></section><section><h3>资源与环境</h3><p>${h(t.resource)}</p></section>
        <section><h3>值得投入的工作</h3><p>${h(t.upgrade)}</p></section><section><h3>主要难点</h3><p>${h(t.risk)}</p></section>
        <section class="topic-wide"><h3>如何验收成果</h3><p>${h(t.acceptance)}</p></section>
        <section class="topic-scope"><h3>当前原型已实现</h3><p>${h(t.implemented)}</p></section><section class="topic-scope"><h3>后续开发范围</h3><p>${h(t.pending)}</p></section>
        <section class="topic-wide"><p>周期按一人每周约 15 小时估算，指完整选题的开发投入。评分来自本项目的选题分析，侧重软件工程与 AI 应用，不是课程评分或录取概率。</p></section>
      </div><footer class="topic-dialog-footer"><a href="../../report/index.html#topic-${h(t.id)}">查看完整选题分析</a><button type="button" class="secondary" data-action="topic-close">返回项目</button></footer>
    </dialog>`;
  }
  function openTopic(trigger) {
    const dialog = document.querySelector('#topic-dialog');
    if (!dialog || dialog.open) return;
    topicTrigger = trigger;
    previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog.showModal();
    dialog.scrollTop = 0;
    document.querySelector('#topic-title').focus();
  }
  function start(config) {
    project=config;
    try {state=JSON.parse(localStorage.getItem(key())) || structuredClone(config.seed);}catch {state=structuredClone(config.seed);storageOK=false;}
    if(!state || typeof state!=='object' || state.schema!==1){state=structuredClone(config.seed);storageOK=false;}
    const dirs=['01-repair-agent','02-process-rag','03-mlops','04-tower-defense'];
    document.body.className=(config.theme || '')+' theme-'+config.id;
    document.documentElement.style.colorScheme = ['mlops','tower'].includes(config.id) ? 'dark' : 'light';
    if(config.accent)document.documentElement.style.setProperty('--accent',config.accent);
    document.body.innerHTML=`<a class="skip" href="#view">跳到正文</a><aside class="rail"><a class="brand" href="#overview"><span class="brand-icon">${icon(config.icon)}</span>${h(config.title)}</a><p class="brand-note">${h(config.subtitle)}</p><div class="rail-label">工作区</div><nav>${config.nav.map(([route,label,i])=>`<a href="#${route}" data-nav="${route}">${icon(i)}${h(label)}</a>`).join('')}</nav><div class="rail-bottom">数据保存在当前浏览器<a href="../../index.html">← 返回项目总览</a><a href="../../report/index.html#scope">选题分析与开发范围</a></div></aside><div class="surface"><header class="topbar"><span><a class="topbar-home" href="../../index.html">项目总览</a>${h(config.workspace || '个人工作区')} / ${h(config.subtitle)}</span><div class="actions"><span class="environment">本地原型</span><button type="button" class="secondary topic-entry" data-action="topic-info" aria-haspopup="dialog" aria-controls="topic-dialog">${icon('help')}选题介绍</button><select id="project-switch" aria-label="切换项目">${dirs.map((d,i)=>`<option value="${d}" ${d===config.folder?'selected':''}>${['测试与修复','工艺资料检索','模型发布平台','塔防工作室'][i]}</option>`).join('')}</select></div></header><p class="storage-warning" id="storage-warning" ${storageOK?'hidden':''}>本地存储不可用或数据格式不匹配，当前改动请及时导出备份。</p><main id="view" class="content" tabindex="-1"></main></div><div id="toast" role="status" aria-live="polite" class="toast" hidden></div><dialog id="confirm" aria-labelledby="confirm-title" aria-describedby="confirm-desc"><h2 id="confirm-title"></h2><p id="confirm-desc"></p><div class="actions"><button data-confirm>确认</button><button class="secondary" data-cancel>取消</button></div></dialog>${topicMarkup()}`;
    const topicDialog = document.querySelector('#topic-dialog');
    if (topicDialog) {
      topicDialog.addEventListener('close', () => {
        document.body.style.overflow = previousOverflow;
        if (topicTrigger?.isConnected) topicTrigger.focus();
      });
      topicDialog.addEventListener('click', event => {
        if (event.target !== topicDialog) return;
        const box = topicDialog.getBoundingClientRect();
        if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) topicDialog.close();
      });
    }
    document.querySelector('#project-switch').addEventListener('change',event=>{if(dirs.includes(event.target.value))location.href='../'+event.target.value+'/index.html';});
    document.querySelector('[data-cancel]').onclick=()=>document.querySelector('#confirm').close();
    document.addEventListener('click',async event=>{
      if(event.target.closest('.skip')){event.preventDefault();document.querySelector('#view').focus();return;}
      const el=event.target.closest('[data-action]');if(!el || el.disabled)return;
      const action=el.dataset.action,id=el.dataset.id;
      if(action==='topic-info')return openTopic(el);
      if(action==='topic-close')return document.querySelector('#topic-dialog').close();
      if(action==='export-state')return download(state,project.id+'-workspace.json');
      if(action==='reset-state')return confirmAction('重置本地工作区？','本项目的本地新增记录将被删除，恢复初始示例。建议先导出备份。',()=>{state=structuredClone(project.seed);save();go('overview');toast('已恢复示例数据。');});
      el.disabled=true;try{await project.action?.(action,id,state,el);}catch(error){toast(error.message);}finally{el.disabled=false;}
    });
    document.addEventListener('submit',async event=>{
      const form=event.target.closest('[data-form]');if(!form)return;event.preventDefault();
      const button=form.querySelector('[type=submit]');if(button.disabled)return;
      button.disabled=true;button.setAttribute('aria-busy','true');
      const values=Object.fromEntries(new FormData(form).entries());
      try{await project.submit(form.dataset.form,values,state,form);}catch(error){toast(error.message);}finally{button.disabled=false;button.removeAttribute('aria-busy');}
    });
    document.addEventListener('input',event=>{
      if(!event.target.matches('[data-filter]'))return;
      const scope=event.target.closest('.panel'),q=event.target.value.trim().toLocaleLowerCase();let n=0;
      scope.querySelectorAll('tbody tr').forEach(row=>{row.hidden=!row.textContent.toLocaleLowerCase().includes(q);if(!row.hidden)n++;});
      scope.querySelector('[data-count]').textContent=n+' 条记录';scope.querySelector('.filter-empty').hidden=n>0;
    });
    window.addEventListener('hashchange',render);
    window.addEventListener('message',event=>{
      const frame=document.querySelector('iframe');if(!frame || event.source!==frame.contentWindow || event.origin!==location.origin)return;
      if(event.data?.type!=='engineering-result' || event.data.project!==project.id)return;
      project.onResult?.(event.data,state);save();toast('运行结果已保存，可在记录页查看。');
    });
    render();
  }
  return {h,icon,uid,date,now,badge,origin,link,button,title,panel,pad,notice,empty,table,metrics,kv,field,select,area,form,steps,timeline,tabs,progress,toast,save,audit,download,route,go,render,workbench,api,confirm:confirmAction,settings,guide,start,topicMarkup,get state(){return state;}};
})();
