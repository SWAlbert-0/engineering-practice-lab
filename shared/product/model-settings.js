/* Configuration stays on the local server; credentials never enter browser storage. */
(() => {
  'use strict';
  const form = document.querySelector('#model-settings-form');
  if (!form) return;
  const message = document.querySelector('#model-settings-message');
  let busy = false;
  async function api(path = '', body) {
    const response = await fetch('/api/model-settings' + path, body === undefined ? {cache:'no-store'} : {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
    });
    const value = await response.json();
    if (!response.ok) throw Error(value.error || '模型配置请求失败。');
    return value;
  }
  function display(value) {
    for (const name of ['base_url','model']) form.elements[name].value = value[name] || '';
    form.elements.api_key.value = '';
    form.elements.api_key.placeholder = value.key_present ? '已有密钥；留空保留，不回显' : '请输入 API Key；本地无认证服务可填 local';
    const source = {overview:'总览页面配置',environment:'服务端环境变量',invalid:'保存的配置无法读取，请重新保存'}[value.source];
    document.querySelector('#model-config-status').textContent = (value.configured ? '已配置 · ' : '尚未配置 · ') + source + '。';
  }
  async function action(run) {
    if (busy) return;
    busy = true;
    const buttons = [...form.querySelectorAll('button')];
    buttons.forEach(button => button.disabled = true);
    message.textContent = '正在处理…';
    try { await run(); } catch (error) { message.textContent = error.message || '无法连接本地服务。'; }
    finally {busy = false; buttons.forEach(button => button.disabled = false);}
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    action(async () => {display(await api('', Object.fromEntries(new FormData(form)))); message.textContent = '已保存，四个项目及独立修复运行器共用此配置。';});
  });
  document.querySelector('#model-settings-clear').addEventListener('click', () => action(async () => {
    display(await api('/clear', {})); message.textContent = '已清除页面保存的配置，当前状态按服务端环境变量显示。';
  }));
  document.querySelector('#model-settings-test').addEventListener('click', () => {
    if (!document.querySelector('#model-test-consent').checked) {message.textContent = '请先确认发送一次实际文本请求。'; return;}
    action(async () => {const value = await api('/test', {confirm_call:true}); message.textContent = value.message;});
  });
  api().then(display).catch(() => {document.querySelector('#model-config-status').textContent = '配置暂不可用，请通过本地服务访问并刷新重试。';});
})();
