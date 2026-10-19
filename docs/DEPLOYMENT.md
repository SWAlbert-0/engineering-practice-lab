# 容器部署与运行管理

六个项目和调研报告由统一应用镜像提供网页与 API。D11 另用同一镜像运行独立 worker，并构建一次性测试使用的小型镜像。使用者只需要 Docker，无需自行建立 Python/Conda 环境，也没有前端打包、数据库或 GPU 前置要求。

## 首次启动

Windows/macOS：安装并启动 [Docker Desktop](https://docs.docker.com/desktop/)，Windows 使用 Linux 容器模式。Linux：安装 [Docker Engine](https://docs.docker.com/engine/install/) 和 [Compose 插件](https://docs.docker.com/compose/install/linux/)。先确认 `docker info`、`docker compose version` 正常；推荐当前 Compose v2。旧版不支持 `--wait` 时更新 Compose。

Windows 首次安装可按以下步骤操作：

1. 从 [Docker Desktop for Windows 官方页面](https://docs.docker.com/desktop/setup/install/windows-install/) 下载安装包，Intel/AMD 电脑选择 x86_64，ARM 电脑选择对应版本。
2. 使用 WSL 2 后端。若未安装 WSL，在管理员 PowerShell 执行 `wsl --install`，按提示重启；已有 WSL 可用 `wsl --update` 更新。
3. 打开 Docker Desktop，等待引擎启动并保持运行，使用 Linux 容器。
4. 重新打开 PowerShell，确认 `docker info` 和 `docker compose version` 成功。无需激活 Conda。

若需要用 Git 克隆或更新仓库，还需安装 Git；使用源码 ZIP 启动则无需 Git。仅安装 Docker 命令行而未启动引擎时，无法构建或启动项目。

使用有仓库访问权限的账号获取完整源码，或从 GitHub 下载 ZIP 并解压：

```bash
git clone https://github.com/SWAlbert-0/engineering-practice-lab.git
cd engineering-practice-lab
docker compose up --build -d --wait
```

三个系统使用相同命令。第一次会联网下载 `python:3.12-slim`、系统运行库和精确锁定的 Python 依赖，并构建本机架构的镜像；后续保留构建缓存。当前没有预发布到镜像仓库，`docker compose pull` 不能代替首次构建。构建完成后，默认离线模式不需要外部服务。

等待命令成功后，打开 <http://127.0.0.1:8765>。`/healthz` 表示服务及六个引擎已加载，不代表可选模型服务已验证可用。所有项目入口、主题、图文指南和示例媒体均在镜像内。

## 日常操作

| 需求 | 命令 |
|---|---|
| 查看状态与健康情况 | `docker compose ps` |
| 查看最近日志并持续跟踪 | `docker compose logs -f --tail=100` |
| 临时停止 / 再次启动 | `docker compose stop` / `docker compose start` |
| 停止并移除容器（保留镜像） | `docker compose down` |
| 获取代码更新 | `git pull`，然后 `docker compose up --build -d --wait` |
| 重新下载基础镜像并构建 | `docker compose build --pull`，然后 `docker compose up -d --wait` |

D01 资料、D09 需求/用例与 D11 修复任务/证据保存在独立的服务端 SQLite 数据库，`process-data` 命名卷挂载到 `/data`。重建容器或清理浏览器不会删除该卷；`docker compose down -v` 会删除数据，应避免误用。备份与恢复见 [D01 工作区说明](D01_WORKSPACE.md) 、[D09 工作区说明](D09_WORKSPACE.md) 和 [D11 工作区说明](D11_WORKSPACE.md)。其余三项仍使用浏览器 LocalStorage，不自动跨设备同步。应用服务不挂载源码或 Docker socket。受信任的 repair-worker 挂载数据卷和 Docker socket，用于创建任务容器；任务容器没有宿主或数据库挂载。

## 端口与可选配置

默认无需 `.env`。需要更换端口或启用模型时，复制模板：

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```bash
# macOS / Linux
cp .env.example .env
```

编辑 `.env`，例如将 `LAB_PORT=8765` 改为 `LAB_PORT=8766`，再执行 `docker compose up --build -d --wait`。访问地址改为 <http://127.0.0.1:8766>；容器内部端口保持 8765。环境变量优先于 `.env`；如果修改文件不生效，检查终端是否已经设置了同名变量。

模型配置的三个变量默认留空，开启方法见 [MODEL_SETUP.md](MODEL_SETUP.md)。Compose 自动读取根目录 `.env` 并注入服务端环境；Python 直接启动不会读取该文件。修改模型参数后重建容器进程即可：`docker compose up -d --force-recreate --wait`。本地模型服务的 `127.0.0.1` 在容器内指向容器自身，不能直接沿用宿主机回环地址；Docker Desktop 可使用 `host.docker.internal`，Linux 需要另行配置可达地址。

`.env` 被 Git 和 Docker 构建上下文排除。不要把密钥写进 Dockerfile、镜像或截图，也不要分享包含密钥展开结果的 `docker compose config` 输出。镜像只复制所需运行文件，不包含 `.git`、本机环境和测试依赖。

## 容器结构与限制

| 项目 | 约定 |
|---|---|
| Python 与运行依赖 | Python 3.12；六个运行包在 `requirements.container.txt` 固定版本 |
| 服务进程 | 容器内监听 `0.0.0.0:8765`；宿主机仅发布 `127.0.0.1` |
| 权限 | UID/GID 10001，根文件系统只读，移除 Linux capabilities |
| 临时文件 | `/tmp` 使用 64 MiB tmpfs，供内置可信测试样例使用，重建容器即清空 |
| 健康检查 | 每 10 秒检查 `/healthz`，启动宽限 30 秒；连续失败显示 unhealthy |
| 日志与重启 | 每份 10 MiB、最多 3 份；`unless-stopped` 重启策略 |

健康失败不会由 Docker 自动重启仍活着的进程；重启策略作用于退出进程。D11 的 worker 和一次性受限容器说明见 [D11工作区](D11_WORKSPACE.md)。`repair-image` 检查完成后退出为正常状态；worker 提供单独健康检查，默认启动命令同时等待应用和 worker 就绪。Web 服务仍非 root；受信任 worker 启动时设置 socket 附加组，主进程随后使用 UID/GID 10001；它持有 Docker socket，其能力与受限任务容器不同。Base image 和系统包未锁定 digest，不能宣称镜像逐字节可复现。首次构建若缺少某架构的预编译 wheel 会明确失败，不隐式安装编译工具链。

## 离线交付镜像（可选）

在有网络且目标 CPU 架构一致的机器上构建并导出：

```bash
docker compose build
docker save -o engineering-practice-lab-image.tar engineering-practice-lab:local engineering-practice-lab-repair:local
```

交付镜像 tar、`compose.yaml` 和 `.env.example`，或保留完整仓库。在目标机器执行：

```bash
docker load -i engineering-practice-lab-image.tar
docker compose up --no-build --pull never -d --wait
```

只交付同架构镜像；Intel/AMD64 与 ARM64 不通用。不要把含个人密钥的 `.env` 一起发送。镜像 tar 较大，不提交到 Git 仓库。

## 故障排查与验收

| 现象 | 处理方式 |
|---|---|
| Cannot connect to Docker daemon | 启动 Docker Desktop 或系统 Docker 服务，确认 `docker info` 正常 |
| Windows 报镜像 OS 不匹配 | 切换到 Linux containers |
| 拉基础镜像 / apt / Python 包失败 | 检查 Docker 的代理与网络。Python 下载已增加 120 秒读取超时、连接重试和构建缓存；可在 `.env` 设置 `LAB_PIP_INDEX_URL` 指向可访问的公开 HTTPS PyPI 镜像，再执行 `docker compose build`。不要在地址中写凭据或关闭证书验证 |
| 端口被占用 | 修改 `.env` 的 `LAB_PORT`，重跑启动命令 |
| 服务 unhealthy 或启动超时 | `docker compose logs --tail=100` 查看引擎加载错误，修复后重新构建 |
| 更新后仍看到旧页面 | 确认执行带 `--build` 的命令并刷新浏览器；镜像使用复制的源码，不热挂载宿主机文件 |
| D11 运行器不可用 | 查看 `docker compose logs --tail=100 repair-worker`；确认 Linux 引擎、socket 权限、任务镜像及 worker 健康，重新执行带 `--build` 的启动命令 |
| 模型配置齐全但请求失败 | 检查模型名称、容器内可达地址、认证和图像能力；默认离线功能不依赖该配置 |

仓库的 [Container smoke test](../.github/workflows/container-smoke.yml) 在 GitHub Actions 中验证 Compose、真实构建、只读非 root 容器、健康检查、六项目网页与离线 API。接口检查脚本只使用 Python 标准库：`python scripts/container_smoke.py`（需默认端口且关闭模型配置）。它不是视频内容理解或外部模型质量评测。

实现依据：[Compose up](https://docs.docker.com/reference/cli/docker/compose/up/)、[Compose services](https://docs.docker.com/reference/compose-file/services/)、[Dockerfile](https://docs.docker.com/reference/dockerfile/)。

---

# 本地 Python 开发方式

容器使用者不需要执行以下步骤。希望直接运行 Python 并修改代码时，六个项目继续共用一个 Conda 或 `.venv` 环境。默认仅监听本机。D11 在本地模式只运行内置可信候选，不需要也不自动连接 Docker；手写与模型候选使用 Compose 的独立运行器。

## 1. 获取完整仓库

本仓库为私密仓库，协作者需先获得访问权限，并使用自己已授权的 Git 凭据或 SSH。不要把令牌写入脚本或仓库地址。

```bash
git clone https://github.com/SWAlbert-0/engineering-practice-lab.git
cd engineering-practice-lab
```

也可以在 GitHub 下载并解压完整 ZIP；不要只复制一个 demo 文件夹。没有安装 Conda 或 Python 时，先安装其中之一：推荐已有 Conda 的开发者继续使用 Conda；无 Conda 时安装 Python 3.12。脚本不自动安装系统级运行时。

## 2. 有 Conda：一条命令建环境并启动

先确认当前终端可运行 `conda --version`。支持 Miniconda、Anaconda、Miniforge；无需先激活项目环境。旧版 Conda 如果不支持脚本中的参数，请先更新 Conda。

Windows PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Manager conda
```

macOS / Linux：

```bash
bash start.sh --manager conda
```

也可直接从 Anaconda Prompt 或任何可调用 Conda 的终端运行跨平台入口：

```bash
conda run --no-capture-output -n base python launch.py --manager conda
```

脚本会依次完成：

1. 查找名为 `engineering-practice-lab` 的共用环境；没有则根据 `environment.yml` 创建。
2. 已有环境首次交给脚本管理，或环境配置发生变化时，执行 `conda env update`。不使用 `--prune`，也不调用 pip。
3. 检查 Python 3.12、NumPy、scikit-learn、Node.js 22，并实际加载六个 Python 引擎与 UTF-8 语料。
4. 检查通过后启动服务，终端显示访问地址。按 Ctrl+C 停止服务，环境保留供下次复用。

只调用 `conda run`，不要求脚本修改终端的激活状态。依赖校验成功后，在环境内保存清单摘要；后续配置未变则跳过安装，可离线启动。首次创建与需要更新依赖时仍需要访问 Conda 软件源。

## 3. 没有 Conda：一条命令创建 .venv 并启动

需要 Python 3.10–3.13，推荐 3.12。Windows 安装 Python 时保留 Python Launcher 或将 Python 加入 PATH；Linux 发行版可能还需要对应版本的 `python3-venv` 系统包。

Windows PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Manager venv
```

macOS / Linux：

```bash
bash start.sh --manager venv
```

直接指定 Python 的等价入口：

```powershell
# Windows，安装了 Python Launcher 与 Python 3.12
py -3.12 launch.py --manager venv
```

```bash
# macOS / Linux
python3.12 launch.py --manager venv
```

脚本创建仓库根目录 `.venv`，并仅通过该环境的 Python 执行 `-m pip install -r requirements.txt`。不会把依赖装进系统 Python，也不会为每个项目分别创建环境。不需要手动激活 `.venv`，依赖未变时会复用它。

无 Conda 分支只安装页面运行所需的 Python 依赖；Node.js 不是启动服务的必需项。如果要执行 JavaScript 测试，请另外准备 Node.js 22。

## 4. 自动选择与常用参数

省略 Manager 时自动检测：当前终端能找到 Conda 就使用 Conda，否则使用 `.venv`。如果 Conda 安装在自定义路径且当前终端不可见，请使用 Anaconda Prompt、初始化过 Conda 的终端，或把 `CONDA_EXE` 指向实际的 Conda 可执行文件。明确指定 Conda 后，失败不会自动改用 pip。

| 操作 | Windows PowerShell | macOS / Linux |
|---|---|---|
| 自动选择并启动 | `powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1` | `bash start.sh` |
| 指定端口 | 同上，追加 `-Port 8766` | 追加 `--port 8766` |
| 强制同步依赖 | 追加 `-Update` | 追加 `--update` |
| 只准备环境和检查 | 追加 `-Check` | 追加 `--check` |

这些参数也可以和 `-Manager conda` / `--manager conda` 或 venv 组合使用。`launch.py` 使用小写长参数，如 `--port`、`--update`、`--check`。显式更新会重新执行安装/同步命令，但不会强制把所有已满足范围的包升级到最新版本。

日常更新：先 `git pull`，再运行原来的启动命令。仅修改页面或代码不会触发依赖重装。当前依赖文件使用兼容范围，并非逐包精确锁定，不保证不同日期或操作系统得到完全相同版本。

## 5. 故障排查

| 现象 | 处理方式 |
|---|---|
| 找不到 Conda | 使用 Anaconda Prompt / 已初始化终端；确认 `conda --version`。不必为此改用 venv |
| PowerShell 禁止运行脚本 | 使用上方带 `-ExecutionPolicy Bypass` 的命令，仅作用于新进程，不修改系统执行策略；也可使用 `conda run ... launch.py` 或 `py -3.12 launch.py` |
| 首次下载失败、软件源不可达 | 根据安装器错误检查网络、代理或已有软件源配置，修复后重跑；脚本不会在失败后启动服务，也不会关闭证书校验 |
| 当前环境健康检查失败 | 先加 `-Update` / `--update` 同步依赖；失败细节会直接输出，修复前不会写入新的成功标记 |
| Python 版本不符合要求 | 有 Conda 时由环境文件指定 3.12；无 Conda 时显式用 Python 3.12 执行 `launch.py` |
| `.venv` 不完整或来自另一台机器 | 确认其中没有要保留的文件，停止服务后将 `.venv` 移走，再用 Python 3.12 重建。脚本不会自动删除已有目录 |
| Linux 提示缺少 ensurepip / venv | 通过系统包管理器安装与所用 Python 版本对应的 venv 组件后重试 |
| 端口 8765 已占用 | 停止旧服务，或指定 8766；脚本不会终止其他进程 |
| 新端口下看不到历史记录 | LocalStorage 按来源隔离，端口变化会使用另一份浏览器存储；旧记录仍在旧端口的来源下 |

同一环境不要同时运行两个首次安装/更新过程。依赖安装中断时可修复网络后重试；脚本只在安装和加载检查都成功后保存摘要。

## 6. 开发测试

Conda 已准备好时：

```bash
conda run --no-capture-output -n engineering-practice-lab python -m unittest discover -s tests -v
conda run --no-capture-output -n engineering-practice-lab node tests/test_ui.cjs
conda run --no-capture-output -n engineering-practice-lab node tests/test_products.cjs
```

无 Conda 时先激活 `.venv` 再运行相同测试命令。Windows 为 `.\.venv\Scripts\Activate.ps1`，macOS/Linux 为 `source .venv/bin/activate`。Node 测试中的 Python 子进程需要使用该环境的 Python，避免系统 Python 缺少依赖。

启动脚本的离线逻辑检查：`python -m unittest discover -s tests -p test_launch.py -v`。真实安装与系统覆盖情况见 [VALIDATION.md](VALIDATION.md)。

## 实现依据

- [Conda env create](https://docs.conda.io/projects/conda/en/stable/commands/env/create.html)
- [Conda env update](https://docs.conda.io/projects/conda/en/stable/commands/env/update.html)
- [Conda run](https://docs.conda.io/projects/conda/en/26.3.x/commands/run.html)
- [Python venv](https://docs.python.org/3/library/venv.html)
