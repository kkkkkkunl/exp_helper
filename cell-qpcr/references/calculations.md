# 数值计算契约

## 调用

Python 3.9+：`python -B scripts/calculate.py`，标准输入为 JSON。`experiment-skill.json` 列出九个稳定计算、各输入/输出单位和 basis。请求用 `calculation` 选择；`inputs.<name>` 为 `{value, unit, source}`，来源为 user、confirmed_parameter 或 calculated；`params.confirmed` 必须是 true。主 workflow 中 calculated 还须有 calculation_id/output 及真实 depends_on。

## 方法和参数

- `rt_reaction`：params 明确 reaction_type（RT/-RT）、method_profile=AG11728-v6-all-in-one；-RT 另有 nrt_source。按选定规程核对质量/体积≤50 ng/uL，gDNA/总量=0.1、RT/NRT/总量=0.2。其他方法只返回待复核候选值，不能放行。
- `qpcr_recipe`：method_profile=AG11701-v4e1、rox_basis 为本次仪器核对依据；2x Premix 为总量一半，原液等效≤总量10%。这些是所选方法约束，不是通用标准。
- `treatment_duration`：start_epoch/end_epoch 的单位 s，params.start_time/end_time 为同一时点含时区 ISO8601，必须数值一致。
- `quantity_sum`：params.unit 为 uL 或 well；输入 a/b 与输出 quantity 同单位。manifest 对该多态计算不预声明固定数值字段，脚本验证两项有限非负值、来源、同单位及整数孔数；主 workflow 仍校验真实 calculated 依赖。
- 三项 mix：k1/k2/k3 均显式输入，满足 k1≥k2≥k3≥1，不逐级连乘；required 必须是实际下游输出汇总，不手造合计。

## 公式与状态

RNA体积=质量/浓度；水=总体积−RNA−gDNA−RT。RNA当量=原始RNA质量/RT体积/总稀释倍数，模板=目标当量/当量浓度，原液等效=模板/总稀释倍数。引物终浓度=工作液浓度×引物体积/总体积。

单孔公共底液=Premix+补水+ROX。mix3 每组分×实际孔数×k3；mix2 底液/模板×块实际孔数×k2；mix1 各组分×同组成实际孔数×k1。供液余额按实际下游需求扣除。孔数为正整数；负补水或供液不足拒绝。

只有 computed 的 outputs 是通过该项约束的数值；needs_review 的 candidate_outputs 仅供解释异常，不能当执行方案。数值结果不代表计划多表、曲线或实验方法均已验证。公式来自原模板与体积守恒；实际来源见 sources.md。
