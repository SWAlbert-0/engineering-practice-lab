# D11 / D13 真实资料评测

日期：2026-10-20。已完成真实公开资料的隔离运行，以及本地 **Qwen3-0.6B Q8_0 CPU** 的实际推理诊断。D11固定5仓库30历史缺陷，29例复现；本轮模型没有产出公共测试可接受的补丁。D13固定两个领域20篇文献60例，完成单次与阅读/复查两种真实模型运行，结果没有显示稳定的分工优势。**更强模型、全仓定位和整篇综述独立人工盲评仍未完成。**

原始模型输出、输入哈希、用量与逐例状态保存在 `evaluations/`。历史的缺配置预检不代表最终运行状态；上游补丁、词法检索、协议测试和模型成绩分别记录，不互相替代。

## D11：5个真实仓库 / 30个历史缺陷

来源为[原始BugsInPy](https://github.com/soarsmu/BugsInPy)，固定数据提交 `11c5f1eea954a42132cfd06bf257766a7963e0fd`。它提供真实缺陷的旧/新提交及相关测试；本项目没有自行注入错误或把别人论文中的修复率作为成绩。

| 仓库 | BugsInPy编号 | 数量 |
|---|---|---:|
| psf/black | 1–7 | 7 |
| httpie/cli（原jakubroztocil/httpie） | 1–5 | 5 |
| tornadoweb/tornado | 1–6 | 6 |
| tqdm/tqdm | 1–6 | 6 |
| ytdl-org/youtube-dl | 1–6 | 6 |

清单为 `evaluations/d11/manifest.json`。每例保存源仓库、40位提交、原始Python版本、测试文件/命令、元数据SHA-256、上游修复链接和标题。三个工程分类为边界/空值、解析/协议、资源状态/兼容性；分类来自修复标题与测试，不冒充原数据集的专家标签。

样本在执行前按编号固定；失败样本不删除、不替换。30例全部属于公开评估集，没有另设开发集或隐藏保留集，预训练污染无法排除。

### 执行语义与隔离

运行器从固定buggy提交取源码，将上游fixed提交的测试和关联测试资料固定到两个版本，然后只把该修复提交变更的生产文件覆盖到buggy基线上，沿用BugsInPy的checkout思路。它不是把远距离两个提交之间所有改动都当成一个修复。

每个版本分别运行触发测试和相关测试模块。保存测试身份、失败/错误/跳过、返回码、日志尾部、耗时、镜像内容ID、源码快照与固定测试哈希。触发集合必须相同；缺陷版须有实际测试失败，修复版全部触发测试通过，测试收集错误不算复现。相同测试的失败与连带teardown错误单独保留，不将后者当成额外缺陷。相关模块不等于全仓测试或独立验收集。

外部代码仅在一次性Docker容器执行：禁外网、只读根、非root、去掉capabilities、no-new-privileges、1CPU/768MiB/128进程、受限tmpfs。仅挂载本次公开源码和只读检查器，不挂载应用数据、凭据或Docker socket；容器完成/超时后清理。测试代码文件前后哈希用于发现运行期改写；格式化素材允许由原测试改写，变化路径单独记录，每个阶段重新从原始快照恢复，避免阶段之间互相污染。该检查不是对Python解释器内的对抗性测试作弊作形式化保证。

依赖下载/镜像构建是受信任准备步骤，允许网络；实际测试禁外网，回环网络可供HTTP测试使用。所有依赖装在评估镜像，不使用宿主全局pip，也不改变应用的Docker/Conda/venv共用环境。

### 对历史环境的明确适配

- 统一使用Python 3.8.20；原Python 3.6.9/3.7.x/3.8.x要求仍保存在清单。不是原环境的逐字节重建。
- 每项目有明列的依赖版本；HTTPie旧例另用requests 2.0.0，最早fixture例用pytest 3.2.1和plain断言。镜像ID随实际构建保存，未完整锁定全部传递依赖与基础镜像digest。
- 不在宿主创建源仓库符号链接。安全的内部文件链接物化；缺失的文档构建链接和不参与本次测试的App Engine目录别名省略，逐例记录。越界或未许可链接拒绝。
- HTTPie-4的原测试固定访问httpbin.org。评估时将该名字映射到回环地址，在同一禁外网容器内运行真实HTTPbin 0.7.0服务；不更改断言或放开外网。其结果是本地服务重放，不是对现有公共站点的网络验收。
- Black增加原框架也会创建的tests包标记；缺失的打包生成文件 `_black_version.py` 使用 `0+bugsinpy.<commit>`，明确是评估标识，不是实际发行版本。

### 运行与模型对照

在已有共用环境、仓库根目录执行，需本机Docker引擎；每次输出目录必须不存在：

```bash
python -m scripts.evaluation.d11 --project black --output evaluations/local-runs/d11-black
```

其他四仓库用相应project参数。GitHub Actions `research-evaluation.yml`会自动执行五仓库，保存原始证据工件。**工作流绿色仅表示评测工具正常产出结果，不表示30例全部复现**，须查看summary中的状态分布。

真实模型需先在本机进程配置 `LAB_LLM_BASE_URL`、`LAB_LLM_MODEL`、`LAB_LLM_API_KEY`，再显式追加 `--model`。每个已复现样本最多3次调用、每次6000输出token、输入总长上限10万字符；不可用或超限如实记录，不自动回退。调用失败不自动重发。

这是**已知修复文件定位的条件评测**：允许文件取自上游修复文件名，提示不含上游修复内容；不评估全仓定位能力。候选只能写允许的Python文件，不能改测试或配置。第一轮候选作为单轮对照，同一轨迹最多3轮作为有限循环对照；两者共享首轮，非独立重复实验。记录公共测试可接受率、非法候选、完整轨迹及测试变化。公开测试通过称为test-plausible，不能宣称语义完全正确或直接合入。

Web工作区仍只开放原三个受控教学快照；本研究CLI不是给网页开放任意Git URL或shell执行的后门。本轮已有跨仓库小模型负向诊断；独立缺陷保留集、完整修复效能、外部PR与完整实际成本仍未完成。

## D13：两个领域 / 20篇文献 / 60个专家标注样本

采用两项原始公开数据，不用AI虚构论文：

| 数据 | 本次范围 | 专家标注 | 许可与归属 |
|---|---|---|---|
| [SciFact](https://github.com/allenai/scifact) | 生物医学10篇摘要 / 30个claim-document样本 | 支持/反驳/信息不足与证据句 | Wadden等，2020；标注CC BY 4.0，摘要S2ORC ODC-By 1.0 |
| [QASPER v0.3](https://allenai.org/data/qasper) | NLP10篇提取文本 / 30个问答样本 | 专业读者答案及证据段 | Dasigi等，2021；标注CC BY 4.0，文本来自S2ORC，原论文权利保留 |

原始压缩包SHA-256、固定文献与问题ID、文献/标注哈希在 `evaluations/d13/manifest.json`。固定取原development分割，未调用模型前按明确排序规则选出10篇/30样本。QASPER要求原标注证据能逐字定位到实际段落、文本不超过24000字符；SciFact只提供摘要，不能称为阅读全文。20篇不是20个独立实验，论文内问题相关。

这是给定文献的语义支持/证据选择与论文问答**子任务**，不是完整D13多论文综述评测；也不能把两个不同任务的准确率和token F1混成一个质量分。新工具复用实际 `shared.model_client` 适配器，没有重定义网页生产工作流。

原始正文仅下载到本地缓存，不在仓库重发整篇语料。标注来自原数据集，不能写成“本项目已组织两名专家独立标注”。公共标注不是本项目的新盲评。

### 重建、运行与预算

```bash
python -m scripts.evaluation.d13_data --cache evaluations/cache --output evaluations/local-runs/data.json
python -m scripts.evaluation.d13 --data evaluations/local-runs/data.json --mode lexical --output evaluations/local-runs/lexical
python -m scripts.evaluation.d13 --data evaluations/local-runs/data.json --mode single --input-policy lexical-top4 --structured --max-calls 60 --output evaluations/local-runs/single
python -m scripts.evaluation.d13 --data evaluations/local-runs/data.json --mode staged --input-policy lexical-top4 --structured --max-calls 120 --output evaluations/local-runs/staged
```

`lexical`为确定性词重叠检索，固定预测SUPPORT；没有语义推理。`single`每样本1次、1500输出token；`staged`阅读1000 + 复查500、每样本最多2次，提示均不给gold标签、答案和证据位置。两模式仅最大输出token预算相同，输入token/实际价格不一定相同；不能称为已完成等费用实验。`--limit`可做小规模连通检查；无预算或无配置不会发送请求。真实服务错误与JSON/证据索引错误如实保存，不重发或降级。

SciFact指标为标签准确率和证据句F1；QASPER为参考答案token F1和证据段F1（对合法参考标注取最佳值）。F1衡量词或位置重合，不代替自由论述的语义正确性。选中的样本始终保留在分母；全部缺少配置时指标为null，不显示0分或虚构成绩。最终D13运行记录了服务实际返回的usage；本地计算的货币费用未知，保留null。

### 双人盲评材料

当两个模式均产生同一批实际输出后：

```bash
python -m scripts.evaluation.d13_blind pack --data evaluations/local-runs/data.json --run evaluations/local-runs/single --run evaluations/local-runs/staged --output evaluations/local-runs/blind
python -m scripts.evaluation.d13_blind score --key evaluations/local-runs/blind/unblinding.json --review-a evaluations/local-runs/blind/reviewer-A.csv --review-b evaluations/local-runs/blind/reviewer-B.csv --output evaluations/local-runs/human-report.json
```

将 `review-pack.json` 和各自CSV分别交给两名独立评审；不要把 `unblinding.json` 交给评审。任务随机排序，不含模型/模式身份和gold标签。评审逐项填写支持关系0/1、覆盖度/归纳质量0–2、实际审核秒数和问题说明。工具拒绝空项、重复/缺失、过期预测哈希、同名评审和非有限耗时；输出支持分歧、Cohen κ及评分/时间。署名仍是自报，工具不能认证身份或专家资格，也不会替人自动填分。

本次已用两组实际输出生成120项随机盲评材料（包括失败案例），两份CSV保持空白，未填写人类分数。完整原文盲评包仅在本地生成，按上述命令可重建；提交目录保存实际模型输出，不重复分发整篇语料。完成子任务人工审核后，还须以真实D13多论文写作输出开展整篇归纳/覆盖、引用支持和条件差异的独立评审，才可关闭D13-05。

## 最终实测与证据

### D11：复现与模型诊断分别计数

| 仓库 | 固定样本 | 缺陷失败、上游修复通过 | 真实小模型诊断 |
|---|---:|---:|---|
| black | 7 | 7 | 7例输入超出协议范围 |
| httpie | 5 | 5 | 5例请求失败或超时 |
| tornado | 6 | 5 | 1例未复现、1例输入超限、4例请求失败或超时 |
| tqdm | 6 | 6 | 1例三轮候选均被拒绝、5例请求失败或超时 |
| youtube-dl | 6 | 6 | 3例输入超限、3例请求失败或超时 |
| 合计 | 30 | 29 | 没有test-plausible候选，完整修复质量仍无法判断 |

`tornado-3`在当前适配环境中缺陷版和修复版的触发测试都通过，因此标为未复现，未删除或换样。输入超限共11例，请求失败/超时17例，三轮预算耗尽1例，未复现不进入模型阶段1例。`actual_recorded_calls=3`仅表示成功解析并保存的3次输出，不是所有发起的请求数；这些17例原始error均为请求失败/超时（没有擅自推断具体网络或服务器原因），错误请求的输出/usage没有完整记录，不能说其余案例没有推理或推算总费用。3个已解析输出均未通过候选检查。原始工件保留错误详情与轨迹；仓库保留逐测试身份、实际镜像ID、状态与诊断日志，并已从五个最终CI工件下载并保存所有模型逐例原始JSON；artifact记录提供原ZIP的SHA-256。tqdm-1的模型三轮都只复述协议示例“allowed path / complete file”，因此被候选路径检查拒绝，没有执行为有效补丁。

运行使用固定官方权重与llama.cpp，CPU 2线程、上下文32768、seed 0；完整文件生成协议每次45秒超时。当前负向结果同时反映弱模型、输入限制和协议失败，**不是充分评测后的“语义修复率0%”**。单轮与最多三轮的公共测试可接受候选数均为0，语义修复率保留null。29例上游补丁正控成功不属于模型成绩。

- [最终历史缺陷复现CI](https://github.com/SWAlbert-0/engineering-practice-lab/actions/runs/39409631610)：五仓库与公开语料基线任务全部成功。
- [真实小模型诊断CI](https://github.com/SWAlbert-0/engineering-practice-lab/actions/runs/39409631644)：五仓库全部产出真实诊断记录。
- 持久结果：[`evaluations/d11/results/2026-10-20/`](../evaluations/d11/results/2026-10-20/)。评测代码提交：`ce5f24dfc3040bbcde78695b3072e800d3774409`。

### D13：实际单次 / 分阶段比较

原包重建通过，固定20篇/60例，数据指纹 `e54b73208eba9f9b699020a6843c88849e6500cd10bc443e48710be4cd5d944e`。词法基线的生物医学证据F1为0.3333、固定SUPPORT标签准确率0.3000；NLP证据F1为0.2222、答案token F1为0.1019；它没有模型推理。

实际模型为官方Qwen3-0.6B Q8_0，权重及可移植llama.cpp b11753二进制均校验SHA-256；CPU 6线程、上下文16384、单slot、关闭thinking、温度0，未指定随机seed，不声称跨硬件逐字节确定。准确来源和参数见 [`local-model-provenance.json`](../evaluations/d13/results/2026-10-20/local-model-provenance.json)。没有安装宿主全局pip依赖。

最终比较均使用v3提示、同一批问题、词法top-4完整句/段和原始全局证据索引，不给gold或答案；不是完整正文输入。`--structured`约束JSON字段、枚举和可用索引，不能保证事实与语义正确。两模式最大输出预算均1500 token/例，实际总输入与总费用并不相等。

| 实测指标 | 单次模型 | 阅读 + 复查 |
|---|---:|---:|
| 合法完成 / 全部固定样本 | 59 / 60 | 60 / 60 |
| 实际请求数 | 60 | 120 |
| 生物医学标签准确率（分母30） | 0.3667 | 0.4000 |
| 生物医学证据F1 | 0.3133 | 0.3467 |
| NLP证据F1 | 0.2822 | 0.2822 |
| NLP答案token F1 | 0.2202 | 0.2214 |
| 实际输入token | 32,381 | 67,845 |
| 实际输出token | 2,786 | 5,245 |
| 实际总token | 35,167 | 73,090 |
| 累计请求耗时（秒） | 160.70 | 304.50 |
| 新人工专家语义评分 / 货币成本 | null / null | null / null |

失败输出计入全体样本指标的分母；单次模式1例标签和证据是否存在不一致。分阶段多判断对1个医学样本，NLP答案F1变化很小，却使用约2.08倍token和1.90倍累计请求时间；**不能据此宣称稳定优势、统计显著或多智能体效果提升**。耗时是客户端测得的请求累加，不含模型下载/启动、数据准备或完整网页任务。

另外保留无结构约束诊断：60次真实请求仅1例输出合法，59例索引/答案格式错误。约束解码改善输出协议，最终质量分仍然偏低。此前完整输入v2尝试执行38条后连接中断（3条完成），22条未执行；摘要单独保留，不混入最终配对指标。早期 `single-preflight.json` / `staged-preflight.json` 是模型安装之前的缺配置检查，也不纳入比较。

两例连通检查和失败的完整输入尝试已用于排查协议问题。本次是公开development子集上的开发诊断，**没有未接触的保留集、独立重复种子、预训练污染排除或独立人工评分**。20篇中的问题彼此相关，不能当作60个独立研究复现。当前结果仅覆盖给定文献的核验/问答子任务，不能证明整篇D13综述质量。

原始逐例输出、输入哈希、错误、实际usage、耗时和汇总见 [`evaluations/d13/results/2026-10-20/`](../evaluations/d13/results/2026-10-20/)，`model-comparison.json`汇总三次最终v3运行。重建数据后可生成包含全部120条实际输出的双人盲评包，尚无真实评审提交。

### 重建本地小模型服务

可选Linux x86_64 CPU入口：

```bash
python -m scripts.evaluation.local_model --directory /tmp/lab-cpu-model --serve --threads 2
```

工具从明确的官方来源下载固定版本并校验SHA-256，启动OpenAI兼容本地服务；不会自动写入项目环境或改用云端。按终端提示在另一个已有项目环境的进程配置模型变量，再执行上面的研究CLI。此引导默认2线程/32768上下文/seed 0；与本次D13实际6线程/16384上下文参数不同，复现实测需以provenance为准。量化文件Q8_0已实际运行，尚未做FP16/Q4/Q8的成对质量、内存和速度对照，也未评测D12视觉模型量化。

### 功能回归

[最终容器与六项目浏览器CI](https://github.com/SWAlbert-0/engineering-practice-lab/actions/runs/39409631847)成功：224项Python测试中219通过、5项在普通阶段跳过，另行执行5项真实Docker测试全部通过；六工作区、D11/D13复查增强、新体验引导和重启持久化全部通过。该结果证明工程流程正常，不代替上面的业务质量评估。详细记录见[验证文档](VALIDATION.md)。
