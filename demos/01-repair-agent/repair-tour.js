/* A guided run owns only its two task IDs. Business actions still need a click. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const key = 'lab-repair-tour-v2';
  const sample = 'opensource-mean';
  const stages = [
    ['create', '运行修复案例', '这里的平均值函数误用了整除，会丢失小数。案例已填好：先运行错误候选，再修订一次。点击「创建并执行」。', '认识缺陷'],
    ['wait-first', '正在复现与修订', '运行器正在执行两轮真实测试。完成后会自动带你查看结果，无需重复提交。', '运行修复'],
    ['first', '先看未通过的候选', '两轮执行已结束。点击「第 1 轮」，看看第一次修复遗漏了什么。', '核对证据'],
    ['failure', '打开失败用例', '点击红色失败用例，查看这组输入的预期、实际结果和测试日志。', '核对证据'],
    ['second', '查看修订后的结果', '日志说明了失败原因。现在点击「第 2 轮」，查看修订后的候选。', '核对证据'],
    ['changes', '比较修复前后', '点击「测试变化」，查看哪些失败被修复，以及是否出现新的失败。', '核对证据'],
    ['diff', '核对实际代码改动', '点击「代码差异」，对照平均值计算与空输入处理，核对补丁的修改范围。', '核对证据'],
    ['review', '记录你的审查', '测试通过后还需人工核对。点击「记录审查结论」，为这份补丁留下判断依据。', '人工审查'],
    ['review-form', '确认审查依据', '已填入体验用的审查示例。请阅读并按你的判断修改，再点击确认；此记录只用于教学案例。', '人工审查'],
    ['create-second', '再跑一次单轮修复', '已填好同一案例的单轮任务。点击「创建并执行」，与刚才的两轮修订进行对照。', '运行对照'],
    ['wait-second', '正在执行对照任务', '这次直接使用正确候选，只运行一轮。完成后自动准备两次运行的对照表。', '运行对照'],
    ['compare', '保存两次运行的对照', '已选中本次体验的两项任务。点击「保存对照报告」，固定测试结果、候选轮次和审查记录。', '运行对照'],
    ['export', '导出你的体验结果', '报告已保存。点击「导出 Markdown」，下载可复查的对照记录。', '导出记录'],
    ['complete', '已走完完整修复流程', '你已完成两次真实运行、失败定位、补丁审查和对照导出。任务与报告已保存在本机工作区。', '体验完成']
  ];
  let run = {active:false, stage:'create', first:'', second:'', report:''};
  try { const saved = JSON.parse(localStorage.getItem(key)); if (saved && stages.some(s => s[0] === saved.stage)) run = {...run, ...saved}; } catch {}
  let task, renderedRoute = '', target, allowed, lastTarget, submitting = false, problem = '', syncing = false;
  const view = $('#workspace-view');
  if (!view) return;
  const entry = document.createElement('section');
  entry.id = 'experience-guide'; entry.className = 'repair-tour-entry'; entry.setAttribute('aria-labelledby', 'experience-title');
  view.before(entry);
  const shade = document.createElement('div'); shade.className = 'repair-tour-shade'; shade.hidden = true;
  shade.innerHTML = '<svg aria-hidden="true"><path fill-rule="evenodd"></path></svg><div class="repair-tour-ring"></div>';
  document.body.append(shade);
  const card = document.createElement('section'); card.className = 'repair-tour-card'; card.hidden = true;
  card.setAttribute('role', 'region'); card.setAttribute('aria-label', '当前体验步骤');
  document.body.append(card);
  const store = () => { try { localStorage.setItem(key, JSON.stringify(run)); } catch {} };
  const stageIndex = () => stages.findIndex(s => s[0] === run.stage);
  function entryView() {
    entry.hidden = run.active;
    entry.innerHTML = `<div><span class="tour-eyebrow">D11 · 功能体验引导</span><h2 id="experience-title">跟着一个缺陷，走完一次修复。</h2><p>平均值函数教学案例 · 无需模型密钥 · 约 5 分钟</p><div class="tour-route"><span>运行修复</span><i>→</i><span>核对证据</span><i>→</i><span>人工审查</span><i>→</i><span>对照导出</span></div><details class="tour-source"><summary>案例来源与改编说明</summary><p>TheAlgorithms / Python · MIT。故意注入整除缺陷，空输入约定返回 0；用于体验流程，并非上游历史缺陷。</p><a href="https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/maths/average_mean.py" target="_blank" rel="noopener">查看原始函数 ↗</a></details></div><div class="tour-entry-action"><button type="button" data-tour="start" data-case-fill>一键导入案例并开始 <span aria-hidden="true">→</span></button>${run.first && run.stage !== 'complete' ? '<button type="button" data-tour="resume" class="secondary">继续上次体验</button>' : ''}<small>自动填入案例；每次执行与审查由你点击确认。</small></div>`;
  }
  function change(stage) {
    run.stage = stage; submitting = false; problem = ''; lastTarget = null;
    if (stage !== 'review-form') { $('#review-dialog').close(); delete $('#review-dialog').dataset.tourOpen; }
    store(); sync();
  }
  function expectedRoute() {
    const first = 'task/' + run.first;
    switch (run.stage) {
      case 'create': case 'create-second': return 'new?repository=' + sample;
      case 'wait-first': case 'first': return first;
      case 'failure': return first + '?attempt=1&tab=diff';
      case 'second': return first + '?attempt=1&tab=tests';
      case 'changes': return first + '?attempt=2&tab=tests';
      case 'diff': return first + '?attempt=2&tab=changes';
      case 'review': case 'review-form': return first + '?attempt=2&tab=diff';
      case 'wait-second': return 'task/' + run.second;
      case 'compare': return 'comparisons?repository=' + sample;
      case 'export': case 'complete': return 'comparison/' + run.report;
    }
  }
  // Evidence navigation may retain a test ID or phase query. Compare only the
  // keys this step requires; never select a task from the global recent list.
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
  function findTarget() {
    const stage = run.stage;
    if (stage === 'create' || stage === 'create-second') {
      const form = $('#task-form'); if (!form) return;
      fill(form, {repository:sample, title:stage === 'create' ? '开源算法案例 · 平均值精度修复' : '开源算法案例 · 单轮修复对照', mode:'offline', candidate:stage === 'create' ? 'progressive' : 'correct', max_attempts:stage === 'create' ? '2' : '1'});
      return form.querySelector('[type=submit]');
    }
    if (stage === 'first') return $('.attempt-tabs a[href*="attempt=1"]');
    if (stage === 'failure') return $('.test-row.fail');
    if (stage === 'second') return $('.attempt-tabs a[href*="attempt=2"]');
    if (stage === 'changes') return $('.patch-tabs a[href*="tab=changes"]');
    if (stage === 'diff') return $('.patch-tabs a[href*="tab=diff"]');
    if (stage === 'review') return $('#open-review');
    if (stage === 'review-form') {
      const dialog = $('#review-dialog');
      if (dialog.dataset.tourOpen !== run.first) {
        if (!dialog.open) dialog.show();
        dialog.dataset.tourOpen = run.first;
      }
      const form = $('#review-form');
      fill(form, {actor:'体验用户（教学审查）', decision:'approved', comment:'教学案例核对：平均值使用普通除法保留小数，空输入返回 0；第 2 轮回归与独立验收均通过。'});
      return form.querySelector('[type=submit]');
    }
    if (stage === 'compare') {
      const form = $('#comparison-form'); if (!form) return;
      fill(form, {title:'平均值精度修复 · 两轮与单轮对照'});
      form.querySelectorAll('[name=task_ids]').forEach(input => { input.checked = [run.first, run.second].includes(input.value); });
      if (form.querySelectorAll('[name=task_ids]:checked').length !== 2) throw Error('本次体验的任务暂不可用，请退出后检查任务记录。');
      return form.querySelector('[type=submit]');
    }
    if (stage === 'export') return $('.page-heading a[href*="format=markdown"]');
  }
  function renderCard() {
    const index = stageIndex(), stage = stages[index];
    const busy = run.stage.startsWith('wait-');
    const message = problem || (submitting ? '正在保存，请稍候…' : stage[2]);
    const signature = JSON.stringify([run.stage, message, Boolean(target), target?.disabled]);
    if (card.dataset.signature === signature) return;
    card.dataset.signature = signature;
    card.dataset.stage = run.stage;
    card.innerHTML = `<div class="tour-card-top"><span class="tour-eyebrow">${esc(stage[3])} <b>${Math.min(index + 1, 13)} / 13</b></span><button type="button" data-tour="exit" class="tour-exit" aria-label="退出体验引导">退出体验 ×</button></div><div class="tour-progress" role="progressbar" aria-label="体验进度" aria-valuemin="0" aria-valuemax="13" aria-valuenow="${Math.min(index,13)}"><span style="width:${index / 13 * 100}%"></span></div><h2>${esc(stage[1])}</h2><p role="status" ${problem ? 'class="tour-problem"' : ''}>${esc(message)}</p>${run.stage === 'complete' ? '<button type="button" data-tour="exit">完成体验，查看报告</button>' : problem ? '<button type="button" data-tour="retry">重新检查本步</button>' : `<div class="tour-hint">${busy ? '<span class="tour-spinner" aria-hidden="true"></span> 等待真实执行结果' : target?.disabled ? '运行器未就绪，请稍候或退出后检查运行器。' : '只需操作高亮区域，其余内容已暂时锁定。'}</div>`}`;
  }
  function position() {
    if (!run.active) return;
    const width = innerWidth, height = innerHeight;
    const rect = (allowed || target)?.getBoundingClientRect();
    const pad = 7;
    const hole = rect ? {left:Math.max(0,rect.left-pad), top:Math.max(0,rect.top-pad), right:Math.min(width,rect.right+pad), bottom:Math.min(height,rect.bottom+pad)} : {left:0,top:0,right:0,bottom:0};
    // Keep the evidence being discussed readable, while only the outlined
    // action accepts input. The surrounding navigation stays behind the mask.
    const contextSelector = {first:'.attempt-bar',failure:'.diff-scroll',second:'.test-details',changes:'.test-details',diff:'.test-changes',review:'.diff-scroll',compare:'.comparison-choices',export:'.comparison-columns'}[run.stage];
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
      (allowed || target).scrollIntoView({block:'center', behavior:'instant'});
      target.focus({preventScroll:true});
      requestAnimationFrame(() => {
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
      document.body.classList.toggle('repair-tour-active', run.active);
      target = allowed = null;
      if (!run.active) return;
      if (!$('#workspace-error').hidden) problem = $('#error-message').textContent;
      if (run.stage === 'complete') { renderCard(); position(); return; }
      const expected = expectedRoute();
      if (!onRoute(expected)) { location.hash = expected; renderCard(); position(); return; }
      if (view.inert || view.getAttribute('aria-busy') === 'true' || renderedRoute !== location.hash.slice(1)) { renderCard(); position(); return; }
      if (run.stage.startsWith('wait-')) {
        if (task?.id === (run.stage === 'wait-first' ? run.first : run.second)) {
          if (task.status === 'succeeded') { const next = run.stage === 'wait-first' ? 'first' : 'compare'; syncing = false; change(next); return; }
          if (['failed','cancelled','interrupted','timed_out'].includes(task.status)) problem = '本次任务未完成。请退出体验，在任务页查看原因；修复运行器后可重新开始。';
        }
      } else target = findTarget();
      allowed = run.stage === 'review-form' ? $('#review-form') : target;
      const message = $(run.stage === 'review-form' ? '#review-form .form-message' : '#workspace-view .form-message');
      if (message?.textContent.trim()) problem = message.textContent.trim();
      if (!$('#workspace-error').hidden) problem = $('#error-message').textContent;
      renderCard(); focusTarget(); position();
    } catch (error) { problem = error.message; renderCard(); position(); }
    finally { syncing = false; }
  }
  function exit() {
    run.active = false; submitting = false; store();
    if ($('#review-dialog').open) $('#review-dialog').close();
    delete $('#review-dialog').dataset.tourOpen;
    sync(); document.documentElement.style.removeProperty('--tour-card-height');
    entry.querySelector('button').focus({preventScroll:true});
  }
  function start(resume) {
    if (!resume) run = {active:true,stage:'create',first:'',second:'',report:''};
    else run.active = true;
    problem = ''; lastTarget = null; store(); sync();
  }
  function permitted(element) { return card.contains(element) || Boolean(allowed?.contains(element)); }
  // Capture events before workspace handlers. A visual mask alone would still
  // allow keyboard activation, label clicks and accidental form submissions.
  for (const type of ['pointerdown','click','dblclick','change','input','submit']) {
    document.addEventListener(type, event => {
      if (!run.active || permitted(event.target)) return;
      // Submit is fired on the form, rather than its highlighted submit button.
      if (type === 'submit' && target?.form === event.target && event.submitter === target) return;
      event.preventDefault(); event.stopImmediatePropagation();
    }, true);
  }
  document.addEventListener('keydown', event => {
    if (!run.active) return;
    if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); exit(); return; }
    if (event.key === 'Tab') {
      const candidates = [...(allowed ? (allowed.matches('button,a,input,select,textarea') ? [allowed] : allowed.querySelectorAll('button,a,input,select,textarea')) : []), ...card.querySelectorAll('button')].filter(el=>!el.disabled && el.getClientRects().length);
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
      submitting = true; renderCard();
      fetch(url, {cache:'no-store'}).then(async response => {
        if (!response.ok) throw Error('导出暂时失败，请点击「重新检查本步」后重试。');
        const blob = await response.blob(), link = document.createElement('a');
        link.href = URL.createObjectURL(blob); link.download = 'repair-comparison-' + run.report + '.md'; link.hidden = true;
        card.append(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(link.href), 1000);
        change('complete');
      }).catch(error => { problem = error.message; submitting=false; renderCard(); position(); });
      return;
    }
    const next = {first:'failure',failure:'second',second:'changes',changes:'diff',diff:'review',review:'review-form'}[run.stage];
    if (next) queueMicrotask(() => change(next));
  });
  document.addEventListener('submit', event => {
    if (!run.active || !['task-form','review-form','comparison-form'].includes(event.target.id)) return;
    submitting = true; renderCard(); position();
  });
  window.addEventListener('repair:render', event => {
    task = event.detail.task; renderedRoute = event.detail.route;
    sync();
  });
  window.addEventListener('repair:task-created', event => {
    if (!run.active) return;
    if (run.stage === 'create') { run.first = event.detail.id; change('wait-first'); }
    else if (run.stage === 'create-second') { run.second = event.detail.id; change('wait-second'); }
  });
  window.addEventListener('repair:review-saved', event => { if (run.active && run.stage === 'review-form' && event.detail.id === run.first) change('create-second'); });
  window.addEventListener('repair:comparison-created', event => { if (run.active && run.stage === 'compare') {run.report = event.detail.id; change('export');} });
  window.addEventListener('hashchange', () => {lastTarget=null; sync();});
  window.addEventListener('resize', position);
  window.addEventListener('scroll', position, true);
  // Form errors and disabled buttons can change without a full route render.
  new MutationObserver(() => { if (run.active) {submitting=false; sync();} }).observe(view, {childList:true,subtree:true,attributes:true,attributeFilter:['disabled']});
  new MutationObserver(() => {if(run.active) {submitting=false; sync();}}).observe($('#review-form .form-message'), {childList:true});
  new MutationObserver(() => {if(run.active) sync();}).observe($('#workspace-error'), {childList:true,subtree:true,attributes:true,attributeFilter:['hidden']});
  window.LabRepairTour = {version:2, get state() {return {...run};}};
  sync();
})();
