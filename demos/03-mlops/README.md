# 模型发布实验

来源：丁箐 项目二。

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

访问 `http://127.0.0.1:8765/demos/03-mlops/`。请通过本地服务访问，直接打开 HTML 无法调用 Python API。
后续依赖统一更新根目录环境配置，不为此 demo 单独创建环境。

## 演示步骤

默认污染0.65运行 → 观察回滚 → 改为0运行 → 特征偏移2运行 → 取消真实标签运行。

## 本次实现

两个真实CPU逻辑回归模型、固定种子、数据hash、独立训练/验证/当前窗口、PSI、同窗口质量比较、活动模型切换和新预测。

## 当前边界

合成数据；只在本次请求内生效，无数据库或模型注册中心；未接DVC、MLflow、Docker、Prometheus/Grafana和CI/CD。坏候选故意绕过发布门禁用于演练。

## 完整项目下一步

补DVC数据版本、MLflow registry/alias、容器API、指标抓取和仪表盘；发布前验证门禁、金丝雀流量；处理标签延迟；回滚后验证服务真正加载对应模型。
