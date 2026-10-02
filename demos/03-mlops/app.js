'use strict';
let result;
const form = $('#mlops-form');
const updateLabels = () => {
  $('#nv').textContent = `${Math.round(Number($('#noise').value) * 100)}%`;
  $('#sv').textContent = Number($('#shift').value).toFixed(1);
};
form.addEventListener('input', () => { updateLabels(); markStale(); });
form.addEventListener('change', markStale);
const presets = { normal: [0, 0, true], bad: [.65, 0, true], drift: [0, 2, true], unlabeled: [.65, 0, false] };
document.querySelectorAll('[data-preset]').forEach(button => button.addEventListener('click', () => {
  const [noise, shift, labels] = presets[button.dataset.preset];
  $('#noise').value = noise;
  $('#shift').value = shift;
  $('#labels').checked = labels;
  updateLabels();
  markStale();
  $('#status').textContent = `已选择“${button.textContent}”，点击运行实验查看结果。`;
}));
form.addEventListener('submit', event => {
  event.preventDefault();
  if ($('#run').disabled) return;
  busy($('#run'), async () => {
    $('#status').textContent = '正在训练并评估模型…';
    $('#export').disabled = true;
    const params = { noise: Number($('#noise').value), shift: Number($('#shift').value), labels: $('#labels').checked };
    result = await post('/api/mlops', params);
    const pct = value => value === null ? '无标签，未评估' : `${(value * 100).toFixed(1)}%`;
    $('#decision').textContent = result.action;
    $('#decision').className = `result-state ${result.rollback ? 'warning' : ''}`;
    $('#explain').textContent = result.labels
      ? `候选版本在同一窗口的准确率${result.drop >= 0 ? '下降' : '提升'} ${Math.abs(result.drop * 100).toFixed(1)} 个百分点。${result.rollback ? '超过 8 个百分点的阈值，已使用旧版重新预测。' : '未触发回滚条件。'}`
      : '尚未取得真实标签，当前准确率无法计算。保留候选版本，等待后续评估。';
    $('#versions').innerHTML = [
      ['v1', '旧版', result.validation_v1, result.v1_accuracy],
      ['v2', '候选', result.validation_v2, result.v2_accuracy]
    ].map(([version, label, validation, current]) => `<tr><td>${version} · ${label}</td><td class="number">${pct(validation)}</td><td>${pct(current)}</td><td class="success">${result.active_version === version ? '使用中' : '—'}</td></tr>`).join('');
    $('#drift-summary').textContent = `特征 PSI：${result.psi.toFixed(3)}。${result.drift ? '超过 0.2，检测到分布漂移。' : '未超过 0.2。'} 漂移告警不单独触发回滚。`;
    const bins = ['< −1', '−1 ~ −0.5', '−0.5 ~ 0', '0 ~ 0.5', '0.5 ~ 1', '≥ 1'];
    $('#hist').className = '';
    $('#hist').innerHTML = result.histogram.reference.map((value, index) => {
      const current = result.histogram.current[index];
      return `<div class="hist-row"><span class="hist-label">${escapeHTML(bins[index])}</span><div>
        <div class="hist-measure"><div class="hist-track"><div class="hist-fill" style="width:${value * 100}%"></div></div><span class="hist-value">${(value * 100).toFixed(1)}%</span></div>
        <div class="hist-measure"><div class="hist-track"><div class="hist-fill current" style="width:${current * 100}%"></div></div><span class="hist-value">${(current * 100).toFixed(1)}%</span></div></div></div>`;
    }).join('');
    $('#dataset').textContent = `训练 ${result.n_train} 条 / 验证 ${result.n_validation} 条 / 当前 ${result.n_current} 条。数据标识：${result.data_hash}`;
    $('#trace').innerHTML = result.trace.map(item => `<li>${escapeHTML(item)}</li>`).join('');
    $('#samples').innerHTML = result.samples.map((sample, index) => `<tr><td class="number">${index + 1}</td>
      <td><code>[${sample.features.map(value => value.toFixed(2)).join(', ')}]</code></td><td class="number">${sample.prediction}</td><td class="number">${(sample.probability * 100).toFixed(1)}%</td></tr>`).join('');
    $('#sample-model').textContent = `使用 ${result.active_version} / 前 5 条样本`;
    $('#run-context').textContent = `本次配置：标签污染 ${Math.round(params.noise * 100)}% / 特征偏移 ${params.shift.toFixed(1)} / ${params.labels ? '有' : '无'}真实标签`;
    $('#status').textContent = `实验完成，用时 ${result.duration_ms} ms。`;
    $('#export').disabled = false;
    publishResult('mlops', result);
  });
});
$('#export').addEventListener('click', () => downloadJSON(result, 'model-release-results.json'));
