(() => {
  'use strict';
  const submit=form=>form+' [type=submit]';
  const training=(c,n)=>c.fill(c.$('#train-form'),{name:'Iris 教学体验 · 版本'+n,dataset:c.run.dataset,c:n===1?'1':'0.5',seed:'42',min_accuracy:'0.70',max_log_loss:'0.80'});
  const wait=(c,next,save)=>({path:'jobs/'+c.run.job,result:j=>{if(j.status==='succeeded'){save?.(j.result);return next;}if(['failed','cancelled','interrupted'].includes(j.status))throw Error(j.error||'后台任务未完成，请退出检查。');}});
  const trainResponse=(c,r)=>{if(r.path==='training-jobs'){c.run.job=r.result.job_id;return 'wait-train-'+c.run.cycle;}};
  const reviewResponse=(c,r)=>{if(r.path==='models/'+c.run.model+'/reviews'&&r.body.decision==='approved')return 'deploy-'+c.run.cycle;};
  const deployResponse=(c,r)=>{if(r.path==='deployments'){c.run.job=r.result.job_id;return c.run.rollback?'wait-rollback':'wait-deploy-'+c.run.cycle;}};
  const predict=(c,r,next)=>{if(r.path==='predict'){if(r.result.model_id!==c.run.model)throw Error('活动模型发生变化，请退出体验核对版本。');c.run.prediction=r.result;return next;}};
  const steps=[
    {id:'import',title:'保存公开训练数据',text:'已填入 Iris 二分类教学数据。点击「保存数据快照」；这些数据不代表业务泛化效果。',route:()=> 'import',target:submit('#import-form'),read:'#import-form',async prepare(c){const f=c.$('#import-form');if(!f||f.dataset.guidedStage)return;const a=await c.asset('iris');c.fill(f,{...a.fields,text:a.text});},response(c,r){if(r.path==='datasets'){c.run.dataset=r.result.dataset_id;c.run.cycle=1;return 'train-1';}}}
  ];
  for(const n of [1,2])steps.push(
    {id:'train-'+n,title:'训练第 '+n+' 个模型版本',text:'已选定本次数据和固定随机种子。点击「创建并训练」，生成真实的验证指标与模型权重。',route:c=>'train?dataset='+c.run.dataset,target:submit('#train-form'),read:'#train-form',prepare(c){c.run.cycle=n;training(c,n);},response:trainResponse},
    {id:'wait-train-'+n,title:'正在训练模型',text:'等待实际训练与制品重载校验完成，不会自动审核或加载。',route:c=>'job/'+c.run.job,poll:c=>wait(c,'review-open-'+n,r=>{c.run.model=r.model_id;c.run['model'+n]=r.model_id;})},
    {id:'review-open-'+n,title:'核对模型质量与血缘',text:'阅读固定划分、指标与适用范围，点击「记录模型审核」。通过训练门禁不等于已获人工认可。',route:c=>'model/'+c.run.model,target:'#open-model-review',read:'.equal-grid',next:'review-form-'+n},
    {id:'review-form-'+n,restore:'review-open-'+n,title:'记录本次模型审核',text:'已填入教学审核示例。按你的判断修改，再点击「保存模型审核」。',route:c=>'model/'+c.run.model,target:submit('#model-review-form'),allow:'#model-review-form',prepare(c){c.fill(c.$('#model-review-form'),{actor:'体验用户（模型核对）',decision:'approved',comment:'已核对 Iris 教学数据、固定验证划分、质量门禁和 JSON 权重；不作为生产泛化证明。'});},response:reviewResponse},
    {id:'deploy-'+n,title:'准备加载已审核版本',text:'点击「加载此版本」，检查切换目标与特征结构。',route:c=>'model/'+c.run.model,target:'a[href^="#deploy?model="]',read:'.equal-grid',next:'deploy-form-'+n},
    {id:'deploy-form-'+n,title:'确认模型加载',text:'已填入发布说明。请勾选「我已核对目标模型、特征结构和影响范围」，再点击「校验并发布」。',route:c=>'deploy?model='+c.run.model,target:submit('#deploy-form'),allow:'#deploy-form',read:'.candidate-pair',prepare(c){c.fill(c.$('#deploy-form'),{actor:'体验用户（教学发布）',comment:'加载本轮已审核 Iris 模型，用于真实预测与监控教学。'});},response:deployResponse},
    {id:'wait-deploy-'+n,title:'正在校验并加载权重',text:'只有加载探针成功才会切换活动版本。完成后自动准备预测输入。',route:c=>'job/'+c.run.job,poll:c=>wait(c,'predict-'+n)},
    {id:'predict-'+n,title:'发送一次真实预测',text:'已填入四个特征。点击「发送真实预测请求」，响应会记录实际模型版本与概率。',route:()=> 'service',target:submit('#predict-form'),read:'#predict-form',prepare(c){c.fill(c.$('#predict-form'),{rows:JSON.stringify([{sepal_length:5.1,sepal_width:3.5,petal_length:1.4,petal_width:0.2}])});},response:(c,r)=>predict(c,r,n===1?'train-2':'monitor-data')}
  );
  steps.push(
    {id:'monitor-data',title:'导入有偏移的教学窗口',text:'已填入 Iris 的合成特征偏移窗口。点击「保存数据快照」；它重复使用教学数据，不是独立留出集。',route:()=> 'import',target:submit('#import-form'),read:'#import-form',async prepare(c){const f=c.$('#import-form');if(!f||f.dataset.guidedStage)return;const a=await c.asset('iris-shift');c.fill(f,{...a.fields,text:a.text});},response(c,r){if(r.path==='datasets'){c.run.monitor=r.result.dataset_id;return 'monitor';}}},
    {id:'monitor',title:'评估当前监控窗口',text:'已选中本次窗口和教学阈值。点击「创建并评估窗口」，区分漂移、输入质量与有标签效果。',route:c=>'new-window?dataset='+c.run.monitor,target:submit('#monitor-form'),read:'#monitor-form',response(c,r){if(r.path==='monitoring-jobs'){c.run.job=r.result.job_id;return 'wait-monitor';}}},
    {id:'wait-monitor',title:'正在评估监控数据',text:'等待真实窗口报告与告警生成。不会因漂移自动回滚。',route:c=>'job/'+c.run.job,poll:c=>wait(c,'window',r=>{c.run.window=r.window_id;})},
    {id:'window',title:'查看本次窗口的告警',text:'报告已固定本次数据与模型。点击本窗口的告警，查看触发原因。',route:c=>'window/'+c.run.window,target:c=>{const a=c.$('a[href^="#alert/"]');if(!a)throw Error('本次窗口没有告警，可退出体验查看报告；不会补造告警。');c.run.alert=a.getAttribute('href').slice(7);return 'a[href^="#alert/"]';},read:'#workspace-view .panel',next:'alert'},
    {id:'alert',title:'记录告警处理依据',text:'已填入教学处理说明。点击「保存处理记录」；漂移不直接等于模型质量下降。',route:c=>'alert/'+c.run.alert,target:submit('#alert-action-form'),allow:'#alert-action-form',prepare(c){c.fill(c.$('#alert-action-form'),{actor:'体验用户（监控核对）',status:'acknowledged',comment:'已核对本窗口是教学合成偏移，并保留报告；接下来手工回滚历史版本验证流程，不作为自动生产决策。'});},response(c,r){if(r.path==='alerts/'+c.run.alert+'/actions'){c.run.model=c.run.model1;c.run.rollback=true;return 'rollback';}}},
    {id:'rollback',title:'手工回滚已验证的历史版本',text:'已指定第一个教学模型。请核对影响范围并勾选确认，再点击「校验并回滚」。',route:c=>'deploy?model='+c.run.model1+'&rollback=1',target:submit('#deploy-form'),allow:'#deploy-form',read:'.candidate-pair',prepare(c){c.fill(c.$('#deploy-form'),{actor:'体验用户（教学回滚）',comment:'返回本轮首个已核对的模型，并再次进行实际预测以确认切换。'});},response:deployResponse},
    {id:'wait-rollback',title:'正在加载历史权重',text:'等待真实回滚任务成功；失败时保留当前服务并停止推进。',route:c=>'job/'+c.run.job,poll:c=>wait(c,'verify-rollback')},
    {id:'verify-rollback',title:'验证回滚后的实际预测',text:'点击「发送真实预测请求」，核对返回的模型确实是本轮第一个版本。',route:()=> 'service',target:submit('#predict-form'),read:'#predict-form',prepare(c){c.fill(c.$('#predict-form'),{rows:JSON.stringify([{sepal_length:5.1,sepal_width:3.5,petal_length:1.4,petal_width:0.2}])});},response:(c,r)=>predict(c,r,'export')},
    {id:'export',title:'导出模型与数据血缘',text:'回滚验证已完成。点击「导出模型与血缘」，下载本次模型的权重、指标和来源记录。',route:c=>'model/'+c.run.model1,target:'a[href*="/export"]',read:'.equal-grid',download:true,filename:c=>'D02-'+c.run.model1+'.json'},
    {id:'complete',title:'已走完模型生命周期',text:'你已实际训练、审核和加载两个模型，完成预测、窗口评估、告警处理及历史回滚。教学结果不能代替业务验证。',route:c=>'model/'+c.run.model1}
  );
  LabGuidedTour.mount({id:'D02',api:'/api/mlops-workspace/',title:'让一个模型，走完发布与监控。',description:'Iris 教学数据 · 两次真实训练 · 约 8 分钟',flow:['训练审核','发布预测','监控告警','回滚导出'],source:'Fisher/UCI Iris · CC BY 4.0。合成偏移只演示监控；训练、验证和窗口均不代表独立业务评估。',initial:{dataset:'',model:'',cycle:1,rollback:false},steps});
})();
