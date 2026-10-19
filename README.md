# Engineering Practice Lab

工程实践选题研究与原型实现。本仓库包含 25 个课程选题的分析报告，以及 6 个具有独立界面与业务流程的项目原型，支持通过 Docker Compose 统一部署。

选题材料来自丁箐老师的 14 个选题和白天老师的 11 个选题，当前实现的六个项目均选自丁箐老师的题目。各项目的已实现功能、模拟流程与待开发范围在文档中分别说明。

## 项目概览

| 编号与选题 | 项目入口 | 已实现功能 |
|---|---|---|
| **D01** · 基于 RAG 的轻量级企业工艺生成 | [工艺资料检索](demos/02-process-rag/README.md) | 首页直接检索、材料分类、来源定位、离线/模型草案、逐工序审核及检索评估 |
| **D02** · 基于 MLOps 的全链路 AI 模型部署与监控系统 | [模型发布平台](demos/03-mlops/README.md) | 逻辑回归训练、准确率与 PSI 计算、实验内模型切换、发布审批与告警流程模拟 |
| **D09** · 基于大模型 API 的智能需求分析与用例生成工具 | [需求设计台](demos/05-requirements/README.md) | 首页导入需求、原文/目录/用例并排编辑、自动草稿、冲突恢复、追踪审核与发布导出 |
| **D11** · 基于大语言模型智能体的自动化软件测试与缺陷修复系统 | [测试与修复](demos/01-repair-agent/README.md) | 固定快照、持久任务、独立容器、离线/手写/模型候选、有限修订、测试证据与补丁审查 |
| **D12** · 轻量级多模态大模型的视频理解与推理系统 | [视频观察台](demos/04-video-understanding/README.md) | 浏览器视频解码与抽帧、时间戳校验、分析记录及可选视觉模型问答 |
| **D13** · 基于多智能体协同的科研文献智能综述生成系统 | [文献研读室](demos/06-literature/README.md) | 文献摘记管理、离线综合、单次模型综合、并行阅读、引用位置检查与人工审核 |

`D01` 等编号对应原始选题，`demos/` 下的目录序号用于代码组织，两者不一一对应。各项目的用途、操作流程、实现入口与后续评估方案见 [选题与实现说明](docs/PROJECTS.md)。

## 完善计划与参考调研

[参考调研与完善计划](docs/RESEARCH_AND_ROADMAP.md) 对六个选题的 18 个主要参考对象进行对照，说明共用架构、功能与界面改进、评估方法及阶段安排。[实施任务清单](docs/IMPLEMENTATION_BACKLOG.md) 列出 37 项任务的依赖、估算与完成条件，D01、D09 与 D11 已交付本机工作区首版，当前实现与限制见 [D01 工作区说明](docs/D01_WORKSPACE.md) 、[D09 工作区说明](docs/D09_WORKSPACE.md) 和 [D11 工作区说明](docs/D11_WORKSPACE.md)。独立业务质量评估与其余能力继续按清单推进。

启动服务后可访问 [HTML 调研报告](report/upgrade-plan.html)，其中包含页面结构建议、工期估算与任务筛选。GitHub 中可直接阅读上述 Markdown 文档。

## 运行方式选择

项目支持 Docker Compose、Conda 和 Python venv 三种运行方式。三种方式均一次启动全部六个项目，默认访问地址为 <http://127.0.0.1:8765>。

| 运行方式 | 适用情况 | 前置环境 | 环境管理 |
|---|---|---|---|
| **Docker Compose（推荐）** | 使用统一运行环境，减少本机依赖配置 | Docker Desktop，或 Docker Engine + Compose v2 | 自动构建应用与任务镜像，附带独立修复运行器 |
| **Conda** | 已安装 Conda，或需要直接开发与调试 Python 代码 | 可在当前终端调用的 Conda | 自动创建或复用共用环境 `engineering-practice-lab`，依赖通过 Conda 安装 |
| **Python venv** | 未安装 Conda，希望直接使用本机 Python | Python 3.10–3.13，推荐 3.12 | 自动创建或复用仓库内共用 `.venv`，依赖仅安装到该虚拟环境 |

选择其中一种方式即可。Docker 方式无需在宿主机安装 Python、Conda 或 Node.js；本地运行不要求安装 Docker。默认离线功能无需模型密钥、数据库或 GPU。

### 获取源码

使用 Git 获取和更新源码时需安装 Git；访问私密仓库需具备相应权限。

```bash
git clone https://github.com/SWAlbert-0/engineering-practice-lab.git
cd engineering-practice-lab
```

也可下载并解压完整源码 ZIP，然后在仓库根目录打开终端执行以下任一启动命令。

### 方式一：Docker Compose

Windows / macOS 安装并启动 Docker Desktop，使用 Linux 容器；Linux 安装 Docker Engine 与 Docker Compose v2。先确认 `docker info` 和 `docker compose version` 正常。

三个系统使用相同命令：

```bash
docker compose up --build -d --wait
```

D11 默认启动独立 `repair-worker`；`repair-image` 镜像检查完成后退出属于正常状态。应用服务不挂载 Docker socket；只有受信任的 worker 使用它创建受限测试容器。

首次构建需要联网下载基础镜像、系统运行库与 Python 依赖；后续构建复用缓存。`--wait` 等待健康检查通过后返回，容器在后台运行，Docker 引擎需保持运行。

当前采用源码构建方式，未发布预构建镜像。容器内监听 `0.0.0.0:8765`，Compose 仅向宿主机的 `127.0.0.1` 发布端口。

```bash
# 查看服务状态
docker compose ps

# 查看并持续跟踪日志
docker compose logs -f --tail=100

# 停止并移除容器，保留镜像
docker compose down
```

### 方式二：Conda

先确认当前终端可执行 `conda --version`，无需提前创建或激活项目环境。

Windows PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Manager conda
```

macOS / Linux：

```bash
bash start.sh --manager conda
```

脚本根据 `environment.yml` 创建或复用 `engineering-practice-lab`，通过 Conda 安装依赖，检查通过后启动服务。六个项目共用一个环境，按 `Ctrl+C` 停止服务。

环境已准备时，也可手动运行：

```bash
conda activate engineering-practice-lab
python server.py
```

### 方式三：Python venv

先安装 Python 3.10–3.13，推荐 3.12，并确认当前终端能调用 Python。Linux 可能需要安装对应版本的 `python3-venv` 系统包。

Windows PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Manager venv
```

macOS / Linux：

```bash
bash start.sh --manager venv
```

脚本自动创建或复用仓库内的 `.venv`，仅在该虚拟环境中安装 `requirements.txt` 中的运行依赖，随后启动服务。无需提前激活 `.venv`，按 `Ctrl+C` 停止服务。Node.js 仅用于开发测试，不是此方式运行页面的前置条件。

### 更新与配置

使用 Git 获取源码时，先执行 `git pull`，再重新运行所选方式的启动命令。Docker 方式需保留 `--build` 参数；Conda/venv 启动脚本按依赖清单检查并同步环境。使用源码 ZIP 时，以更新后的完整源码替换代码并保留所需配置。

完整的安装步骤、端口设置、环境参数、镜像离线交付与故障排查见 [部署说明](docs/DEPLOYMENT.md)。模型模式的配置方式见 [模型配置说明](docs/MODEL_SETUP.md)。

## 目录结构

| 路径 | 内容 |
|---|---|
| `report/` | 25 个选题的 HTML 分析报告、选题数据与来源 |
| `demos/01-repair-agent/` | D11 测试与修复 |
| `demos/02-process-rag/` | D01 工艺资料检索 |
| `demos/03-mlops/` | D02 模型发布与监控 |
| `demos/04-video-understanding/` | D12 视频理解与推理 |
| `demos/05-requirements/` | D09 需求分析与用例生成 |
| `demos/06-literature/` | D13 文献综述 |
| `server.py` | 静态页面、业务 API 与健康检查入口 |
| `shared/` | 公共界面组件、主题、图文指南与模型客户端 |
| `Dockerfile` / `compose.yaml` | 镜像构建与容器运行配置 |
| `requirements.container.txt` | 固定版本的容器 Python 运行依赖 |
| `environment.yml` | 共用 Conda 开发环境 |
| `requirements.txt` | 共用 `.venv` 运行依赖 |
| `start.ps1` / `start.sh` / `launch.py` | 本地环境准备与启动脚本 |
| `tests/` | Python 引擎、HTTP 接口与前端逻辑测试 |
| `docs/` | 项目说明、部署文档、截图与验收记录 |

部署时应保留完整仓库。服务启动时加载全部六个引擎，单独复制一个项目目录无法直接运行。

## 页面与数据管理

各项目的 `index.html` 提供导航、列表、详情与操作流程，D01/D09/D11 直接调用持久化业务 API，其他项目的 `workbench.html` 承载计算工作台。页面使用 hash 路由，支持浏览器前进与后退。

项目采用独立主题，并提供“选题介绍”弹窗。图文指南按需求分析、架构设计、代码开发、任务流程、验收与排查、后续开发六章组织，包含模块关系图、流程图、代码示例与操作入口。

D01 的资料/草案、D09 的需求/用例及 D11 的任务/补丁/测试记录保存在服务端独立 SQLite 数据库，共用 Docker 的 `process-data` 卷，本地默认使用 `data/`。关闭浏览器、清理浏览器记录或重建容器不影响同一数据目录中的资料；删除数据卷会删除全部记录。其余三个项目仍使用浏览器 LocalStorage，换浏览器、设备或端口不会自动同步。页面范围与状态规则见 [交互流程说明](docs/PRODUCT_FLOWS.md)。

## 可选模型配置

D01 支持结构化工艺草案，D09 支持模型需求分析与结构化用例生成，D11 在独立 Docker 运行器中支持模型候选与有限修订，D12 支持采样帧视觉问答，D13 支持单次综合与并行阅读模式。启用时需设置以下服务端环境变量，并在页面显式选择模型模式：

- `LAB_LLM_BASE_URL`：OpenAI 兼容 API 的基础地址。
- `LAB_LLM_MODEL`：模型名称；视频问答要求模型支持图像输入。
- `LAB_LLM_API_KEY`：访问密钥。

Docker Compose 可从根目录 `.env` 读取并注入配置，模板见 `.env.example`。密钥仅在服务端读取，不包含在镜像或页面响应中。默认离线功能无需上述配置；模型模式会向所配置的外部服务发起请求。配置步骤、数据发送范围与调用预算见 [模型配置说明](docs/MODEL_SETUP.md)。

## 实现范围与限制

各项目均为工程实践原型，尚未完成原题要求的全部集成与评估。

| 项目 | 当前限制 |
|---|---|
| 测试与修复 | 仅开放三个原创单函数快照，Docker 支持手写与可选模型候选；本地模式仅执行可信样例。独立验收为公开测试，尚未完成5仓库/30缺陷评测；无账户认证、任意仓库检出或远程 PR |
| 工艺资料检索 | 文本型 PDF/TXT/Markdown 可动态入库；默认 LSA，预训练嵌入及模型草案按需配置。内置八段为教学资料；无账户权限、OCR、复杂表格或独立工艺保留集评测，审核为本地记录 |
| 模型发布平台 | 使用合成数据训练两个逻辑回归模型，通过标签污染构造质量下降。实验内回滚会切换模型并重新预测；发布审批与流量配置为本地模拟，未连接模型注册中心或生产推理服务。PSI 0.2 与准确率下降 8 个百分点为教学阈值 |
| 视频观察台 | 支持实际抽帧与可选视觉 API，离线模式仅校验采样输入。尚未部署本地轻量模型或完成两套基准实验 |
| 需求设计台 | 规则或模型生成结构化需求、验收条件与用例；需要人工补齐与核对。尚未实现 ER/UML、自动测试执行或完整的100样例评测 |
| 文献研读室 | 使用 5 篇真实论文的人工摘要摘记。引用检查验证摘记中的位置匹配，不代表语义支持；全文解析与跨领域盲评尚未完成 |

## 测试与验证

在已准备的共用 Conda 开发环境中执行：

```bash
conda activate engineering-practice-lab
python -m unittest discover -s tests -v
node tests/test_ui.cjs
node tests/test_products.cjs
```

Python 引擎、工作区/API 与前端检查的执行结果见验收记录；D01/D09/D11 另设真实浏览器验收，覆盖首页入口、核心编辑、审核导出、冲突恢复与容器重启持久化。Node.js 随 Conda 开发环境提供，用于测试；运行镜像不包含 Node.js 或测试目录。前端逻辑测试使用 DOM 适配器，不替代浏览器布局验收。

容器构建、健康启动、六项目离线接口、非 root 用户与只读文件系统已通过 [GitHub Actions 容器验证](https://github.com/SWAlbert-0/engineering-practice-lab/actions/runs/39192530062)。平台覆盖、浏览器检查与外部模型服务的验证边界见 [验收记录](docs/VALIDATION.md)。

## 文档索引

| 文档 | 内容 |
|---|---|
| [D11 工作区说明](docs/D11_WORKSPACE.md) | 修复任务、独立运行器、模型预算、测试/审查证据与备份 |
| [D01 工作区说明](docs/D01_WORKSPACE.md) | 文档入库、索引、草案审核、接口、数据备份与限制 |
| [选题与实现说明](docs/PROJECTS.md) | 六个选题的用途、操作流程、实现入口、边界与评估方案 |
| [部署说明](docs/DEPLOYMENT.md) | Docker 安装、容器运行、本地开发与故障排查 |
| [交互流程说明](docs/PRODUCT_FLOWS.md) | 页面范围、记录状态与人工审核规则 |
| [模型配置说明](docs/MODEL_SETUP.md) | 可选模型配置、调用预算与数据发送范围 |
| [界面设计说明](docs/DESIGN_SKILLS.md) | 设计参考、主题与验证范围 |
| [参考调研与完善计划](docs/RESEARCH_AND_ROADMAP.md) | 相似项目、功能与界面方案、技术取舍、实施阶段 |
| [实施任务清单](docs/IMPLEMENTATION_BACKLOG.md) | 37 项待实施任务、依赖、工时与完成条件 |
| [验收记录](docs/VALIDATION.md) | 已完成检查与未验证范围 |
| [开发记录](docs/WORKLOG.md) | 项目范围与部署方式的变更记录 |

选题报告中的难度、周期与价值评估属于项目规划参考。仓库不包含原始课程 PDF 或模型访问密钥。
