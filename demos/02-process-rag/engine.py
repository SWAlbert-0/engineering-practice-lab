"""BM25 + TF-IDF/LSA dense vectors + RRF; extractive grounded draft, not an LLM."""
import json,math,re,time
from pathlib import Path
from collections import Counter
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
DOCS=json.loads((Path(__file__).parent/'corpus.json').read_text())
def tokens(text):
    groups=re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z0-9]+',text.lower());out=[]
    for s in groups:
        out+=([s[i:i+2] for i in range(len(s)-1)] if len(s)>1 and '\u4e00'<=s[0]<='\u9fff' else [s])
    return out
T=[Counter(tokens(d['text'])) for d in DOCS];AVG=sum(sum(t.values()) for t in T)/len(T)
V=TfidfVectorizer(analyzer=tokens);X=V.fit_transform(d['text'] for d in DOCS)
SVD=TruncatedSVD(n_components=min(6,len(DOCS)-1),random_state=42);D=normalize(SVD.fit_transform(X))
def search(query,material='全部',mode='hybrid'):
    if material not in ('全部','铝合金','不锈钢','铜合金'):raise ValueError('未知材料')
    if mode not in ('hybrid','bm25'):raise ValueError('未知检索模式')
    start=time.perf_counter();qt=tokens(query);qv=normalize(SVD.transform(V.transform([query])));dense=(D@qv.T).ravel()
    lexical=[]
    for c in T:
        score=0
        for t in set(qt):
            n=sum(t in x for x in T);idf=math.log(1+(len(T)-n+.5)/(n+.5));f=c[t];score+=idf*f*2.5/(f+1.5*(.25+.75*sum(c.values())/AVG))
        lexical.append(score)
    ids=[i for i,d in enumerate(DOCS) if material=='全部' or d['material'] in (material,'通用')]
    a=sorted(ids,key=lambda i:lexical[i],reverse=True);b=sorted(ids,key=lambda i:float(dense[i]),reverse=True)
    scores={i:(1/(60+a.index(i)+1)+1/(60+b.index(i)+1) if mode=='hybrid' else lexical[i]) for i in ids}
    # A lexical gate prevents zero-evidence dense matches; then rerank with explicit material match.
    ranked=sorted([i for i in ids if lexical[i]>0],key=lambda i:scores[i]+(.004 if DOCS[i]['material']!='通用' and DOCS[i]['material'] in query else 0),reverse=True)[:3]
    hits=[dict(DOCS[i],bm25=round(lexical[i],4),dense=round(float(dense[i]),4),fusion=round(scores[i],6)) for i in ranked]
    refused=not hits or max(lexical)<1.2
    return {'mode':mode,'provider':'BM25 + LSA（小语料降维向量）+ RRF + 材料规则重排；抽取式草案，未调用 LLM',
      'hits':hits,'refused':refused,'draft':'知识库证据不足，无法生成工艺草案。请补充材料、图纸和批准的工艺文档。' if refused else '\n\n'.join(f'{n+1}. {d["text"]} [{d["id"]} · 第{d["page"]}页]' for n,d in enumerate(hits)),
      'duration_ms':round((time.perf_counter()-start)*1000,2),'corpus_size':len(DOCS),'disclaimer':'全部语料为自编教学示例，不是企业生产工艺；转速、进给量不自动推断。'}
