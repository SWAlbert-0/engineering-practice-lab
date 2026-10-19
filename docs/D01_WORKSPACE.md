# D01 工艺资料工作区

更新：2026-10-19。适用范围：本机单工作区的可用首版。文档与业务记录已从浏览器演示数据迁移为服务端持久化，账户隔离、企业审批及生产工艺质量认证尚未实现。

## 核心流程

1. 在“资料目录 → 导入资料”上传 UTF-8 TXT、Markdown 或文本型 PDF，填写资料名称与材料。
2. 在“处理任务”检查解析和索引状态；完成后资料进入有效索引。可以上传 [导入验收样例](../demos/02-process-rag/samples/import-check.md)，检索 `ZXDOC` 验证。
3. 在“检索资料”输入问题、选择材料与策略，检查返回段落。点击资料标题回到指定文档版本、页码与高亮原文。
4. 从检索结果形成草案：默认离线摘录；配置模型后可选择结构化生成。
5. 编辑工序、引用和参数后“保存为新版本”。旧内容与审核记录保留，新版本重新待审核。
6. 逐工序核对内容、来源范围和参数，填写记录人及审核意见，再确认通过或退回。
7. 导出 Markdown / JSON。导出包含草案版本、证据快照与该版本审核记录，可用于人工复核，不表示企业生产批准。

检索不到足够证据时不生成草案。用户新增无来源数值或参数时，必须补充人工确认依据才能通过审核；模型生成的无来源数值或参数会被拒绝，而非自动补全。数值和引用检查是结构/位置检查，工艺语义与参数适用性仍需人工核查。

## 文档与版本

- 单文件上限 8 MiB、PDF 最多 100 页、提取文本最多 30 万字；最多 50 份有效文档、1500 个有效段落，最多 20 个等待/运行任务。
- PDF 仅提取现有文本层；加密文件、扫描件与无文本页面需另行处理。解析子进程限时 25 秒，Linux 另限制解析进程地址空间为 512 MiB；不构成通用文档安全沙箱。
- 原始文件、提取页、版本和哈希全部保存在 SQLite。相同文件哈希重复上传会返回已有记录。
- 上传替换版本须保留文档名称与材料。新版本解析/建索引成功后，才切换有效文档与索引；失败保留旧版本，可查看错误并重试。
- 删除将文档移出有效索引，历史版本仍供引用追溯；不属于彻底擦除。引用已替换或删除来源的草案会显示过期，不能通过审核，需要重新检索形成新草案。
- 构建期间资料库若被其他操作修改，构建任务拒绝发布，保留当前生效快照。重试由使用者确认，不自动重复发起嵌入调用。

## 检索与模型配置

默认策略为 BM25 + 本机 TF-IDF/LSA + RRF，另提供 BM25 基线。LSA 为小语料降维向量，不是预训练语义嵌入。默认拒答采用教学阈值，需要结合实际资料评估后调整。

可选预训练嵌入使用 OpenAI 兼容 `/embeddings` 接口，在 `.env` 中配置：

```dotenv
LAB_EMBED_BASE_URL=https://你的嵌入服务地址/v1
LAB_EMBED_MODEL=你的嵌入模型
LAB_EMBED_API_KEY=你的密钥
```

重新创建服务后，到“索引与数据”显式选择预训练嵌入并重建索引。资料段落会发送到该服务；使用此索引继续上传资料也会发起编码请求。切换服务地址或模型后需要重建，关键词模式仍可独立使用。嵌入与模型输出格式校验、错误和超时不会伪装为离线成功。

工艺草案大模型使用共用 `LAB_LLM_BASE_URL`、`LAB_LLM_MODEL`、`LAB_LLM_API_KEY`，见 [模型配置](MODEL_SETUP.md)。每次生成保存模式、模型名、提示词版本、索引和证据版本；当前未统计可靠的 token 用量与金额，用量显示为未知。模型客户端仍为一次调用，不自动进行多轮收费重试。

直接 Python 运行时使用进程环境变量；`.env` 仅由 Docker Compose 读取。所有业务项目继续共用一个 Conda 环境，增加的 PDF 依赖为 pypdf。

## 持久化与备份

Docker 默认挂载 `process-data` 命名卷到 `/data`，环境变量 `LAB_DATA_DIR=/data`。根文件系统继续只读，UID/GID 10001 可写数据卷。`docker compose down` 不删除卷；不要使用 `down -v`，除非明确需要删除包括原始资料在内的全部数据。

Conda/venv 默认在仓库 `data/` 生成数据库，也可用 `LAB_DATA_DIR` 指定目录；该目录不进入 Git 或镜像构建上下文。服务静态资源入口不公开数据库、隐藏文件与配置文件。

在运行中的 Docker 服务创建一致性备份：

```bash
docker compose exec -T lab python scripts/backup_process_data.py --output /data/process-backup.sqlite3
docker compose cp lab:/data/process-backup.sqlite3 ./process-backup.sqlite3
```

本地 Python 环境：

```bash
python scripts/backup_process_data.py --output process-backup.sqlite3
```

备份目标必须不存在。脚本使用 SQLite backup API 并校验完整性，包含原始文档、索引、草案、检索和审核，不包含环境变量中的模型密钥。

恢复前先停止服务。Docker 可使用相同服务配置执行恢复，保留旧文件供回退：

```bash
docker compose stop lab
docker compose run --rm --no-deps -v ./process-backup.sqlite3:/restore.sqlite3:ro lab python -c "import sqlite3; src=sqlite3.connect('file:/restore.sqlite3?mode=ro',uri=True); assert src.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; dst=sqlite3.connect('/data/process.sqlite3'); src.backup(dst); dst.close(); src.close()"
docker compose up -d --wait
```

执行恢复前应另存当前数据库备份。恢复后检查资料数量、草案版本和来源定位。本地恢复也须停止服务，可使用 SQLite backup API 写回目标数据库，避免直接覆盖运行中的 WAL 数据库。

## 旧浏览器记录

新版不会自动删除旧的 `engineering-product:rag:v1` LocalStorage。“索引与数据”检测到旧记录时，提供完整 JSON 导出，以及将其中未索引文本导入服务端的入口。导入按内容去重；若部分提交失败，可修复问题后重试。旧草案和审核记录只作为历史备份保留，不转换为新版已审核记录。

## 任务与审核约定

后台任务表持久保存排队、运行、成功、失败、取消及中断状态。当前使用进程内单 worker 线程，尚未拆成独立 worker 服务；重启后运行中的任务标为中断，等待任务继续处理。用户可以手动重试，已发生的外部调用可能产生费用。

取消在解析或外部请求返回后的阶段边界生效，不能立即终止正在等待的模型请求；PDF 子进程另有硬超时。索引发布、文档版本切换及任务产物提交为原子事务。

草案采用追加版本与乐观并发检查。更新过期版本返回 409。审核表绑定版本，任何内容修改均产生新版本并要求重新核查；记录人是本地填写信息，未提供身份认证或角色权限。共享访问前仍需补齐权限与隔离。

## 接口

| 方法与路径 | 用途 |
|---|---|
| `GET /api/process/workspace` | 文档、索引、任务、记录摘要与能力状态 |
| `POST /api/process/documents` | 以 JSON/Base64 上传或替换文件 |
| `GET /api/process/documents/{id}?version=...` | 指定文档版本、提取页与版本历史 |
| `GET /api/process/documents/{id}/file?version=...` | 下载原文件 |
| `POST /api/process/documents/{id}/delete` | 从有效索引移除，保留历史 |
| `POST /api/process/rebuild` | 重建离线或预训练嵌入索引 |
| `POST /api/process/jobs/{id}/cancel` / `retry` | 取消或重试处理任务 |
| `POST /api/process/search` | 在生效快照上检索并保存记录 |
| `GET /api/process/searches/{id}` | 获取检索与证据快照 |
| `POST /api/process/drafts` | 提交离线/模型草案任务 |
| `GET /api/process/drafts/{id}?version=...` | 草案与审核历史 |
| `POST /api/process/drafts/{id}/save` / `review` | 保存新版本或审核指定版本 |
| `GET /api/process/drafts/{id}/export?format=markdown` | 导出 Markdown，默认格式为 JSON |
| `POST /api/process/evaluate` | 提交每批最多 50 题的评估 |
| `GET /api/process/evaluations/{id}` | 评估结果、指标及逐题记录 |

旧 `/api/rag` 与 `workbench.html` 保留为固定八段教学检索基线，不读取新资料库，也不作为新工作区入口。

## 评估与后续范围

“检索评估”可编辑问题集，或参考 [教学问题集](../demos/02-process-rag/samples/evaluation.json)。每题设置 `query`、`expected_document_ids` 或 `should_refuse`。评估固定索引快照，保存 Recall@5、MRR、拒答精确率/召回率和逐题结果，支持 JSON 导出；分母为零时显示未定义。

当前自动化验收覆盖数据、版本、索引、审核门禁、模型协议、PDF、API 与浏览器流程，未完成独立工艺领域的 20 文档/100 问题保留集及人工语义支持评测。教学样例的命中率不能视为真实企业工艺质量。

后续仍需：账户与工作区权限、独立 worker 与租约、OCR/复杂表格、来源语义支持评估、真实模型服务和不同硬件上的质量/性能验证。当前未迁移为 FastAPI/SQLAlchemy，SQLite 工作区通过现有服务适配运行，后续可按共用架构渐进迁移。


## 页面加载与升级排查

D01 入口为 `/demos/02-process-rag/` 或 `/demos/02-process-rag/index.html`。新版使用独立的 `workspace.js`，与旧版依赖共享组件的 `product.js` 分开，避免升级时复用旧脚本缓存。静态资源响应要求浏览器重新验证缓存；入口页面保留不依赖业务脚本的加载提示、失败说明和重新加载按钮。接口不可用时仍显示导航与重新读取入口。

更新后请重新启动服务。Docker 方式：

```bash
git pull
docker compose up -d --build --wait
```

Conda 或 venv 方式请停止原来的 Python 服务，再在原环境运行 `python server.py`。随后在 D01 页面按 `Ctrl+F5` 强制刷新一次。如果提示“资料服务版本不匹配”或“无法识别的响应”，请确认 8765 端口运行的是更新后的服务；若提示无法连接，请确认服务正常启动。

浏览器回归覆盖截图中的完整 `index.html` 路径、旧脚本地址隔离、脚本下载失败、初始化异常、禁用 JavaScript、旧服务响应与网络中断后的重试恢复。
