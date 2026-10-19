'use strict';
(() => {
 const project=document.body.dataset.project,params=new URLSearchParams(location.search),isReq=project==='requirements';
 const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const input=document.querySelector('#input'),form=document.querySelector('#task-form'),button=document.querySelector('#run'),status=document.querySelector('#status'),output=document.querySelector('#result'),download=document.querySelector('#export');
 let current=null;
 input.value=params.get(isReq?'text':'topic') || (isReq?'用户可以查看本人订单。\n管理员应快速完成订单导出。':'Agent如何利用外部反馈改进任务执行？');
 if(!isReq){let selected;try{selected=JSON.parse(params.get('ids') || '[]');}catch{selected=[];}if(!Array.isArray(selected))selected=[];document.querySelector('#papers').insertAdjacentHTML('beforeend',LiteratureSeed.map(p=>`<label><input type="checkbox" name="paper" value="${escape(p.id)}" ${(!selected.length||selected.includes(p.id))?'checked':''}><span>${escape(p.title)}<small>${p.year} · ${escape(p.area)}</small></span></label>`).join(''));}
 fetch('/api/capabilities').then(r=>r.ok?r.json():Promise.reject()).then(c=>{document.querySelector('#capability').textContent=c.llm?'模型已配置。模型模式会请求服务并产生实际费用；密钥不会传到页面。':'当前未配置模型；离线模式可直接运行。模型模式需设置服务端 LAB_LLM_* 环境变量。';document.querySelectorAll('[data-model]').forEach(o=>o.disabled=!c.llm);}).catch(()=>{document.querySelector('#capability').textContent='请通过本地服务访问。模型配置状态暂不可用。';});
 form.addEventListener('input',()=>{if(current){download.disabled=true;document.querySelector('#run-context').textContent='输入已修改，请重新运行；下方保留上次结果。';}});
 form.addEventListener('change',()=>{if(current){download.disabled=true;document.querySelector('#run-context').textContent='配置已修改，请重新运行。';}});
 form.addEventListener('submit',async event=>{
  event.preventDefault();if(button.disabled)return;
  const mode=document.querySelector('#mode').value,text=input.value.trim();
  const payload=isReq?{text,mode}:{topic:text,ids:Array.from(document.querySelectorAll('[name=paper]:checked')).map(x=>x.value),mode};
  const controls=Array.from(form.querySelectorAll('input,textarea,select,button')),previous=controls.map(c=>c.disabled);controls.forEach(c=>c.disabled=true);button.setAttribute('aria-busy','true');download.disabled=true;status.textContent=mode==='offline'?'正在执行本地处理…':'正在请求模型并核验结构与引用…';status.classList.remove('error');
  try{
   const response=await fetch(isReq?'/api/requirements':'/api/literature',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw Error(data.error || '请求失败');
   current=data;output.innerHTML=isReq?requirementResult(data):literatureResult(data);status.textContent='运行完成';document.querySelector('#run-context').textContent=data.provider+' · '+data.duration_ms+' ms';download.disabled=false;
   publishResult(project,data,isReq?{spec:params.get('spec') || '',text}:{scope:params.get('scope') || ''});
  }catch(error){status.textContent=error.message || '无法连接服务，请检查 server.py。';status.classList.add('error');document.querySelector('#run-context').textContent='本次未生成可导出结果。';}
  finally{controls.forEach((c,i)=>c.disabled=previous[i]);button.removeAttribute('aria-busy');}
 });
 const table=(headers,rows)=>`<div class="table-wrap"><table><thead><tr>${headers.map(x=>'<th>'+escape(x)+'</th>').join('')}</tr></thead><tbody>${rows.map(row=>'<tr>'+row.map(x=>'<td>'+escape(x)+'</td>').join('')+'</tr>').join('')}</tbody></table></div>`;
 function requirementResult(r){return `<div class="task-summary"><span>${r.requirements.length} 条需求</span><span>${r.cases.length} 条用例草案</span><span>${r.issues.length} 个待确认问题</span></div><h2>需求与原文</h2>${table(['编号','角色','原文'],r.requirements.map(q=>[q.id,q.actor,q.source]))}<h2>待确认问题</h2>${r.issues.length?table(['需求','问题'],r.issues.map(i=>[i.requirement,i.question])):'<p>规则未发现问题，仍需人工检查完整性。</p>'}<h2>用例草案</h2>${table(['用例','需求','类型','预期'],r.cases.map(c=>[c.id,c.requirement,c.kind,c.expected]))}<p class="boundary-note">${escape(r.boundary)}</p>`;}
 function literatureResult(r){return `<div class="task-summary"><span>${r.papers.length} 篇摘记</span><span>${r.claims.length} 条论述</span><span>${r.model_calls} 次模型调用</span></div><h2>执行过程</h2><ol class="role-events">${r.trace.map(t=>'<li><strong>'+escape(t.role)+' / '+escape(t.action)+'</strong><p>'+escape(t.detail)+'</p></li>').join('')}</ol><h2>带引用的草稿</h2>${r.claims.map(c=>`<article class="workbench-claim"><small>${escape(c.paper)}</small><p>${escape(c.text)}</p><blockquote>${escape(c.quote)}</blockquote><small>${escape(c.reason)}</small></article>`).join('')}<p class="boundary-note">${escape(r.boundary)}</p>`;}
 download.addEventListener('click',()=>{if(!current||download.disabled)return;const a=document.createElement('a'),u=URL.createObjectURL(new Blob([JSON.stringify(current,null,2)],{type:'application/json'}));a.href=u;a.download=project+'-result.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);});
})();
