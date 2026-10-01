"""Real CPU training and paired evaluation; simulated labeled production windows."""
import hashlib,time
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score,log_loss

def data(seed,n,shift=0):
    r=np.random.default_rng(seed);x=r.normal(size=(n,4));x[:,0]+=shift
    y=(x[:,0]+.8*x[:,1]-.6*x[:,2]+r.normal(0,.25,n)>0).astype(int)
    return x,y

def run(noise=.4,shift=0,labels=True):
    start=time.perf_counter();x,y=data(42,500);vx,vy=data(43,200);px,py=data(44,300,shift)
    stable=LogisticRegression(random_state=42).fit(x,y)
    # Controlled training-label corruption models a bad candidate release.
    bad=y.copy();r=np.random.default_rng(45);mask=r.random(len(y))<noise;bad[mask]=1-bad[mask]
    candidate=LogisticRegression(random_state=42).fit(x,bad)
    pred= candidate.predict(px);prev=stable.predict(px)
    old=float(accuracy_score(py,prev));new=float(accuracy_score(py,pred));drop=old-new
    rollback=labels and drop>.08;action='回滚到 v1' if rollback else ('保持 v2，等待标签核验' if not labels else '保留 v2')
    reference=np.histogram(x[:,0],bins=[-np.inf,-1,-.5,0,.5,1,np.inf])[0]/len(x)
    current=np.histogram(px[:,0],bins=[-np.inf,-1,-.5,0,.5,1,np.inf])[0]/len(px)
    psi=float(np.sum((current-reference)*np.log((current+1e-6)/(reference+1e-6))))
    active=stable if rollback else candidate
    sample=[[float(t) for t in row] for row in px[:5]]
    return {'provider':'真实 CPU 逻辑回归训练；合成数据模拟生产窗口','seed':42,'n_train':500,'n_validation':200,'n_current':300,
      'data_hash':hashlib.sha256(x.tobytes()+y.tobytes()).hexdigest()[:16], 'noise':noise,'shift':shift,'labels':labels,
      'v1_accuracy':old if labels else None,'v2_accuracy':new if labels else None,'drop':drop if labels else None,
      'validation_v1':float(accuracy_score(vy,stable.predict(vx))),'validation_v2':float(accuracy_score(vy,candidate.predict(vx))),
      'psi':psi,'drift':psi>.2,'threshold':.08,'rollback':bool(rollback),'action':action,'active_version':'v1' if rollback else 'v2',
      'histogram':{'reference':reference.tolist(),'current':current.tolist()},
      'samples':[{'features':row,'prediction':int(p),'probability':round(float(prob),4)} for row,p,prob in zip(sample,active.predict(px[:5]),active.predict_proba(px[:5])[:,1])],
      'duration_ms':round((time.perf_counter()-start)*1000,2),
      'trace':['固定随机种子生成训练/验证/监控窗口','训练 v1 和含标签噪声的候选 v2','计算特征分布 PSI','在同一监控窗口比较 v1/v2' if labels else '真实标签缺失：不计算线上准确率',action,'用当前活动模型重新预测样本']}
