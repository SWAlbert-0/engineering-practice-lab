'use strict';
(() => {
  const h = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels = {reproduced:'正控复现成功',not_reproduced:'缺陷未复现',input_out_of_scope:'输入超限',model_error:'请求失败或超时',budget_exhausted:'候选被拒，预算耗尽',not_eligible_not_reproduced:'未进入模型修复',passed:'通过',failure:'失败',error:'错误',skipped:'跳过',rejected:'协议拒绝'};
  const label = value => labels[value] || value || '未记录';
  const base = 'research-data/';
  const cache = new Map();
  async function read(name) {
    if (cache.has(name)) return cache.get(name);
    const response = await fetch(base + name, {cache:'no-store'});
    if (!response.ok) throw Error('实验记录读取失败，请点击“重新读取”重试。');
    const data = await response.json();
    cache.set(name, data);
    return data;
  }
  const table = (heads, rows) => `<div class="table-scroll"><table><thead><tr>${heads.map(x=>`<th scope="col">${h(x)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(x=>`<td>${x}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  const heading = (title, description, action='') => `<header class="page-heading"><div><h1>${h(title)}</h1><p>${h(description)}</p></div><div class="actions">${action}</div></header>`;
  const download = (file, text) => `<a class="button secondary" href="${base}${h(file)}" download>${h(text)}</a>`;
  const code = value => `<code>${h(value ?? '未记录')}</code>`;
  const options = (values, selected) => values.map(([v,l])=>`<option value="${h(v)}" ${v===selected?'selected':''}>${h(l)}</option>`).join('');

  function overview(index, query) {
    const project = query.get('project') || '', status = query.get('status') || '';
    const rows = index.cases.filter(c=>(!project || c.project===project) && (!status || c.status===status || c.model_status===status));
    const summary = index.summary;
    return heading('真实仓库实验',`BugsInPy · ${index.date} 归档 · 只读查看实验结果`,download('index.json','下载实验索引')) +
      `<section class="paper evaluation-scope"><h2>先看复现，再看模型修复</h2><p>固定选取 5 个仓库的 30 个历史缺陷。正控使用上游修复，模型候选单独验证；全部样本保留，包括未复现和请求失败。</p><div class="evaluation-counts"><div><span>正控复现 / 固定样本</span><strong>${summary.reproduction.reproduced} / ${index.cases.length}</strong></div><div><span>模型候选通过公共测试</span><strong>${summary.model_diagnostic.test_plausible}</strong></div><div><span>语义修复率</span><strong>尚无法判断</strong></div></div><p class="muted">本轮模型为 Qwen3-0.6B；输入限制、超时与协议错误影响了实验。模型总用量和费用未完整记录。页面不会发起模型调用。</p></section>` +
      `<section class="section research-cases"><h2>查看缺陷与证据</h2><form id="research-filter" class="list-filter"><label>仓库<select name="project" aria-label="仓库">${options([['','全部仓库'],...Array.from(new Set(index.cases.map(c=>c.project))).map(p=>[p,p])],project)}</select></label><label>实验结果<select name="status" aria-label="实验结果">${options([['','全部结果'],...['reproduced','not_reproduced','input_out_of_scope','model_error','budget_exhausted','not_eligible_not_reproduced'].map(s=>[s,label(s)])],status)}</select></label><button type="submit" class="secondary">筛选</button><a href="#research">清除筛选</a></form><p role="status">显示 ${rows.length} / ${index.cases.length} 个缺陷</p>` +
      (rows.length ? table(['缺陷 / 上游修复说明','正控复现','模型诊断'],rows.map(c=>[`<a href="#research/${h(c.id)}${query.size?'?'+h(query.toString()):''}"><strong>${h(c.id)}</strong></a><small>${h(c.upstream_fix_title)}</small>`,h(label(c.status)),h(label(c.model_status))])) : '<p class="paper">没有符合条件的记录，请更换筛选条件。</p>') +
      `</section><aside class="note"><strong>如何理解结果</strong><p>正控成功只说明缺陷版与上游修复版在指定环境中呈现不同测试结果。当前模型输入文件由上游修改范围提供，并未验证自动全仓定位能力；公共测试通过也不等于语义正确。</p><a href="../../docs/RESEARCH_EVALUATION.md">查看实验方法与限制 →</a></aside>`;
  }

  function detail(data, query) {
    const c = data.case, reproduction = data.reproduction;
    const pairs = Object.entries(data.variants);
    const testRows = phase => {
      const ids = new Set(pairs.flatMap(([,v])=>(v.phases[phase]?.tests || []).map(t=>t.id)));
      return [...ids].map(id=>[code(id),...['buggy','upstream_repair'].map(v=>{
        const tests = data.variants[v]?.phases[phase]?.tests?.filter(t=>t.id===id) || [];
        return h(tests.length?tests.map(t=>label(t.status)).join(' / '):'未运行 / 无记录');
      })]);
    };
    const model = data.model;
    const unreproduced = c.status==='not_reproduced' ? '<aside class="note"><strong>为什么未复现？</strong><p>本例缺陷版的触发测试也通过了，未形成“失败→通过”的正控证据，因此未进入模型修复。具体结果见下方测试表。</p></aside>' : '';
    return heading(c.id, c.upstream_fix_title,`<a class="button secondary" href="#research${query.size?'?'+h(query.toString()):''}">返回实验列表</a>${download(c.id+'.json','下载本例证据')}`) +
      `<div class="research-detail"><section class="paper"><h2>1 · 固定版本与环境</h2><dl><dt>缺陷版本</dt><dd>${code(c.buggy_commit)}</dd><dt>上游修复版本</dt><dd>${code(c.fixed_commit)}</dd><dt>Python</dt><dd>实际适配 3.8.20；原始版本 ${h(c.original_python)}</dd><dt>依赖配置</dt><dd>${code(reproduction.dependency_profile)}</dd><dt>基线源码 SHA-256</dt><dd>${code(reproduction.source_preparation?.base_snapshot_sha256)}</dd></dl><a href="${h(c.upstream_fix_url)}" target="_blank" rel="noopener">查看上游修复 →</a><details><summary>固定测试文件与内容哈希</summary>${table(['文件','SHA-256'],Object.entries(reproduction.frozen_test_sha256 || {}).map(([p,s])=>[code(p),code(s)]))}</details><details><summary>清单中的测试命令</summary><pre>${h(c.test_commands.join('\n'))}</pre></details><p class="muted">定位范围来自上游修改文件，非模型自动定位：${h((reproduction.production_files||[]).join('、'))}</p></section>` +
      `<section class="paper"><h2>2 · 正控复现</h2><p><strong>${h(label(c.status))}</strong></p>${unreproduced}<p>运行 ${h(data.reproduction_run.run_id)} · <a href="${h(data.reproduction_run.job_url)}" target="_blank" rel="noopener">原始 CI 记录</a></p>${pairs.map(([name,v])=>`<details><summary>${name==='buggy'?'缺陷版':'上游修复版'}执行环境与退出码</summary><p>镜像 ${code(v.image)}</p>${table(['阶段','退出码','测试文件未改动'],Object.entries(v.phases).map(([p,x])=>[h(p),h(x.returncode),x.test_files_unchanged===true?'是':x.test_files_unchanged===false?'否':'未记录']))}</details>`).join('')}<h3>触发测试</h3>${table(['测试身份','缺陷版','上游修复版'],testRows('trigger'))}<details><summary>查看相关模块回归测试</summary>${table(['测试身份','缺陷版','上游修复版'],testRows('regression'))}</details></section>` +
      `<section class="paper"><h2>3 · 模型诊断</h2><p><strong>${h(label(model.status))}</strong></p><p>${h(model.error|| (model.status==='input_out_of_scope'?'输入超出本轮配置的范围，未得到有效候选。':model.status==='budget_exhausted'?'返回的候选未通过协议校验，有限轮次已用完。':'详见本例证据中的原始状态与候选记录。'))}</p><p>独立模型实验运行 ${h(data.model_run_id)} · ${h(data.model_run.model.model)}</p><p class="muted">与上方正控属于不同运行。已解析候选数不是全部请求次数；缺失的总用量和费用不能按零计算。</p>${model.attempts?.length?table(['候选轮次','结果','输入哈希','记录的 token 总数'],model.attempts.map(a=>[h(a.number),h(label(a.status)),code(a.input_sha256),h(a.usage?.total_tokens??'未记录')])):'<p>没有已解析的候选记录。</p>'}</section></div>`;
  }
  window.RepairResearch = {async render(id, query) {
    const index = await read('index.json');
    if (!id) return overview(index, query);
    if (!index.cases.some(c=>c.id===id)) return heading('未找到此实验','请返回固定缺陷清单。','<a href="#research">返回实验列表</a>');
    return detail(await read(id+'.json'), query);
  }};
  document.addEventListener('submit', event => {
    if (event.target.id !== 'research-filter') return;
    event.preventDefault();
    const query = new URLSearchParams(new FormData(event.target));
    location.hash = 'research?' + query;
  });
})();
