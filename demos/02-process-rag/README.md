# 工艺资料检索

来源：丁箐 项目一。

## 运行

在仓库根目录启动，全部项目共用同一个环境：

```powershell
# Windows PowerShell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

```bash
# macOS / Linux
bash start.sh
```

脚本优先使用当前终端可调用的 Conda，自动创建/复用 `engineering-practice-lab`。无 Conda 时需要 Python 3.10–3.13（推荐3.12），自动创建共用 `.venv`。无需先手动激活，首次安装后会直接启动服务。

访问 `http://127.0.0.1:8765/demos/02-process-rag/`。环境、端口与检查参数见 [完整部署说明](../../docs/DEPLOYMENT.md)。请通过本地服务访问所有项目功能。

## 演示步骤

输入问题 → 选材料和策略 → 检索 → 点击无证据示例 → 导出证据。

## 本次实现

中文双字token、BM25、TF-IDF+SVD低维向量、RRF融合、材料过滤和规则重排、页码引用、无依据拒答。

## 当前边界

8段自编教学卡；抽取式草案；无LLM、真实语义预训练模型、PDF解析和多轮记忆。LSA会随语料变化；规则拒答阈值仅为教学用。

## 完整项目下一步

接真实授权PDF和页码映射、Chroma/Weaviate等向量库、预训练嵌入和cross-encoder；人工标注留出问题集；比较Recall@k/MRR、引用支持率、拒答错误和延迟；工艺参数必须人工核准。


## 项目页面与记录

知识库 → 文档详情 → 检索工作台 → 检索记录 → 草案编辑与审核 → 检索评估。

支持粘贴文本或导入 UTF-8 .txt 文件供预览，新增资料标记“待索引”，不会进入当前检索。检索结果可转成待审核草案，编辑后重新进入待审核。固定评估会实际发起4次检索，检查首条命中与拒答。

项目入口是 `index.html`；原计算或游戏页面保留为 `workbench.html`，由项目入口嵌入。新增记录保存在当前浏览器，可在设置页导出或重置，不会自动同步到其他设备。
