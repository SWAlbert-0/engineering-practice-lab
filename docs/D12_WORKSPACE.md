# D12 视频观察台

当前交付是面向单机短视频的素材与证据工作区。原片、采样、分析与人工核对均保存在服务端。离线入口无需 GPU 或模型密钥，离线结果明确不包含视觉推理。

## 使用流程

1. 打开 `/demos/04-video-understanding/`，上传 MP4 / WebM，或导入教学示例。
2. 在处理任务中等待校验通过；查看结果返回播放器。
3. 选择1–6帧创建采样任务，完成后点击缩略图或时间线定位原片。
4. 输入问题，选择离线整理或已配置的视觉模型。等待任务完成，查看回答。
5. 对模型给出的每条画面证据逐项核对，记录核对人、结论与说明。
6. 导出JSON或Markdown。JSON包含完整原片哈希、解码器、采样参数、实际PTS、帧哈希、模型标识、回答与核对历史。

页面内提供选题介绍弹窗及需求分析、架构、代码入口、任务流程、故障恢复和部署边界六章指南。原片播放器、采样帧、时间线与证据共同构成主工作区。

## 数据与可复现性

- 数据目录：`LAB_DATA_DIR/video/`，默认`data/video/`。SQLite WAL保存对象和任务，`files/`保存原片与采样帧；Docker继续共用`process-data`卷。
- 原片上限16 MiB、600秒、3840×2160，MP4 / WebM；视频编码支持H.264、VP8、VP9、AV1。浏览器具体解码支持可能不同，失败时提供原片下载和转为H.264的提示。
- 工作区原片合计256 MiB、活动队列最多12项；当前上传采用有界Base64 JSON。规划中的200 MB和分块上传尚未交付。
- 均匀采样`uniform-midpoint-v1`：以每个均分区间中点为目标，选择最近实际帧；重复索引去重。保存原始PTS、相对视频流起点的秒数、原片哈希、帧序号、图像哈希、FFmpeg版本。相同原片、参数和解码器下可复现；跨FFmpeg版本不承诺字节一致。
- 时间不是模型生成值。模型只返回给定`frame_id`，服务端映射回固定时间和图像哈希；未知帧、重复引用、空证据或结构错误会使任务失败，不保存回答。格式合法不代表语义正确，仍需人工核对。
- 新采样创建独立对象并更新当前批次，旧回答保留并标为历史采样回答。历史批次可切换查看。
- Range播放、HEAD、原片与帧哈希校验均通过受限API；文件路径不由客户端指定。只开放`file,pipe`解码协议，不接收视频URL。

## 任务、失败与恢复

本版本为一个服务进程加一个顺序工作线程；同一数据目录只运行一个应用实例。任务状态持久化为queued / running / cancelling / succeeded / failed / cancelled / interrupted，保留状态变更时刻。不是分布式租约worker，不能多副本共用数据库。

取消正在解码的任务会终止FFmpeg；取消已发送的模型请求只阻止结果发布，无法撤销上游计费。模型调用超时沿用45秒，取消状态可等待请求返回。模型、采样不自动重试，用户手动重试创建关联新任务。服务重启后活动任务标为interrupted，需手动重试。

解码失败、超时、缺少FFmpeg、原片/帧丢失或哈希变化均明确失败。删除前需等待活动任务结束；删除同步清理原片、帧和分析，任务状态日志保留。文件和数据库不构成跨文件原子事务；极端崩溃时可能留孤立文件，尚无通用垃圾回收与备份恢复工具。

## 可选视觉服务

沿用`LAB_LLM_BASE_URL`、`LAB_LLM_MODEL`、`LAB_LLM_API_KEY`。兼容chat/completions和图像输入的远端服务或本地推理服务可使用同一适配器；本地模型部署与硬件评估尚未完成。只发送最多6张512像素采样图与问题，不发送原视频或音频。

能力页只报告配置是否齐全，`vision_verified=false`明确表示未做独立视觉探测。实际调用成功并通过结构校验才记录回答；不可用时不降级为伪造回答。接口密钥不进入浏览器、导出或任务记录。模型标识、提示版本和耗时会保存，但供应商可变别名不等于不可变权重版本。

## API

所有写入为同源JSON，错误沿用WorkspaceError和400/403/404/409/503状态。

| 方法与路径（前缀`/api/video-workspace/`） | 含义 |
|---|---|
| GET workspace | 素材、采样、分析、任务、能力及限制 |
| POST assets | name、content（纯Base64）上传并创建校验任务 |
| GET assets/{id} | 素材元数据 |
| GET/HEAD assets/{id}/media | 原片，支持单段Range |
| POST assets/{id}/sampling-jobs | count整数1–6 |
| GET samples/{id} | 不可变采样与帧映射 |
| GET assets/{id}/frames/{sample}/{frame} | 哈希校验后的JPEG |
| POST analyses | sample_id、question、mode:offline/llm |
| GET analyses/{id} | 完整回答与核对历史 |
| POST analyses/{id}/reviews | revision、index、verdict、reviewer、note；乐观锁保护 |
| GET analyses/{id}/export?format=json或markdown | 记录下载 |
| GET jobs/{id} | 任务状态 |
| POST jobs/{id}/cancel或retry | 取消或显式新建重试 |
| POST assets/{id}/delete | 删除素材和关联产物 |

## 部署与验证

Docker镜像新增系统FFmpeg，运行方式不变。共用Conda环境新增`ffmpeg>=6`。已有Conda环境须执行`conda env update -f environment.yml`以补齐依赖。venv仍使用现有脚本；FFmpeg是外部程序，须事先安装并使`ffmpeg -version`和`ffprobe -version`可用，无全局pip安装。

专项测试：`python -m unittest discover -s tests -p 'test_video_*.py' -v`；真实浏览器：`node tests/test_video_browser.cjs`，重启后增加`--check-persistence`。CI继续回归全部六个项目、非root与只读容器、D11隔离以及原工作区重启恢复。

测试中的模型响应为明确的协议桩，用于校验引用与取消，不是实际视觉推理。实际验证结果见[验证记录](VALIDATION.md)。

## 待完成边界

Qwen3-VL-4B实际本地推理、精度/量化/采样消融、显存/延迟与能耗评估、MVBench和Video-MME固定子集均未完成。没有真实视觉供应商问答质量成绩。镜头/变化采样、长视频、音频/字幕、时间区间推断、时间线缩放、跨实验并排比较、分块上传、多人权限与分布式worker仍待开发。
