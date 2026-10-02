# 余晖守线

来源：白天 B类第5题。

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

访问 `http://127.0.0.1:8765/demos/04-tower-defense/`。本demo是纯浏览器游戏，也可直接双击本目录 `index.html`。
后续依赖统一更新根目录环境配置，不为此 demo 单独创建环境。

## 演示步骤

打开index.html → 空地建塔 → 开始下一波 → 赚金币继续建塔 → 完成5波；可暂停或重开。

## 本次实现

固定1/60秒逻辑步长、两类塔、目标选择、路径移动、减速、金币、五波、击杀统计、胜负和重置。

## 当前边界

Canvas网页原型；没有Unity/Godot工程、动态寻路、存档、编辑器、资源管理、对象池或压力性能数据。

## 完整项目下一步

迁移至目标引擎；关卡和波次数据化、编辑器、寻路/行为树、存档；做同硬件压力基准，先定位再优化；用可复现回放验证。
