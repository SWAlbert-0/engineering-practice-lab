/* Guided D09 flow: own document/job/suite/release IDs; real version and review gates. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const key = 'lab-requirements-tour-v1';
  const example = {
    title:'教学案例 · RealWorld 登录接口测试设计',
    text:'已有用户通过POST /users/login提交email和password。成功返回200及用户信息；认证失败返回401；请求字段不符合要求时返回422。'
  };
  const stages = [
    ['import','保存案例需求','已填入 RealWorld 登录接口节选。点击「保存需求原文」，建立有版本的需求记录。','导入需求'],
    ['analyze','生成第一版用例','已选离线规则，不调用模型。点击「分析并生成用例集」，查看规则生成的草案。','分析需求'],
    ['wait-analysis','正在整理验收条件','正在执行真实分析任务。完成后自动进入本次生成的用例集，无需重复提交。','分析需求'],
    ['edit-success','补齐成功登录用例','已填入虚构账号、正确密码及返回 200 的预期。可修改高亮表单中的内容，阅读后点击「保存为新版本」。','完善用例'],
    ['edit-auth','补齐认证失败用例','已填入错误密码及返回 401 的预期。检查输入与预期，再点击「保存为新版本」。','完善用例'],
    ['edit-fields','纠正规则的场景分类','规则把状态码误当成数量边界。已改为「异常」场景，并填入缺少密码字段、返回 422 的例子。检查后保存新版本。','完善用例'],
    ['trace','追踪每条用例的依据','三条教学用例均已提交。点击「追踪矩阵」，核对原文、验收条件与用例之间的关联。','核对来源'],
    ['trace-source','从矩阵回到原文','点击第一条原文编号，回到对应段落，确认状态码与预期结果确实来自需求。','核对来源'],
    ['quality','检查整理结果','原文段落已定位。点击「结构检查」，查看待确认项、关联和审核进度。','检查结构'],
    ['review-back','准备人工核对','结构检查不是语义审核。点击「用例编辑」，回到已保存的三条用例。','人工核对'],
    ['review-open','核对本次三条用例','已选中本次体验的三条用例。确认操作、输入、预期和来源后，点击「核对所选用例」。','人工核对'],
    ['review-form','记录你的核对结论','已填入教学核对示例。请阅读并按你的判断修改，再确认记录；不会自动认可用例。','人工核对'],
    ['publish-open','发布已核对的版本','本次版本已核对。点击「检查并发布」，保存原文、用例与核对记录的固定快照。','发布快照'],
    ['publish-form','确认本次发布','已填入体验用记录人。点击「检查条件并发布」；服务端会检查最新版本、草稿及审核条件。','发布快照'],
    ['export','导出发布结果','点击高亮的「JSON」，下载本次发布快照。以后修改需求不会覆盖这份记录。','导出记录'],
    ['complete','已走完需求设计流程','你已完成需求导入、规则分析、三条用例修订、来源追踪、人工核对、发布和导出。教学用例未向真实系统发起测试请求。','体验完成']
  ];
  const fresh = () => ({active:false,stage:'import',document:'',job:'',suite:'',version:1,release:''});
  let run = fresh();
  try { const saved=JSON.parse(localStorage.getItem(key)); if(saved && stages.some(s=>s[0]===saved.stage)) run={...run,...saved}; } catch {}
  // Reopen review through its real action after reload to restore the editor's
  // selection state. A previously open dialog alone is not an approval target.
  if(run.stage==='review-form')run.stage='review-open';
  let state, detail, renderedRoute='',target,allowed,lastTarget,submitting=false,problem='',syncing=false,prefilling=false;
  const view = $('#workspace-view');
  if (!view) return;
  const entry = document.createElement('section');
  entry.id = 'experience-guide'; entry.className = 'requirements-tour-entry'; entry.setAttribute('aria-labelledby', 'experience-title');
  view.before(entry);
  const shade = document.createElement('div'); shade.className = 'requirements-tour-shade'; shade.hidden = true;
  shade.innerHTML = '<svg aria-hidden="true"><path fill-rule="evenodd"></path></svg><div class="requirements-tour-ring"></div>';
  document.body.append(shade);
  const card = document.createElement('section'); card.className = 'requirements-tour-card'; card.hidden = true;
  card.setAttribute('role', 'region'); card.setAttribute('aria-label', '当前体验步骤');
  document.body.append(card);
  const store = () => { try { localStorage.setItem(key, JSON.stringify(run)); } catch {} };
  const stageIndex = () => stages.findIndex(s => s[0] === run.stage);
  function entryView() {
    entry.hidden=run.active;
    entry.innerHTML=`<div><span class="tour-eyebrow">D09 · 功能体验引导</span><h2 id="experience-title">从一段需求，走到可复查的测试设计。</h2><p>RealWorld 登录接口节选 · 虚构测试账号 · 无需模型密钥 · 约 5 分钟</p><div class="tour-route"><span>导入分析</span><i>→</i><span>完善用例</span><i>→</i><span>核对来源</span><i>→</i><span>审核发布</span></div><details class="tour-source"><summary>案例来源与体验范围</summary><p>RealWorld Conduit OpenAPI · MIT。使用仓库内中文选译的登录接口节选；账号与密码仅为虚构教学数据。只生成测试设计，不访问真实接口。</p><a href="https://github.com/gothinkster/realworld/blob/ebbcdeb8d55b42a3a613c787560498b8ef10003f/specs/api/openapi.yml" target="_blank" rel="noopener">查看原始规格 ↗</a></details></div><div class="tour-entry-action"><button type="button" data-tour="start" data-case-fill>一键导入案例并开始 <span aria-hidden="true">→</span></button>${run.document && run.stage!=='complete'?'<button type="button" data-tour="resume" class="secondary">继续上次体验</button>':''}<small>自动填入教学内容；保存、核对与发布由你点击确认。</small></div>`;
  }
  function change(stage) {
    run.stage=stage; submitting=false; problem=''; lastTarget=null;
    for(const name of ['review','publish']) if(stage!==name+'-form') {$('#'+name+'-dialog').close(); delete $('#'+name+'-dialog').dataset.tourOpen;}
    store(); sync();
  }
  function editingIndex() {return ['edit-success','edit-auth','edit-fields'].indexOf(run.stage);}
  function expectedRoute() {
    const suite='suite/'+run.suite, version='version='+run.version;
    switch(run.stage) {
      case 'import':return 'import';
      case 'analyze':return 'document/'+run.document;
      case 'wait-analysis':return 'jobs';
      case 'edit-success':case 'edit-auth':case 'edit-fields':return suite+'?case=TC-00'+(editingIndex()+1)+'&'+version;
      case 'trace':case 'quality':return suite+'?'+version;
      case 'trace-source':return suite+'?mode=trace&'+version;
      case 'review-back':return suite+'?mode=quality&'+version;
      case 'review-open':case 'review-form':case 'publish-open':case 'publish-form':return suite+'?mode=edit&'+version;
      case 'export':case 'complete':return 'releases';
    }
  }
  function onRoute(expected) {
    const [path, query = ''] = expected.split('?'), [actual, search = ''] = location.hash.slice(1).split('?');
    const params = new URLSearchParams(search);
    return actual === path && [...new URLSearchParams(query)].every(([k,v]) => params.get(k) === v);
  }
  function fill(form, fields) {
    if (form.dataset.tourStage === run.stage) return;
    for (const [name, value] of Object.entries(fields)) {
      const input = form.elements.namedItem(name);
      if (!input) throw Error('案例表单与页面版本不一致，请刷新后重试。');
      input.value = value; input.dispatchEvent(new Event('change', {bubbles:true}));
    }
    form.dataset.tourStage = run.stage;
  }
  function fillCase(form) {
    if(form.dataset.tourStage===run.stage) return;
    if(detail.set.id!==run.suite || detail.cases.length!==3 || detail.source.text!==example.text) throw Error('案例结构与预期不一致，请退出体验核对本次用例集。');
    // Preserve a server-side draft on refresh; never overwrite the user's edits.
    if(detail.draft) {form.dataset.tourStage=run.stage;return;}
    const index=editingIndex();
    const specs=[
      {title:'正确凭据登录返回 200',kind:'正向',input:'POST /users/login，user={email: "learner@example.invalid", password: "Teaching-Only-Example"}',expected:'返回 HTTP 200 及用户信息。',criteria:[0,1]},
      {title:'错误密码登录返回 401',kind:'异常',input:'POST /users/login，user={email: "learner@example.invalid", password: "Wrong-Teaching-Password"}',expected:'认证失败，返回 HTTP 401。',criteria:[0,2]},
      {title:'请求缺少密码字段返回 422',kind:'异常',input:'POST /users/login，user={email: "learner@example.invalid"}，不包含 password 字段。',expected:'请求字段不符合要求，返回 HTTP 422。',criteria:[0,3]}
    ];
    const spec=specs[index], requirement=detail.analysis.data.requirements[0];
    prefilling=true;
    try {
      fill(form,{title:spec.title,kind:spec.kind,precondition:'教学环境中已存在 learner@example.invalid，正确密码为 Teaching-Only-Example；账号和密码均为虚构示例。',questions:''});
      const steps=form.querySelectorAll('[data-step]');
      if(steps.length!==2 || requirement.criteria.length!==4) throw Error('规则生成格式已变化，请退出体验检查用例。');
      const values=[{action:'准备本用例的教学请求数据',input:spec.input,expected:'请求数据与本用例描述一致。'},{action:'向教学环境提交登录请求并记录响应',input:spec.input,expected:spec.expected}];
      steps.forEach((step,i)=>{for(const [name,value] of Object.entries(values[i]))step.querySelector('[name='+name+']').value=value;});
      const ids=spec.criteria.map(i=>requirement.criteria[i].id);
      form.querySelectorAll('[name=criterion_ids]').forEach(input=>input.checked=ids.includes(input.value));
      // Use the editor's own draft/save path, including revision conflict checks.
      form.elements.title.dispatchEvent(new Event('input',{bubbles:true}));
      form.querySelector('.case-questions').open=false;
    } finally {prefilling=false;}
  }
  function findTarget() {
    switch(run.stage) {
      case 'import': {const form=$('#import-form');if(!form)return;fill(form,example);return form.querySelector('[type=submit]');}
      case 'analyze': {const form=$('#analyze-form');if(!form)return;fill(form,{mode:'offline'});return form.querySelector('[type=submit]');}
      case 'edit-success':case 'edit-auth':case 'edit-fields': {const form=$('#case-form');if(!form)return;fillCase(form);return $('#commit-cases');}
      case 'trace':return $('.work-modes a[href*="mode=trace"]');
      case 'trace-source':return $('[data-source-route]');
      case 'quality':return $('.work-modes a[href*="mode=quality"]');
      case 'review-back':return $('.work-modes a[href*="mode=edit"]');
      case 'review-open': {
        const boxes=[...document.querySelectorAll('[name=review-case]')];
        if(boxes.length!==3) throw Error('本次用例数量已变化，请退出体验核对。');
        boxes.forEach(input=>input.checked=true);
        if($('#review-selected-count').textContent!=='已选择 3 条用例')$('#review-selected-count').textContent='已选择 3 条用例';
        return $('#open-review');
      }
      case 'review-form':case 'publish-form': {
        const name=run.stage==='review-form'?'review':'publish',dialog=$('#'+name+'-dialog'),form=$('#'+name+'-form');
        if(dialog.dataset.tourOpen!==run.suite) {if(!dialog.open)dialog.show();dialog.dataset.tourOpen=run.suite;}
        fill(form,name==='review'?{actor:'体验用户（教学核对）',decision:'approved',comment:'已逐条核对成功登录 200、认证失败 401、字段无效 422 的来源与测试输入；测试账号为虚构教学数据。'}:{actor:'体验用户（教学发布）'});
        return form.querySelector('[type=submit]');
      }
      case 'publish-open':return $('#open-publish');
      case 'export':return document.querySelector(`a[href="/api/requirements-workspace/releases/${CSS.escape(run.release)}/export?format=json"]`);
    }
  }
  function evidenceSelector() {
    if(editingIndex()>=0) return '#case-form';
    return {import:'#import-form',analyze:'.source-document',trace:'.review-layout','trace-source':'.table-scroll',quality:'.source-panel','review-back':'.metrics','review-open':'.review-list','publish-open':'.review-list',export:'#workspace-view .table-scroll'}[run.stage];
  }
  function renderCard() {
    const index = stageIndex(), stage = stages[index], total = stages.length - 1;
    const busy = run.stage.startsWith('wait-');
    const message = problem || (submitting ? '正在保存，请稍候…' : stage[2]);
    const signature = JSON.stringify([run.stage, message, Boolean(target), target?.disabled]);
    if (card.dataset.signature === signature) return;
    card.dataset.signature = signature;
    card.dataset.stage = run.stage;
    card.innerHTML = `<div class="tour-card-top"><span class="tour-eyebrow">${esc(stage[3])} <b>${Math.min(index + 1, total)} / ${total}</b></span><button type="button" data-tour="exit" class="tour-exit" aria-label="退出体验引导">退出体验 ×</button></div><div class="tour-progress" role="progressbar" aria-label="体验进度" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${Math.min(index,total)}"><span style="width:${index / total * 100}%"></span></div><h2>${esc(stage[1])}</h2><p role="status" ${problem ? 'class="tour-problem"' : ''}>${esc(message)}</p>${run.stage === 'complete' ? '<button type="button" data-tour="exit">完成体验，查看发布记录</button>' : problem ? '<button type="button" data-tour="retry">重新检查本步</button>' : `<div class="tour-hint">${busy ? '<span class="tour-spinner" aria-hidden="true"></span> 等待真实执行结果' : target?.disabled ? '运行器未就绪，请稍候或退出后检查运行器。' : '只需操作高亮区域，其余内容已暂时锁定。'}</div>`}`;
  }
  function position() {
    if (!run.active) return;
    const width = innerWidth, height = innerHeight;
    const rect = (allowed || target)?.getBoundingClientRect();
    const pad = 7;
    const hole = rect ? {left:Math.max(0,rect.left-pad), top:Math.max(0,rect.top-pad), right:Math.min(width,rect.right+pad), bottom:Math.min(height,rect.bottom+pad)} : {left:0,top:0,right:0,bottom:0};
    // Keep the evidence being discussed readable, while only the outlined
    // action accepts input. The surrounding navigation stays behind the mask.
    const contextSelector = evidenceSelector();
    const evidence = contextSelector ? $(contextSelector)?.getBoundingClientRect() : null;
    const holes = rect ? [hole] : [];
    if (evidence && evidence.bottom > 0 && evidence.top < height) {
      const area = {left:Math.max(0,evidence.left-pad),top:Math.max(0,evidence.top-pad),right:Math.min(width,evidence.right+pad),bottom:Math.min(height,evidence.bottom+pad)};
      if (rect && area.left < hole.right && area.right > hole.left && area.top < hole.bottom && area.bottom > hole.top) {
        holes[0] = {left:Math.min(area.left,hole.left),top:Math.min(area.top,hole.top),right:Math.max(area.right,hole.right),bottom:Math.max(area.bottom,hole.bottom)};
      } else holes.push(area);
    }
    const rectangle = r => `M${r.left},${r.top}H${r.right}V${r.bottom}H${r.left}Z`;
    shade.querySelector('svg').setAttribute('viewBox', `0 0 ${width} ${height}`);
    shade.querySelector('path').setAttribute('d', rectangle({left:0,top:0,right:width,bottom:height}) + holes.map(rectangle).join(''));
    const ring = shade.lastElementChild;
    ring.hidden = !target;
    if (target) { const r = target.getBoundingClientRect(); Object.assign(ring.style, {left:r.left-5+'px',top:r.top-5+'px',width:r.width+10+'px',height:r.height+10+'px'}); }
    // Place the instruction beside, above or below the current action, with a
    // reserved mobile footer so it never covers a button or review field.
    const cardWidth = card.offsetWidth, cardHeight = card.offsetHeight;
    let left = Math.max(12,width-cardWidth-24), top = 20;
    if (width <= 760) { left = 12; top = height-cardHeight-12; }
    else if (rect) {
      if (hole.left > cardWidth + 40) { left = hole.left-cardWidth-24; top = Math.max(20, Math.min(hole.top,height-cardHeight-20)); }
      else if (width-hole.right > cardWidth+40) { left=hole.right+24; top=Math.max(20,Math.min(hole.top,height-cardHeight-20)); }
      else top = hole.top > cardHeight+36 ? hole.top-cardHeight-24 : Math.min(height-cardHeight-20,hole.bottom+24);
    }
    Object.assign(card.style, {left:left+'px',top:Math.max(12,top)+'px'});
    document.documentElement.style.setProperty('--tour-card-height', cardHeight+'px');
  }
  function focusTarget() {
    if (target && target !== lastTarget) {
      lastTarget = target;
      target.scrollIntoView({block:'center', behavior:'instant'});
      target.focus({preventScroll:true});
      const focused=target;
      requestAnimationFrame(() => {
        if(!run.active || target!==focused || !focused.isConnected)return;
        position();
        if (innerWidth <= 760 && target.getBoundingClientRect().bottom > card.getBoundingClientRect().top-18) {
          window.scrollBy(0, target.getBoundingClientRect().bottom-card.getBoundingClientRect().top+32); position();
        }
      });
    }
  }
  function sync() {
    if (syncing) return;
    syncing = true;
    try {
      entryView(); card.hidden = shade.hidden = !run.active;
      document.body.classList.toggle('requirements-tour-active', run.active);
      target = allowed = null;
      if (!run.active) return;
      if (!$('#workspace-error').hidden) problem = $('#error-message').textContent;
      if (run.stage === 'complete') { renderCard(); position(); return; }
      const expected = expectedRoute();
      if (!onRoute(expected)) { location.hash = expected; renderCard(); position(); return; }
      if (view.inert || view.getAttribute('aria-busy') === 'true' || renderedRoute !== location.hash.slice(1)) { renderCard(); position(); return; }
      if(run.stage==='wait-analysis') {
        const job=state?.jobs.find(j=>j.id===run.job);
        if(job?.status==='succeeded' && job.document_id===run.document) {run.suite=job.result.set_id;run.version=1;syncing=false;change('edit-success');return;}
        if(job && ['failed','cancelled','interrupted'].includes(job.status)) problem=job.error||'分析任务未完成，请退出体验检查本次任务。';
      } else target=findTarget();
      allowed=editingIndex()>=0?$('#case-form'):run.stage==='review-form'?$('#review-form'):run.stage==='publish-form'?$('#publish-form'):target;
      const message = $(run.stage === 'review-form' ? '#review-form .form-message' : run.stage === 'publish-form' ? '#publish-form .form-message' : '#workspace-view .form-message');
      if (message?.textContent.trim() && !message.textContent.includes('…')) problem = message.textContent.trim();
      if (!$('#workspace-error').hidden) problem = $('#error-message').textContent;
      renderCard(); focusTarget(); position();
    } catch (error) { problem = error.message; renderCard(); position(); }
    finally { syncing = false; }
  }
  function exit() {
    run.active=false;submitting=false;store();
    for(const name of ['review','publish']) {$('#'+name+'-dialog').close();delete $('#'+name+'-dialog').dataset.tourOpen;}
    sync();document.documentElement.style.removeProperty('--tour-card-height');entry.querySelector('button').focus({preventScroll:true});
  }
  function start(resume) {
    if(!resume)run=fresh();
    run.active=true;problem='';lastTarget=null;store();sync();
  }
  function permitted(element) {
    if(card.contains(element) || target?.contains(element))return true;
    return Boolean(allowed?.contains(element)) && !element.closest('button,a');
  }
  // Capture events before workspace handlers. A visual mask alone would still
  // allow keyboard activation, label clicks and accidental form submissions.
  for (const type of ['pointerdown','click','dblclick','change','input','submit']) {
    document.addEventListener(type, event => {
      if (!run.active || prefilling || permitted(event.target)) return;
      // Submit is fired on the form, rather than its highlighted submit button.
      if (type === 'submit' && target?.form === event.target && event.submitter === target) return;
      event.preventDefault(); event.stopImmediatePropagation();
    }, true);
  }
  document.addEventListener('keydown', event => {
    if (!run.active) return;
    if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); exit(); return; }
    if (event.key === 'Tab') {
      const candidates = [...(allowed ? (allowed.matches('button,a,input,select,textarea') ? [allowed] : allowed.querySelectorAll('button,a,input,select,textarea')) : []), ...card.querySelectorAll('button')].filter(el=>permitted(el) && !el.disabled && el.getClientRects().length);
      if (!candidates.length) return;
      const index = candidates.indexOf(document.activeElement), offset = event.shiftKey ? -1 : 1;
      event.preventDefault(); candidates[(index+offset+candidates.length)%candidates.length].focus(); return;
    }
    if (!permitted(event.target) && ['Enter',' '].includes(event.key)) {event.preventDefault(); event.stopImmediatePropagation();}
  }, true);
  document.addEventListener('focusin', event => {
    if (run.active && !permitted(event.target)) (target && !target.disabled ? target : card.querySelector('button'))?.focus({preventScroll:true});
  });
  document.addEventListener('click', event => {
    const action = event.target.closest('[data-tour]');
    if (action) {
      if (action.dataset.tour === 'exit') exit();
      else if (action.dataset.tour === 'retry') { problem=''; submitting=false; document.querySelectorAll('.form-message').forEach(el=>el.textContent=''); $('#workspace-error').hidden=true; window.dispatchEvent(new HashChangeEvent('hashchange')); }
      else start(action.dataset.tour === 'resume');
      return;
    }
    if (!run.active || !target?.contains(event.target) || target.disabled) return;
    if (run.stage === 'export') {
      event.preventDefault();
      if (submitting) return;
      const url = target.href;
      const exporting=run;
      submitting = true; renderCard();
      fetch(url, {cache:'no-store'}).then(async response => {
        if (!response.ok) throw Error('导出暂时失败，请点击「重新检查本步」后重试。');
        const blob = await response.blob();
        if(!run.active || run!==exporting)return;
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob); link.download = 'requirements-release-' + run.release + '.json'; link.hidden = true;
        card.append(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(link.href), 1000);
        change('complete');
      }).catch(error => {if(run.active && run===exporting){problem = error.message; submitting=false; renderCard(); position();}});
      return;
    }
    const next = {trace:'trace-source','trace-source':'quality',quality:'review-back','review-back':'review-open','review-open':'review-form','publish-open':'publish-form'}[run.stage];
    if (next) queueMicrotask(() => change(next));
  });
  document.addEventListener('submit', event => {
    if (!run.active || !['import-form','analyze-form','review-form','publish-form'].includes(event.target.id)) return;
    submitting = true; renderCard(); position();
  });
  window.addEventListener('requirements:render',event=>{state=event.detail.state;detail=event.detail.detail;renderedRoute=event.detail.route;sync();});
  window.addEventListener('requirements:imported',event=>{if(run.active&&run.stage==='import'){run.document=event.detail.document_id;change('analyze');}});
  window.addEventListener('requirements:analyzed',event=>{if(run.active&&run.stage==='analyze'){run.job=event.detail.job_id;change('wait-analysis');}});
  window.addEventListener('requirements:committed',event=>{
    if(!run.active||editingIndex()<0||event.detail.set_id!==run.suite)return;
    const index=editingIndex();run.version=event.detail.version;
    // Let the workspace finish navigating before advancing to the next case.
    queueMicrotask(()=>change(['edit-auth','edit-fields','trace'][index]));
  });
  window.addEventListener('requirements:reviewed',event=>{
    if(run.active&&run.stage==='review-form'&&event.detail.set_id===run.suite) {
      if(event.detail.decision==='approved')change('publish-open');
      else {change('review-open');problem='已记录退回修改。可退出体验继续修订，或重新核对后记录结论。';sync();}
    }
  });
  window.addEventListener('requirements:published',event=>{if(run.active&&run.stage==='publish-form'){run.release=event.detail.release_id;change('export');}});
  window.addEventListener('hashchange', () => {lastTarget=null; sync();});
  window.addEventListener('resize', position);
  window.addEventListener('scroll', position, true);
  // Form errors and disabled buttons can change without a full route render.
  new MutationObserver(() => { if (run.active) {submitting=false; sync();} }).observe(view, {childList:true,subtree:true,attributes:true,attributeFilter:['disabled']});
  for (const id of ['review-form','publish-form']) new MutationObserver(() => {if(run.active) {submitting=false; sync();}}).observe($('#'+id+' .form-message'), {childList:true});
  new MutationObserver(() => {if(run.active) sync();}).observe($('#workspace-error'), {childList:true,subtree:true,attributes:true,attributeFilter:['hidden']});
  new MutationObserver(()=>{if(run.active && $('#conflict-dialog').open)exit();}).observe($('#conflict-dialog'),{attributes:true,attributeFilter:['open']});
  window.LabRequirementsTour = {version:1, get state() {return {...run};}};
  sync();
})();
