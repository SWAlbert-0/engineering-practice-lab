'use strict';
(() => {
 const $=id=>document.getElementById(id),player=$('player');let frames=[],objectURL='',material='内置原创样片',busy=false,modelReady=false;
 const h=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const count=new URLSearchParams(location.search).get('frames');if(['2','4','6'].includes(count))$('frame-count').value=count;
 fetch('/api/capabilities').then(r=>r.json()).then(c=>{modelReady=!!c.llm;$('mode').options[1].disabled=!modelReady;$('capability').textContent=c.llm?'模型已配置；请确认该模型支持图像输入。':'未配置模型。离线可验证采样；内容问答需要服务端配置支持图像的模型。';}).catch(()=>{$('capability').textContent='请通过本地服务启动。';});
 function invalidate(){frames=[];$('frames').innerHTML='';$('answer').innerHTML='';$('analyze').disabled=true;}
 function lock(value){busy=value;for(const id of ['file','sample-video','frame-count','sample','question','mode'])$(id).disabled=value;$('analyze').disabled=value||!frames.length;if(!value)$('mode').options[1].disabled=!modelReady;}
 function message(text,error=false){$('status').textContent=text;$('status').classList.toggle('error',error);}
 function useSample(){if(objectURL){URL.revokeObjectURL(objectURL);objectURL='';}player.src='sample.webm';material='内置原创样片';$('material').textContent='内置原创样片 · 蓝色方块横向移动';$('file').value='';invalidate();message('已恢复样片，请重新抽帧。');}
 $('sample-video').onclick=useSample;
 $('file').onchange=()=>{const file=$('file').files[0];if(!file)return;if(!file.type.startsWith('video/')){message('请选择浏览器支持的视频格式。',true);return;}if(file.size>150*1024*1024){message('演示限制为150MB以内的视频。',true);return;}if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(file);player.src=objectURL;material=file.name;$('material').textContent=file.name+' · 仅在当前浏览器会话读取';invalidate();message('已更换视频，请等待元信息后重新抽帧。');};
 $('frame-count').onchange=()=>{invalidate();message('帧数已改变，请重新抽帧。');};
 $('question').oninput=()=>{if(frames.length){$('answer').innerHTML='';message('问题已修改，可以分析现有采样帧。');}};
 player.addEventListener('loadedmetadata',()=>{if(!Number.isFinite(player.duration)||player.duration>600||player.duration<=0){invalidate();message('只支持10分钟以内、具有有效时长的视频。',true);}else message('视频已就绪：'+player.duration.toFixed(2)+'秒。可以开始抽帧。');});
 player.addEventListener('error',()=>message('浏览器无法解码该视频，请尝试WebM或常见MP4格式。',true));
 function seek(t){return new Promise((resolve,reject)=>{if(Math.abs(player.currentTime-t)<.001&&player.readyState>=2){resolve();return;}const timer=setTimeout(()=>{cleanup();reject(Error('视频定位超时，请换一个浏览器可解码的文件。'));},8000);const done=()=>{cleanup();resolve();};function cleanup(){clearTimeout(timer);player.removeEventListener('seeked',done);}player.addEventListener('seeked',done);player.currentTime=t;});}
 $('sample').onclick=async()=>{if(busy)return;if(!Number.isFinite(player.duration)||player.duration<=0||player.duration>600){message('请先加载有效视频。',true);return;}lock(true);player.pause();invalidate();message('正在实际解码并抽取画面…');const before=performance.now();
  try{const n=Number($('frame-count').value),canvas=document.createElement('canvas');canvas.width=320;canvas.height=180;const ctx=canvas.getContext('2d');for(let i=0;i<n;i++){const t=Math.min(player.duration-.05,player.duration*(i+.5)/n);await seek(t);ctx.fillStyle='#000';ctx.fillRect(0,0,320,180);const ratio=Math.min(320/player.videoWidth,180/player.videoHeight),w=player.videoWidth*ratio,hh=player.videoHeight*ratio;ctx.drawImage(player,(320-w)/2,(180-hh)/2,w,hh);const image=canvas.toDataURL('image/jpeg',.45);if(image.length>30000)throw Error('画面压缩后仍过大，请换用内容更简单的短片。');frames.push({time:Number(t.toFixed(3)),image});}$('frames').innerHTML=frames.map((f,i)=>`<button type="button" data-frame="${i}" aria-label="跳到${f.time.toFixed(2)}秒"><img src="${f.image}" alt="${f.time.toFixed(2)}秒画面"><span>${f.time.toFixed(2)}s</span></button>`).join('');message('已抽取'+n+'帧，浏览器采样耗时'+Math.round(performance.now()-before)+'ms；尚未执行内容理解。');
  }catch(error){invalidate();message(error.message,true);}finally{lock(false);}
 };
 $('frames').onclick=e=>{const b=e.target.closest('[data-frame]');if(b&&!busy)player.currentTime=frames[Number(b.dataset.frame)].time;};
 $('video-form').onsubmit=async e=>{e.preventDefault();if(busy||!frames.length)return;lock(true);message($('mode').value==='llm'?'正在发送采样图像并请求模型…':'正在校验采样输入…');
  try{const r=await fetch('/api/video',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:$('question').value.trim(),frames,mode:$('mode').value,duration:player.duration})}),data=await r.json();if(!r.ok)throw Error(data.error || '分析失败');$('answer').innerHTML='<h2>本次结果</h2><p class="answer-text">'+h(data.answer)+'</p>'+data.evidence.map(x=>'<div class="evidence-entry"><strong>'+x.time.toFixed(2)+'秒</strong><p>'+h(x.observation)+'</p></div>').join('')+'<p class="boundary-note">'+h(data.uncertainty)+'</p><p class="boundary-note">'+h(data.boundary)+'</p>';publishResult('video',data,{material,frames});message('分析完成，记录已保存。');}catch(error){message(error.message,true);}finally{lock(false);}
 };
 addEventListener('pagehide',()=>{if(objectURL)URL.revokeObjectURL(objectURL);});
})();
