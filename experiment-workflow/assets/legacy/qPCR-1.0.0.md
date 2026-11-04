---
record_type: method_template
template_name: cell-qpcr
template_version: "1.0.0"
experiment_id: ""
experiment_title: 细胞 RT-qPCR
project: ""
project_category: ""
sample_batch: ""
start_date: ""
completed: false
completed_at: null
important: false
voided: false
tags: [template, cell, qpcr]
---

## 使用范围与填写原则

**本模板仅用于细胞来源的基因表达 RT-qPCR**，操作规程覆盖**贴壁细胞 → 总 RNA → cDNA → SYBR Green qPCR → 结果整理**。已有细胞来源 RNA 或 cDNA 可以从对应阶段进入，填写其来源；不包含组织、血液、体液、病原体定量或基因组拷贝数实验。悬浮细胞的提取步骤不在本版本覆盖范围内。

1. **参考方案、实际执行、实测值、计算值分开**。下列操作参数是待确认的参考值，不表示本次已经执行；空白不填零，结果不由模板生成。
2. **样品身份沿用 workflow 台账**。培养孔位不是样品编号；细胞、RNA、cDNA 和 −RT 产物分别关联真实来源。下表中的来源细胞、RNA、cDNA ID 均填写已有编号或台账链接，不按当前日期自动伪造。
3. **普通回答仅为会话草稿**。明确保存、阶段确认、暂停或提交最终结果时，按主 workflow 相应授权处理。模板文件本身不创建实验、不扣库存、不写日历。
4. **Markdown 正文供查阅与填写，文末唯一标记 YAML 供阶段交互读取**。使用 `format: staged` 时须配套支持嵌入式 YAML 的 workflow；Obsidian 的 Meta Bind、MarkCalc 是可选界面组件，不承担保存授权或生命周期判断。
5. **正式实验记录仅收录本次实际执行内容**，不将本模板全部步骤、空表或未做阶段复制为已执行事实。（来源：[W1]、[W2]。）

### 基本信息

实验名称：`INPUT[text:experiment_title]`  
课题：`INPUT[text:project]`  
课题小分类：`INPUT[text:project_category]`  
样品批次：`INPUT[text:sample_batch]`  
实际开始日期：`INPUT[text:start_date]`

| 项目 | 本次内容 |
|---|---|
| 实验编号／记录位置 | |
| 实验目的与目标基因 | |
| 操作者／复核者 | |
| 入口阶段 | 细胞设计／RNA 提取／逆转录／qPCR／已有细胞 qPCR 结果整理 |
| 来源实验、阶段及附件 | |
| 本次确认的模板版本 | |

## 阶段一：细胞样品与实验设计

### 样品与分组

**生物学重复**必须由实验设计明确；**技术复孔**不能代替独立生物学重复。样品、分组和基因名称的映射需可追溯，不能仅凭名称后缀判断独立性。（来源：[D1]、[G1]。）

| 来源细胞 ID | 细胞系／物种 | 培养板及孔位 | 分组 | 生物学重复 ID | 独立性依据 | 处理条件 |
|---|---|---|---|---|---|---|
| | | | | | | |
<!-- calc: @name = samples -->

| 来源细胞 ID | 处理开始时间 | 收样时间 | 处理时长 h（计算） | 融合度／细胞数（实测） | 来源／保存位置 |
|---|---|---|---:|---|---|
| | | | | | |
<!-- calc:
@name = sample_times ;
${处理时长 h（计算）} = durationH(cell("处理开始时间", row), cell("收样时间", row))
-->

### 引物与 assay 信息

**Assay ID**标识一套具体引物对；同名基因的不同引物对不自动合并。F、R 序列按 **5′→3′** 填写。默认单孔 F、R 各 **0.4 μL**，是沿用原模板的项目起始参数；若工作液为 **10 μM**、体系为 **10 μL**，各引物终浓度为 **0.4 μM**。厂商常用起始终浓度为 **0.2 μM**，可在 **0.1–1.0 μM** 范围优化；本模板默认值不等同于厂商最优条件。（来源：[S3]，第 3 页；0.4 μM 为体积公式推导。）

| Assay ID | 基因／物种 | 用途 | F 序列 | R 序列 | 扩增子 bp | 特异性／效率证据 |
|---|---|---|---|---|---:|---|
| | | 目标／内参 | | | | |
<!-- calc: @name = primers -->

| Assay ID | F 工作液 μM | R 工作液 μM | F 单孔 μL | R 单孔 μL | F 终浓度 μM（计算） | R 终浓度 μM（计算） |
|---|---:|---:|---:|---:|---:|---:|
| | 10 | 10 | 0.4 | 0.4 | | |
<!-- calc:
@name = primer_volumes ;
${F 终浓度 μM（计算）} = has(cell("Assay ID", row)) ? product(cell("F 工作液 μM", row), cell("F 单孔 μL", row), 0.1) : "" ;
${R 终浓度 μM（计算）} = has(cell("Assay ID", row)) ? product(cell("R 工作液 μM", row), cell("R 单孔 μL", row), 0.1) : ""
-->

### 分析设计预登记

| 分析范围 ID | 纳入分组／板号／批次 | 独立生物学重复声明 | 固定内参 Assay ID | 目标 Assay ID | 校准组 | 方法适用性依据 |
|---|---|---|---|---|---|---|
| | | 有／无／尚未明确 | | | | |

1. 默认 **ΔΔCq 法**。先明确内参稳定性、扩增特异性和效率适用依据；不能仅因模板默认 GAPDH 就认定它适用于本实验。
2. 内参按额外说明优先；未指定时整批 **GAPDH** 优先，整批不存在时使用已明确身份的 **actin assay**；同一可比较范围固定内参，不逐样品切换，不混并不同 actin 亚型。
3. 多个明确对照候选时先明确校准关系；完全没有对照标识才采用首次出现分组并登记假设。固定内参或校准关系不明确时，仅暂停受影响计算。（项目规则来源：[D1]；方法来源：[L1]。）

## 阶段二：贴壁细胞总 RNA 提取

### 开始前清点

| 类别 | 物品 | 核对内容 | 清点 |
|---|---|---|---|
| 试剂 | GOONIE 400-100、PBS、无水乙醇 | 批号／效期；Wash Buffer 首次使用已加 **45 mL** 无水乙醇 | ☐ |
| 耗材 | RNA 纯化柱及收集管、无 RNase 枪头与离心管 | 数量与细胞量匹配 | ☐ |
| 设备 | 摇床、离心机、移液器、冰盒、−80°C 冰箱 | 状态及设置已核对 | ☐ |
| 质控 | NanoDrop 或实际采用的定量设备 | 空白液、设备编号及测量方式已登记 | ☐ |

### 参考操作步骤

以下为 **GOONIE 400-100，241212 版**贴壁细胞方法。常规参考细胞量为 **1×10⁵–2×10⁶**；六孔板融合度 **60% 以上**时，说明书建议 **1 mL Lysis Buffer、2 根柱**，须根据本次样品确认。不能将参考细胞量写成实测细胞数。（来源：[S1]，第 1–2 页。）

1. 吸尽培养基，PBS 清洗 **1 次**，吸尽残留 PBS。
2. 常规样品加入 **500 μL Lysis Buffer**，室温 **120–150 rpm、2 min**；吹吸 **10 次**，避免气泡。
3. 加入与裂解液**等体积无水乙醇**，吹吸 **10 次**混匀后上柱；记录沉淀及分柱情况。
4. 室温 **12,000×g、1 min**，弃废液。
5. 加 **500 μL Wash Buffer**，按相同条件离心，弃废液。
6. 空柱按相同条件离心；转入无 RNase 1.5 mL 管，开盖晾干 **2 min**。
7. 柱膜中央加 **20–30 μL Elution Buffer**，室温静置 **2 min**；项目起始洗脱量沿用 **20 μL**，本次实际量另记。
8. 室温 **12,000×g、1 min**洗脱；记录 RNA 产物编号、实际体积及保存位置，按说明书保存于 **−80°C**。（来源：[S1]，第 2 页。）

### 实际执行与 RNA 产物

| 来源细胞 ID | 日期／尝试编号 | 实际步骤与偏离 | 裂解液 μL | 乙醇 μL | 柱数 | RNA ID | 实际洗脱体积 μL |
|---|---|---|---:|---:|---:|---|---:|
| | | | | | | | |

**定量设备／编号：**  
**空白液：**  
**测量日期时间：**

| RNA ID | 浓度 ng/μL（实测） | A260/A280（实测） | A260/A230（实测） | 完整性／其他 QC | 保存条件／位置 |
|---|---:|---:|---:|---|---|
| | | | | | |
<!-- calc: @name = rna_quant -->

> 直接从已有细胞 RNA 进入时，仅登记其来源与本次实际检测，不将原提取步骤记为本次已执行。吸光度比值不是 RNA 完整性的替代记录。

## 阶段三：去除 gDNA 与逆转录

### 试剂与方法选择

1. 核对 **AG11728 Version 6**、RNA 编号、批次、冰盒、无 RNase 反应管与耗材、PCR 仪程序。
2. 默认沿用原模板的 **All in one**：gDNA 去除与逆转录同管进行。该方法的适用条件依据厂商说明及本次 RNA 状态确认；采用两步法时，另记录去 gDNA 条件与所用体系，不套用 All in one 步骤冒充实际过程。
3. **−RT**采用 **NRT Control Reaction Mix**替换含逆转录酶的 5× RT Reaction Mix，保留相同来源 RNA 和相应条件；不能把水或未处理 RNA 标成已制备的 −RT 反应产物。（来源：[S2]，正文第 4–6 页。）

### 逆转录体系计算

每行是一管拟配反应，**RT 管 ID**仅为管位标签，不代替产物台账编号；计算值须核对后才能用于配液。RNA 浓度从上表读取，覆盖栏保留“沿用”时读取上表，有实际依据时改填实测值；显式填写零会报错。−RT 行将“RT／NRT mix”理解为 NRT Control Reaction Mix，并填写真实反应类型。

| RT 管 ID | 类型 | RNA ID | 浓度覆盖 ng/μL | RNA 质量 ng | 总体积 μL | gDNA mix μL | RT／NRT mix μL |
|---|---|---|---:|---:|---:|---:|---:|
| | RT | | 沿用 | 1000 | 20 | 2 | 4 |
<!-- calc: @name = rt_inputs -->

| RT 管 ID | RNA 浓度 ng/μL（采用） | RNA 体积 μL（计算） | 补水 μL（计算） | 体系状态 |
|---|---:|---:|---:|---|
| | | | | |
<!-- calc:
@name = rt_calc ;
${RT 管 ID} = tcell("rt_inputs", "RT 管 ID", row) ;
${RNA 浓度 ng/μL（采用）} = has(cell("RT 管 ID", row)) ? prefer(tcell("rt_inputs", "浓度覆盖 ng/μL", row), tlookup("rna_quant", "RNA ID", tcell("rt_inputs", "RNA ID", row), "浓度 ng/μL（实测）")) : "" ;
${RNA 体积 μL（计算）} = has(cell("RT 管 ID", row)) ? divide(tcell("rt_inputs", "RNA 质量 ng", row), cell("RNA 浓度 ng/μL（采用）", row)) : "" ;
${补水 μL（计算）} = has(cell("RT 管 ID", row)) ? water(tcell("rt_inputs", "总体积 μL", row), [cell("RNA 体积 μL（计算）", row), tcell("rt_inputs", "gDNA mix μL", row), tcell("rt_inputs", "RT／NRT mix μL", row)]) : "" ;
${体系状态} = has(cell("RT 管 ID", row)) ? rtCheck(cell("RNA 浓度 ng/μL（采用）", row), tcell("rt_inputs", "RNA 质量 ng", row), tcell("rt_inputs", "总体积 μL", row), tcell("rt_inputs", "gDNA mix μL", row), tcell("rt_inputs", "RT／NRT mix μL", row), cell("补水 μL（计算）", row)) : ""
-->

**补水 = 总体积 − RNA 体积 − 实际 gDNA mix 体积 − 实际 RT／NRT mix 体积**。不再写死扣除 6 μL；水为零可接受，负值或非正浓度报错。20 μL SYBR 用途反应的厂商 RNA 起始量建议不超过 **1,000 ng**，超过时须重新核对方法，不能仅因体积可容纳而放行。（来源：[S2]，正文第 5–6 页；公式为体积守恒推导。）

### 参考加样与程序

默认 All in one 顺序：无 RNase 水 → gDNA Clean Reaction Mix → 5× RT Reaction Mix（−RT 为 NRT mix）→ RNA，轻柔混匀、短暂离心。**37°C、15 min → 85°C、5 s → 4°C Hold**。两步法另登记完整程序。立即使用可暂置冰上或 4°C；短期 −20°C、长期 −80°C，实际保存时间与冻融次数另记。（来源：[S2]，正文第 6 页。）

| RT 管 ID | 日期／尝试 | 实际方法／程序／用量确认 | cDNA 或 −RT 产物 ID | 实际反应体积 μL | 保存位置 | 异常与处置 |
|---|---|---|---|---:|---|---|
| | | | | | | |

### cDNA 工作液与 RNA 当量

**RNA 当量浓度**是起始 RNA 质量除以 RT 体积和稀释倍数的计算值，**不是实测 cDNA 浓度**。已有细胞来源 cDNA 可填入可追溯的原始 RNA 质量与 RT 体积；缺失时不推定其 RNA 当量，可在配液组成表直接登记实际模板体积及依据。（来源：[S2]，正文第 4 页；当量关系为定义与公式推导。）

| 模板 ID | 产物类型 | 来源 RT 管／实验链接 | 原始 RNA 质量 ng | RT 体积 μL | 稀释倍数 | 目标当量 ng/孔 |
|---|---|---|---:|---:|---:|---:|
| | cDNA／−RT | | | | 1 | 25 |
<!-- calc: @name = cdna_inputs -->

| 模板 ID | RNA 当量 ng/μL（计算） | 所需模板 μL/孔（计算） | 原液等效 μL/孔（计算） |
|---|---:|---:|---:|
| | | | |
<!-- calc:
@name = cdna_calc ;
${模板 ID} = tcell("cdna_inputs", "模板 ID", row) ;
${RNA 当量 ng/μL（计算）} = has(cell("模板 ID", row)) ? rnaEquivalent(tcell("cdna_inputs", "原始 RNA 质量 ng", row), tcell("cdna_inputs", "RT 体积 μL", row), tcell("cdna_inputs", "稀释倍数", row)) : "" ;
${所需模板 μL/孔（计算）} = has(cell("模板 ID", row)) ? divide(tcell("cdna_inputs", "目标当量 ng/孔", row), cell("RNA 当量 ng/μL（计算）", row)) : "" ;
${原液等效 μL/孔（计算）} = has(cell("模板 ID", row)) ? divide(cell("所需模板 μL/孔（计算）", row), tcell("cdna_inputs", "稀释倍数", row)) : ""
-->

## 阶段四：qPCR 配液、板图与运行

### 上机前清点与运行信息

| 类别 | 物品 | 核对内容 | 清点 |
|---|---|---|---|
| 试剂 | AG11701、F/R 引物、模板、水、按需 ROX | 批号／效期／浓度；预混液避光、轻柔混匀 | ☐ |
| 对照 | NTC、已制备 −RT | 每套 assay 的对照设计及来源已写入板图 | ☐ |
| 耗材 | 光学板、封膜、枪头、EP 管／试剂槽 | 仪器兼容、清洁及数量 | ☐ |
| 设备 | qPCR 仪、离心机、移液器 | 型号、通道、程序与 ROX 要求 | ☐ |

| 板号／运行 ID | 仪器型号／编号 | ROX 要求及依据 | ROX 工作液与单孔体积 | 程序文件 | 日期／原始文件 |
|---|---|---|---|---|---|
| | | | | | |

### 单孔配液组成组

每个**组成组 ID**对应一套相同单孔体积组成。默认总体积 **10 μL**，2× Premix **5 μL**，模板槽 **0.5 μL**，F/R 各 **0.4 μL**，不加 ROX 时补水 **3.7 μL**。需要 ROX 时显式填入并从补水扣除；**ROX=0 只是未额外加入的起始配置，不能代替仪器适配核查**。（来源：[S3]，第 3–4 页；10 μL 为原模板采用的等比例缩小体系。）

| 组成组 ID | Premix μL | 模板槽 μL | F μL | R μL | ROX μL | 水 μL（计算） | mix1 单位 μL（计算） | 组成状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| | 5 | 0.5 | 0.4 | 0.4 | 0 | | | |
<!-- calc:
@name = recipes ;
${水 μL（计算）} = has(cell("组成组 ID", row)) ? water(10, [cell("Premix μL", row), cell("模板槽 μL", row), cell("F μL", row), cell("R μL", row), cell("ROX μL", row)]) : "" ;
${mix1 单位 μL（计算）} = has(cell("组成组 ID", row)) ? total([cell("Premix μL", row), cell("ROX μL", row), cell("水 μL（计算）", row)]) : "" ;
${组成状态} = has(cell("组成组 ID", row)) ? recipeCheck(cell("Premix μL", row), cell("模板槽 μL", row), cell("F μL", row), cell("R μL", row), cell("ROX μL", row), cell("水 μL（计算）", row)) : ""
-->

若不同模板的 RNA 上样量或稀释倍数导致所需体积不同，分别建立组成组。不同 assay 的 F/R 体积不同也须分组。组成不同的 mix1 不合并配制。

### 三级 mix 余量系数

| 层级 | 系数 | 含义 |
|---|---:|---|
| mix1 | 1.30 | 相对实际计划孔数配制公共底液 |
| mix2 | 1.15 | 相对每个模板配液块的实际计划孔数加入底液与模板 |
| mix3 | 1.10 | 相对每个“配液块—assay”实际技术孔数加入 mix2 与引物 |
<!-- calc: @name = mix_factors -->

**三个系数均相对实际孔数，不逐级连乘**。必须满足 **k1 ≥ k2 ≥ k3 ≥ 1**。此为原模板沿用的项目配液余量，不是厂商统一推荐值；管壁损失、试剂槽死体积及移液器可操作性仍需人工核对。

### 配液块与实际孔数

**配液块 ID**对应“同板、同模板或同对照、同组成组”的一管 mix2。每个配液块分别编号；同一样品跨板时另建块。NTC 单独建块，模板槽加入等体积无核酸酶水；−RT 单独建块，模板槽加入已制备的 −RT 产物，不能混入 RT 样品块。

| 配液块 ID | 板号／运行 ID | 类型 | 模板 ID | 组成组 ID | 模板体积采用依据／稀释记录 |
|---|---|---|---|---|---|
| | | RT／NTC／−RT | | | |
<!-- calc: @name = blocks -->

每行对应一管 mix3。**计划孔数**直接来自本表，包含单列的 NTC、−RT，不再由“样品数×引物数×复孔数”推定。技术复孔起始值沿用 **2 孔**；实际设多少孔就填多少，不能把该数计作生物学重复数。

| 配液块 ID | Assay ID | 技术孔数 | mix2 转入 μL（计算） | F 加入 μL（计算） | R 加入 μL（计算） | mix3 总量 μL（计算） | 配液核对 |
|---|---|---:|---:|---:|---:|---:|---|
| | | 2 | | | | | |
<!-- calc:
@name = targets ;
${mix2 转入 μL（计算）} = has(cell("配液块 ID", row)) ? targetMix(cell("配液块 ID", row), cell("技术孔数", row), tlookup("blocks", "配液块 ID", cell("配液块 ID", row), "组成组 ID"), tcol("recipes", "组成组 ID"), tcol("recipes", "F μL"), tcol("recipes", "R μL"), tlookup("mix_factors", "层级", "mix3", "系数")) : "" ;
${F 加入 μL（计算）} = has(cell("配液块 ID", row)) ? product(cell("技术孔数", row), tlookup("mix_factors", "层级", "mix3", "系数"), tlookup("primer_volumes", "Assay ID", cell("Assay ID", row), "F 单孔 μL")) : "" ;
${R 加入 μL（计算）} = has(cell("配液块 ID", row)) ? product(cell("技术孔数", row), tlookup("mix_factors", "层级", "mix3", "系数"), tlookup("primer_volumes", "Assay ID", cell("Assay ID", row), "R 单孔 μL")) : "" ;
${mix3 总量 μL（计算）} = has(cell("配液块 ID", row)) ? total([cell("mix2 转入 μL（计算）", row), cell("F 加入 μL（计算）", row), cell("R 加入 μL（计算）", row)]) : "" ;
${配液核对} = has(cell("配液块 ID", row)) ? targetCheck(cell("技术孔数", row), cell("Assay ID", row), tlookup("blocks", "配液块 ID", cell("配液块 ID", row), "组成组 ID"), tcol("recipes", "组成组 ID"), tcol("recipes", "F μL"), tcol("recipes", "R μL"), tlookup("primer_volumes", "Assay ID", cell("Assay ID", row), "F 单孔 μL"), tlookup("primer_volumes", "Assay ID", cell("Assay ID", row), "R 单孔 μL"), cell("mix3 总量 μL（计算）", row), tlookup("mix_factors", "层级", "mix3", "系数")) : ""
-->

### mix2：按模板配液块配置

| 配液块 ID | 计划孔数（计算） | mix1 取用 μL（计算） | 模板／NTC 水 μL（计算） | mix2 配制 μL（计算） | mix3 需用 μL（计算） | 剩余 μL（计算） | 供液状态 |
|---|---:|---:|---:|---:|---:|---:|---|
| | | | | | | | |
<!-- calc:
@name = mix2 ;
${配液块 ID} = tcell("blocks", "配液块 ID", row) ;
${计划孔数（计算）} = has(cell("配液块 ID", row)) ? sumWhere(tcol("targets", "配液块 ID"), tcol("targets", "技术孔数"), cell("配液块 ID", row)) : "" ;
${mix1 取用 μL（计算）} = has(cell("配液块 ID", row)) ? product(cell("计划孔数（计算）", row), tlookup("mix_factors", "层级", "mix2", "系数"), tlookup("recipes", "组成组 ID", tcell("blocks", "组成组 ID", row), "mix1 单位 μL（计算）")) : "" ;
${模板／NTC 水 μL（计算）} = has(cell("配液块 ID", row)) ? product(cell("计划孔数（计算）", row), tlookup("mix_factors", "层级", "mix2", "系数"), tlookup("recipes", "组成组 ID", tcell("blocks", "组成组 ID", row), "模板槽 μL")) : "" ;
${mix2 配制 μL（计算）} = has(cell("配液块 ID", row)) ? total([cell("mix1 取用 μL（计算）", row), cell("模板／NTC 水 μL（计算）", row)]) : "" ;
${mix3 需用 μL（计算）} = has(cell("配液块 ID", row)) ? sumWhere(tcol("targets", "配液块 ID"), tcol("targets", "mix2 转入 μL（计算）"), cell("配液块 ID", row)) : "" ;
${剩余 μL（计算）} = has(cell("配液块 ID", row)) ? difference(cell("mix2 配制 μL（计算）", row), cell("mix3 需用 μL（计算）", row)) : "" ;
${供液状态} = has(cell("配液块 ID", row)) ? supplyCheck(cell("mix2 配制 μL（计算）", row), cell("mix3 需用 μL（计算）", row), [tlookup("mix_factors", "层级", "mix1", "系数"), tlookup("mix_factors", "层级", "mix2", "系数"), tlookup("mix_factors", "层级", "mix3", "系数")]) : ""
-->

### mix1：按相同组成组配置公共底液

含 ROX 时加入 mix1 并同步减少水。这里的“Premix”是含酶的 2× 预混液，不能作为纯酶体积解释。

| 组成组 ID | 计划孔数（计算） | Premix μL（计算） | 水 μL（计算） | ROX μL（计算） | mix1 配制 μL（计算） | mix2 需用 μL（计算） | 剩余 μL（计算） | 供液状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| | | | | | | | | |
<!-- calc:
@name = mix1 ;
${组成组 ID} = tcell("recipes", "组成组 ID", row) ;
${计划孔数（计算）} = has(cell("组成组 ID", row)) ? sumWhere(tcol("blocks", "组成组 ID"), tcol("mix2", "计划孔数（计算）"), cell("组成组 ID", row)) : "" ;
${Premix μL（计算）} = has(cell("组成组 ID", row)) ? product(cell("计划孔数（计算）", row), tlookup("mix_factors", "层级", "mix1", "系数"), tcell("recipes", "Premix μL", row)) : "" ;
${水 μL（计算）} = has(cell("组成组 ID", row)) ? product(cell("计划孔数（计算）", row), tlookup("mix_factors", "层级", "mix1", "系数"), tcell("recipes", "水 μL（计算）", row)) : "" ;
${ROX μL（计算）} = has(cell("组成组 ID", row)) ? product(cell("计划孔数（计算）", row), tlookup("mix_factors", "层级", "mix1", "系数"), tcell("recipes", "ROX μL", row)) : "" ;
${mix1 配制 μL（计算）} = has(cell("组成组 ID", row)) ? total([cell("Premix μL（计算）", row), cell("水 μL（计算）", row), cell("ROX μL（计算）", row)]) : "" ;
${mix2 需用 μL（计算）} = has(cell("组成组 ID", row)) ? sumWhere(tcol("blocks", "组成组 ID"), tcol("mix2", "mix1 取用 μL（计算）"), cell("组成组 ID", row)) : "" ;
${剩余 μL（计算）} = has(cell("组成组 ID", row)) ? difference(cell("mix1 配制 μL（计算）", row), cell("mix2 需用 μL（计算）", row)) : "" ;
${供液状态} = has(cell("组成组 ID", row)) ? supplyCheck(cell("mix1 配制 μL（计算）", row), cell("mix2 需用 μL（计算）", row), [tlookup("mix_factors", "层级", "mix1", "系数"), tlookup("mix_factors", "层级", "mix2", "系数"), tlookup("mix_factors", "层级", "mix3", "系数")]) : ""
-->

实际加样顺序仍为 **mix1 → 分配至各配液块并加入对应模板形成 mix2 → 按 assay 分配并加入 F/R 形成 mix3 → 每孔 10 μL 分装**。上表按计算依赖展示，不能将余量也作为单孔增量加入。

### 配液放行核对

1. 每张表按实际需要扩展行数；**rt_calc、cdna_calc、mix2、mix1**行数分别与其来源表一致。表内 ID 唯一；每个“配液块—assay”只保留一行。
2. 每条配液块须在 targets 中有实际计划孔，且每条 targets 的块、组成组、assay 都能匹配；无孤立行、重复 ID、无效类型或无效孔数。
3. RT 与 −RT 配液块的模板 ID 及原始来源正确；**组成组模板槽体积与所需模板体积一致**。直接指定体积时记录实际依据，不冒充已知 RNA 当量。
4. 对原液及稀释液均核对**原液等效体积 = 加样体积÷稀释倍数**，不超过 qPCR 总体积的 **10%**；10 μL 体系即原液等效不超过 **1 μL/孔**。超出时调整设计并重算，不能单靠补水非负放行。（来源：[S3]，第 3 页。）
5. 所有组成状态、引物体积匹配、系数与供液检查通过；同时核对可操作的移液体积、总模板量及独立计算结果。这里的“供液量足够”仅表示体积守恒，不代表实验条件已验证。

### 板图与逐孔映射

**板号：**  
**板图文件／仪器导入文件：**

| 行／列 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | | | | | | | | | | | | |
| B | | | | | | | | | | | | |
| C | | | | | | | | | | | | |
| D | | | | | | | | | | | | |
| E | | | | | | | | | | | | |
| F | | | | | | | | | | | | |
| G | | | | | | | | | | | | |
| H | | | | | | | | | | | | |

格内建议填写“配液块 ID／Assay ID／技术孔号”，每块板复制一份。以下逐孔表为分析映射依据，不能仅靠示意板图恢复生物学重复身份。

| 运行 ID | 孔位 | 配液块 ID | 类型 | 模板 ID | 生物学重复 ID | 分组 | Assay ID | 技术孔号 |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

核对每板孔数 **≤96**、孔位不重复、实际逐孔数与 targets 的计划孔数逐项相符；空位不作为零值记录。

### qPCR 参考程序与实际执行

| 步骤 | 温度 | 时间 | 循环／采集 |
|---|---:|---:|---|
| 预变性 | **95°C** | **30 s** | 1 次 |
| 变性 | **95°C** | **5 s** | 与下一步组成 **40** 个循环 |
| 退火／延伸 | **60°C** | **30 s** | 此步采集荧光 |
| 熔解曲线 | 按实际仪器 | 按实际程序 | 记录程序文件及峰形 |

上表为厂商两步法参考程序，实际仪器、引物与扩增子适配情况另记，不能将默认熔解程序套用于所有仪器。（来源：[S3]，第 3 页。）

| 日期／尝试 | 实际配液与用量确认 | 实际程序／ROX／通道 | 封板／离心情况 | 原始运行文件 | 异常与处置 |
|---|---|---|---|---|---|
| | | | | | |

## 阶段五：原始数据、质控与结果整理

### 原始证据

| 原始文件／链接 | 板号／运行 ID | 导出时间／软件版本 | 板位映射文件 | 数据范围／重复导出说明 |
|---|---|---|---|---|
| | | | | |

保留仪器原始运行文件、未筛选 Cq、板位文件、扩增与熔解曲线；不修复科研原图。**仪器 Excluded、Undetermined、No Ct、空白和非数值 Cq 保留原样**，解析状态另列，不用零、固定循环数或检测限代填。（来源：[D1]、[W1]。）

| 文件／原始行 | 运行 ID／孔位 | 模板 ID | 分组／生物学重复 ID | Assay ID | Cq 原始值 | Excluded 原值 | 备注／排除依据 |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

### 复孔质控规则

**最大差值 = 同一样本、同一 assay 的有效技术孔最大 Cq − 最小 Cq**，以未作显示舍入的数据判定。下列 **0.5／1.0 Cq 阈值为项目规则**，不归因于 MIQE。（来源：[D1]。）

| 有效孔数 | 最大差值 | 状态 | 默认处理 |
|---|---|---|---|
| ≥2 | <0.5 Cq | 严格合格 | 保留 |
| ≥2 | ≥0.5 且 <1.0 Cq | 未达严格标准 | 保留可计算结果并标记 |
| ≥2 | ≥1.0 Cq | 严重不合格 | 保留可计算结果并标记 |
| 1 | 不定义复孔差值 | 复孔不足 | 保留可计算结果并标记 |
| 0 | 不定义复孔差值 | 无有效 Cq | 无法计算，不画成零柱 |

Excluded 孔不参与有效均值；不得因为差值不合格而静默删孔。**可计算状态与 QC 状态分列**；目标、内参或校准来源存在 QC 风险时，结果应携带对应风险标记。

| 核对项 | 实际结果／证据 | 影响范围与处置 |
|---|---|---|
| 扩增曲线、熔解特异性 | | |
| NTC、−RT | | |
| 引物效率及方法适用性 | | |
| 有效孔、Excluded 与未检出 | | |
| 复孔差值及最大差值所在样本／基因／孔位 | | |
| 缺失匹配内参／校准样本 | | |
| 所有人工排除／复测依据 | | |

### 相对表达量计算与统计

1. **ΔCq = 目标基因平均 Cq − 同一样本固定内参平均 Cq**；缺匹配内参不借用同组其他样本。
2. 有独立生物学重复时，**校准基准 = 同一目标基因校准组各可计算生物学重复 ΔCq 的算术均值**，样本等权；**ΔΔCq = 样本 ΔCq − 校准基准**；**相对表达量 = 2^(−ΔΔCq)**。
3. 保留对照重复变异，不强制每个对照重复或对照表达量算术均值等于 1。无独立生物学重复时按分组产生单个 ΔCq，校准组相对表达量为 1。
4. 无独立生物学重复时不加误差条、不做显著性检验；有明确独立重复时默认使用**样本 SD**，指定时用 **SEM**，并报告实际可计算的 n；n<2 不绘制该组误差条。不自动添加显著性星号。
5. 显示默认 **3 位小数**，计算保留原始精度；不把无法计算当成表达量为零。（项目选择来源：[D1]、[A1]；方法来源：[L1]。）

| 分析范围 | 模板／生物学重复 ID | 分组 | 目标 assay | 固定内参 assay | ΔCq | 校准基准 | ΔΔCq | 相对表达量 | 计算状态 | QC 状态 |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| | | | | | | | | | | |

### 分析技能交接与交付核对

**qpcr-ddcq**在所依据访谈中仍是拟实现的分析技能名，本模板不宣称它已存在、安装或可运行。实际分析时先解析项目 `skills/analysis` 索引，记录真正使用的技能或工具；缺工具时保留待分析状态。（来源：[D1]、[W3]。）

| 项目 | 本次采用内容 |
|---|---|
| 技能／工具名称、版本或哈希 | |
| 输入文件与板位／样本映射 | |
| 固定内参、校准关系、纳入范围 | |
| 实际参数、排除规则及假设 | |
| 输出工作簿／图表／验证记录 | |
| 结果已回填的位置 | |

| 工作表 | 约定内容 | 核对 |
|---|---|---|
| 说明 | 参数、阈值来源、内参／校准、缺失与排除、验证状态 | ☐ |
| 原始数据 | 完整逐孔证据、原始 Cq 与 Excluded | ☐ |
| 复孔质控 | 有效孔数、均值、最大差值、状态与异常 | ☐ |
| 计算过程 | 可追溯公式、ΔCq、校准基准、ΔΔCq、表达量 | ☐ |
| 整理数据 | **无表头，仅“分组、基因、相对表达量”三列**；分组优先 | ☐ |
| 作图 | 每目标基因独立 Excel 原生柱形图；无标题图例；纵轴从零、轴名“基因名 relative expression”；分类轴零基线清晰、标签位于轴线下方 | ☐ |

该表是分析输出要求，不是本次已经生成或检验通过的工作簿。未做公式重算或图表渲染时明确记为未验证。无异常时报告“全部复孔严格合格”及最大差值位置；存在异常时列出完整清单。（来源：[D1]。）

### 结论与证据

**已有结果支持的结论：**

**基于结果的解释／假设：**

**限制、缺失与复测依据：**

**图表与完整结果链接：**

## 阶段暂停、库存与完成

### 本轮实际收尾

| 阶段／样品／尝试 | 已执行步骤 | 未执行步骤 | 实际中断点／保存状态 | 继续依据／待补项 | 后续日期／时间／时长 |
|---|---|---|---|---|---|
| | | | | | |

1. 同次实验续接沿用编号；用旧样品开展新实验另建编号并关联来源。RNA、cDNA 产物独立登记，不能把前序来源操作复制为本次事实。
2. 本模板**不声明可自动放行的安全暂停点**，YAML 的 `pause_after` 均为 false。真实暂停照实保存；保存记录或写了储存条件不等于已经验证任意中断时长后都可继续。
3. 暂停时保存已做部分，未做步骤保持未执行并进入日历后续事项；没有真实远端回执不报告排期成功。
4. 保存后核查本轮实际库存变化，清单须包含来源／产物编号、实际量与单位；不以配液理论用量自动扣库存，不重复提交历史消耗。（来源：[W1]、[W2]。）

| 事件／来源 ID | 材料／产物 ID | 实际操作 | 数量 | 单位 | 位置 | 已展示并确认的依据 |
|---|---|---|---:|---|---|---|
| | | | | | | |

### 最终结果与归档

**completed／completed_at 只表示结果整理状态**；执行进度、归档状态和日历同步单独由 workflow 管理。明确提交本次最终结果后，按实际范围整理与关联附件，再更新完成状态并检查归档；单独上传原始数据、初步讨论或勾选清单不触发完成。不保留原模板直接设置完成状态的“完成并归档”按钮。（来源：[W1]、[W2]。）

## 方法、规则与来源

### 厂商操作依据

1. **[S1] GOONIE**：《细胞 RNA 快速提取试剂盒说明书》，400-100，241212 版，第 1–2 页。本地：[[30_Manuals/01_RNA_qPCR/GOONIE_细胞RNA快速提取试剂盒_400-100_241212_说明书.pdf]]；[官方产品页](https://gooniebio.com/product/8.html)。本次已核对本地扫描页，网页访问未成功。
2. **[S2] Accurate Biology**：《Evo M-MLV RT Mix Kit with gDNA Clean for qPCR Ver.2》，AG11728，Version 6，正文第 4–7 页。本地：[[30_Manuals/01_RNA_qPCR/Accurate_Biology_Evo_M-MLV_RT_Premix_for_qPCR_Ver2_AG11728_Version6_说明书.pdf]]；[厂商说明书地址](https://agbio.com.cn/wp-content/uploads/2023/03/UM_AG11728-DV-Version-6.pdf)。本次已核对本地正文，网页访问未成功。
3. **[S3] Accurate Biology**：《SYBR Green Premix Pro Taq HS qPCR Kit》，AG11701，V4E1，第 3–4 页。本地：[[30_Manuals/01_RNA_qPCR/Accurate_Biology_SYBR_Green_Pro_Taq_HS_qPCR_AG11701_V4E1_说明书.pdf]]；[官方产品及说明书页](https://en.agbio.com.cn/en/product/sybr-green-premix-pro-taq-hs-qpcr-kit/)。已核对本地说明书与官方产品页。

### 项目规则与计算依据

1. **[D1] qPCR 设计访谈**：[qPCR技能设计访谈.md](../../docs/qPCR技能设计访谈.md)。仅将用户原始要求及第一、二轮明确选择作为已确认规则；“拟实施完整方案”不因此整体转为已确认或已实现。
2. **[A1] 共同校准决策**：[ADR 0008](../../docs/adr/0008-qpcr-calibration-preserves-biological-variation.md)。
3. **[G1] 领域术语**：[GLOSSARY.md](../../docs/GLOSSARY.md)。
4. **[W1] 主 workflow**：[SKILL.md](../SKILL.md)。
5. **[W2] 阶段交互与模板规范**：[stage-record-module.md](../references/stage-record-module.md)、[stage-template-rules.md](../references/stage-template-rules.md)。
6. **[W3] 分析与结果边界**：[result-module.md](../references/result-module.md)。
7. **[L1] 方法文献**：Livak KJ, Schmittgen TD. *Methods*. 2001;25(4):402–408. DOI：[10.1006/meth.2001.1262](https://doi.org/10.1006/meth.2001.1262)，已核对 [PubMed 书目与摘要](https://pubmed.ncbi.nlm.nih.gov/11846609/)。项目 QC 阈值和默认内参不是该论文规定。
8. **模板重建来源**：用户提供的 `F:/实验文件/实验记录/80_Templates/qPCR.md`；本轮确认“Markdown 中嵌入 YAML”“保留三级 mix”，补充限定“只用于细胞 qPCR”。重建日期：**2026-11-04**。未覆盖原文件。
9. **[L2] 报告透明性参考**：Bustin SA, et al. MIQE 2.0. *Clinical Chemistry*. 2025;71(6):634–651. DOI：[10.1093/clinchem/hvaf043](https://academic.oup.com/clinchem/article/71/6/634/8119148)。用于报告字段与可追溯性核对；引用指南不表示本模板或某次实验已经满足全部要求。

## 附录一：MarkCalc 计算函数

<details>
<summary>展开计算函数与使用限制</summary>

以下为本模板自带的纯计算函数。计算表使用 MarkCalc 的 `cell/tcell/tlookup/tcol` 语法；未安装插件时，公式只保留为文本，可人工复算。离线验证不等同于已在实际 Obsidian／MarkCalc 版本运行。

```calc-js
const warn = "⚠ 参数缺失或无效";
const has = v => v !== undefined && v !== null && v !== 0 && String(v).trim() !== "";
const number = v => typeof v !== "boolean" && v !== null && v !== undefined && String(v).trim() !== "" && Number.isFinite(Number(v));
const positive = v => number(v) && Number(v) > 0;
const nonnegative = v => number(v) && Number(v) >= 0;
const total = a => Array.isArray(a) && a.every(nonnegative) ? a.reduce((s, v) => s + Number(v), 0) : warn;
const product = (...a) => a.every(nonnegative) ? a.reduce((s, v) => s * Number(v), 1) : warn;
const divide = (a, b) => positive(a) && positive(b) ? Number(a) / Number(b) : warn;
const difference = (a, b) => nonnegative(a) && nonnegative(b) ? Number(a) - Number(b) : warn;
const water = (v, a) => {
    if (!positive(v) || !Array.isArray(a) || !a.every(nonnegative)) return warn;
    const w = Number(v) - total(a);
    return w < -1e-9 ? "⚠ 体系超容：补水为负" : Math.max(0, w);
};
const rnaEquivalent = (m, v, d) => positive(m) && positive(v) && positive(d) ? Number(m) / Number(v) / Number(d) : warn;
const sumWhere = (keys, values, key) => {
    if (!has(key) || !Array.isArray(keys) || !Array.isArray(values) || keys.length !== values.length) return warn;
    const selected = keys.map((k, i) => k === key ? i : -1).filter(i => i >= 0).map(i => values[i]);
    return selected.length && selected.every(nonnegative) ? total(selected) : warn;
};
const uniqueValue = (id, keys, values) => {
    if (!has(id) || !Array.isArray(keys) || !Array.isArray(values) || keys.length !== values.length) return warn;
    const indexes = keys.map((k, i) => k === id ? i : -1).filter(i => i >= 0);
    return indexes.length === 1 ? values[indexes[0]] : warn;
};
const recipeCheck = (p, c, f, r, x, w) => {
    if (![p, c, f, r].every(positive) || ![x, w].every(nonnegative)) return warn;
    if (Math.abs(Number(p) - 5) > 1e-9) return "⚠ 10 μL 体系须核对 2× Premix 比例";
    return Math.abs(total([p, c, f, r, x, w]) - 10) <= 1e-9 ? "体积组成通过；仍须核对方法与 ROX" : "⚠ 单孔总体积不为10 μL";
};
const rtCheck = (c, m, v, g, r, w) => {
    if (![c, m, v, g, r].every(positive) || !nonnegative(w)) return warn;
    if (Number(m) / Number(v) > 50 + 1e-9) return "⚠ RNA 起始量超过等比例1 μg/20 μL";
    if (Math.abs(Number(g) / Number(v) - 0.1) > 1e-9 || Math.abs(Number(r) / Number(v) - 0.2) > 1e-9) return "⚠ 试剂比例变化，须核对方法";
    return "体积通过；参数须确认";
};
const targetMix = (block, n, recipe, ids, fv, rv, k) => {
    const f = uniqueValue(recipe, ids, fv), r = uniqueValue(recipe, ids, rv);
    if (!has(block) || !positive(n) || !Number.isInteger(Number(n)) || !positive(f) || !positive(r) || !number(k) || Number(k) < 1) return warn;
    const v = 10 - Number(f) - Number(r);
    return v > 0 ? v * Number(n) * Number(k) : warn;
};
const targetCheck = (n, assay, recipe, ids, fv, rv, f, r, v, k) => {
    if (!has(assay) || !positive(n) || !Number.isInteger(Number(n)) || ![f, r, v].every(positive) || !number(k) || Number(k) < 1) return warn;
    const rf = uniqueValue(recipe, ids, fv), rr = uniqueValue(recipe, ids, rv);
    if (!positive(rf) || !positive(rr) || Math.abs(Number(f) - Number(rf)) > 1e-9 || Math.abs(Number(r) - Number(rr)) > 1e-9) return "⚠ 引物体积不匹配组成组";
    return Math.abs(Number(v) - 10 * Number(n) * Number(k)) <= 1e-9 ? "体积匹配；须核对ID及来源" : "⚠ mix3体积不守恒";
};
const supplyCheck = (made, needed, ks) => {
    if (!Array.isArray(ks) || ks.length !== 3 || !ks.every(positive) || !(Number(ks[0]) >= Number(ks[1]) && Number(ks[1]) >= Number(ks[2]) && Number(ks[2]) >= 1)) return "⚠ 系数须满足k1≥k2≥k3≥1";
    if (!positive(made) || !positive(needed)) return warn;
    return Number(made) + 1e-9 >= Number(needed) ? "供液量足够；须核对死体积" : "⚠ 上游供液不足";
};
exports.has = has;
exports.prefer = (manual, automatic) => manual === "沿用" || manual === "" || manual === null || manual === undefined ? automatic : manual;
exports.total = total;
exports.product = product;
exports.divide = divide;
exports.difference = difference;
exports.water = water;
exports.rnaEquivalent = rnaEquivalent;
exports.sumWhere = sumWhere;
exports.rtCheck = rtCheck;
exports.recipeCheck = recipeCheck;
exports.targetMix = targetMix;
exports.targetCheck = targetCheck;
exports.supplyCheck = supplyCheck;
exports.durationH = (start, end) => {
    if (!has(start) || !has(end)) return "";
    const a = new Date(String(start).replace(" ", "T")), b = new Date(String(end).replace(" ", "T"));
    if (!Number.isFinite(a.getTime()) || !Number.isFinite(b.getTime())) return "⚠ 时间格式错误";
    if (b < a) return "⚠ 收样时间早于开始时间";
    return (b - a) / 3600000;
};
```

</details>

## 附录二：workflow 阶段定义

<details>
<summary>展开嵌入式 YAML 阶段定义</summary>

以下是阶段交互定义，不是已发生的实验记录。`measurement: true` 不设默认值；数值参数默认值只有本次明确确认后才可成为实际操作参数。每阶段入口都要求核对细胞来源；已有 RNA／cDNA 只关联来源，不自动补写之前的操作。

在实际实验项目中，将下列条目合并至现有 `method_templates`，不要覆盖其他配置。`path` 相对实际项目根目录填写；下例假设本文件放在项目的 `方法模板` 目录。此配置示例不是阶段定义，不会被读取器选中。

```yaml
method_templates:
  - name: cell-qpcr
    path: 方法模板/qPCR.md
    version: "1.0.0"
    format: staged
```

首次采用时用主技能的模板校验命令核对项目配置；本次交付没有初始化实际项目或写入该配置。嵌入块的 `version: 1` 是结构版本，frontmatter 的 `template_version` 是方法模板版本，两者含义不同。

```yaml experiment-workflow
version: 1
stages:
  - id: cells
    title: 细胞样品与实验设计
    entry: true
    pause_after: false
    requires: []
    input_types: [cells]
    outputs: []
    next: [rna]
    steps:
      - id: identity
        title: 核对细胞来源、分组与独立重复
        fields:
          - id: cell_origin
            label: 细胞系、物种及来源细胞编号；已有材料须列来源实验、阶段或可追溯依据
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: design
            label: 分组、处理条件、生物学重复ID及独立性依据；未知须明确说明
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: timing
            label: 实际处理开始与收样时间、培养孔位及状态
            type: string
            unit: null
            required: false
            measurement: false
            allow_unknown: []
      - id: assays
        title: 登记引物及分析映射
        fields:
          - id: assay_map
            label: 具体assay、F/R序列与工作液浓度、单孔体积、特异性及效率证据
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: analysis_map
            label: 可比较分析范围、固定内参、目标基因、校准关系及方法适用性依据
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
  - id: rna
    title: 贴壁细胞总RNA提取
    entry: true
    pause_after: false
    requires: []
    input_types: [cells]
    outputs: [rna]
    next: [rt]
    steps:
      - id: prepare
        title: 核对细胞量、试剂与方法
        fields:
          - id: cell_origin
            label: 细胞系、物种及来源细胞编号；已有材料须列来源实验、阶段或可追溯依据
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: kit
            label: 本次确认采用的试剂盒及版本
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
            default: GOONIE 400-100 241212
          - id: cell_state
            label: 本次实际细胞量、融合度、培养面积及方法选择依据
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: reagent_check
            label: 试剂批号、Wash Buffer乙醇添加及耗材设备核查
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
      - id: extract
        title: 实际完成裂解、上柱、洗柱与洗脱
        fields:
          - id: actual_record
            label: 实际PBS清洗、裂解、乙醇、上柱、洗柱、干燥、洗脱条件及偏离；未做步骤不得写为完成
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: lysis_volume
            label: 本次确认的常规裂解液体积；高密度方案另记
            type: number
            unit: uL
            required: true
            measurement: false
            allow_unknown: []
            default: 500
          - id: elution_volume
            label: 本次确认的单柱洗脱液加入体积
            type: number
            unit: uL
            required: true
            measurement: false
            allow_unknown: []
            default: 20
      - id: quantify
        title: 登记实际RNA产物与质控
        fields:
          - id: rna_id
            label: 实际RNA产物台账编号及来源细胞；不自动按日期造号
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: concentration
            label: RNA浓度
            type: number
            unit: ng/uL
            required: true
            measurement: true
            allow_unknown: [unmeasured, not_applicable]
          - id: recovered_volume
            label: 实际回收体积
            type: number
            unit: uL
            required: true
            measurement: true
            allow_unknown: [unmeasured, not_applicable]
          - id: quality
            label: A260/A280、A260/A230、完整性或实际测量方法、设备及时间
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: storage
            label: 实际保存温度、位置、日期及可追溯状态
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
  - id: rt
    title: 去gDNA与逆转录
    entry: true
    pause_after: false
    requires: []
    input_types: [rna]
    outputs: [cdna, nrt_control]
    next: [qpcr]
    steps:
      - id: inputs
        title: 核对细胞RNA来源与本次RT或-RT设计
        fields:
          - id: cell_origin
            label: 细胞系、物种及来源细胞编号；已有材料须列来源实验、阶段或可追溯依据
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: rna_source
            label: RNA台账编号、实际浓度及采用依据；继承材料不补写原提取操作
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: kit
            label: 本次确认采用的试剂盒版本
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
            default: AG11728 Version 6
          - id: method
            label: 本次确认的RT方法；两步法须另提供完整条件
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
            default: All in one
          - id: reaction_type
            label: 实际反应类型RT或-RT；-RT核对NRT Control Reaction Mix
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
      - id: reaction
        title: 核对配液计算并记录实际反应
        fields:
          - id: rna_mass
            label: 本次确认的RNA上样质量
            type: number
            unit: ng
            required: true
            measurement: false
            allow_unknown: []
            default: 1000
          - id: total_volume
            label: 本次确认的RT总体积
            type: number
            unit: uL
            required: true
            measurement: false
            allow_unknown: []
            default: 20
          - id: gdna_volume
            label: 本次确认的gDNA mix体积
            type: number
            unit: uL
            required: true
            measurement: false
            allow_unknown: []
            default: 2
          - id: rt_mix_volume
            label: 本次确认的RT或NRT mix体积
            type: number
            unit: uL
            required: true
            measurement: false
            allow_unknown: []
            default: 4
          - id: actual_record
            label: 实际RNA与水体积、反应液组成、加样顺序、完整温控程序及异常；补水负值不得放行
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
      - id: products
        title: 登记cDNA或-RT产物及稀释
        fields:
          - id: product_id
            label: 实际cDNA或-RT台账编号、类型及对应RNA来源
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: actual_volume
            label: 实际反应液回收体积
            type: number
            unit: uL
            required: true
            measurement: true
            allow_unknown: [unmeasured, not_applicable]
          - id: dilution
            label: 实际稀释倍数、原始RNA质量与RT体积来源；未知不补算当量
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: storage
            label: 实际保存温度、位置、日期及冻融情况
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
  - id: qpcr
    title: 细胞来源cDNA的qPCR检测
    entry: true
    pause_after: false
    requires: []
    input_types: [cdna, nrt_control]
    outputs: []
    next: [results]
    steps:
      - id: prepare
        title: 核对模板、仪器、引物与阴性对照
        fields:
          - id: cell_origin
            label: 细胞系、物种及来源细胞编号；已有材料须列来源实验、阶段或可追溯依据
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: template_map
            label: cDNA或-RT产物、来源实验、生物学重复与分组映射
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: instrument
            label: 实际仪器、板号、ROX需求及工作液、反应通道和核对依据
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: assays_controls
            label: 实际assay、引物浓度和用量、NTC及-RT布局与来源
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: total_volume
            label: 本次确认的单孔qPCR总体积
            type: number
            unit: uL
            required: true
            measurement: false
            allow_unknown: []
            default: 10
      - id: mixes
        title: 核对并实际完成三级mix配液
        fields:
          - id: mix1_factor
            label: 本次确认的mix1余量系数
            type: number
            unit: null
            required: true
            measurement: false
            allow_unknown: []
            default: 1.3
          - id: mix2_factor
            label: 本次确认的mix2余量系数
            type: number
            unit: null
            required: true
            measurement: false
            allow_unknown: []
            default: 1.15
          - id: mix3_factor
            label: 本次确认的mix3余量系数
            type: number
            unit: null
            required: true
            measurement: false
            allow_unknown: []
            default: 1.1
          - id: actual_record
            label: 实际组成组、配液块及assay孔数清单；逐项体积、稀释、原液等效体积、供液和ID核对；实际配制与消耗另记
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
      - id: run
        title: 记录实际板位、分装与运行
        fields:
          - id: well_map
            label: 逐孔实际映射、技术孔号、对照类型；孔数与配液计划逐项一致
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: actual_record
            label: 实际加样、封板、离心、仪器程序、采集设置、运行日期与异常
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: raw_files
            label: 真实原始运行文件、板位文件、未筛选Cq和曲线链接
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
  - id: results
    title: 细胞qPCR质控与结果整理
    entry: true
    pause_after: false
    requires: []
    input_types: [cdna, nrt_control]
    outputs: []
    next: []
    steps:
      - id: evidence
        title: 核对原始数据与样本映射
        fields:
          - id: cell_origin
            label: 细胞系、物种及来源细胞编号；已有材料须列来源实验、阶段或可追溯依据
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: raw_evidence
            label: 真实文件、板号、原始行及映射；保留Cq原值、Excluded、未检出和重复导出依据
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: design
            label: 实际可比较范围、固定内参、校准组和独立生物学重复声明
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
      - id: quality
        title: 记录质控、缺失与排除依据
        fields:
          - id: qc_result
            label: 实际有效孔数、差值等级、最大差值位置、曲线、NTC/-RT、效率和全部异常；未做分析不能声称合格
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: exclusions
            label: 所有排除及缺失清单；无排除也须有实际核查依据
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
      - id: organize
        title: 按明确请求整理分析产物与结论
        fields:
          - id: analysis_provenance
            label: 实际调用技能或工具、版本/哈希、参数、输入输出及验证范围；缺工具明确记录
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: results
            label: 本次用户明确提交的结果、证据链接、回填位置及适用限制；不从模板生成结果
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
          - id: inventory_review
            label: 本轮已展示的真实库存清单及确认范围；无变化须列核查依据
            type: string
            unit: null
            required: true
            measurement: false
            allow_unknown: []
```

</details>
