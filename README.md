# 工程实践选题实验室

基于丁箐老师14题、白天老师11题的选题研究，以及4个独立目录的可运行原型。调研日期：2026-10-01。

## 快速开始：全部 demo 共用一个 Conda 环境

先安装 Miniconda 或 Anaconda，在仓库根目录执行以下命令。Windows 可使用 Anaconda Prompt；已初始化 Conda 的 PowerShell、macOS 和 Linux 终端也可使用。

```bash
conda env create -f environment.yml
conda activate engineering-practice-lab
python server.py
```

环境只创建一次。之后每次运行：

```bash
conda activate engineering-practice-lab
python server.py
```

浏览器打开 http://127.0.0.1:8765 。端口占用可使用 `python server.py --port 8766`。
所有选题 demo 共用 `engineering-practice-lab`，不为每个 demo 建环境。后续新增 demo 的依赖也统一维护在根目录 `environment.yml`。

环境配置包含 Python 3.12、NumPy、scikit-learn，以及塔防引擎测试所需的 Node.js，均通过 Conda 安装。塔防与报告也可直接打开 HTML；前三个 demo 需要上述服务端。
不需要 API Key。创建环境需要网络，安装后全部原型可离线运行。

拉取新版配置后，更新同一个环境：

```bash
conda env update -n engineering-practice-lab -f environment.yml
```

环境已存在时使用更新命令，不必重复创建。如果 Windows PowerShell 提示无法激活，先改用 Anaconda Prompt 运行上述命令。

## 目录

| 路径 | 内容 | 对应选题 |
|---|---|---|
| `report/index.html` | 独立HTML调研报告，筛选/排序/逐题分析/来源 | 全部25题 |
| `demos/01-repair-agent/` | 可信样例的测试-候选补丁-独立验证 | 丁箐 项目十一 |
| `demos/02-process-rag/` | BM25+LSA/RRF、引用和拒答 | 丁箐 项目一 |
| `demos/03-mlops/` | 真实训练、分布监控、配对质量评估和版本切换 | 丁箐 项目二 |
| `demos/04-tower-defense/` | 两类塔、五波敌人、完整胜负闭环 | 白天 B类第5题 |
| `environment.yml` | 所有 demo 共用的 Conda 环境 | 全项目 |
| `shared/` | 公用界面样式/交互工具 |
| `tests/` | 引擎与HTTP验收测试 |
| `docs/` | 验收记录、后续开发范围 |

每个 demo 的主要实现和说明在其独立文件夹，Python 服务端与样式共用。复制单个目录时应同时保留根目录 server.py 和 shared；无需拆成多个仓库。

## Demo边界

这是用于比较选题的最小原型集，不是课程完整交付。

- **修复**：真实执行自编可信fixture和测试；候选补丁预置，未调用LLM。只允许内置ID，不运行用户任意输入代码。独立测试指不参与候选选择的验收样例，仍是公开教学数据。
- **RAG**：8段自编教学工艺卡，页码是教学卡页码；LSA是小语料降维向量，不能冒充预训练语义嵌入。抽取式草案不是LLM生成。没有PDF上传、企业数据或真实生产参数。
- **MLOps**：真正训练两个逻辑回归模型，数据为合成；坏版本由训练标签污染产生。回滚为单次实验内切换活动模型并重新推理，未接注册中心/服务热切换。PSI 0.2 与下降8个百分点是教学阈值。
- **塔防**：真实Canvas交互游戏，原创程序绘制，不含游戏引擎工程和外部素材。

仅绑定127.0.0.1，面向个人本地演示。可信fixture的Python子进程不是安全沙箱，不可将此执行器直接扩展为公网任意代码执行服务。

## 测试

```bash
conda activate engineering-practice-lab
python -m unittest discover -s tests -v
node tests/test_tower.cjs
```

Node.js 已包含在共用 Conda 环境中，仅用于塔防引擎测试，不是运行浏览器游戏的必要依赖。测试结果与界面验证限制见 `docs/VALIDATION.md`。

## 推荐主线

默认：D11 测试修复Agent；均衡：D01 工艺RAG；平台工程：D02 MLOps；游戏客户端：白天B5塔防。D09需求用例生成可以作为D11的前置模块。建议最后只选一个主项目做深。

分析是面向个人目标的判断；周期为每周15小时的一人估算，非老师承诺、市场统计或录取概率。源码和报告不包含原始课程PDF或任何密钥。
