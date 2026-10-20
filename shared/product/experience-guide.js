/* Guidance and attributed case prefills; never auto-submit business or model requests. */
(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const first = rows => Array.isArray(rows) ? rows[0] : null;
  const recent = (state, key, prefix, fallback, suffix='') => first(state?.[key])?.id ? prefix + first(state[key]).id + suffix : fallback;
  const projects = {
    '01-repair-agent': {id:'D11',name:'测试与缺陷修复',minutes:'8–12',api:'repair',home:'overview',steps:[
      {title:'看懂待修复的缺陷',route:()=> 'repositories',target:'.repo-cards, .table-scroll, h1',do:'打开一个代码快照，查看原函数、缺陷说明与测试输入。先尝试解释：哪个边界会出错？',expect:'能指出至少一个失败输入，并知道候选只能修改哪个文件。'},
      {title:'跑一次“失败后修订”',route:()=> 'new',target:'#task-form',do:'选离线预置候选，将策略改为“先失败再修订”，候选轮数选2，再提交任务。不需要模型密钥。',expect:'任务先复现缺陷，再保存失败候选和修订候选；可在任务记录中看到实际状态。'},
      {title:'把测试、日志与改动对上',route:s=>recent(s,'tasks','task/','tasks'),target:'.tabs, .task-tabs, h1',do:'在刚创建的任务中切换候选轮次，打开“测试变化”，再点击失败用例查看日志与代码差异。',expect:'能分清原有失败、新修复和新增失败，而不只看一个通过数量。'},
      {title:'亲自记录补丁审查',route:s=>recent(s,'tasks','task/','tasks'),target:'[data-review], #open-review, h1',do:'选择测试已通过的候选，打开审查窗口，填写核对人、结论和具体依据。失败候选应不能被认可。',expect:'任务出现绑定本次候选的人工结论；“测试通过”和“人工认可”分别显示。'},
      {title:'对照两次真实运行',route:()=> 'comparisons',target:'#comparison-form, h1',do:'再为同一快照创建一次离线任务。到“任务对照”选中两项同环境运行，保存报告并逐项比较。',expect:'报告固定两次运行的测试、轮次和当时审查；条件不同会被明确拒绝。'},
      {title:'带走可复核的记录',route:s=>recent(s,'comparisons','comparison/','tasks'),target:'.page-heading, h1',do:'在对照报告下载JSON或Markdown；也可回到任务下载补丁与完整JSON，再刷新页面核对记录。',expect:'本机得到实际下载文件，刷新后任务和报告仍能打开。'}]},
    '02-process-rag': {id:'D01',name:'工艺资料检索',minutes:'8–12',api:'process',home:'overview',sample:'samples/import-check.md',sampleLabel:'下载自编教学资料',steps:[
      {title:'导入一份可定位的资料',route:()=> 'upload',target:'#upload-form',do:'点击开源案例的一键填入，将PLA材料资料放入上传表单；检查后提交建立索引。也可下载原教学资料。',expect:'资料处理成功，能打开原文与版本。若正在使用嵌入索引，导入可能调用你已配置的服务。'},
      {title:'用独特关键词检索',route:()=> 'search',target:'#search-form',do:'若使用开源案例，点击一键填入检索问题或输入“Generic PLA print temperature”；若使用旧教学资料，输入“ZXDOC 声发射检验”。运行检索；再试一个资料中没有的问题，比较有证据与资料不足的表现。',expect:'匹配结果能对应刚上传的内容；资料不足时不会凭空给出生产参数。'},
      {title:'打开证据对应的原文',route:s=>recent(s,'searches','search-result/','history'),target:'.evidence, .source, h1',do:'从刚才的检索记录点击来源，核对原句、位置及适用范围。留意原文中要求另行确认的条件。',expect:'你能解释答案依据哪段文字，以及原文没有支持什么。'},
      {title:'形成并修改工艺草案',route:s=>recent(s,'searches','search-result/','history'),target:'.page-heading, h1',do:'从有证据的结果形成离线草案，进入草案编辑。离线内容是摘编，缺失参数应保留待确认。',expect:'草案与本次检索来源绑定，修改后产生需要重新核对的版本。'},
      {title:'逐工序核对与导出',route:s=>recent(s,'drafts','draft/','drafts'),target:'form, h1',do:'逐工序核对条件、参数与来源，填写实际判断依据，再使用页面导出入口。',expect:'没有依据的内容可以退回；下载对应已保存版本，不能把未核对草案当成正式工艺。'},
      {title:'观察来源变化的影响',route:()=> 'documents',target:'h1',do:'选择体验资料上传新版本，修改一处原句；再回到旧检索与旧草案查看来源变化提示。',expect:'旧版本仍可追溯，当前内容与旧证据能被区分。'}]},
    '03-mlops': {id:'D02',name:'模型发布与监控',minutes:'10–15',api:'mlops',home:'overview',steps:[
      {title:'创建有标记的教学数据',route:()=> 'datasets',target:'#sample-form',do:'点击一键填入Iris公开数据，检查4个特征和0/1标签后保存；或继续使用原合成教学数据入口。',expect:'列表出现真实数据快照、列结构和内容哈希；合成数据不代表业务效果。'},
      {title:'启动训练并看真实评估',route:()=> 'train',target:'#train-form',do:'选择刚创建的训练数据，保留固定种子，提交训练。到实验记录查看划分、指标与制品。',expect:'训练任务有实际状态与结果；能区分训练数据、测试指标和保存制品。'},
      {title:'审核后才加载模型',route:()=> 'models',target:'h1',do:'打开刚训练的模型，核对指标与数据血缘，填写人工审核，再进入部署页面加载它。',expect:'未审核模型不能直接加载；服务页显示当前实际活动版本。'},
      {title:'发起一次真实预测',route:()=> 'service',target:'form, h1',do:'查看特征顺序，输入一组数值并请求预测。记录响应中的模型版本与制品哈希。',expect:'返回实际模型输出，版本与当前活动模型一致。'},
      {title:'比较三类监控窗口',route:()=> 'datasets',target:'#sample-form',do:'若用Iris训练，在案例材料中选择原样、合成特征偏移、无标签监控窗口，分别填入并保存；再到监控页评估。它们重复使用教学数据，不作为真实泛化评价；无标签不能计算准确率。',expect:'漂移、缺失与有标签质量有不同含义；不因漂移就直接断言模型变差。'},
      {title:'处理告警并追溯版本',route:()=> 'alerts',target:'h1',do:'打开一条实际告警并记录处理依据。训练、审核第二个版本后，可在服务页体验历史回滚并重新预测。',expect:'告警保留处理记录，回滚后预测使用真正切换的版本，而非只改显示文字。'}]},
    '04-video-understanding': {id:'D12',name:'视频理解与证据',minutes:'6–10',api:'video',home:'studio',steps:[
      {title:'导入一段可播放的素材',route:()=> 'studio',target:'#sample-import',do:'点击开源案例的一键填入，选择公开视频后亲自点击“上传并校验”；原教学示例也可使用。',expect:'看到实际画面与时长，刷新后素材仍在。'},
      {title:'让服务器固定采样',route:()=> 'studio',target:'#sampling',do:'选择采样帧数，创建采样任务，等待任务成功。采样由服务器从原片解码，不依赖你当前播放器停在哪。',expect:'出现真实缩略图、帧编号和原片时间；可以切换历史采样。'},
      {title:'从一帧回到原片',route:()=> 'studio',target:'.frame, #player',do:'点击一张缩略图，观察播放器时间与画面；再在播放器中查看前后几秒，检查单帧遗漏了什么。',expect:'原片跳到该帧附近，证据有可核对的时间位置。'},
      {title:'体验记录与可选模型问答',route:()=> 'studio',target:'#question-form',do:'先选离线模式保存采样观察记录。配置兼容视觉服务后，才选择模型问答；模型模式会发送采样帧。',expect:'离线记录明确不含视觉推理，模型失败会显示真实错误。'},
      {title:'回看并核对证据',route:()=> 'records',target:'h1',do:'打开刚保存的记录，逐帧回看。只有实际模型回答才有语义证据核对；离线记录不冒充模型答案。',expect:'能从记录回到原片，核对结果绑定对应采样与回答。'},
      {title:'导出并检查旧结果',route:()=> 'records',target:'h1',do:'下载记录JSON；返回观察台改变采样，再查看旧记录的状态和原时间映射。',expect:'下载包含实际证据映射，采样变化不会悄悄复用旧回答。'}]},
    '05-requirements': {id:'D09',name:'需求分析与用例',minutes:'8–12',api:'requirements',home:'overview',steps:[
      {title:'从考勤需求样例开始',route:()=> 'import',target:'#fill-sample',do:'点击开源案例的一键填入，阅读RealWorld API中文选译，再保存需求；原考勤样例仍可使用。',expect:'需求有服务端版本与分段编号，内容不是只留在浏览器中。'},
      {title:'生成一组待核对用例',route:s=>recent(s,'documents','document/','documents'),target:'#analyze-form',do:'打开刚导入的需求，先选规则模式，提交分析。没有模型密钥也能体验原文到用例的流程。',expect:'得到绑定需求版本的用例集；规则输出明确保留待确认内容。'},
      {title:'编辑步骤、输入与预期',route:s=>recent(s,'sets','suite/','sets'),target:'#case-form, .case-editor, h1',do:'选一条用例，分别修改操作步骤、输入和预期。等待草稿保存，刷新确认，再提交新版本。',expect:'能区分自动保存的草稿与已提交版本，提交后需重新核对。'},
      {title:'沿追踪关系回看原文',route:s=>recent(s,'sets','suite/','sets','?mode=trace'),target:'h1',do:'切换追踪矩阵，点击关联原文。检查该用例覆盖哪个需求，以及预期结果是否真的有依据。',expect:'每条关联可定位到具体原文，不把“有链接”等同于语义正确。'},
      {title:'人工核对并发布',route:s=>recent(s,'sets','suite/','sets','?mode=quality'),target:'h1',do:'逐条核对用例，记录人和判断依据。完成当前版本核对后，再使用发布入口。',expect:'未核对或来源过期的用例集会被阻止发布，已发布快照保持固定。'},
      {title:'导出后体验需求变更',route:s=>recent(s,'sets','suite/','sets'),target:'h1',do:'下载CSV/JSON已保存版本；修订原需求中的一个条件，再查看变更影响和旧用例的来源状态。',expect:'导出文件可复查，新需求不会静默覆盖旧版本的证据与审核。'}]},
    '06-literature': {id:'D13',name:'文献研读与综述',minutes:'12–18',api:'literature',home:'overview',steps:[
      {title:'建立有边界的研究专题',route:()=> 'new',target:'#project-form',do:'点击一键填入开放可视化论文的专题设置。阅读研究问题和提纲，亲自确认范围后保存。',expect:'专题保存了问题、筛选标准和提纲。只体验流程时，可使用明确标为虚构的教学文本。'},
      {title:'导入并筛选一篇材料',route:()=> 'import',target:'#fill-sample',do:'从开源案例选择seaborn或ArviZ，一键填入论文文本和出处，检查后导入；两篇分别保存。回到专题记录纳入理由。',expect:'原文件、范围与版本可追溯；摘要、摘记与提供的原文有明确标记。'},
      {title:'读原文并整理证据',route:s=>recent(s,'projects','project/','overview','?tab=matrix'),target:'h1',do:'在专题发起离线阅读，等待摘录进入证据矩阵。逐条打开原文，将方法、发现、局限分类并亲自核对。',expect:'引文有真实位置；离线摘录不自动获得语义确认。'},
      {title:'比较文献与证据条件',route:s=>recent(s,'projects','project/','overview','?tab=compare'),target:'h1',do:'查看文献对照；有两条有效证据后，可在“证据关系”记录支持、分歧或补充及其条件。',expect:'你能看到缺失类别和不同实验条件；关系是人工判断，不是自动科研结论。'},
      {title:'检查就绪后生成章节',route:s=>recent(s,'projects','project/','overview','?tab=audit'),target:'h1',do:'打开写作前检查，按阻断项返回补齐。确认提纲和全部证据后，到章节草案选择离线编排。',expect:'结构不满足时不生成；离线结果明确是摘编，不宣称完成高质量综述。'},
      {title:'核对每条论述的支持关系',route:s=>recent(s,'drafts','draft/','overview'),target:'h1',do:'编辑章节并提交版本；在“引用核对”逐条打开证据，检查论述是否超出原文条件，再保存判断。',expect:'编辑后旧核对失效，缺少支持或来源过期的草案不能发布。'},
      {title:'发布、导出并验证来源变化',route:()=> 'releases',target:'h1',do:'完成当前版本审核后发布，下载Markdown、BibTeX与证据JSON。再修订材料，观察旧草案过期与已发布快照保持不变。',expect:'导出对应实际版本，原文—证据—论述—人工记录可以串联复查。'}]}
  };
  const folder = location.pathname.split('/').filter(Boolean).find(part => projects[part]);
  const config = projects[folder];
  if (!config) return;
  let catalog=[], selectedCase='', caseBusy=false, caseMessage='', caseError='', dirtyForms=new WeakSet();
  let view, root, context={}, saved={}, observer, pendingFocus=false, request=0, signature='', timer, lastRead=0;
  const storageKey = 'lab-experience-v1-' + config.id;
  try { saved = JSON.parse(localStorage.getItem(storageKey) || '{}'); } catch { saved = {}; }
  let current = Number.isInteger(saved.current) ? Math.max(0,Math.min(config.steps.length-1,saved.current)) : 0;
  let active = saved.active === true, done = Array.isArray(saved.done) ? saved.done.filter(i=>Number.isInteger(i)&&i>=0&&i<config.steps.length) : [];
  function save(){try{localStorage.setItem(storageKey,JSON.stringify({current,active,done}));}catch{/* Guidance remains usable when browser storage is disabled. */}}
  function route(){return location.hash.slice(1)||config.home;}
  function clearHighlight(){document.querySelectorAll('.experience-target').forEach(el=>el.classList.remove('experience-target'));}
  function locate(){
    if(!active||view.inert||view.getAttribute('aria-busy')==='true')return;
    const step=config.steps[current], desired=step.route(context), same=route().split('?')[0]===desired.split('?')[0];
    if(!same)return;
    const target=step.target.split(',').map(selector=>view.querySelector(selector.trim())).find(Boolean);
    if(!target)return;
    clearHighlight();target.classList.add('experience-target');
    target.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
    if(!target.hasAttribute('tabindex')&&!target.matches('input,select,textarea,button,a'))target.tabIndex=-1;
    target.focus({preventScroll:true});pendingFocus=false;
  }
  function render(force=false){
    const home=route().split('?')[0]===config.home,step=config.steps[current], destination=step.route(context);
    const nextSignature=JSON.stringify([active,current,done,home,destination,catalog.length,selectedCase,caseBusy,caseMessage,caseError]);
    if(!force&&signature===nextSignature){if(pendingFocus)locate();return;}
    signature=nextSignature;
    root.className='experience-guide'+(active?' experience-active':'')+(!home&&!active?' experience-compact':'');
    root.innerHTML=`<div class="experience-heading"><div><span class="experience-kicker">${esc(config.id)} · 功能体验引导</span><h2 id="experience-title">${active?'跟着做一遍 · '+esc(config.name):'第一次体验？从这里走完一次完整流程。'}</h2><p>${active?`第 ${current+1} / ${config.steps.length} 步 · 已自行确认 ${done.length} 步`:`约 ${esc(config.minutes)} 分钟 · 开放案例可一键填入 · 每一步都能打开真实功能`}</p></div><div class="experience-head-actions">${active?'<button type="button" data-experience="pause" class="experience-secondary">收起引导</button>':`<button type="button" data-experience="start">${done.length||current?'继续体验':'跟着做一遍'} <span aria-hidden="true">→</span></button>`}</div></div>${casePanel()}${active?`<div class="experience-layout"><div class="experience-current"><div class="experience-number" aria-hidden="true">${String(current+1).padStart(2,'0')}</div><div><h3 tabindex="-1">${esc(step.title)}</h3><p>${esc(step.do)}</p><div class="experience-expected"><strong>应该看到什么</strong><p>${esc(step.expect)}</p></div><div class="experience-actions"><a href="#${esc(destination)}" data-experience="go" class="experience-primary">打开本步功能</a><button type="button" data-experience="locate" class="experience-secondary">定位操作位置</button>${config.sample&&current===0?`<a href="${esc(config.sample)}" download>${esc(config.sampleLabel)}</a>`:''}</div></div></div><details class="experience-map" ${matchMedia('(min-width: 900px)').matches?'open':''}><summary>查看全部 ${config.steps.length} 步</summary><ol>${config.steps.map((s,i)=>`<li><button type="button" data-experience-step="${i}" ${current===i?'aria-current="step"':''}><span>${done.includes(i)?'✓':i+1}</span>${esc(s.title)}</button></li>`).join('')}</ol></details></div><div class="experience-footer"><p>按你的实际体验确认进度；引导不代替项目中的测试、审核或发布。</p><div class="experience-actions"><button type="button" data-experience="previous" class="experience-secondary" ${current===0?'disabled':''}>上一步</button><button type="button" data-experience="next">${current===config.steps.length-1?'我已体验，完成引导':'已看到预期结果，下一步'}</button></div></div>`:`${home?`<div class="experience-preview">${config.steps.slice(0,3).map((s,i)=>`<span><b>${i+1}</b>${esc(s.title)}</span>`).join('')}<span class="experience-more">… 共 ${config.steps.length} 步</span></div>`:''}${done.length===config.steps.length?'<p class="experience-complete">你已自行确认本轮体验。可以重新体验，或打开完整图文指南继续深入。</p>':''}<div class="experience-links"><a href="#guide">完整图文指南</a>${done.length||current?'<button type="button" class="experience-text" data-experience="reset">重新体验</button>':''}</div>`}`;
    if(pendingFocus)locate();
  }
  async function update(){
    if(active&&Date.now()-lastRead>1100){const ticket=++request;lastRead=Date.now();try{const response=await fetch(config.api==='process'?'/api/process/workspace':'/api/'+config.api+'-workspace/workspace',{cache:'no-store'});if(response.ok){const data=await response.json();if(ticket!==request)return;context=data;}}catch{/* Existing business error messages remain authoritative. */}}
    render();
  }
  function chosenCase(){return catalog.find(item=>item.id===selectedCase)||catalog[0];}
  function casePanel(){
    const item=chosenCase();
    if(!item)return `<div class="experience-case"><strong>开源案例</strong><p>${caseError?esc(caseError):'正在读取随项目打包的开放案例…'}</p><a href="../../index.html#model-settings">统一模型 API 设置 →</a></div>`;
    return `<div class="experience-case"><div><span class="experience-kicker">开源 / 开放资料案例 · ${esc(item.license)}</span><h3>${esc(item.title)}</h3><p>${esc(item.description)}</p><small>来源版本：${esc(item.revision.length===40?item.revision.slice(0,12):item.revision)}</small><div class="experience-case-links"><a href="${esc(item.source_url)}" target="_blank" rel="noopener noreferrer">查看原始来源 ↗</a><a href="../../docs/OPEN_EXAMPLES.md">归属与改编说明</a>${item.file?`<a href="${esc(item.file)}" download>下载案例材料</a>`:''}</div></div><div class="experience-case-controls">${catalog.length>1?`<label>${config.id==='D13'?'选择开放论文':'选择案例材料'}<select data-case-choice>${catalog.map(row=>`<option value="${esc(row.id)}" ${row.id===item.id?'selected':''}>${esc(row.title)}</option>`).join('')}</select></label>`:''}<button type="button" data-case-fill ${caseBusy?'disabled':''}>${caseBusy?'正在填入…':config.id==='D13'&&current===0?'一键填入专题设置':'一键填入案例'}</button><a href="../../index.html#model-settings">统一模型 API 设置 →</a><small>只准备输入。请检查后亲自提交；不会自动调用模型或审核发布。</small></div><p class="experience-case-message" role="status">${esc(caseMessage||caseError)}</p></div>`;
  }
  async function fillCase(){
    if(caseBusy)return;
    const item=chosenCase();if(!item)return;
    const existing=view.querySelector('form');
    if(existing&&dirtyForms.has(existing)&&!confirm('当前表单有你编辑的内容，是否用开源案例替换？'))return;
    caseBusy=true;caseMessage='';caseError='';render(true);
    try{
      let options=item;
      if(config.id==='D13'&&current===0)options={route:'new',form:'#project-form',fields:{title:'开放案例 · 科研可视化工具的证据对照',question:'seaborn与ArviZ分别服务哪些分析任务？它们的接口、使用条件和局限有哪些差异？仅根据这两篇论文作有条件的对照，不比较未报告的性能。',inclusion:'纳入本案例两篇JOSS开放论文，保留各自研究对象。',exclusion:'不纳入无原文材料，不推测未报告的效果。',outline:'研究对象与方法\n主要能力与使用条件\n局限与证据空白'}};
      if(config.id==='D01'&&active&&current===1)options={route:'search',form:'#search-form',fields:{query:'Generic PLA print temperature 适用机器'}};
      let content;
      if(options.file){
        const response=await fetch(options.file,{cache:'no-store'});if(!response.ok)throw Error('案例材料读取失败，请刷新重试。');
        content=await response.arrayBuffer();
        if(!crypto.subtle)throw Error('案例校验需要通过localhost或HTTPS访问。');
        const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',content))].map(x=>x.toString(16).padStart(2,'0')).join('');
        if(digest!==options.sha256)throw Error('案例材料与来源清单的哈希不一致，请更新完整源码。');
      }
      const navigating=route()!==options.route;
      if(navigating){location.hash=options.route;await new Promise(resolve=>setTimeout(resolve,80));}
      let form;
      for(let i=0;i<120;i++){
        form=view.querySelector(options.form);
        if(form&&!view.inert&&view.getAttribute('aria-busy')!=='true'&&route()===options.route&&(!view.dataset.route||view.dataset.route===options.route))break;
        form=null;await new Promise(resolve=>setTimeout(resolve,50));
      }
      if(!form)throw Error('目标表单尚未就绪，请先处理页面错误，再点击填入。');
      const fileInput=options.input_selector?form.querySelector(options.input_selector):form.querySelector('input[type=file]');
      if(fileInput)fileInput.value='';
      for(const [name,value] of Object.entries(options.fields||{})){
        const input=form.elements.namedItem(name);if(!input)throw Error('案例字段与页面不一致，请更新后刷新。');
        input.value=value;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));
      }
      if(options.text_field){const input=form.elements.namedItem(options.text_field);input.value=new TextDecoder('utf-8',{fatal:true}).decode(content);input.dispatchEvent(new Event('input',{bubbles:true}));}
      else if(content&&fileInput){const files=new DataTransfer();files.items.add(new File([content],options.file.split('/').pop(),{type:options.file.endsWith('.webm')?'video/webm':'text/plain'}));fileInput.files=files.files;fileInput.dispatchEvent(new Event('change',{bubbles:true}));}
      if(config.id==='D13'&&current===0)form.elements.outline_confirmed.checked=false;
      dirtyForms.delete(form);form.scrollIntoView({block:'center'});form.querySelector('input,textarea,select')?.focus({preventScroll:true});
      caseMessage='案例已填入，请检查后点击页面提交按钮。未自动提交、调用模型或确认审核。';
    }catch(error){caseError=error.message;}
    finally{caseBusy=false;render(true);}
  }
  function initialize(){
    view=document.querySelector('#workspace-view, #rag-view, #view');if(!view)return;
    root=document.createElement('section');root.id='experience-guide';root.setAttribute('aria-labelledby','experience-title');view.before(root);
    root.addEventListener('change',event=>{if(event.target.matches('[data-case-choice]')){selectedCase=event.target.value;caseMessage='';render(true);}});
    document.addEventListener('input',event=>{if(event.isTrusted&&event.target.closest('form'))dirtyForms.add(event.target.closest('form'));});
    root.addEventListener('click',event=>{
      if(event.target.closest('[data-case-fill]')){fillCase();return;}
      const stepButton=event.target.closest('[data-experience-step]');
      if(stepButton){current=Number(stepButton.dataset.experienceStep);save();render(true);root.querySelector('h3')?.focus();return;}
      const button=event.target.closest('[data-experience]');if(!button)return;
      switch(button.dataset.experience){
        case 'start':active=true;lastRead=0;save();render(true);update();root.querySelector('h3')?.focus();break;
        case 'pause':active=false;save();clearHighlight();render(true);root.querySelector('[data-experience="start"]')?.focus();break;
        case 'previous':current=Math.max(0,current-1);save();render(true);root.querySelector('h3')?.focus();break;
        case 'next':if(!done.includes(current))done.push(current);if(current===config.steps.length-1)active=false;else current++;lastRead=0;save();clearHighlight();render(true);update();(root.querySelector('h3')||root.querySelector('button'))?.focus();break;
        case 'reset':current=0;done=[];active=true;save();clearHighlight();render(true);root.querySelector('h3')?.focus();break;
        case 'go':pendingFocus=true;lastRead=0;setTimeout(()=>update(),100);break;
        case 'locate':pendingFocus=true;if(route().split('?')[0]!==config.steps[current].route(context).split('?')[0])location.hash=config.steps[current].route(context);else locate();break;
      }
    });
    window.addEventListener('hashchange',()=>{clearHighlight();update();});
    matchMedia('(min-width: 900px)').addEventListener('change',()=>render(true));
    observer=new MutationObserver(records=>{if(records.every(record=>record.type==='attributes'))return;clearTimeout(timer);timer=setTimeout(update,180);});
    observer.observe(view,{childList:true,subtree:true});
    render(true);if(active)update();
    fetch('/shared/examples/catalog.json',{cache:'no-store'}).then(response=>{if(!response.ok)throw Error();return response.json();}).then(value=>{catalog=value.cases.filter(item=>item.project===config.id);selectedCase=catalog[0]?.id||'';render(true);}).catch(()=>{caseError='案例清单暂不可用，请刷新重试；仍可使用原功能导入自己的材料。';render(true);});
  }
  window.LabExperienceGuide={version:1,projects};
  initialize();
})();
