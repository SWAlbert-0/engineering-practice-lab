/* Frontend behavior checks using a small DOM adapter and real engine responses.
 * This does not test browser layout, CSS rendering, or native downloads. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const response = spawnSync(process.env.PYTHON || 'python', ['-c', `import json,server
print(json.dumps({'repair':server.repair.run('boundary','correct'),'wrong':server.repair.run('boundary','wrong'),'rag':server.rag.search('铝合金薄壁精加工','铝合金'),'refusal':server.rag.search('量子纠缠实验'),'bad':server.mlops.run(.65,0,True),'unlabeled':server.mlops.run(.65,0,False),'drift':server.mlops.run(0,2,True)}))`], {cwd: root, encoding: 'utf8'});
assert.equal(response.status, 0, response.stderr);
const data = JSON.parse(response.stdout);
class Element {
  constructor(id = '') { this.id = id; this.listeners = {}; this.value = ''; this.checked = false; this.disabled = false; this.textContent = ''; this.innerHTML = ''; this.className = ''; this.dataset = {}; this.attrs = {}; this.open = false;
    this.classList = {add: c => { this.className += ` ${c}`; }, remove: c => { this.className = this.className.split(' ').filter(x => x !== c).join(' '); }, contains: c => this.className.split(' ').includes(c)};
  }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  fire(type, values = {}) { for (const fn of this.listeners[type] || []) fn({preventDefault() {}, target: this, ...values}); }
  setAttribute(k, v) { this.attrs[k] = v; }
  removeAttribute(k) { delete this.attrs[k]; }
  getAttribute(k) { return this.attrs[k]; }
  closest(selector) { return selector === 'form' ? this.form : null; }
  focus() { this.focused = true; }
  scrollIntoView() { this.scrolled = true; }
  replaceChildren(...rows) { this.rows = rows; }
}
function page(folder) {
  const html = read(`${folder}/index.html`), nodes = new Map(), groups = {};
  for (const match of html.matchAll(/<([a-z]+)\b([^>]*\bid="([^"]+)"[^>]*)>/g)) {
    const node = new Element(match[3]), attributes = match[2];
    node.value = attributes.match(/\bvalue="([^"]*)"/)?.[1] || '';
    node.disabled = /\bdisabled\b/.test(attributes); node.checked = /\bchecked\b/.test(attributes);
    node.className = attributes.match(/\bclass="([^"]*)"/)?.[1] || '';
    node.tag = match[1]; nodes.set(node.id, node);
  }
  const get = id => { assert(nodes.has(id), `Missing HTML element: ${folder} #${id}`); return nodes.get(id); };
  const forms = [...nodes.values()].filter(n => n.tag === 'form');
  const form = forms[0];
  for (const key of ['preset', 'example']) {
    groups[`[data-${key}]`] = Array.from(html.matchAll(new RegExp(`<button[^>]*data-${key}="([^"]+)"[^>]*>([^<]+)</button>`, 'g')), m => {
      const n = new Element(); n.dataset[key] = m[1]; n.textContent = m[2]; n.form = form; return n;
    });
  }
  for (const node of nodes.values()) node.form = form;
  if (form) form.querySelectorAll = () => [...nodes.values()].filter(n => ['input', 'select', 'textarea'].includes(n.tag) || n.id === 'unknown').concat(...Object.values(groups));
  const document = {
    querySelector: selector => get(selector.slice(1)),
    querySelectorAll: selector => groups[selector] || [],
    getElementById: id => nodes.get(id),
    addEventListener() {},
    createElement: () => ({click() { downloaded++; }})
  };
  let downloaded = 0;
  const pending = [], requests = [];
  const window = new Element();
  const context = vm.createContext({document, window, location: {protocol: 'http:', hash: ''}, Blob, URL, performance,
    setTimeout: fn => fn(), requestAnimationFrame: fn => { context.nextFrame = fn; },
    fetch: async (url, options) => { requests.push({url, body: JSON.parse(options.body)}); const next = pending.shift(); if (next instanceof Error) throw next; assert(next, 'Missing API response'); return {ok: true, json: async () => next}; }
  });
  const run = code => vm.runInContext(code, context);
  const load = file => run(read(file));
  load('shared/ui.js');
  return {get, groups, context, run, load, pending, requests, document, nodes, html, window, downloads: () => downloaded};
}
async function submit(p, id = 'run') {
  const button = p.get(id); button.form.fire('submit');
  assert(button.disabled, 'Duplicate submissions blocked during request');
  for (let i = 0; i < 10; i++) await Promise.resolve();
  assert(!button.disabled, 'Run button restored after request');
}
(async () => {
  const repair = page('demos/01-repair-agent');
  repair.get('case').value = 'boundary'; repair.get('case').selectedOptions = [{text: '运费计算：边界条件'}];
  repair.get('candidate').value = 'correct'; repair.get('candidate').selectedOptions = [{text: '正确候选'}];
  repair.load('demos/01-repair-agent/app.js');
  repair.pending.push(new Error('offline'));
  await submit(repair);
  assert.match(repair.get('status').textContent, /无法连接/); assert(repair.get('status').classList.contains('error'));
  assert(repair.get('export').disabled); assert(!repair.get('case').disabled);
  repair.pending.push(data.repair); await submit(repair);
  assert.equal(repair.get('decision').textContent, '通过'); assert.equal(repair.get('held').textContent, '3 / 3');
  assert(!repair.get('status').classList.contains('error')); assert.match(repair.get('diff').innerHTML, /diff-add/);
  repair.get('export').fire('click'); assert.equal(repair.downloads(), 1);
  repair.get('repair-form').fire('change'); assert(repair.get('export').disabled); assert.match(repair.get('run-context').textContent, /上次结果/);
  repair.pending.push(data.wrong); await submit(repair); assert.equal(repair.get('decision').textContent, '未通过');

  const rag = page('demos/02-process-rag'); rag.load('demos/02-process-rag/app.js');
  rag.groups['[data-example]'][0].fire('click'); rag.get('mode').value = 'hybrid';
  rag.pending.push(data.rag); await submit(rag, 'search');
  assert.equal(rag.requests[0].body.material, '铝合金');
  assert.match(rag.get('draft').innerHTML, /href="#source-AL-02"/); assert.match(rag.get('hits').innerHTML, /id="source-AL-02"/);
  rag.get('unknown').fire('click'); assert(rag.get('export').disabled); assert.equal(rag.get('material').value, '全部');
  rag.pending.push(data.refusal); await submit(rag, 'search'); assert.equal(rag.get('draft-state').textContent, '资料不足');
  rag.get('query').value = '  '; await submit(rag, 'search'); assert.match(rag.get('status').textContent, /请输入/); assert.equal(rag.requests.length, 2);
  rag.get('query').value = 'test';
  const escaped = structuredClone(data.rag); escaped.draft = '<script>alert(1)</script>'; escaped.hits[0].text = '<img onerror=alert(1)>';
  rag.pending.push(escaped); await submit(rag, 'search');
  assert(!rag.get('draft').innerHTML.includes('<script>')); assert(!rag.get('hits').innerHTML.includes('<img '));

  const mlops = page('demos/03-mlops'); mlops.load('demos/03-mlops/app.js');
  mlops.pending.push(data.bad); await submit(mlops);
  assert.equal(mlops.get('decision').textContent, '回滚到 v1'); assert.match(mlops.get('sample-model').textContent, /v1/);
  mlops.groups['[data-preset]'].find(n => n.dataset.preset === 'unlabeled').fire('click');
  assert(!mlops.get('labels').checked); assert(mlops.get('export').disabled);
  mlops.pending.push(data.unlabeled); await submit(mlops);
  assert.match(mlops.get('versions').innerHTML, /无标签，未评估/); assert(!mlops.get('versions').innerHTML.includes('NaN')); assert.match(mlops.get('sample-model').textContent, /v2/);
  mlops.groups['[data-preset]'].find(n => n.dataset.preset === 'drift').fire('click');
  mlops.pending.push(data.drift); await submit(mlops);
  assert.equal(mlops.get('sv').textContent, '2.0'); assert.match(mlops.get('drift-summary').textContent, /检测到分布漂移/); assert.equal(mlops.get('decision').textContent, '保留 v2');

  const game = page('demos/04-tower-defense');
  game.context.TowerEngine = require('../demos/04-tower-defense/engine.js');
  const drawing = new Proxy({}, {get: (obj, key) => obj[key] || (() => {}), set: (obj, key, val) => {obj[key] = val; return true;}});
  game.get('game').getContext = () => drawing;
  game.get('game').getBoundingClientRect = () => ({left: 10, top: 20, width: 450, height: 250});
  game.get('tower').value = 'bolt'; game.load('demos/04-tower-defense/app.js');
  game.get('game').fire('click', {clientX: 105, clientY: 50}); // Logical map (190,60).
  assert.equal(game.get('gold').textContent, 110); assert.equal(game.run('game.towers[0].x'), 190);
  game.get('next').fire('click'); game.run('render()'); assert.equal(game.get('wave').textContent, '1 / 5'); assert(game.get('next').disabled);
  game.get('pause').fire('click'); assert(game.run('game.paused')); assert.equal(game.get('pause').textContent, '继续');
  game.get('reset').fire('click'); assert.equal(game.get('gold').textContent, 160); assert(!game.run('game.paused'));
  game.run("game.state='lost';render()"); assert.equal(game.get('next').textContent, '本局结束'); assert(game.get('pause').disabled);

  const report = page('report');
  const topics = JSON.parse(read('report/topics.json'));
  report.get('topic-rows').rows = topics.map(t => { const n = new Element(); n.dataset.id = t.id; return n; });
  report.get('topic-sort').value = 'score';
  report.document.querySelectorAll = selector => selector === '.topic-detail' ? topics.map(t => report.get('topic-' + t.id)) : [];
  report.run(report.html.match(/<script>([\s\S]*?)<\/script>/)[1]);
  report.get('topic-teacher').value = '白天'; report.get('topic-teacher').fire('input'); assert.equal(report.get('topic-rows').rows.length, 11);
  report.get('topic-query').value = 'zzzz'; report.get('topic-query').fire('input'); assert.equal(report.get('topic-count').textContent, '0 / 25 题'); assert.equal(report.get('no-topics').hidden, false);
  report.get('topic-query').value = ''; report.get('topic-teacher').value = ''; report.get('topic-sort').value = 'difficulty'; report.get('topic-sort').fire('input');
  const ordered = report.get('topic-rows').rows.map(row => topics.find(t => t.id === row.dataset.id).difficulty);
  assert.deepEqual(ordered, [...ordered].sort((a,b) => a-b));
  report.context.location.hash = '#topic-D11'; report.window.fire('hashchange'); assert(report.get('topic-D11').open);
  report.window.fire('beforeprint'); assert(topics.every(t => report.get('topic-' + t.id).open));
  report.window.fire('afterprint'); assert(!report.get('topic-D01').open); assert(report.get('topic-D11').open);
  console.log('Frontend behavior checks passed: repair, retrieval, model release, tower controls, report filters.');
})().catch(error => {console.error(error); process.exitCode = 1;});
