# D09 需求设计工作区

适用范围：本机单工作区首版。需求、用例与审核由服务端保存；未提供账户认证、对象权限或多人审批。

## 从原文到发布

1. **导入需求**：粘贴文本，或选择 UTF-8 TXT / Markdown。保存名称、原文、文件名、SHA256 和段落编号。也可使用 [考勤样例](../demos/05-requirements/samples/attendance.md)。
2. **分析版本**：在文档页选择离线规则或模型。任务绑定具体原文版本，结果不覆盖已有用例集。
3. **核对来源**：用例编辑器左侧显示原文，右侧显示当前用例。点击“定位原文”回到对应段落；追踪矩阵按验收条件展示原文依据、用例和审核状态。
4. **完善用例**：修改标题、场景、所属需求、验收关联、前置条件、操作、输入和预期。可以新增/删除用例、增删步骤，合并完全重复候选。没有原文依据的业务条件保留为待确认，不凭空补造阈值。
5. **提交版本**：修改停止约 700ms 后保存为服务端草稿，刷新可恢复。“保存为新版本”固定整套内容，原版本与审核保留，新版本重新待核对。
6. **审核**：勾选具体用例，弹窗显示数量和编号，填写记录人及核对说明。可以核对通过或退回；未提交草稿、未解决问题、失效关联或受影响来源不能核对通过。
7. **发布**：须引用当前原文、没有草稿、全部用例在当前版本核对通过，且每项验收条件都有关联。发布保存当时的原文、用例、审核与哈希，后续修订不覆盖快照。
8. **导出**：支持 CSV / JSON / Markdown。用例集导出是已提交版本，不含自动草稿；发布记录导出固定快照。JSON 可校验后导回新文档与用例集，旧审核仅作历史材料，不自动成为新审批。

“已核对”是内容评审记录，不表示测试执行成功。原文匹配与编号关联也不代表语义完整或业务正确。

## 输入与生成边界

- 一份原文最多 20,000 个 Unicode 字符、40 个非空段落；单段最多 1,500 字。浏览器文件上限 80 KiB。按非空行分段，不把 Markdown 当作可执行 HTML。
- 段落 `P001` 等编号只在具体文档版本内有效，偏移按 Python Unicode 码点计数，`text[start:end]` 对应原文。需求 `REQ-001`、条件 `AC-001-01` 和用例 `TC-001` 在具体分析/用例集内解释，不能跨批次只凭短编号关联。
- 离线模式识别常见中文角色与约束，形成适用的正向、异常、边界和权限场景模板，缺少具体数据时保留问题。它不是语义理解模型，仍可能遗漏或错误拆分条件。
- 模型模式实际请求结构化需求、验收条件、问题和用例步骤，单次最多 6 个原文段落、24 条模型用例。引用必须逐字存在于对应段落，条件索引、场景、字段和正向场景覆盖须通过校验，失败结果不创建用例集。
- 使用共用 `LAB_LLM_BASE_URL`、`LAB_LLM_MODEL`、`LAB_LLM_API_KEY`，见 [模型配置](MODEL_SETUP.md)。单次请求输出上限 6,000 token；接口不支持时会明确失败。保存模型名与提示词版本，实际 token/金额暂记未知。未完成真实商业模型质量评测。
- 每个用例集最多 160 条用例，每条最多 20 个步骤。最多 100 份文档、10 个排队/运行任务。一次分析只作一次模型请求，不自动重复计费调用。
- 内置样例为自编考勤需求。当前没有 ER/UML、任意测试执行或 Jira 全量同步。

## 草稿、冲突与审核

服务端草稿绑定 `base_version` 和 `draft_revision`，同一工作区共享一份草稿。它提供跨浏览器数据恢复，不提供独立用户草稿隔离。过期原文写入、草稿写入或提交均返回 409，不能覆盖他人的较新内容。

冲突窗口展示当前用例的本地内容、服务端内容及两个版本号。可以先下载本地修改备份，再读取服务端手动合并；本地修改备份不等同可导入的完整用例集。关闭窗口只保留本地视图，不会强制覆盖服务端。

新版本不沿用旧审核。审核时拒绝含待确认问题或“待确认/待补充/待完善”字段的用例，核对通过须填写至少五字说明。记录人是手动输入字段，没有身份校验。发布检查的条件关联率只是结构检查；人工需确认业务语义、具体输入和预期。

需求原文修订以逐段文本比较定位受影响需求，受影响用例不能核对通过；未变化段落的旧版用例可继续记录评审，但旧来源用例集不能发布为最新需求成果。新增段落、同义改写与跨段影响需要人工复核。应对最新原文重新分析，首版不自动把旧审核或用例合并到新分析。

## 任务与运行

任务队列保存在 SQLite，后台单线程依次处理。排队任务可取消，运行任务在外部请求返回后的阶段边界检查取消。服务重启后运行任务标为中断；排队任务继续。失败/取消/中断任务可手动提交新的运行，旧任务保留。重启时已发出但未落库的模型请求可能已经计费，不能保证外部调用恰好一次。

当前沿用标准库 HTTP 服务和原生 JavaScript，与 D01 相同；未整体迁移到规划中的 FastAPI/SQLAlchemy 或独立 worker 进程。没有新增 Python 依赖，六项目继续共用同一个 Conda 环境或容器。

Docker 更新：

```bash
git pull
docker compose up -d --build --wait
```

入口：<http://127.0.0.1:8765/demos/05-requirements/>。Conda/venv 的原有启动脚本保持不变。升级后可按 Ctrl+F5 强制刷新。新页面使用独立 `workspace.js`，加载失败时保留提示与重试入口。

## 数据与备份

D09 为 `/data/requirements.sqlite3`；D01 为 `/data/process.sqlite3`，共用现有 `process-data` 命名卷，各自独立数据库。源码本地运行默认使用仓库 `data/`，也可由 `LAB_DATA_DIR` 指定目录。清理浏览器或普通 `docker compose down` 不删除数据，`down -v` 会删除卷内两个项目的数据。

为运行中的 D09 创建一致性快照：

```bash
docker compose exec -T lab python scripts/backup_process_data.py --project requirements --output /data/d09-backup.sqlite3
docker compose cp lab:/data/d09-backup.sqlite3 ./d09-backup.sqlite3
```

本地共用环境：

```bash
python scripts/backup_process_data.py --project requirements --output d09-backup.sqlite3
```

目标文件必须不存在。备份含原文、分析、草稿、任务、版本、审核和发布，不含环境变量中的密钥；会校验 SQLite 完整性。恢复前应备份现有库并停止服务，避免覆盖正在使用的 WAL 文件。Docker 恢复：

```bash
docker compose stop lab
docker compose run --rm --no-deps -v ./d09-backup.sqlite3:/restore.sqlite3:ro lab python -c "import sqlite3; src=sqlite3.connect('file:/restore.sqlite3?mode=ro',uri=True); assert src.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; dst=sqlite3.connect('/data/requirements.sqlite3'); src.backup(dst); dst.close(); src.close()"
docker compose up -d --wait
```

旧版 `engineering-product:requirements:v1` LocalStorage 不自动删除，数据页可导出备份。旧需求可以重新粘贴分析，旧审核不直接转换。`workbench.html` 与原 `/api/requirements` 仅保留为规则/模板教学基线，新工作区使用独立 API。

## API

共同前缀为 `/api/requirements-workspace`，与旧教学接口区分。这是首版实际路径，规划中的 `/api/v1` 尚未统一迁移。

| 方法 / 路径 | 用途 |
|---|---|
| GET `/workspace` | 文档、任务、用例集和发布摘要 |
| POST `/documents` | 保存名称、正文和 TXT/MD 文件名 |
| GET `/documents/{id}?version=N` | 原文与段落、历史版本 |
| POST `/documents/{id}/revisions` | 带 `base_version` 修订原文 |
| POST `/documents/{id}/analyses` | 对指定版本提交离线/模型任务 |
| GET `/documents/{id}/changes?before=N&after=M` | 段落文本差异 |
| POST `/jobs/{id}/cancel` 或 `/retry` | 取消 / 新建重试任务 |
| GET `/sets/{id}?version=N` | 用例、分析、来源、草稿与审核 |
| POST `/sets/{id}/draft` | 带原版本和草稿修订号自动保存 |
| POST `/sets/{id}/discard-draft` | 校验版本后放弃自动草稿 |
| POST `/sets/{id}/commit` | 从指定草稿固定新版本 |
| POST `/sets/{id}/reviews` | 指定版本、用例编号和确认数量进行审核 |
| POST `/sets/{id}/publish` | 门禁检查后保存发布快照 |
| GET `/sets/{id}/export?format=json` | 导出已提交用例集版本 |
| GET `/releases/{id}/export?format=json` | 导出固定发布快照 |
| POST `/imports` | 校验 D09 JSON 并建立待核对用例集 |

导出格式另支持 `csv` 和 `markdown`。CSV 为 UTF-8 BOM，对可能被表格软件当作公式的文本加前缀，JSON 保留原字段。静态服务不公开数据库，同源检查限制跨站写入；这些措施不构成登录与工作区授权。

## 验收与质量评估

```bash
python -m unittest discover -s tests -v
node tests/test_products.cjs
node tests/test_ui.cjs
# 仅开发验收需要 Playwright 与 Chromium；运行产品不需要 Node.js
node tests/test_requirements_browser.cjs
```

单元/API 验收使用临时数据库和模型桩，覆盖引用校验、非法模型不入库、版本冲突、草稿恢复、审核门禁、来源影响、发布不可变、导出回导和任务恢复。浏览器验收使用隔离的 CI 卷，覆盖真实上传、编辑自动保存、刷新恢复、双浏览器冲突、核对发布、JSON 回导、原文变更、390px 页面及容器重启。

后续独立评估仍按计划准备 100 条需求，按业务来源分组为 20 条开发和 80 条保留，两名审核者标注验收条件和用例；比较规则与单轮模型，报告提取 P/R/F1、人工可用率、重复率及审核耗时。当前没有这些真实质量结果，不以自动化检查数代替业务质量。
