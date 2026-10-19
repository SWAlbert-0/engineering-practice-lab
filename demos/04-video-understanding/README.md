# 视频观察台

对应丁箐老师项目 D12。

## 启动

在仓库根目录运行，继续共用现有环境：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

macOS / Linux 使用 `bash start.sh`。浏览器打开 <http://127.0.0.1:8765/demos/04-video-understanding/>。入口需要本地服务，不直接双击HTML执行计算。

## 当前能力

浏览器实际预览和JPEG抽帧；离线采样校验；可选多模态模型问答与时间戳证据；本地分析记录。

## 完整选题待完成

开源视频模型轻量化、GPU训练/推理、至少两个基准的效率精度比较均未完成。

## 模型与数据

默认离线，无需密钥。模型模式必须在工作台显式选择后运行，配置见 [MODEL_SETUP.md](../../docs/MODEL_SETUP.md)。未使用真实API密钥完成线上验收。

新增记录保存在当前浏览器的LocalStorage，切换端口或浏览器不自动同步。设置页可导出JSON；当前没有导入恢复或后端业务数据库。

## 指南

页面“项目指南”包括需求分析、架构、代码、任务流程、验收与后续开发，并配有SVG图。顶部“选题介绍”保留原题要求、分析评分与实现范围，估算和评分没有因新增演示而上调。

## 验证

在共用环境的仓库根目录运行 `python -m unittest discover -s tests -v` 与 `node tests/test_products.cjs`。模型协议使用离线桩测试；完整系统测试边界见 [VALIDATION.md](../../docs/VALIDATION.md)。

## 原创样片

sample.webm是项目用FFmpeg合成的12秒WebM，蓝色方块横向移动；只用于预览和抽帧验证，没有第三方视频素材。运行时不需要FFmpeg。用户视频最长10分钟、150MB，实际可解码格式取决于浏览器；采样每次2/4/6帧。
