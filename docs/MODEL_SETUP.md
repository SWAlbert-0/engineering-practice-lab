# 统一模型 API 与可选模型模式

六个项目使用统一应用镜像；D11 另有独立 worker 和任务镜像。本地开发继续共用原有 Conda 环境。项目一、九、十一、十二、十三的本地处理不需要密钥；只有在工作台选择模型模式并点击运行时才发起请求。没有配置或请求失败时明确报错，不将离线结果伪装成模型结果。

## 推荐：在总览页面配置

启动后打开项目总览的“统一模型 API”，填写兼容Chat Completions的基础地址、文本模型名与API Key，点击“保存统一配置”。D01/D09/D11/D13使用文本模型；D12使用可选视觉模型名（留空时使用文本模型），共用同一个地址与Key。D02继续在本地训练/预测，不需要大模型API。嵌入索引仍用独立的LAB_EMBED参数，不把文本生成模型冒充嵌入模型。

保存配置不会发送模型请求；只有选择具体模型任务，或勾选费用确认后点击“测试已保存的文本连接”，才会调用。连接测试只验证文本和JSON协议，不能证明视觉能力或任务质量。保存后新执行任务立即读取，无需重启；运行中的任务固定其启动时的地址/密钥/模型，D13并行节点也保持一致。D11/D13的排队/重试任务已有配置身份检查，来源变化时要求新建任务。

密钥不回显到页面，不写入LocalStorage、业务记录或导出。配置保存在服务端数据目录的`model-settings.json`，POSIX下权限0600；Docker的应用和独立repair-worker以同一数据身份读取共享卷，因此无需分别配置。此为本机单工作区的受信任设置，不是多租户凭据管理。Windows权限由本机账户和目录ACL控制；迁移数据时保护此文件，不要提交到Git。

留空Key只会保留同一基础地址已有的Key；更换地址必须重新输入。“清除页面配置，恢复环境变量”删除页面保存项，随后按环境变量重新判断是否可用。页面配置优先于以下环境变量；损坏的配置会显示不可用，不静默切换供应商。上游重定向不会携带Key自动跟随，请填写最终API基础地址。

Docker Desktop访问宿主模型时，地址用`host.docker.internal`替换`127.0.0.1`；页面输入的地址由容器内服务端访问。Linux需使用容器实际可达的地址。离线功能和[开源案例](OPEN_EXAMPLES.md)的一键填入均无需API。

接口：`GET /api/model-settings`返回基础地址/模型和是否已有Key，不返回Key；同源JSON的`POST /api/model-settings`保存，`POST /api/model-settings/clear`清除；`POST /api/model-settings/test`必须携带`confirm_call: true`，显式发送一次最多32输出token的文本协议请求。费用依供应商计，不虚构金额。

## DeepSeek 官方 API

基础地址填写 `https://api.deepseek.com/v1`，文本模型填写 `deepseek-flash` 或账号可用的 `deepseek-v4-pro`，Key 使用 DeepSeek 开放平台生成的 API Key。保存后再勾选费用确认并测试已保存的文本连接。

DeepSeek 这两个模型默认开启思考，而本项目的输出预算用于最终 JSON；客户端对官方地址的这两个模型显式关闭思考，并启用 JSON 输出，避免 32 token 的连接测试在思考阶段就被截断。其他兼容服务保持原有参数；研究 CLI 显式传入的 JSON Schema 约束保留原样，需供应商支持。

HTTP 401 表示密钥认证失败，请在总览页面重新输入有效的 DeepSeek API Key 并点击保存；密钥框留空会保留旧密钥，不能修复认证错误。HTTP 402 表示余额不足，429 表示限流或配额限制。`finish_reason=length` 会单独提示输出上限，不能作为连接正常的依据。不要把 Key 发到聊天或日志中。

## 可选：Docker Compose 环境变量配置


复制根目录 `.env.example` 为 `.env`，编辑以下三个变量：

```dotenv
LAB_LLM_BASE_URL=https://你的模型服务基础地址/v1
LAB_LLM_MODEL=你已开通的模型名称
LAB_LLM_API_KEY=你的密钥
```

替换占位值后执行 `docker compose up -d --force-recreate --wait`；首次部署使用 `docker compose up --build -d --wait`。Compose 将变量注入服务端，不需要改 Dockerfile 或重新安装依赖；`.env` 不进入镜像，也不提交 Git。变量留空时仍能使用默认离线功能。

Docker Desktop 上调用宿主机的模型服务，可将地址中的 `127.0.0.1` 改为 `host.docker.internal`；Linux 使用容器可访问的实际服务地址。基础地址不带 `/chat/completions`。

## 直接运行 Python 时的服务端配置

使用提供 `/chat/completions` 的 OpenAI 兼容 API，在启动服务的同一终端设置：

```powershell
$env:LAB_LLM_BASE_URL = "https://你的模型服务基础地址/v1"
$env:LAB_LLM_MODEL = "你已开通的模型名称"
$env:LAB_LLM_API_KEY = "你的密钥"
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

macOS / Linux：

```bash
export LAB_LLM_BASE_URL="https://你的模型服务基础地址/v1"
export LAB_LLM_MODEL="你已开通的模型名称"
export LAB_LLM_API_KEY="你的密钥"
bash start.sh
```

替换占位值后再使用。直接运行 Python 时只读取进程环境变量，不自动加载 `.env`；Docker Compose 负责读取并注入 `.env`。基础地址不包含 `/chat/completions`。需要换模型时更新变量并重启服务。模型客户端不引入额外模型框架；D01 文本 PDF 解析增加共用 pypdf 依赖。

页面通过 `/api/capabilities` 只获知配置是否齐全；不会获取密钥或完整服务地址。配置齐全不表示模型一定可用，认证、格式和模态错误会在实际请求时显示。

## 模式与调用预算

| 项目 | 离线模式 | 模型模式 |
|---|---|---|
| 工艺资料工作区 | 离线摘录与草案编辑审核 | 1 次结构化工序草案生成；嵌入 API 配置与调用另见 [D01说明](D01_WORKSPACE.md) |
| 测试与修复 | 预置候选和真实测试 | 仅独立 Docker 运行器支持；1–3轮候选，每轮最多1次API调用、1800输出token；传输失败不自动重发，实际费用未知 |
| 需求设计台 | 规则提取与用例模板 | 1 次结构化调用实际生成需求、验收条件和用例步骤；首版最多 6 段、输出上限 6,000 token，引用与结构不合格不入库 |
| 文献研读室 | 原文摘录与证据编排，无语义综合 | 阅读和写作分开：单次模式每阶段 1 次；分工模式阅读最多 6 次/并发 3，写作最多 4 次/并发 2；引用检查不调用模型 |
| 视频观察台 | 服务端采样记录，无视觉回答 | 1次图像消息调用，提交1–6张最长边512像素的实际采样帧；返回帧ID后严格映射时间 |

模型模式产生实际调用费用。D13 阅读发送明确纳入的上传文本及范围，写作发送已核对证据及元数据；不自动抓取外部论文。模型输入超过 24000 字时拒绝任务，不截断后声称阅读全文。视频模式需要支持 `image_url` 图像内容的模型，只发送采样JPEG，不发送原视频或音频。

客户端采用温度0、单次45秒超时；默认3000输出token上限，各项目可明确覆盖，不假定服务支持额外的结构化输出参数。返回内容必须可解析为JSON；再由各项目验证来源片段、文献引用或证据时刻。语义支持仍需人工判断。

网页任务当前可查看执行节点/调用安排与任务时间，没有完整token用量或金额统计。原功能测试使用离线桩验证协议与错误路径；独立研究CLI已实际运行本地Qwen小模型，见后文，不代表外部付费供应商已验收。

D11 的模型请求发送固定教学源码、缺陷描述与回归反馈，不发送宿主文件、数据库或模型密钥。独立验收的输入/输出不进入修订反馈。任务创建时须确认预算，重试再次确认；Conda/venv 本地模式不执行模型源码。完整约束见 [D11工作区](D11_WORKSPACE.md)。

D13 任务保留成功节点，显式重试仅在输入指纹、模型配置一致时复用。取消不撤销已发出的请求；无可靠 usage 时不显示费用或 token 估算。支持范围与评估见 [D13说明](D13_WORKSPACE.md)。

D02无需大模型API。其可选MLflow参数/指标同步使用独立的 LAB_MLFLOW_URL、LAB_MLFLOW_EXPERIMENT、LAB_MLFLOW_TOKEN；默认无需外部追踪服务，范围见 [D02说明](D02_WORKSPACE.md)。

## 可选研究评测与实际用量

研究CLI为共用模型适配器增加可选telemetry，保留服务实际返回的prompt/completion/total token、客户端测量秒数和模型身份哈希；不保存密钥或完整服务地址。最终D13单次/分阶段运行已取得实际usage。没有usage的请求保留未知，货币费用保持null；不会补填旧网页任务。

`--structured`仅为研究CLI显式启用的JSON-schema输出约束，需要服务支持；普通项目请求不默认添加此参数。结构符合不证明语义正确。可选固定本地CPU运行时与已执行的模型/协议参数、原始结果及限制见[真实资料评测](RESEARCH_EVALUATION.md)。D12视觉模型与跨量化档位评测没有完成。
