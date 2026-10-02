# 工艺证据检索台

来源：丁箐 项目一。

## 运行

全部 demo 共用根目录 `environment.yml` 定义的 `engineering-practice-lab` 环境。首次使用在仓库根目录执行：

```bash
conda env create -f environment.yml
```

环境已创建后不必重复创建，每次启动只需：

```bash
conda activate engineering-practice-lab
python server.py
```

访问 `http://127.0.0.1:8765/demos/02-process-rag/`。请通过本地服务访问，直接打开 HTML 无法调用 Python API。
后续依赖统一更新根目录环境配置，不为此 demo 单独创建环境。

## 演示步骤

输入问题 → 选材料和策略 → 检索 → 点击无证据示例 → 导出证据。

## 本次实现

中文双字token、BM25、TF-IDF+SVD低维向量、RRF融合、材料过滤和规则重排、页码引用、无依据拒答。

## 当前边界

8段自编教学卡；抽取式草案；无LLM、真实语义预训练模型、PDF解析和多轮记忆。LSA会随语料变化；规则拒答阈值仅为教学用。

## 完整项目下一步

接真实授权PDF和页码映射、Chroma/Weaviate等向量库、预训练嵌入和cross-encoder；人工标注留出问题集；比较Recall@k/MRR、引用支持率、拒答错误和延迟；工艺参数必须人工核准。
