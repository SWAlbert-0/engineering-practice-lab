# 工程实践项目

基于丁箐老师14题、白天老师11题的选题研究，以及4个独立目录的多页面交互原型。调研日期：2026-10-01。

## 一条命令启动

获取完整仓库后，在根目录执行。四个项目共用一个环境，无需逐个部署。

**Windows PowerShell：**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

**macOS / Linux：**

```bash
bash start.sh
```

| 当前环境 | 自动处理 |
|---|---|
| 终端可调用 Conda | 创建或复用 `engineering-practice-lab`，依赖全部通过 Conda 安装，不调用 pip |
| 没有 Conda，已安装 Python 3.10–3.13 | 创建或复用仓库内 `.venv`，仅在该虚拟环境中安装 Python 依赖；推荐 Python 3.12 |
| 两者都没有 | 提示先安装 Miniconda / Anaconda，或 Python 3.12 |

浏览器打开 <http://127.0.0.1:8765>，Ctrl+C 停止。首次安装需要网络；以后配置未变时跳过安装，可离线运行。Conda 环境还包含测试用 Node.js 22，无 Conda 分支运行页面不需要 Node.js。

**明确使用 Conda**：Windows 命令追加 `-Manager conda`，macOS/Linux 追加 `--manager conda`。无需提前激活；也可从 Anaconda Prompt 直接执行：

```bash
conda run --no-capture-output -n base python launch.py --manager conda
```

**明确使用无 Conda 方案**：对应追加 `-Manager venv` / `--manager venv`。

端口占用可追加 `-Port 8766` / `--port 8766`；只创建环境并检查用 `-Check` / `--check`；强制同步依赖用 `-Update` / `--update`。已有环境继续复用；四个 demo 不各自创建环境。

拉取更新后重跑同一启动命令即可。完整步骤、系统要求、私密仓库访问与故障排查见 [部署说明](docs/DEPLOYMENT.md)。原有 `conda activate engineering-practice-lab` 后运行 `python server.py` 的方式仍可使用。

## 目录

| 路径 | 内容 | 对应选题 |
|---|---|---|
| `report/index.html` | 独立HTML调研报告，筛选/排序/逐题分析/来源 | 全部25题 |
| `demos/01-repair-agent/` | 测试与修复：内置样例、候选补丁与验收 | 丁箐 项目十一 |
| `demos/02-process-rag/` | BM25+LSA/RRF、引用和拒答 | 丁箐 项目一 |
| `demos/03-mlops/` | 模型发布实验：训练、分布监控与版本切换 | 丁箐 项目二 |
| `demos/04-tower-defense/` | 两类塔、五波敌人、经济与胜负判断 | 白天 B类第5题 |
| `environment.yml` | 所有 demo 共用的 Conda 环境 | 全项目 |
| `start.ps1` / `start.sh` / `launch.py` | 自动选择环境、安装检查和启动 | 全项目 |
| `requirements.txt` | 仅用于无 Conda 开发者的共用 `.venv` | 全项目 |
| `shared/` | 公用界面样式/交互工具 |
| `tests/` | 引擎与HTTP验收测试 |
| `docs/` | 验收记录、后续开发范围 |

每个 demo 的主要实现和说明在其独立文件夹，Python 服务端与样式共用。复制单个目录时应同时保留根目录 server.py 和 shared；无需拆成多个仓库。

## 页面与操作流程

| 项目 | 页面范围 | 可实际完成的操作 |
|---|---|---|
| 测试与修复 | 仓库、任务、执行记录、补丁审查、验收规则、设置 | 登记仓库信息、创建任务、运行测试、保存审查结论与备注 |
| 工艺资料检索 | 知识库、文档、检索、记录、草案审核、评估、设置 | 导入文本供预览、检索内置语料、编辑审核草案、运行固定问题评估 |
| 模型发布平台 | 数据集、实验、模型版本、发布、监控、告警 | 实际训练、保存指标、模拟审批发布与回滚、记录告警处理结论 |
| 塔防工作室 | 大厅、关卡、图鉴、布阵编辑、战斗、战绩、设置 | 三种资源难度、保存布阵并带入游戏、设置速度、保存结束战绩 |

各目录 `index.html` 是项目入口，`workbench.html` 是嵌入其中的计算或游戏工作台。页面路径使用 hash 路由，可以通过地址栏返回与前进。

新增记录保存在当前浏览器 LocalStorage；关闭页面后可继续查看，切换浏览器或清理站点数据不会自动同步。设置页可导出工作区记录或重置为初始示例。示例记录有单独标记；运行历史来自实际计算。详细页面与状态说明见 [docs/PRODUCT_FLOWS.md](docs/PRODUCT_FLOWS.md)。

## 图文项目指南

每个项目导航中的指南已扩展为六章项目说明：需求分析、架构设计、代码开发、任务流程、验收与排查、后续开发。每份包含模块关系图、分支流程图、代码片段与可直接进入功能页面的操作步骤。目录支持章节跳转，图表可在小屏内部横向滚动。内容按当前代码编写，并区分真实计算、本地流程模拟与未实现能力。

- [测试与修复指南](demos/01-repair-agent/index.html#guide)
- [工艺资料检索指南](demos/02-process-rag/index.html#guide)
- [模型发布平台指南](demos/03-mlops/index.html#guide)
- [塔防开发指南](demos/04-tower-defense/index.html#guide)

请通过本地服务打开这些 HTML 页面；GitHub 中可查看对应源码。指南内容位于 `shared/product/guides-data.js`，排版与图示由 `guides.js`、`guides.css` 提供，随四个项目主题显示。

## 主题与选题介绍

四个项目分别采用代码审查台、工艺资料阅览室、模型发布控制室和林地塔防主题。每个项目顶部都有“选题介绍”按钮，可查看老师来源、难度、简历价值、周期、要求与当前实现范围。

设计 skills 的调研来源、主题说明与验证边界见 [docs/DESIGN_SKILLS.md](docs/DESIGN_SKILLS.md)。所有资源随仓库提供，不需要安装新依赖。

## Demo边界

这些项目包含完整的页面导航、详情与功能引导；真实运行部分与本地模拟流程分别标明。尚未完成课程要求中的全部后端集成。

- **修复**：真实执行自编可信fixture和测试；候选补丁预置，未调用LLM。只允许内置ID，不运行用户任意输入代码。独立测试指不参与候选选择的验收样例，仍是公开教学数据。
- **RAG**：8段自编教学工艺卡，页码是教学卡页码；LSA是小语料降维向量，不能冒充预训练语义嵌入。抽取式草案不是LLM生成。新增文本仅保存在浏览器供预览，不参与服务端检索；没有PDF解析、企业数据或真实生产参数。
- **MLOps**：真正训练两个逻辑回归模型，数据为合成；坏版本由训练标签污染产生。计算中的回滚为单次实验内切换活动模型并重新推理；发布页的审批与流量配置另作为本地流程模拟，未接注册中心/服务热切换。PSI 0.2 与下降8个百分点是教学阈值。
- **塔防**：真实Canvas交互游戏，原创程序绘制，不含游戏引擎工程和外部素材。

仅绑定127.0.0.1，面向个人本地演示。可信fixture的Python子进程不是安全沙箱，不可将此执行器直接扩展为公网任意代码执行服务。

## 测试

```bash
conda activate engineering-practice-lab
python -m unittest discover -s tests -v
node tests/test_tower.cjs
node tests/test_ui.cjs
node tests/test_products.cjs
```

Node.js 已包含在共用 Conda 环境中，用于塔防引擎与前端逻辑测试，不是运行浏览器游戏的必要依赖。前端测试使用 DOM 适配器与实际引擎返回值，不包含浏览器布局验收。测试结果与界面验证限制见 `docs/VALIDATION.md`。

## 推荐主线

默认：D11 测试修复Agent；均衡：D01 工艺RAG；平台工程：D02 MLOps；游戏客户端：白天B5塔防。D09需求用例生成可以作为D11的前置模块。建议最后只选一个主项目做深。

分析是面向个人目标的判断；周期为每周15小时的一人估算，非老师承诺、市场统计或录取概率。源码和报告不包含原始课程PDF或任何密钥。
