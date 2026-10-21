# 开源与开放案例

五项目的“跟着做一遍”均提供一键填入。材料随源码打包，无需在体验时访问外站；填入时校验文件SHA-256。固定版本、源文件链接、许可和转换后哈希在[案例清单](catalog.json)。

| 项目 | 来源与许可 | 本次处理与体验方式 |
|---|---|---|
| D01 | [UltiMaker fdm_materials](https://github.com/Ultimaker/fdm_materials)，CC0-1.0 | 固定Generic PLA XML，提取顶层打印/待机/热床参数并转换为中文Markdown；保留设备覆盖与适用范围提示。一键填入上传表单，第二步也可填入检索问题。不是生产验证SOP。 |
| D02 | [Fisher/UCI Iris](https://archive.ics.uci.edu/dataset/53/iris)，CC BY 4.0；原始数据取自固定scikit-learn提交 | 只取setosa和versicolor两类共100行，保留4个数值特征，标签0/1；不合成样本。一键填入CSV，保存后可实际训练。另有原样、petal_length增加1.5的合成偏移、无标签三份匹配4特征的监控CSV；均重复使用教学数据，不能作为独立泛化评价。公开教学集的好分数不代表业务泛化。数据引用：Fisher, R. A. (1936), Iris, UCI Machine Learning Repository, DOI 10.24432/C56C76。 |
| D09 | [RealWorld Conduit OpenAPI](https://github.com/gothinkster/realworld)，MIT | 对登录、注册、当前用户与创建文章规格进行中文选译；保留状态码，把密码强度/限流等未定义内容作为待澄清。一键填入需求正文，不访问公共演示服务。 |
| D11 | [TheAlgorithms/Python average_mean.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/maths/average_mean.py)，MIT | 去掉注解/文档/命令行入口，将空输入规则改为返回0，并故意注入整除变异。是本项目教学改编，不是上游历史缺陷。新增固定白名单快照，一键选择两轮离线任务，提交后才执行。 |
| D13 | Waskom, M. L. (2021), [seaborn: statistical data visualization](https://doi.org/10.21105/joss.03021)，CC BY 4.0 | 使用正式发表的JOSS PDF，经`pdftotext -raw`提取正文；不含图像，页布局已变化。附作者、DOI、许可和改编说明。一键填入专题设置，下一步选论文并填入实际文本。 |
| D13 | Kumar, R., Carroll, C., Hartikainen, A., & Martin, O. (2019), [ArviZ a unified library for exploratory analysis of Bayesian models in Python](https://doi.org/10.21105/joss.01143)，CC BY 4.0 | 同上。两篇论文研究对象不同，不直接比较未报告的效果。可分别导入后建立文献/证据条件对照。 |

D01 XML、D09 OpenAPI和D11原算法副本在`shared/examples/sources/`；MIT许可原文与CC0文本在`shared/examples/licenses/`。案例资料各自适用上述许可，不代表第三方作者认可本项目。D13保留原始PDF的SHA-256和提取文本哈希，材料范围在页面与文本中标明。

一键填入不会保存业务记录、运行模型、自动审核或发布。提交前可修改；当前表单有使用者编辑时会先提示替换。原先的考勤、合成数据、自编工艺和视频教学素材继续保留。所有案例都不属于独立保留集，不能用来声称真实业务或模型质量已验收。

统一模型API在[总览页面](../../index.html#model-settings)配置。保存无需重启，不自动测试；显式测试发送一次文本请求。D02的训练和预测不依赖此大模型配置。
