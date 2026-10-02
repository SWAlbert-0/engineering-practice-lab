'use strict';
let result;
const form = $('#rag-form');
form.addEventListener('input', markStale);
form.addEventListener('change', markStale);
const examples = {
  aluminum: ['铝合金薄壁零件如何安排粗加工与精加工？', '铝合金'],
  steel: ['不锈钢钻孔需要注意什么？', '不锈钢'],
  quality: ['量具校准过期了怎么办？', '全部']
};
document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', () => {
  [$('#query').value, $('#material').value] = examples[button.dataset.example];
  markStale();
  $('#query').focus();
}));
$('#unknown').addEventListener('click', () => {
  $('#query').value = '量子纠缠的实验步骤是什么？';
  $('#material').value = '全部';
  markStale();
  $('#query').focus();
});
form.addEventListener('submit', event => {
  event.preventDefault();
  if ($('#search').disabled) return;
  busy($('#search'), async () => {
    $('#status').textContent = '正在检索资料…';
    $('#export').disabled = true;
    const params = { query: $('#query').value.trim(), material: $('#material').value, mode: $('#mode').value };
    if (!params.query) throw new Error('请输入要检索的问题。');
    result = await post('/api/rag', params);
    $('#draft-state').textContent = result.refused ? '资料不足' : '待审核';
    $('#draft').innerHTML = result.refused
      ? '<p>现有资料没有足够依据回答这个问题。请换一个问题，或补充相关文档。</p>'
      : result.draft.split('\n\n').map(paragraph => {
          let text = escapeHTML(paragraph);
          result.hits.forEach(hit => {
            const citation = `[${hit.id} · 第${hit.page}页]`;
            text = text.replace(escapeHTML(citation), `<a href="#source-${escapeHTML(hit.id)}">${escapeHTML(citation)}</a>`);
          });
          return `<p>${text}</p>`;
        }).join('');
    $('#hits').innerHTML = result.hits.map(hit => `<article class="evidence" id="source-${escapeHTML(hit.id)}">
      <div class="evidence-heading"><h3>${escapeHTML(hit.title)} · 第 ${hit.page} 页</h3><span>${escapeHTML(hit.id)}</span></div>
      <p>${escapeHTML(hit.text)}</p><details><summary>检索分数</summary>
      <p>BM25：${hit.bm25}　LSA：${hit.dense}　${params.mode === 'hybrid' ? 'RRF' : '排序分数'}：${hit.fusion}</p></details></article>`).join('')
      || '<div class="empty">没有找到相关段落。</div>';
    $('#hit-count').textContent = `${result.hits.length} 条`;
    $('#run-context').textContent = `本次检索：${params.query} / ${params.material} / ${params.mode === 'hybrid' ? '混合检索' : '关键词检索'}`;
    $('#status').textContent = `检索完成，用时 ${result.duration_ms} ms。${result.refused ? '未生成草案。' : '草案仅摘录检索到的资料。'}`;
    $('#export').disabled = false;
    publishResult('rag', result, params);
  });
});
$('#export').addEventListener('click', () => downloadJSON(result, 'retrieval-results.json'));
