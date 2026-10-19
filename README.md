# 工程实践项目

基于丁箐老师14题、白天老师11题的选题研究，以及6个独立目录的多页面交互原型。调研日期：2026-10-01。

## 一条命令启动（Docker）

队友只需安装 Git 和 Docker。Windows/macOS 使用已启动的 Docker Desktop（Linux 容器）；Linux 使用 Docker Engine 与 Compose v2。无需安装 Python、Conda、Node.js，也无需逐个部署六个项目。

首次获取私密仓库需要自己的协作者权限：

```bash
git clone https://github.com/SWAlbert-0/engineering-practice-lab.git
cd engineering-practice-lab
docker compose up --build -d --wait
```

浏览器打开 <http://127.0.0.1:8765>。第一次自动下载基础镜像与锁定的依赖并构建，之后复用构建缓存；默认模式无需配置文件、模型密钥或 GPU。`--wait` 会等健康检查通过再返回，服务在后台运行。

```bash
# 查看状态 / 查看日志 / 停止
docker compose ps
docker compose logs -f --tail=100
docker compose down
```

更新代码后：`git pull`，再执行 `docker compose up --build -d --wait`。本仓库提供源码构建，不依赖预先发布的私有镜像。已有 Conda 环境可继续用于开发；Conda 与无 Conda 的本地启动方式保留在 [部署说明](docs/DEPLOYMENT.md)。

完整的配置、换端口、镜像离线交付与故障排查见 [部署说明](docs/DEPLOYMENT.md)。可选模型模式见 [模型配置](docs/MODEL_SETUP.md)。

## 目录

| 路径 | 内容 | 对应选题 |
|---|---|---|
| `report/index.html` | 独立HTML调研报告，筛选/排序/逐题分析/来源 | 全部25题 |
| `demos/01-repair-agent/` | 测试与修复：内置样例、候选补丁与验收 | 丁箐 项目十一 |
| `demos/02-process-rag/` | BM25+LSA/RRF、引用和拒答 | 丁箐 项目一 |
| `demos/03-mlops/` | 模型发布实验：训练、分布监控与版本切换 | 丁箐 项目二 |
| `demos/04-video-understanding/` | 视频预览、实际抽帧、时间戳问答 | 丁箐 项目十二 |
| `demos/05-requirements/` | 需求版本、用例草案与变更追踪 | 丁箐 项目九 |
| `demos/06-literature/` | 证据摘记、角色工作流与综述审核 | 丁箐 项目十三 |
| `Dockerfile` / `compose.yaml` | 一条命令构建、后台启动与健康检查 | 全项目 |
| `requirements.container.txt` | 容器运行依赖精确版本 | 全项目 |
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
| 视频观察台 | 素材、抽帧、分析记录、评估与指南 | 浏览器解码采样、可选视觉模型问答、时间戳证据 |
| 需求设计台 | 需求版本、分析、用例、追踪、变更、质量检查 | 规则/可选模型提取、用例完善、旧版本影响定位 |
| 文献研读室 | 文献、问题、工作流、草稿、审核、模式对照 | 固定摘记池、并行阅读模型流程、人工核查 |

各目录 `index.html` 是项目入口，`workbench.html` 是嵌入其中的计算工作台。页面路径使用 hash 路由，可以通过地址栏返回与前进。

新增记录保存在当前浏览器 LocalStorage；关闭页面后可继续查看，切换浏览器或清理站点数据不会自动同步。设置页可导出工作区记录或重置为初始示例。示例记录有单独标记；运行历史来自实际计算。详细页面与状态说明见 [docs/PRODUCT_FLOWS.md](docs/PRODUCT_FLOWS.md)。

## 图文项目指南

每个项目导航中的指南已扩展为六章项目说明：需求分析、架构设计、代码开发、任务流程、验收与排查、后续开发。每份包含模块关系图、分支流程图、代码片段与可直接进入功能页面的操作步骤。目录支持章节跳转，图表可在小屏内部横向滚动。内容按当前代码编写，并区分真实计算、本地流程模拟与未实现能力。

- [测试与修复指南](demos/01-repair-agent/index.html#guide)
- [工艺资料检索指南](demos/02-process-rag/index.html#guide)
- [模型发布平台指南](demos/03-mlops/index.html#guide)
- [视频理解指南](demos/04-video-understanding/index.html#guide)
- [需求分析指南](demos/05-requirements/index.html#guide)
- [文献综述指南](demos/06-literature/index.html#guide)

请通过本地服务打开这些 HTML 页面；GitHub 中可查看对应源码。指南内容位于 `shared/product/guides-data.js`，排版与图示由 `guides.js`、`guides.css` 提供，随六个项目主题显示。

## 主题与选题介绍

六个项目分别采用代码审查台、工艺资料阅览室、模型发布控制室、视频观察台、需求设计台和文献研读室主题。每个项目顶部都有“选题介绍”按钮，可查看老师来源、难度、简历价值、周期、要求与当前实现范围。

设计 skills 的调研来源、主题说明与验证边界见 [docs/DESIGN_SKILLS.md](docs/DESIGN_SKILLS.md)。所有资源随仓库提供，不需要安装新依赖。

## Demo边界

这些项目包含完整的页面导航、详情与功能引导；真实运行部分与本地模拟流程分别标明。尚未完成课程要求中的全部后端集成。

- **修复**：真实执行自编可信fixture和测试；候选补丁预置，未调用LLM。只允许内置ID，不运行用户任意输入代码。独立测试指不参与候选选择的验收样例，仍是公开教学数据。
- **RAG**：8段自编教学工艺卡，页码是教学卡页码；LSA是小语料降维向量，不能冒充预训练语义嵌入。抽取式草案不是LLM生成。新增文本仅保存在浏览器供预览，不参与服务端检索；没有PDF解析、企业数据或真实生产参数。
- **MLOps**：真正训练两个逻辑回归模型，数据为合成；坏版本由训练标签污染产生。计算中的回滚为单次实验内切换活动模型并重新推理；发布页的审批与流量配置另作为本地流程模拟，未接注册中心/服务热切换。PSI 0.2 与下降8个百分点是教学阈值。
- **视频**：真实抽帧；离线不执行视觉理解。可配置视觉API；本地轻量化模型和两基准实验待完成。
- **需求**：可选模型提取角色和标题，用例来自本地模板。没有ER/UML或完整100样例评测。
- **文献**：使用5篇真实论文的人工摘要摘记；自动检查只验证引用位置。全文解析和跨领域盲评待完成。

容器内监听 `0.0.0.0:8765`，Compose 仅将端口发布到宿主机 `127.0.0.1`；本机 Python 启动仍默认监听 `127.0.0.1`。容器用于统一团队演示环境。可信fixture的Python子进程不是安全沙箱，不可将此执行器直接扩展为公网任意代码执行服务。

## 可选模型模式

新增三个项目默认离线可用。项目九支持模型提取，项目十三支持单次模型综合与并行阅读角色，项目十二支持采样图像问答。密钥只从服务端 `LAB_LLM_BASE_URL`、`LAB_LLM_MODEL`、`LAB_LLM_API_KEY` 环境变量读取，启动后由页面显式选择模型模式。视频模式需要支持图像输入的模型。配置与调用次数见 [MODEL_SETUP.md](docs/MODEL_SETUP.md)。

## 测试

```bash
conda activate engineering-practice-lab
python -m unittest discover -s tests -v
node tests/test_ui.cjs
node tests/test_products.cjs
```

Node.js 已包含在共用 Conda 环境中，用于前端逻辑测试，不是运行页面的必要依赖。前端测试使用 DOM 适配器与实际引擎返回值，不包含浏览器布局验收。测试结果与界面验证限制见 `docs/VALIDATION.md`。

## 推荐主线

默认：D11 测试修复Agent；均衡：D01 工艺RAG；平台工程：D02 MLOps；多模态方向：D12视频理解（需算力与研究指导）。D09需求用例生成可以作为D11的前置模块。建议最后只选一个主项目做深。

分析是面向个人目标的判断；周期为每周15小时的一人估算，非老师承诺、市场统计或录取概率。源码和报告不包含原始课程PDF或任何密钥。
