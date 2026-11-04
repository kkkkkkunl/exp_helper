---
name: cell-qpcr
description: 细胞 RT-qPCR 实验确定后，按当前阶段核对来源、计算 RT 与稀释及三级 mix、校验板位，并交接独立的 qPCR 结果分析；不用于组织提取、病原定量或基因组拷贝数。
version: "1.0.0"
kind: experiment
experiment_types: [cell-qpcr, 细胞RT-qPCR]
metadata:
  version: "1.0.0"
  kind: experiment
---

# 细胞 RT-qPCR

## 启动与范围

仅在用户明确开始或继续且实验类型、模板或方案确定后激活。贴壁细胞→RNA→RT/−RT→SYBR qPCR；允许已有细胞 RNA、cDNA、结果从相应入口进入，登记真实来源，前序操作不补写为本次事实。讨论备选不激活，附件不自动触发分析。

按当前步骤读取 [阶段规则](references/stages.md) 的相关部分；需要数值计算时再读 [计算契约](references/calculations.md)，准备配液时读 [计划模型](references/plan.md)。安装、配置、独立分析交接才读 [接入说明](references/integration.md)。方法参数来源与未验证限制见 [来源](references/sources.md)。

## 计算和记录

1. `experiment-skill.json` 是现有 workflow version 1 数值契约；`scripts/calculate.py` 从 stdin 读请求，仅输出 JSON。Python 3.9+，无第三方依赖。请求明确本次输入、单位、来源与 `params.confirmed: true`；模板参考值先展示确认，不生成实测值。
2. 输入齐全即计算当前步骤并展示，不等待另一次计算指令。`status: computed` 仅代表该项数值通过所声明约束；异常及候选值不可作为放行方案。缺参只阻断依赖部分，不补零。
3. `scripts/validate_plan.py --input <plan.json>` 只读验证多表身份、配方、控制类型、供液与实际逐孔映射。它不是数值计算接口；必须结合其报告核对计划，不能仅凭一个标量 computed 宣称整板放行。
4. 保存计算沿用主 workflow 的 preview/save；保留规则、输入、参数、依赖、技能整包依据。实际用量另据实际操作确认，计算不扣库存、不生成产物、不修改 completed。共享 mix 以已有真实样品作记录归属，params 明确 affected_samples 和配液身份，不伪造 NTC 样品。
5. 同一实验续接用原固定依据，明确升级才展示差异并确认。更正计算只复核依赖下游，不倒改实际操作和库存。

## 结果交接

明确分析请求或确认方案中的分析任务才按项目索引解析 **qpcr-ddcq**。传递真实原始文件、运行/板位、sample/bio_id/assay/scope 映射及确认参数；该技能缺失或工具不足时保留待分析，不回退模板旧公式。分析输出、实际分析技能内容依据和验证范围独立登记，生成文件不等于结果回填或实验结束。
