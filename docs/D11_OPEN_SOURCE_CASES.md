# 项目十一：开源案例调研与借鉴建议

调研日期：2026-10-21。对象为“基于大语言模型智能体的自动化软件测试与缺陷修复系统”。本次核对官方仓库、文档、维护说明和部分核心代码；没有安装或运行这些工具，也没有调用付费模型或重新测定其修复率。默认分支的检查版本及实际阅读文件见 [来源记录](research/d11-open-source-sources-2026-10-21.json)。

## 结论

建议以 **mini-SWE-agent 的执行循环、Agentless 的分层定位、Aider 的代码上下文与编辑反馈、OpenHands 的事件和工作区组织、Pynguin 的测试生成** 作为五个实现参考。以 **SWE-bench 和 BugsInPy** 规范评测。SWE-agent、Qodo Cover 保留为历史和机制参考，不作为首选新增依赖。

这里的优先级是针对本项目的适配判断，不是开源项目的通用排名。选择依据是可检查的机制、与 Python 缺陷任务的关联、复现实验条件及接入成本，不以 Star 或不同条件下的榜单成绩排序。

## 1. 项目十一目前的位置

网页工作区已有四个打包函数快照、真实基线测试、1–3 轮候选、一次性 Docker 测试容器、逐测试变化、固定任务对照、人工审查和导出。它已有清晰的执行与证据流程，但尚未在网页中提供真实仓库检出、多文件定位和补丁编辑。

研究 CLI 与网页应分别评价：已有五个仓库、30 个历史缺陷的固定样本，29 例完成“缺陷版失败、上游修复版通过”的正控复现；这不是模型修复成绩。已有小模型诊断没有产生通过验证的候选，存在输入超限、请求失败和协议失败，不能直接解释成充分评估后的语义修复率为零。详细证据见 [研究评测记录](RESEARCH_EVALUATION.md)。

因此，下一步价值最大的工作是让系统能够在受控真实仓库中找到缺陷、保留有效测试，并产出经独立检查的补丁；增加角色数量或聊天页面本身无法补上这些能力。

## 2. 五个值得重点借鉴的实现

| 案例 | 优秀之处 | 项目十一可借鉴的具体能力 | 优先级 |
|---|---|---|---|
| [mini-SWE-agent](https://github.com/SWE-agent/mini-swe-agent) | 核心职责少，执行过程便于检查 | 模型、环境、代理分离；运行轨迹、调用与时间预算 | 优先 |
| [Agentless](https://github.com/OpenAutoCoder/Agentless) | 定位、修补、验证有明确中间产物 | 文件→函数→编辑位置的分层定位；候选补丁筛选 | 优先 |
| [Aider](https://github.com/Aider-AI/aider) | 面向真实代码库的编辑与反馈体验 | 仓库结构摘要、上下文预算、修改后测试、Git diff | 优先 |
| [OpenHands / SDK](https://github.com/OpenHands/software-agent-sdk) | 执行系统与用户控制台分开组织 | 事件历史、任务工作区、动作确认、远程执行接口 | 按需 |
| [Pynguin](https://github.com/se2p/pynguin) | 自动生成 Python 单元测试的研究工具 | 非 LLM 测试生成对照、断言与覆盖率实验 | 独立实验 |

### mini-SWE-agent：最适合学习执行内核

当前代码将代理循环、模型请求和环境执行分开。`DefaultAgent` 保存消息、调用次数、费用和退出状态，并在每步结束时保存轨迹；配置包含调用次数、费用、总时间和连续格式错误上限。这些机制适合把当前“候选轮次”细化成可复查的模型调用与工具执行事件。[核心代理代码](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/agents/default.py)

建议借鉴接口与记账方式，继续使用现有 worker、任务数据库和受限测试容器。费用检查是在模型调用前核对已累计值，单次请求仍可能使费用越过阈值；不能把它理解成供应商侧的硬限额。Docker 适配器也不能仅凭“使用 Docker”就视为等同于本项目的禁网、只读、无凭据、限资源策略。[环境适配代码](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/environments/docker.py)

版本注意：v2 迁移文档说明默认转为原生工具调用，旧文本解析配置仍可选；不能沿用旧介绍中“完全不用工具调用”的结论。接入已有 DeepSeek 配置时应实际验证消息与工具协议，而非只验证普通文本能返回。[v2 迁移说明](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/docs/advanced/v2_migration.md)

### Agentless：最适合补上真实仓库定位

它将问题处理拆成分层定位、候选修复和补丁验证。定位逐步缩小到文件、类或函数以及细粒度编辑位置；修复阶段生成多个候选，结合回归与复现测试筛选、排序。优点是每阶段可以保存和单独评价，而不只是得到一段最终回答。[官方流程](https://github.com/OpenAutoCoder/Agentless/blob/5ce5888b9f149beaace393957a55ea8ee46c9f71/README.md)、[定位实现](https://github.com/OpenAutoCoder/Agentless/blob/5ce5888b9f149beaace393957a55ea8ee46c9f71/agentless/fl/localize.py)、[候选排序](https://github.com/OpenAutoCoder/Agentless/blob/5ce5888b9f149beaace393957a55ea8ee46c9f71/agentless/repair/rerank.py)

项目十一可先为固定的五仓库缺陷清单增加定位结果：文件、函数、行段、依据和人工修正；固定定位输入后再进入修复。这样能区分“没找到位置”与“找到位置但没修好”。多候选应另设总调用和 token 预算，与单候选循环做相同预算的比较。

其默认分支最新提交在本次核对中为 2024-12-22，适合作为论文方法和实验基线，不宜据此假定它具有持续维护的完整产品能力。生成的复现测试也不是独立验收集，应保留测试来源并人工审查。

### Aider：最适合借鉴代码上下文与编辑体验

Aider 的 repository map 汇总符号，并按代码文件之间的依赖图选择适合 token 预算的相关内容；它不是简单地把整个仓库塞入提示。测试可显式运行，也可配置为编辑后自动执行，失败输出进入后续修正。[仓库映射](https://aider.chat/docs/repomap.html)、[测试反馈](https://aider.chat/docs/usage/lint-test.html)

这直接对应本项目已有小模型输入超限的诊断：先提供仓库结构与定位摘要，再按需读取相关代码；显示哪些文件被发送、截断和省略。编辑界面可采用“本轮修改文件→diff→失败测试→人工接受”的顺序。官方提供 DeepSeek 连接方式，因此也适合作为已有供应商的独立对照工具，但本次没有执行实际模型任务。[DeepSeek 文档](https://aider.chat/docs/llms/deepseek.html)

Aider 是协作编码工具，自动执行测试和 Git 操作不等于已有独立缺陷评测或执行隔离。建议借鉴交互与上下文组织，保留项目十一的只读验收测试、明确的候选身份和独立运行器。

### OpenHands：最适合借鉴系统分层和过程展示

当前 `OpenHands/OpenHands` 主要承担 Agent Canvas 控制台和执行后端选择；Python SDK、Agent Server、工具、对话、工作区和事件由 `software-agent-sdk` 承担。将旧版 OpenHands 的整个单体架构直接套用到当前版本会误判边界。[当前仓库分工](https://github.com/OpenHands/OpenHands/blob/12026be8181b15dfb4f6af3dae600a07b8320e75/README.md)、[SDK 说明](https://github.com/OpenHands/software-agent-sdk/blob/77c6ee584101b929fbb50b7b09a66d3a5a0a1053/README.md)

适合本项目的借鉴是把模型动作、工具输出、补丁产生和测试结果串成可定位的事件历史，并将仓库工作区与任务执行实例区分。动作风险确认与执行沙箱也应分开，确认按钮不应替代容器权限限制。[SDK 确认策略实现](https://github.com/OpenHands/software-agent-sdk/blob/77c6ee584101b929fbb50b7b09a66d3a5a0a1053/openhands-sdk/openhands/sdk/security/confirmation_policy.py)

近期不建议整体替换现有后端或引入整套控制台。先实现最少的事件与工作区接口；只有需要长时间仓库会话、远端工具或多执行后端时，再单独试验 SDK。

### Pynguin：补足自动化测试，而不只研究修复

Pynguin 是 Python 自动单元测试生成的研究工具，适合提供搜索式测试生成对照。它帮助回答“没有 LLM 的方法能发现多少行为”，避免把生成更多测试都归因于模型能力。[项目说明](https://github.com/se2p/pynguin/blob/3c6585c124f9aa3529bf589dfb89a35c5208c1d9/README.md)、[官方文档入口](https://github.com/se2p/pynguin/blob/3c6585c124f9aa3529bf589dfb89a35c5208c1d9/docs/index.rst)

它不是自动修复代理。当前 README 将工具标为研究原型，Python 3.12 等版本的支持仍属实验性；项目十一当前共用 Python 3.12，因此应放在按版本锁定的独立实验环境中验证，不增加到五项目默认安装依赖。

对生成测试应区分行为刻画和缺陷判定：在缺陷代码上学到的断言可能只是固定已有错误。建议记录断言来源，检查测试能否在缺陷版失败、修复版通过，并补充人工判断与适用的变异测试。覆盖率提高不能单独证明测试正确或补丁有效。

## 3. 两个评测基础

### SWE-bench：学习严格的修复判定

SWE-bench 是真实 GitHub 问题的评测基准和运行框架，不是修复代理。其 grading 代码分别评价应由失败变通过的测试与应持续通过的测试；还处理测试没有真正运行、执行错误等情况，避免将空日志当成成功。[评分代码](https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/grading.py)

本项目应继续保留逐测试身份，并将失败原因分成环境、协议、定位、补丁应用、测试和预算等类别。不同模型、样本、候选数和重试预算的公开得分不能直接横比。完整基准的镜像与资源开销明显高于当前函数样例，建议只在显式研究模式中按需运行小样本，不放入首次部署流程。[官方评测说明](https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/README.md)

### BugsInPy：优先复用现有五仓库样本

BugsInPy 提供真实 Python 缺陷及缺陷版、修复版检出和测试等命令，适合研究真实依赖环境下的缺陷复现。它与本仓库已有研究 CLI 的联系最直接，优先复用比重新收集一批演示缺陷更容易形成可复查的进展。[官方仓库与命令](https://github.com/soarsmu/BugsInPy/blob/11c5f1eea954a42132cfd06bf257766a7963e0fd/README.md)

下一步先为已有 30 例保存完整环境身份、测试集合和三种修复策略的结果；未复现样本继续单列，不通过删掉失败样本提高成绩。该基准是历史快照，现代 Python 和依赖适配本身就是实验变量。

## 4. 值得研究但不优先接入的案例

| 案例 | 仍值得学习的内容 | 不作为首选的原因 |
|---|---|---|
| [SWE-agent](https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/README.md) | 专门工具接口、交互历史处理和代理实验设计 | 官方明确将主要开发转向 mini-SWE-agent，并建议后续优先使用后者；并非仓库已归档 |
| [Qodo Cover，原 Cover-Agent](https://github.com/qodo-ai/qodo-cover/blob/adcf55baba40e8fbf8a84e68b70d08bef1e2b9c9/README.md) | 生成测试→执行→读取覆盖率→有限迭代的流程 | 官方在 2025-06-15 声明停止维护；本次 API 显示未归档，不能将未归档误解为仍维护 |

Qodo Cover 可启发一个独立的“建议测试”区域：生成内容先验证并由人确认，再形成有版本的测试集。不能让修复代理直接修改用于给自己判分的验收测试。覆盖率与故障发现应分开报告。

## 5. 建议的改造顺序与验收

以下为基于本项目现状的改造顺序。第 1 项已接入网页“真实仓库实验”：固定归档只读展示、按仓库与结果筛选、逐测试对照和证据下载；其余为后续计划。

| 顺序 | 改造 | 验收证据 | 主要参考 |
|---|---|---|---|
| 1 | 将已有五仓库研究清单接入只读的实验结果页面 | 每例显示 commit、镜像、测试身份、基线结果和未复现原因；网页不开放任意 URL 或 shell | BugsInPy、SWE-bench |
| 2 | 增加文件、函数、行段的定位与上下文预算 | 定位结果可人工纠正；模型输入可追溯；输入超限与修复失败分开统计 | Agentless、Aider |
| 3 | 为现有有限循环增加分阶段事件和完整调用记账 | 调用次数、usage 缺失状态、请求失败、停止原因和补丁身份可复查 | mini-SWE-agent |
| 4 | 增加独立的测试建议及审核流程 | 生成测试不覆盖受保护验收集；缺陷版和修复版都有真实结果；覆盖率不冒充修复率 | Pynguin、Qodo Cover |
| 5 | 比较单轮、有限反馈循环和受控多候选 | 同一固定样本、模型和预算，报告有效补丁、回归破坏、环境失败与人工核验结果 | Agentless、SWE-bench |
| 6 | 需要长任务时再试验 SDK 或远端工作区 | 证明会话恢复、工作区隔离和凭据边界；保持可选部署 | OpenHands SDK |

推荐保留现有“失败测试—日志—代码差异—人工审查”的界面主线。新增页面首先用于展示真实仓库定位、测试来源与失败类别；多代理角色、自动 PR 和多后端调度放在有实测需求之后。

## 6. 维护状态、许可与检查版本

下表的日期是核对时默认分支最新提交的日期，不等同于发布版本或长期维护承诺。完整 SHA 见来源记录。许可标识来自仓库元数据；样本仓库及个别文件可能具有各自的授权范围。

| 仓库 | 默认分支提交日期 | 许可标识 | 检查 SHA 前缀 |
|---|---|---|---|
| SWE-agent/mini-swe-agent | 2026-09-03 | MIT | `04d809ceab9d` |
| SWE-agent/SWE-agent | 2026-07-16 | MIT | `3ea751c087f3` |
| OpenHands/OpenHands | 2026-10-21 | MIT | `12026be8181b` |
| OpenHands/software-agent-sdk | 2026-10-21 | MIT | `77c6ee584101` |
| OpenAutoCoder/Agentless | 2024-12-22 | MIT | `5ce5888b9f14` |
| Aider-AI/aider | 2026-05-22 | Apache-2.0 | `5dc9490bb35f` |
| se2p/pynguin | 2026-10-17 | MIT；仓库内另有其他许可文件 | `3c6585c124f9` |
| qodo-ai/qodo-cover | 2025-06-24 | AGPL-3.0 | `adcf55baba40` |
| SWE-bench/SWE-bench | 2026-09-02 | MIT | `02e7a74ffd0b` |
| soarsmu/BugsInPy | 2025-10-09 | API 未识别，不据此推断授权 | `11c5f1eea954` |

本次只做方案分析与来源核对，不将上游宣传、公开基准分数或上游修复补丁计为项目十一的成果。
