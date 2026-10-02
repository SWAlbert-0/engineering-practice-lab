'use strict';
const $ = selector => document.querySelector(selector);
const escapeHTML = value => String(value).replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[char]));

async function post(path, data) {
  if (location.protocol === 'file:') {
    throw new Error('请先启动 python server.py，再从 http://127.0.0.1:8765 打开此页。');
  }
  let response;
  try {
    response = await fetch(path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    });
  } catch {
    throw new Error('无法连接本地服务，请确认 server.py 仍在运行。');
  }
  let result;
  try { result = await response.json(); }
  catch { throw new Error('服务未返回有效结果，请检查终端中的运行日志。'); }
  if (!response.ok) throw new Error(result.error || '请求失败，请重试。');
  return result;
}

function downloadJSON(data, name) {
  const anchor = document.createElement('a');
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function busy(button, action) {
  const status = $('#status');
  status.classList.remove('error');
  const form = button.closest('form');
  const controls = form ? Array.from(form.querySelectorAll('input,select,textarea,button[data-preset],button[data-example],#unknown')) : [];
  const previous = controls.map(control => control.disabled);
  controls.forEach(control => { control.disabled = true; });
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  try { await action(); }
  catch (error) {
    status.textContent = error.message;
    status.classList.add('error');
  } finally {
    controls.forEach((control, index) => { control.disabled = previous[index]; });
    button.disabled = false;
    button.removeAttribute('aria-busy');
  }
}

function markStale() {
  const download = $('#export');
  if (download) download.disabled = true;
  const context = $('#run-context');
  if (context && context.textContent) context.textContent = '参数已修改。下方仍显示上次结果，请重新运行。';
}
