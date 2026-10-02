'use strict';
let result;
const form = $('#repair-form');
const describe = () => [$('#case').selectedOptions[0].text, $('#candidate').selectedOptions[0].text].join(' / ');
form.addEventListener('change', markStale);
form.addEventListener('submit', event => {
  event.preventDefault();
  if ($('#run').disabled) return;
  busy($('#run'), async () => {
    $('#status').textContent = '正在运行测试…';
    $('#export').disabled = true;
    const description = describe();
    result = await post('/api/repair', { case: $('#case').value, candidate: $('#candidate').value });
    const count = tests => `${tests.filter(test => test.pass).length} / ${tests.length}`;
    $('#before').textContent = count(result.before);
    $('#after').textContent = count(result.after);
    $('#held').textContent = count(result.holdout);
    $('#decision').textContent = result.accepted ? '通过' : '未通过';
    $('#decision').className = result.accepted ? 'success' : 'error';
    $('#issue').textContent = result.issue;
    $('#diff').innerHTML = result.diff.trimEnd().split('\n').map(line => {
      const kind = line.startsWith('+++') || line.startsWith('---') || line.startsWith('@@') ? 'meta'
        : line.startsWith('+') ? 'add' : line.startsWith('-') ? 'remove' : '';
      return `<span class="diff-line diff-${kind}">${escapeHTML(line) || ' '}</span>`;
    }).join('');
    $('#tests').innerHTML = [['修复前', result.before], ['候选回归', result.after], ['独立用例', result.holdout]]
      .flatMap(([stage, tests]) => tests.map(test => `<tr><td class="nowrap">${stage}</td>
        <td><code>${escapeHTML(JSON.stringify(test.input))}</code></td>
        <td><code>${escapeHTML(JSON.stringify(test.expected))}</code></td>
        <td><code>${escapeHTML(test.error || JSON.stringify(test.actual))}</code></td>
        <td class="${test.pass ? 'success' : 'error'} nowrap">${test.pass ? '通过' : '失败'}</td></tr>`)).join('');
    $('#run-context').textContent = `本次配置：${description}`;
    $('#status').textContent = `测试完成，用时 ${result.duration_ms} ms。`;
    $('#export').disabled = false;
    publishResult('repair', result, {case: $('#case').value, candidate: $('#candidate').value});
  });
});
$('#export').addEventListener('click', () => downloadJSON(result, 'repair-results.json'));

const initial = new URLSearchParams(location.search);
if (['boundary','empty','dedupe'].includes(initial.get('case'))) $('#case').value = initial.get('case');
if (['correct','wrong'].includes(initial.get('candidate'))) $('#candidate').value = initial.get('candidate');

if (initial.get('task')) {
  $('#case').disabled = true;
  $('#case').title = '此样例已绑定当前任务；更换样例请新建任务。';
}
