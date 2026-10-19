# 开发者部署与启动

六个项目由根目录 `server.py` 一起提供服务，启动一次即可浏览全部页面。默认地址是 <http://127.0.0.1:8765>；离线模式无需 API Key、数据库或前端构建。以下流程用于本地开发与演示，服务仍只监听本机。

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
3. 检查 Python 3.12、NumPy、scikit-learn、Node.js 22，并实际加载三个 Python 引擎与 UTF-8 语料。
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
