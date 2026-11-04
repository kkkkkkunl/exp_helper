# 多表计划模型

## 结构

JSON 根：confirmed、factors（k1/k2/k3）、samples、templates、assays、recipes、blocks、targets、runs、wells、well_map_kind（planned/actual）。所有表为对象数组，除 targets/wells 外每行唯一 id；完整合成示例见 `../assets/synthetic-plan.json`，不代表实测实验。

| 表 | 必要字段 | 关系 |
|---|---|---|
| samples | id、cell_origin | 实际已有样品的记录归属；不造 NTC 生物样品 |
| templates | id、sample、material_type、source、volume_basis | cdna 或 nrt_control；直接体积须 volume_source；当量模式另有 rna_mass/rt_volume/dilution/target_mass |
| assays | id、gene、source、f_volume、r_volume | 具体引物对，不合并同名基因不同 assay |
| recipes | id、total_volume、premix、template、f_volume、r_volume、rox、dilution、method_profile、rox_basis | 数值均采用 calculate.py 的单位，不同组成独立 |
| blocks | id、run、type、template、recipe | RT/NTC/-RT；NTC template=null；同板同类型同模板同组成不得重复 |
| targets | block、assay、wells | 每配液块-assay 一行，wells 正整数 |
| runs | id、layout | 初版 layout 字符串 96 |
| wells | run、well、block、assay、type | 实际或计划逐孔表，孔位 A1-H12，唯一并同 targets 数量一致 |

## 使用与留痕

校验只读：`python -B scripts/validate_plan.py --input plan.json`。输出 status valid/invalid、具体 scope/reason、各数值计算与限制。报告不写实验项目，保存须走主 workflow 授权。planned 通过不证明 actual 布局；实际板图须另提交 actual 版本再核对。

共享 mix 保存时绑定本次真实样品作记录归属，params 保留 scope/plate/recipe/block/assay/affected_samples 和报告链接，依赖列出真实数值链。不能把归属样品当 NTC 来源，不能把所有 affected_samples 标为已执行。缺失表、孤立 ID、重复孔、错控制类型、模板槽不符、供液不足都不整体放行。
