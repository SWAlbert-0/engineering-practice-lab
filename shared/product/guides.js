'use strict';
window.ProjectGuides = (() => {
  const chapters = [['requirements','需求分析'],['architecture','架构设计'],['development','代码开发'],['workflow','任务流程'],['validation','验收与排查'],['roadmap','后续开发']];
  const h = value => P.h(value);
  const table = (headers, rows) => P.table(headers, rows.map(row=>row.map(h)));
  const text = content => `<p>${h(content)}</p>`;
  const section = (id,number,title,body) => `<section class="guide-chapter" aria-labelledby="guide-${id}"><header class="guide-chapter-heading"><span>${number}</span><h2 id="guide-${id}" tabindex="-1">${title}</h2><a href="#guide" aria-label="返回指南目录">目录 ↑</a></header>${body}</section>`;
  const marker = id => `<defs><marker id="${id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 10 5 0 10z" fill="currentColor"/></marker></defs>`;
  const arrow = (d,id,label,x,y) => `<path class="guide-edge" d="${d}" marker-end="url(#${id})"/>${label?`<text class="guide-edge-label" x="${x}" y="${y}" text-anchor="middle">${h(label)}</text>`:''}`;
  const box = (x,y,w,title,detail) => `<g class="guide-node"><rect x="${x}" y="${y}" width="${w}" height="72" rx="8"/><text x="${x+w/2}" y="${y+29}" text-anchor="middle">${h(title)}</text><text class="guide-node-detail" x="${x+w/2}" y="${y+51}" text-anchor="middle">${h(detail)}</text></g>`;
  function architecture(g,id) {
    const m=`guide-${id}-arch-arrow`,n=g.architecture.nodes;
    const svg=`<svg viewBox="0 0 760 326" role="img" aria-labelledby="guide-arch-title guide-arch-desc"><title id="guide-arch-title">${h(g.architecture.title)}</title><desc id="guide-arch-desc">${h(g.architecture.description)}</desc>${marker(m)}
    ${arrow('M220 72 H280',m,'打开',250,57)}${arrow('M478 72 H538',m,'请求',507,57)}
    ${arrow('M638 110 V214',m,'分派执行',677,168)}${arrow('M538 252 H478',m,'返回',507,236)}
    ${arrow('M282 252 H250 V156 H122 V112',m,'同源消息',191,176)}${arrow('M122 110 V214',m,'保存',90,196)}
    ${box(24,36,196,...n[0])}${box(282,36,196,...n[1])}${box(540,36,196,...n[2])}${box(24,216,196,...n[3])}${box(282,216,196,...n[4])}${box(540,216,196,...n[5])}</svg>`;
    return figure(svg,'图 01 · 当前实现的模块关系',g.architecture.description);
  }
  function workflow(g,id) {
    const f=g.flow,m=`guide-${id}-flow-arrow`;
    const svg=`<svg viewBox="0 0 760 442" role="img" aria-labelledby="guide-flow-title guide-flow-desc"><title id="guide-flow-title">${h(f.title)}</title><desc id="guide-flow-desc">${h(f.description)}</desc>${marker(m)}
    ${arrow('M380 66 V98',m)}${arrow('M380 152 V182',m)}${arrow('M205 235 H170 V324',m,'是',175,218)}${arrow('M555 235 H590 V324',m,'否',582,218)}
    <g class="guide-node"><rect x="220" y="12" width="320" height="54" rx="8"/><text x="380" y="45" text-anchor="middle">${h(f.start)}</text><rect x="220" y="100" width="320" height="54" rx="8"/><text x="380" y="133" text-anchor="middle">${h(f.process)}</text></g>
    <g class="guide-decision"><path d="M380 182 555 235 380 288 205 235z"/><text x="380" y="240" text-anchor="middle">${h(f.decision)}</text></g>
    ${box(20,326,300,f.yes,f.endYes)}${box(440,326,300,f.no,f.endNo)}</svg>`;
    return figure(svg,'图 02 · '+f.title,f.description);
  }
  function figure(svg,caption,description) {
    return `<figure class="guide-figure"><p class="guide-diagram-hint">左右滑动查看完整图示 →</p><div class="guide-diagram" tabindex="0" role="region" aria-label="关系图，小屏可横向滚动查看">${svg}</div><figcaption><strong>${h(caption)}</strong><span>${h(description)}</span></figcaption></figure>`;
  }
  function render(id) {
    const g=window.ProjectGuideData[id];
    const nav=chapters.map(([key,title],i)=>`<a href="#guide/${key}"><span>0${i+1}</span>${title}</a>`).join('');
    const intro=`<header class="guide-cover"><div class="guide-kicker">${h(g.label)}</div><h1>${h(g.name)} · 项目指南</h1><p class="guide-deck">${h(g.subtitle)}</p>${text(g.intro)}<div class="guide-cover-notes"><span>6 个章节 · 2 张结构图</span><span>面向理解、开发与项目演示</span></div></header><nav class="guide-toc" aria-label="指南章节">${nav}</nav>`;
    const requirements=section('requirements','01','需求分析',`<div class="guide-scenario"><span>从一个具体场景出发</span>${text(g.scenario)}</div><h3>谁会使用，交付什么</h3>${table(['使用者','主要任务','输出与边界'],g.roles)}<h3>把需求写成可检查的行为</h3>${table(['需求','设计约束','验收观察点'],g.requirements)}<aside class="guide-callout"><strong>当前实现范围</strong>${text(g.boundary)}</aside>`);
    const arch=section('architecture','02','架构设计',text('先看当前运行的模块，再看数据之间的关系。图中没有把尚未接入的服务画成已实现能力。')+architecture(g,id)+`<h3>核心数据与关联</h3>${table(['对象 / 关联','保存内容','设计说明'],g.objects)}<aside class="guide-callout"><strong>存储与身份</strong>${text('业务记录保存在当前浏览器的 LocalStorage。刷新同一来源页面可继续查看；更换浏览器、端口或清除站点数据会影响可见记录。设置页提供 JSON 导出，但当前没有导入恢复、数据库同步或真实账号权限。')}</aside>`);
    const development=section('development','03','代码开发',text('沿着“入口 → 规则 → 结果 → 页面状态”阅读代码。下面的文件名以当前项目目录为起点；共用代码位于根目录 shared/，接口入口是根目录 server.py。')+table(['文件','关键入口','负责什么'],g.modules)+`<div class="guide-code"><div>${h(g.code.file)}</div><pre><code>${h(g.code.text)}</code></pre></div>${text(g.code.explain)}<h3>建议的开发顺序</h3><ol class="guide-build">${g.build.map(([a,b],i)=>`<li><span>0${i+1}</span><div><h4>${h(a)}</h4>${text(b)}</div></li>`).join('')}</ol>`);
    const flow=section('workflow','04','任务流程',workflow(g,id)+`<h3>在当前页面走一遍</h3><ol class="guide-walkthrough">${g.walkthrough.map(([a,b,route,label],i)=>`<li><span class="guide-step">${i+1}</span><div><h4>${h(a)}</h4>${text(b)}${P.link(route,label+' →','guide-task-link')}</div></li>`).join('')}</ol>`);
    const validation=section('validation','05','验收与排查',text('先验证关键分支，再演示完整流程。以下预期基于内置样例与当前规则，不能替代真实数据或真实用户验收。')+table(['验证场景','怎么操作','通过标准'],g.acceptance)+`<h3>自动检查</h3><div class="guide-code"><div>在仓库根目录执行；下方以 Conda 为例</div><pre><code>${h('conda activate engineering-practice-lab\n'+g.tests)}</code></pre></div>${text('无 Conda 时，先激活一键脚本创建的 .venv，跳过示例中的 conda activate；执行 Node 测试还需安装 Node.js 22。产品流程测试使用 DOM 适配器，不检查 CSS 布局。页面阅读、图表滚动与真实键盘交互需要浏览器另行检查；后端测试只覆盖现有教学计算。')}<h3>遇到问题时</h3><div class="guide-faq">${g.pitfalls.map(([a,b])=>`<details><summary>${h(a)}</summary>${text(b)}</details>`).join('')}</div>`);
    const roadmap=section('roadmap','06','后续开发',text('以下是尚未完成的开发阶段，按依赖关系推进。每个阶段都应留下可演示、可复核的产物，再扩展下一阶段。')+`<ol class="guide-roadmap">${g.roadmap.map(([a,b,c],i)=>`<li><span>阶段 ${i+1}</span><div><h3>${h(a)}</h3>${text(b)}<p class="guide-deliverable">${h(c)}</p></div></li>`).join('')}</ol><aside class="guide-callout"><strong>项目展示怎么讲</strong>${text(g.pitch)}</aside><div class="guide-end"><a href="#guide">返回目录 ↑</a>${P.link('overview','进入项目概览 →')}<button type="button" class="secondary" data-action="topic-info" aria-haspopup="dialog" aria-controls="topic-dialog">查看原选题信息</button></div>`);
    return `<article class="project-guide">${intro}${requirements}${arch}${development}${flow}${validation}${roadmap}</article>`;
  }
  function focus(id) {
    if(!chapters.some(([key])=>key===id))return;
    const heading=document.querySelector('#guide-'+id);
    heading?.focus({preventScroll:true});heading?.scrollIntoView?.({block:'start',behavior:'instant'});
  }
  return {render,focus,chapters};
})();
