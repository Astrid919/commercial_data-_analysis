# 全量药品组合分析

本项目使用上一级 `data/teva_sales.csv`，不覆盖原始数据和已有 small dataset 分析。

## 运行

Python 3.12。正常 Python 环境下：

```powershell
python -m pip install -r requirements.txt
python run_pipeline.py
python analysis/verify_pipeline.py
```

当前机器的打包 Python 可这样运行；项目会自动识别上一级 `.runtime` 中的科学计算依赖：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' run_pipeline.py
```

分段重跑：`python run_pipeline.py --from-stage 8 --to-stage 13`。修改上游逻辑后，应同时重跑依赖该逻辑的下游模块。模型会产生新结果，不与旧结果混用。

## 模块

| 文件 | 职责 |
| --- | --- |
| 01_data_audit.py | 全量读入、指纹、缺失/负值/重复检查、长面板 |
| 02_feature_engineering.py | 保守解析剂量、包装和剂型 |
| 03_portfolio_analysis.py | 月度/年度销量、ATC贡献、INN集中度 |
| 04_market_analysis.py | ATC4优先、ATC3回退、增长分解、INN×ATC4切片 |
| 05_demand_segmentation.py | SKU与INN需求模式、零间隔和生命周期 |
| 06_product_driver_model.py | INN/月固定效应、SKU聚类标准误、ML置换重要度 |
| 07_opportunity_model.py | 连续份额变化与分类排名、purged时间验证、概率校准诊断 |
| 08_forecasting.py | 季节朴素、阻尼ETS、Ridge ARX、全局提升树、冻结2023 |
| 09_hierarchical_forecast.py | Croston/SBA/TSB、底层汇总、交叉层级一致性 |
| 10_substitution_analysis.py | 潜在可用性事件、同分子提升、探索性产品关系 |
| 11_decision_engine.py | K=3至6描述性聚类、独立透明行动规则 |
| 12_figures.py | 八张核心图及治疗领域深入分析 |
| 13_build_chinese_report.py | 从计算结果生成中文Word及Markdown报告 |
| verify_pipeline.py | 独立总量、目标、时间边界、单位解析和层级核验 |
| forecast_lib.py / common.py | 模型、指标、路径与共用运算 |

## 交付

- `report/中文分析报告.docx`：面向商业与供应团队的报告。
- `report/中文分析报告.md`：便于检索、修改和版本管理的报告。
- `outputs/tables/forecast_2024_decision_table.csv`：完整预测与行动清单。
- `outputs/tables/`：全部核心表与审计辅助表，UTF-8 BOM，可用 Excel 打开。
- `outputs/figures/`：8张高分辨率PNG。
- `outputs/models/`：选型锁定记录、预测缓存及已拟合模型。
- `outputs/qa/`：指纹、验证摘要、解释边界及报告版式QA。
- `data/processed/`：长面板、SKU特征、INN月度矩阵及预测中间结果。

## 核心口径

1. 完整13,762个SKU、60个月。1,776个可识别INN；931个未知INN SKU以各自独立键保留。
2. 原始销量包含小数，不擅自乘以1,000或取整。案例描述为包装销量，但倍率/地区/渠道字典缺失。图表注明原始销量单位。
3. 同类市场为样本ATC4或ATC3，至少3个已观测INN。跨多个ATC3的分子不报告单一竞争份额；未知INN仍留在分母。
4. 年度份额是年度销量比值；机会模型目标是锚点当月与6个月后当月的份额差，两种份额动量不可混用。
5. 全量数据中的产品名录/治疗分类为静态快照。锚点的SKU数量等结构特征仅纳入该时点已发生正销量的SKU，但无法消除历史名录缺失引起的幸存者偏差。
6. 解释模型吸收INN×日历月固定效应，按SKU计算聚类标准误。包装与强度为log1p变换；其系数不是精确弹性。时间不变属性不与SKU固定效应同时估计。
7. 机会开发锚点最晚2020-12，标签最晚2021-06；验证锚点2021-07至12。测试前重拟合仅使用标签截至2022-12的观察，冻结测试锚点2023-01至06。
8. 12个月需求选型使用2020-12、2021-06、2021-12三个起点；2022年补充3/6个月验证，不让目标进入2023。留出期为完整2023。生产模型不随留出排名更换。
9. ETS为先估计加性季节项，再对调整后序列进行有限网格SSE拟合的ETS(A,Ad,N)，并非联合最大似然季节ETS。参数网格、目标截尾及递归逻辑均在代码中公开。
10. P50_proxy是规划点预测，未声称为严格条件中位数。P10/P90是样本残差校准范围。年度范围独立于月度，组合范围不通过边际分位数求和构造。仅有3个年度验证路径，必须结合实际覆盖率解读。
11. INN与ATC不是严格树形关系。预测从SKU分别汇总到INN和ATC5/ATC4；直接INN结果按历史产品mix分配以实现总量一致。
12. 零间隔只称潜在可用性事件；替代分析为相关性线索。没有确认OOS、利润模型、停产建议、深度学习或GNN。

## 评价指标

- WAPE：分子月绝对误差之和 / 实际销量之和。
- Bias：预测减实际的总差 / 实际销量之和，负值为低估。
- MASE：各分子绝对误差除以训练期12阶季节差分绝对值均值，再对可定义观测平均；零分母序列单独计数。
- PR-AUC使用average precision定义；Precision/Lift/NDCG按每个锚点月独立排名后平均。
- 校准输出为分箱平均预测概率、真实发生率及数量；Brier是概率平方误差，未使用测试标签调整概率。

## 可选扩展

N-BEATS、MinT和产品替代网络图属于研究设计中的可选项，未纳入本次基线交付。若新增库存、毛利、价格、渠道或厂家数据，可以继续扩展；不要从销量数据推导这些缺失事实。

## 方法来源

- 原始文件：`../data/teva_sales.csv`。
- 背景材料：`../MLapps_Teva_Pharma.pdf`，2024年3月，第17至24、28至31页。
- https://otexts.com/fpp3/tscv.html
- https://otexts.com/fpp3/reconciliation.html
- https://scikit-learn.org/stable/modules/permutation_importance.html
- https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html
