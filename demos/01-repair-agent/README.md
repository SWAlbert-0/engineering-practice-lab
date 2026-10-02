# 测试与缺陷修复验证台

来源：丁箐 项目十一。

## 运行

全部 demo 共用根目录 `environment.yml` 定义的 `engineering-practice-lab` 环境。首次使用在仓库根目录执行：

```bash
conda env create -f environment.yml
```

环境已创建后不必重复创建，每次启动只需：

```bash
conda activate engineering-practice-lab
python server.py
```

访问 `http://127.0.0.1:8765/demos/01-repair-agent/`。请通过本地服务访问，直接打开 HTML 无法调用 Python API。
后续依赖统一更新根目录环境配置，不为此 demo 单独创建环境。

## 演示步骤

选择缺陷 → 选择正确/错误候选 → 运行 → 检查diff和测试 → 导出JSON。

## 本次实现

AST解析、三类缺陷、可信独立进程测试、候选补丁diff、回归和独立验收、失败拒绝。

## 当前边界

候选提供器是离线fixture，不是LLM；没有任意仓库、容器安全隔离、覆盖率或5个开源项目评测。

## 完整项目下一步

先增加LLM提供器与严格补丁schema；保持测试只读；隔离容器禁网和资源配额；至少5个开源项目/3类缺陷；比较同模型单轮基线，测解决率、回归破坏率、预算和覆盖率。
