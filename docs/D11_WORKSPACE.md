# D11 测试与缺陷修复工作区

D11 首版将修复任务、补丁、测试与人工审查保存在服务端。入口为 `/demos/01-repair-agent/`。它针对三个固定的原创 Python 单函数快照，提供受控的“复现 → 候选 → 验证 → 修订 → 审查”流程。

## 运行方式

| 方式 | 启动 | D11 执行范围 |
|---|---|---|
| Docker Compose | `docker compose up --build -d --wait` | 独立 worker + 一次性任务容器；可用离线、手写、模型候选 |
| Conda | 原有 `start.ps1 -Manager conda` / `start.sh --manager conda` | 共用 `engineering-practice-lab` 环境，只执行内置可信候选 |
| Python venv | 原有 `start.ps1 -Manager venv` / `start.sh --manager venv` | 共用 `.venv`，只执行内置可信候选 |

本次没有新增 Python 包。本地模式不以 Python 子进程冒充隔离沙箱，因此不开放手写或模型代码执行。Docker 方式仍是一条启动命令；需要 Linux containers，Compose 会构建应用镜像和小型任务镜像。

Compose 中：

- `lab`：原 Web 服务，UID/GID 10001，只读根文件系统，不挂载 Docker socket。
- `repair-worker`：复用应用镜像，独立进程领取任务，具有 `/data` 和 Docker socket。它是受信任的基础设施进程，socket 权限可控制 Docker 主机，不能向外暴露或装入未经审阅的插件。启动时仅用 SETUID/SETGID 设置数据用户和 socket 附加组，随后主进程降至 UID/GID 10001；不要求手工填写宿主 Docker 组号。数据库采用同组可写权限。
- `repair-image`：构建并检查任务镜像后正常退出。`Exited (0)` 是预期状态。
- 每次测试：worker 通过 Unix socket 的 Docker Engine HTTP API 创建短生命周期容器，完成、取消、超时后删除。使用标准库客户端，不在 Conda 环境中安装 Docker SDK。

worker 仅连接固定 `/var/run/docker.sock`。Windows/macOS Docker Desktop 使用 Linux 引擎；自定义 rootless socket 和远程 Docker daemon 尚未验收。

## 操作流程

1. 选择运费边界、空输入平均值或稳定去重快照，查看源码、测试输入与预期。SHA-256 标识真实内容快照，不是外部 Git commit。
2. 创建任务，选择离线、手写或模型候选。离线策略提供“正确候选”“错误候选”“先失败再修订”，用于核查执行和拒绝链路。
3. 首先运行原始测试，确认缺陷可复现；缺陷未复现则不生成候选。
4. 候选必须为指定路径的一个完整函数文件。服务端生成统一 diff，测试不接受修改。每轮分别运行回归和独立验收，保留每项输入、预期、实际值、错误及耗时。
5. 在任务页切换轮次。点击失败用例可查看日志并返回对应修改文件；执行过程可定位阶段和停止原因。
6. 通过候选进入人工审查，结论绑定候选哈希和任务修订号。失败轮次不能被误认可；并发审查使用修订冲突检测。记录人为本机填写字段，尚未认证身份。
7. 下载 `.patch` 或完整 JSON。可从选定候选继续手写修订；重试创建新任务，不覆盖原证据，不继承认可记录，也不自动创建远程 PR。

原 `workbench.html`、`engine.py` 和 `/api/repair` 继续作为可信样例教学基线。旧 LocalStorage 记录可在设置中下载；不会转换成新运行器的执行或审查证据。

## 隔离与补丁约束

| 边界 | 固定策略 |
|---|---|
| 输入 | 只开放三个已打包的函数快照，不接受任意 Git URL、ZIP 或 shell 命令 |
| 文件 | 只允许当前 `src/*.py` 的精确路径；1–12000 UTF-8 字节；测试、配置和其他文件不可写 |
| Python 范围 | 保留函数名和单参数签名；允许常见纯函数内置操作与 `dict.fromkeys`；禁止 imports、I/O、内部属性、装饰器和模块级执行。AST 检查只是额外限制，Docker 是执行边界 |
| 根文件系统 | 只读；仅 `/tmp` 为 16 MiB 临时内存文件系统，noexec/nosuid |
| 用户与权限 | UID/GID 65534；capabilities 全部移除；no-new-privileges |
| 网络与挂载 | `network=none`；无数据库、Docker socket、宿主目录或凭据挂载；不向任务传入模型密钥 |
| 资源 | 0.5 CPU、128 MiB 内存及同值 swap 上限、32 PIDs |
| 时限 | 单个用例进程 1 秒；一次测试容器 20 秒；任务 240 秒；单个模型请求 45 秒 |
| 候选预算 | 1–3 轮，即最多两次修订；每次模型调用输出上限 1800 token |

运行器在启动前核查实际容器配置，执行时固定本地镜像内容 ID（`sha256:...`），结果中保存环境、源码与测试哈希。镜像标签可更新，但已开始任务在同一固定 image ID 上执行。构建基础镜像未锁定 digest，不能声称跨机器逐字节可复现。

独立测试是公开教学样例，不向修订提示发送独立测试输入/输出细节，但不能据此宣称隐藏保留集或反过拟合保证。所有测试通过仍不等于普遍正确、已修复任意仓库或可以自动合入。

## 模型模式

在 `.env` 配置 `LAB_LLM_BASE_URL`、`LAB_LLM_MODEL`、`LAB_LLM_API_KEY`，重新创建 Compose 服务。应用和 worker 均读取配置，任务创建时固定模型与服务地址的哈希，执行配置不一致则停止。

必须在创建任务页显式选择模型、候选预算并确认调用。每轮仅发送缺陷说明、允许文件、基线代码、上轮候选和回归反馈；服务端接收：

```json
{"files":[{"path":"src/shipping.py","content":"def shipping(total):\n    return 0 if total >= 100 else 10\n"}],"summary":"包含临界金额"}
```

非法路径/语法可在所选预算内修订；服务或传输失败立即停止，不盲目重发付费请求，不伪装为离线成功。新建模型重试任务需再次确认预算。当前可靠记录来源、输入哈希、提示版本和候选轮次；实际 token、费用为未知。开发测试使用模型桩，不调用真实付费服务。

## 状态与恢复

任务状态为 `queued → running → succeeded/failed/timed_out`，以及 `cancelling → cancelled`、心跳失效后的 `interrupted`。执行状态、各项测试、人工结论是三个独立维度。

- 任务领取在 SQLite 事务中完成，避免重复领取；每个运行任务每秒更新心跳。
- worker 被终止后，超过 20 秒无心跳的任务标为中断；恢复后的 worker 按工作区和任务标签删除遗留任务容器，不处理其他容器。
- 用户停止后禁止发布通过结果。模型请求若已在网络中发送，取消状态立即记录，最多等待当前请求超时后结束；不会再执行新候选。
- 应用重启不会终止独立 worker，也不会无条件重发付费请求。
- runner 不可用时创建任务返回 503；不能用看似成功的空结果掩盖故障。

排查：`docker compose logs --tail=100 repair-worker lab`。确认 `repair-image` 构建成功、Docker socket 可达、worker 健康；镜像与快照不一致时重新执行带 `--build` 的启动命令。

## 数据、备份与恢复

数据文件为 `/data/repair.sqlite3`，本地默认为 `data/repair.sqlite3`，与 D01/D09 共用命名卷但数据库独立。所有输入和产物保存在 DB，任务容器删除不影响证据。

```bash
docker compose exec -T lab python scripts/backup_process_data.py --project repair --output /tmp/repair-backup.sqlite3
docker compose cp lab:/tmp/repair-backup.sqlite3 ./repair-backup.sqlite3
```

备份脚本使用 SQLite backup API；输出文件必须尚不存在。恢复前停止应用和 worker，校验备份完整性并通过 backup API 写回，以保留数据库文件权限：

```bash
docker compose stop lab repair-worker
docker compose run --rm --no-deps -v ./repair-backup.sqlite3:/restore/repair.sqlite3:ro lab python -c "import sqlite3; s=sqlite3.connect('file:/restore/repair.sqlite3?mode=ro',uri=True); assert s.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; d=sqlite3.connect('/data/repair.sqlite3'); s.backup(d); d.close(); s.close()"
docker compose up -d --wait
```

恢复后处于运行中的旧任务会由心跳机制标为中断；按需显式重试。不要使用 `docker compose down -v` 清理日常容器。

## API

均使用同源 JSON，错误包含 `error`；有效创建返回 202，输入错误 400、未知对象 404、证据/修订冲突 409、运行器/模型不可用 503。

| 方法与路径 | 用途 |
|---|---|
| `GET /api/repair-workspace/workspace` | 快照、最近200任务和运行器能力 |
| `POST /api/repair-workspace/tasks` | 固定输入并入队；`repository/mode/candidate/max_attempts/title`，人工模式另含 `path/source`，从原候选修订可指定 `parent_id` |
| `GET /api/repair-workspace/tasks/{id}` | 基线、每轮补丁与测试、门禁、事件和审查 |
| `GET /api/repair-workspace/tasks/{id}/events` | 顺序事件 |
| `POST /api/repair-workspace/tasks/{id}/cancel` | 停止任务 |
| `POST /api/repair-workspace/tasks/{id}/retry` | 显式创建新尝试，返回新任务 ID |
| `POST /api/repair-workspace/tasks/{id}/reviews` | `revision/attempt_sha256/decision/actor/comment` |
| `GET /api/repair-workspace/tasks/{id}/export` | 完整 JSON；`format=patch&attempt=2` 下载指定轮次补丁 |

## 评估与下一阶段

当前完成的是固定快照的执行、版本证据、回归门禁和页面闭环。下一阶段按原计划准备至少5个授权开源 Python 仓库与30个独立缺陷，覆盖3类缺陷；按仓库/缺陷族划分开发和验收；在固定模型和预算下比较无修复、单轮和有限循环，记录解决率、回归破坏、非法补丁拦截、耗时与实际成本。

任意仓库检出、依赖镜像构建、外部 Git 提交、多人认证、GitHub PR 集成、覆盖率和跨仓库质量评测均未在本首版实现。原任务清单的共同 FastAPI/ORM/权限迁移继续保留。

实现依据：[Docker Engine API](https://docs.docker.com/reference/api/engine/)、[容器运行选项](https://docs.docker.com/reference/cli/docker/container/run/)、[资源约束](https://docs.docker.com/engine/containers/resource_constraints/)。

## 2026-10-20：逐测试变化与固定任务对照

任务详情新增“测试变化”：将指定候选与原始基线逐项比较，分别标明新修复、新增失败、保持不变和未执行，点击用例继续查看原始日志。通过数量与人工结论保持分离。

“任务对照”可从同一教学快照选择2–4个已结束且有实际基线的任务。服务端在同一事务内读取任务、每轮证据和当时的审查，核对源码/测试哈希、测试集合及执行环境后保存不可变报告。容器ID属于每次执行实例，不作为环境差异；镜像ID、隔离策略或Python版本变化会阻止混比。一个工作区最多100份报告。

报告包含逐用例结果、相对基线的新修复/新失败、最终候选间统一diff、实际轮数、候选测试累计耗时、模型与提示标识、未知用量/费用和证据SHA256。JSON包含冻结的完整任务；Markdown便于验收阅读。后续任务追加审核不会修改旧报告，重新保存对照才会获取新审查。

新增接口（前缀`/api/repair-workspace/`）：

| 方法与路径 | 用途 |
|---|---|
| POST comparisons | title、task_ids（2–4个不同任务），保存对照，返回comparison_id |
| GET comparisons | 最近100份对照摘要 |
| GET comparisons/{id} | 完整固定对照 |
| GET comparisons/{id}/export?format=json或markdown | 原生下载，支持HEAD |

数据库新增`comparisons`表，启动时兼容建立，不改变原任务数据。SQLite备份继续包含此表。本轮修正D11启动兜底页误写成D09的问题，调整对照信息密度、失败状态与窄屏表格；不新增运行依赖。

边界不变：原始输入仍是三个原创教学快照，未接入任意Git仓库或自动生成单测；网页之外已有5仓库/30历史缺陷的独立研究复现与小模型诊断，完整修复质量评估仍未完成。对照工具提供证据组织能力，不将预置候选的结果当作真实模型修复成绩；测试耗时不含模型、网络、排队或整体服务延迟。


## 真实开源仓库研究评测

新增独立研究CLI与固定BugsInPy 5仓库/30历史缺陷清单，实际隔离运行缺陷与上游修复版本、保存源码/测试/镜像哈希与逐测试记录。该CLI不改变网页的三个快照白名单。模型模式是已知修复文件定位的条件评测，区分单轮与最多3轮的公共测试可接受率；实际29/30例成功复现，tornado-3在当前环境未复现。真实Qwen3-0.6B Q8_0诊断中11例输入超限、17例请求失败/超时、1例三轮候选均被拒绝、1例未进入模型阶段，没有公共测试可接受补丁，不能据此声明完整语义修复率。原D11-05尚不能标为完成。数据、环境适配、执行命令、实际分布与限制见[真实资料评测](RESEARCH_EVALUATION.md)。

首页“跟着做一遍”引导覆盖快照、离线两轮任务、测试/日志/diff、审查、任务对照与导出；打开真实页面并定位操作区，由使用者确认预期现象。详见[功能体验引导](EXPERIENCE_GUIDE.md)。

## 开源算法体验与统一API

三个原创快照之外新增固定MIT开源平均值算法的教学改编，明确标注人为整除变异和空输入约定，不计入历史缺陷基准。来源、许可、原算法与本项目变更见[开放案例](OPEN_EXAMPLES.md)。引导可一键选择此快照并填入两轮任务，提交后才运行。模型模式使用总览保存的统一API，独立worker读取同一受限权限文件；任务容器仍不挂载配置文件或凭据。
