# Engineering Practice Lab

工程实践选题研究与原型实现。本仓库包含 25 个课程选题的分析报告，以及 6 个具有独立界面与业务流程的项目原型，支持通过 Docker Compose 统一部署。

选题材料来自丁箐老师的 14 个选题和白天老师的 11 个选题，当前实现的六个项目均选自丁箐老师的题目。各项目的已实现功能、模拟流程与待开发范围在文档中分别说明。

## 项目概览

| 编号与选题 | 项目入口 | 已实现功能 |
|---|---|---|
| **D01** · 基于 RAG 的轻量级企业工艺生成 | [工艺资料检索](demos/02-process-rag/README.md) | BM25、LSA 与 RRF 检索，材料过滤、来源引用、无依据拒答与草案审核 |
| **D02** · 基于 MLOps 的全链路 AI 模型部署与监控系统 | [模型发布平台](demos/03-mlops/README.md) | 逻辑回归训练、准确率与 PSI 计算、实验内模型切换、发布审批与告警流程模拟 |
| **D09** · 基于大模型 API 的智能需求分析与用例生成工具 | [需求设计台](demos/05-requirements/README.md) | 需求版本管理、规则或模型提取、模板用例、人工核对、追踪矩阵与文本变更关联 |
| **D11** · 基于大语言模型智能体的自动化软件测试与缺陷修复系统 | [测试与修复](demos/01-repair-agent/README.md) | 三类内置缺陷测试、候选补丁对比、回归测试、独立验收与人工审查 |
| **D12** · 轻量级多模态大模型的视频理解与推理系统 | [视频观察台](demos/04-video-understanding/README.md) | 浏览器视频解码与抽帧、时间戳校验、分析记录及可选视觉模型问答 |
| **D13** · 基于多智能体协同的科研文献智能综述生成系统 | [文献研读室](demos/06-literature/README.md) | 文献摘记管理、离线综合、单次模型综合、并行阅读、引用位置检查与人工审核 |

`D01` 等编号对应原始选题，`demos/` 下的目录序号用于代码组织，两者不一一对应。各项目的用途、操作流程、实现入口与后续评估方案见 [选题与实现说明](docs/PROJECTS.md)。

## 快速部署

### 环境要求

- Windows / macOS：Docker Desktop，使用 Linux 容器并保持 Docker 引擎运行。
- Linux：Docker Engine 与 Docker Compose v2。
- 使用 Git 获取和更新源码时需安装 Git；下载完整源码 ZIP 后也可部署。

容器包含全部六个项目的运行依赖，无需在宿主机安装 Python、Conda 或 Node.js。默认离线功能无需模型密钥、数据库或 GPU。Docker 安装与环境检查见 [部署说明](docs/DEPLOYMENT.md)。

### 获取源码并启动

访问私密仓库需具备相应的仓库权限。

```bash
git clone https://github.com/SWAlbert-0/engineering-practice-lab.git
cd engineering-practice-lab
docker compose up --build -d --wait
```

启动完成后访问 <http://127.0.0.1:8765>。首次构建需要联网下载基础镜像、系统运行库与 Python 依赖；后续构建复用缓存。`--wait` 等待服务通过健康检查后返回，容器在后台运行。

当前采用源码构建方式，未发布预构建镜像。容器内监听 `0.0.0.0:8765`，Compose 仅向宿主机的 `127.0.0.1` 发布端口。

### 状态、日志与停止

```bash
# 查看服务状态
docker compose ps

# 查看并持续跟踪日志
docker compose logs -f --tail=100

# 停止并移除容器，保留镜像
docker compose down
```

### 更新部署

```bash
git pull
docker compose up --build -d --wait
```

端口配置、镜像离线交付、健康检查与故障排查见 [部署说明](docs/DEPLOYMENT.md)。

## 本地开发

六个项目共用根目录 `server.py` 与同一个 Python 环境。本地开发支持 Conda 或 `.venv`，启动脚本负责环境准备、依赖检查与服务启动。

Windows PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Manager conda
```

macOS / Linux：

```bash
bash start.sh --manager conda
```

Conda 分支根据 `environment.yml` 创建或复用 `engineering-practice-lab` 环境，依赖通过 Conda 安装。无 Conda 时可指定 `-Manager venv` 或 `--manager venv`，在共用 `.venv` 中安装依赖。完整参数与操作说明见 [本地开发部署](docs/DEPLOYMENT.md#本地-python-开发方式)。

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

各项目的 `index.html` 提供导航、列表、详情与操作流程，`workbench.html` 承载计算工作台。页面使用 hash 路由，支持浏览器前进与后退。

项目采用独立主题，并提供“选题介绍”弹窗。图文指南按需求分析、架构设计、代码开发、任务流程、验收与排查、后续开发六章组织，包含模块关系图、流程图、代码示例与操作入口。

业务记录保存在当前浏览器的 LocalStorage，各项目独立存储。关闭页面或重建容器后，同一来源下的记录可以保留；更换浏览器、设备或端口不会自动同步。设置页提供记录导出与重置功能，当前尚未接入共享业务数据库。页面范围与状态规则见 [交互流程说明](docs/PRODUCT_FLOWS.md)。

## 可选模型配置

D09 支持模型提取，D12 支持采样帧视觉问答，D13 支持单次综合与并行阅读模式。启用时需设置以下服务端环境变量，并在页面显式选择模型模式：

- `LAB_LLM_BASE_URL`：OpenAI 兼容 API 的基础地址。
- `LAB_LLM_MODEL`：模型名称；视频问答要求模型支持图像输入。
- `LAB_LLM_API_KEY`：访问密钥。

Docker Compose 可从根目录 `.env` 读取并注入配置，模板见 `.env.example`。密钥仅在服务端读取，不包含在镜像或页面响应中。默认离线功能无需上述配置；模型模式会向所配置的外部服务发起请求。配置步骤、数据发送范围与调用预算见 [模型配置说明](docs/MODEL_SETUP.md)。

## 实现范围与限制

各项目均为工程实践原型，尚未完成原题要求的全部集成与评估。

| 项目 | 当前限制 |
|---|---|
| 测试与修复 | 使用内置可信样例与预置候选补丁，尚未调用大模型或执行任意仓库代码。独立验收用例为不参与候选选择的公开教学数据；Python 子进程不构成不可信代码沙箱 |
| 工艺资料检索 | 使用 8 段自编教学工艺卡与小语料 LSA 向量，草案为抽取式组织。新增文本仅供浏览器预览，不参与服务端检索；尚未接入 PDF 解析、预训练嵌入或模型生成 |
| 模型发布平台 | 使用合成数据训练两个逻辑回归模型，通过标签污染构造质量下降。实验内回滚会切换模型并重新预测；发布审批与流量配置为本地模拟，未连接模型注册中心或生产推理服务。PSI 0.2 与准确率下降 8 个百分点为教学阈值 |
| 视频观察台 | 支持实际抽帧与可选视觉 API，离线模式仅校验采样输入。尚未部署本地轻量模型或完成两套基准实验 |
| 需求设计台 | 模型模式提取角色与标题，用例仍由本地模板构建。尚未实现 ER/UML、自动测试执行或完整的 100 样例评测 |
| 文献研读室 | 使用 5 篇真实论文的人工摘要摘记。引用检查验证摘记中的位置匹配，不代表语义支持；全文解析与跨领域盲评尚未完成 |

## 测试与验证

在已准备的共用 Conda 开发环境中执行：

```bash
conda activate engineering-practice-lab
python -m unittest discover -s tests -v
node tests/test_ui.cjs
node tests/test_products.cjs
```

当前验收记录包含 43 项 Python 测试与前端逻辑检查。Node.js 随 Conda 开发环境提供，用于测试；运行镜像不包含 Node.js 或测试目录。前端逻辑测试使用 DOM 适配器，不替代浏览器布局验收。

容器构建、健康启动、六项目离线接口、非 root 用户与只读文件系统已通过 [GitHub Actions 容器验证](https://github.com/SWAlbert-0/engineering-practice-lab/actions/runs/39192530062)。平台覆盖、浏览器检查与外部模型服务的验证边界见 [验收记录](docs/VALIDATION.md)。

## 文档索引

| 文档 | 内容 |
|---|---|
| [选题与实现说明](docs/PROJECTS.md) | 六个选题的用途、操作流程、实现入口、边界与评估方案 |
| [部署说明](docs/DEPLOYMENT.md) | Docker 安装、容器运行、本地开发与故障排查 |
| [交互流程说明](docs/PRODUCT_FLOWS.md) | 页面范围、记录状态与人工审核规则 |
| [模型配置说明](docs/MODEL_SETUP.md) | 可选模型配置、调用预算与数据发送范围 |
| [界面设计说明](docs/DESIGN_SKILLS.md) | 设计参考、主题与验证范围 |
| [验收记录](docs/VALIDATION.md) | 已完成检查与未验证范围 |
| [开发记录](docs/WORKLOG.md) | 项目范围与部署方式的变更记录 |

选题报告中的难度、周期与价值评估属于项目规划参考。仓库不包含原始课程 PDF 或模型访问密钥。
