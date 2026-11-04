# 来源与验证边界

## 方法来源

| 标识 | 规程 | 本包采用范围 | 来源核查状态 |
|---|---|---|---|
| S1 | GOONIE 400-100，241212 说明书 | 贴壁细胞 RNA 提取记录参考 | 用户模板已列本地扫描件；本包不重新宣称扫描参数经独立审核 |
| S2 | Accurate Biology AG11728 Version 6 | All in one RT/NRT 的已选方法体积约束 | 来自用户提供 qPCR.md 的来源及参数；运行须核对实际试剂版本 |
| S3 | Accurate Biology AG11701 V4E1 | SYBR 体系、2x比例、原液等效及 ROX 核对 | 来自用户模板；仪器适配与方法效果不由计算认证 |

用户提供的原始规程位置为实验记录库 `30_Manuals/01_RNA_qPCR/`，文件名分别为 GOONIE_细胞RNA快速提取试剂盒_400-100_241212_说明书.pdf、Accurate_Biology_Evo_M-MLV_RT_Premix_for_qPCR_Ver2_AG11728_Version6_说明书.pdf、Accurate_Biology_SYBR_Green_Pro_Taq_HS_qPCR_AG11701_V4E1_说明书.pdf。记录实际采用文件及哈希或稳定可恢复来源；本包不附带厂商整本说明书。

## 项目规则

三级余量 1.30/1.15/1.10、10 uL 起始配置、双技术孔等来自用户原模板，不是通用行业阈值。公式为体积守恒或当量定义。QC 0.5/1.0 Cq、内参优先和共同校准是用户项目选择，分析方法参考见 qpcr-ddcq。参数未确认、方法版本不同、曲线/效率未知时分别报告，不推断为实验合格。
