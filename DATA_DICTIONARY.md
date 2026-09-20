# 结果表字段说明

所有销量均为源 CSV 的原始数值单位，保留小数。百分点与百分比不可混用。

| 字段 | 含义 |
| --- | --- |
| SKU | 原始 Morion ID，文本标识 |
| INN / INN_key | 活性成分标签；未知标签拆为 UNKNOWN_SKU_编号 |
| known_inn | 是否有可识别的原始 INN |
| ATC1 至 ATC5 | 源文件治疗层级完整标签 |
| Brand | 原始品牌编码，不是生产商 |
| strength_mg | 可可靠识别的单一质量剂量，统一为mg；浓度/复方/容器重量不强填 |
| strength_parse_status | single_mass 或 not_comparable_or_missing |
| pack_size | 按描述解析的包装数量 |
| dosage_form | 简化剂型类别 |
| sales_2023 / actual_2023 | 2023年12个月销量之和 |
| YoY | 2023销量 / 2022销量 − 1；分母为零时为空 |
| CAGR | 2023销量 / 2019销量的四次方根 − 1 |
| portfolio_share_2023 | INN销量占全部样本销量的比例 |
| market_level / market | 用于分子竞争分析的ATC4或ATC3市场；无有效映射时为空/Excluded |
| peer_share_2023 | 分子年度销量 / 对应样本同类市场年度销量 |
| share_change_12m | 商业清单中为2023年度份额减2022年度份额；机会面板中为当前单月份额减12个月前单月份额 |
| share_change_3m / 6m | 商业清单中为最近3/6个月的窗口份额减前一个等长窗口；机会面板中为单月份额的滞后变化 |
| market_effect | 2022份额 × 市场年度销量变化 |
| share_effect | 2022市场销量 × 分子年度份额变化 |
| interaction | 市场销量变化 × 份额变化 |
| zero_rate | 零销量月份数 / 观测月份数 |
| ADI | 观测月份数 / 正销量月份数 |
| CV / CV2_positive | 全期标准差/均值；正销量大小的变异系数平方 |
| leading_zeros / trailing_zeros | 起始/结束连续零销量月份数 |
| internal_zero_months | 首尾正销量之间的零值月份数 |
| seasonality_strength | log1p销量线性趋势与月份虚拟变量分解后的季节强度代理，不是STL |
| future_share_change | 6个月后单月份额减锚点单月份额；未来市场为零则不可定义 |
| winner | 份额增量正且位于同锚点前25% |
| opportunity_probability | 锁定分类器输出的赢家概率估计，须结合校准表理解 |
| predicted_share_change_6m | 锁定连续目标模型的6个月份额增量预测 |
| P50_proxy / point_forecast | 年度/月份规划点预测，未严格拟合为条件中位数 |
| P10_empirical / P90_empirical | 验证残差校准的规划上下界，不保证名义覆盖率 |
| growth_2024 | 2024点预测 / 2023实际 − 1 |
| holdout_bias | 2023预测减实际的总差 / 实际销量；负值表示低估 |
| action / reason | 商业规则生成的行动和触发解释，与聚类标签独立 |
| supply_watch | 可叠加的供给核查标记，不是确诊缺货 |
| peer_uplift | 内部零事件期间其他同INN SKU月均销量 / 事前3个月均值 − 1 |
| apparent_absorption_ratio | 其他SKU增量 / 焦点SKU事前销量；仅描述性，不是因果吸收率 |
| converged | 线性迭代模型是否在最大迭代次数前收敛；false结果只供诊断、不参与最终选型 |

预测上下界不能按月份或分子直接加总成年度/组合分位数。组合范围单独记录在 `outputs/qa/forecast_summary.json`，完整预测清单为 `outputs/tables/forecast_2024_decision_table.csv`。
