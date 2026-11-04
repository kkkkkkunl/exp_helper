# Spec Delta

## Purpose

使实验级技能在实验确定后按步骤提供计算，已有结果整理、专业分析和科研汇报各自按请求执行，并通过技能依据、稳定结果项及版本保持追溯，避免将计算用量、文件生成、实验结束或归档误作实际操作及分析完成。

## ADDED Requirements

### Requirement: Separate organization from requested analysis
系统 SHALL 区分实验准备计算、整理已有结果与执行结果分析。实验确定后 SHALL 加载对应实验级技能，相关步骤输入齐全时执行其规定计算，无需另发计算指令；技能启动或上样计算 SHALL 不自动触发全部结果分析。独立的结果分析、统计或绘图仍 SHALL 按明确请求或已确认实验方案中的明确任务执行，不因原始附件或最终结果整理指令自行增加统计。分析缺失或受阻 SHALL 如实记录，不编造结果，也不阻塞独立的记录与已有结果整理。

#### Scenario: Organize provided results without analysis
- **WHEN** 用户提交已有结果且未请求新的数据分析
- **THEN** 系统整理提供的内容，不附加新的统计方法、测量值或科学结论

#### Scenario: Prepare loading without a new calculation request
- **WHEN** 已确定实验进入上样步骤，skill 所需输入和参数均已明确
- **THEN** 系统按该 skill 计算并展示上样量，不要求用户再说一次计算，也不自动执行尚未请求的统计分析

### Requirement: Skill-owned loading calculations and bounded failures
计算公式、单位约束及适用条件 SHALL 来自选定 skill，输入采用本次方案来源或用户提供、明确确认的参数，实测信息 SHALL 不由默认值生成。系统 SHALL 只集中收集当前步骤缺项；未知值不填零。缺参、单位不兼容、负补液量或违反已提供约束时 SHALL 明确原因，不将异常值作为可执行上样方案，只暂停相关样品或步骤。

#### Scenario: One sample lacks a required concentration
- **WHEN** 多个样品中只有一个缺少当前步骤必须的浓度
- **THEN** 系统列出该样品缺项，不猜测其上样量，其他输入齐全且无依赖的样品仍可计算

#### Scenario: The inputs produce a negative water volume
- **WHEN** skill 校验发现输入导致负补液量或单位条件不满足
- **THEN** 系统展示异常及依据，暂停受影响计算，不将数值默认为零或当作可执行方案

### Requirement: Freeze skill evidence and review targeted recalculations
首次保存时系统 SHALL 固定实际使用的技能版本或可恢复的内容依据及计算参数，同一实验跨会话续接 SHALL 沿用该依据，不因技能安装更新静默替换。升级 SHALL 先展示差异及受影响计算，经明确确认后重算相关部分并保留原依据；未保存计算随输入更新，已保存更正 SHALL 留存历史，只标记依赖变化的下游待复核，不倒改实际操作或重置无关任务。

#### Scenario: Continue after the installed skill is updated
- **WHEN** 已保存实验暂停后技能安装内容发生变化，再次继续同一实验
- **THEN** 系统沿用原已固定依据；原内容不能恢复时报告依赖问题，不把新版本冒充原版本

#### Scenario: Upgrade the skill explicitly
- **WHEN** 用户确认已展示的技能升级差异及计算影响
- **THEN** 系统保留旧依据并重算受影响部分，已发生实际用量、无关任务及独立结果完成时间不被覆盖

### Requirement: Versioned results and user selection
系统 SHALL 为结果项维护稳定身份、参数和文件证据；数据或分析参数变化形成新版本，相同参数与文件不重复建版本。新版本默认未精选，旧版本及其标记保留，精选仅表示用户选择。

#### Scenario: Add the same result twice
- **WHEN** 相同结果项再次提交相同参数和文件
- **THEN** 不创建重复版本且保留既有精选状态

### Requirement: Named analysis dispatch and execution evidence
系统 SHALL 按已配置条件解析目标技能，多个候选时要求选择，缺失时报告。分析完成 SHALL 记录所用技能及版本、输入、输出和参数证据，不把可定位技能等同于分析已经执行成功。

#### Scenario: Several skills match
- **WHEN** 用户请求的分析匹配多个技能
- **THEN** 系统展示候选并等待选择，不自行执行其中一个

### Requirement: Verifiable organization and targeted invalidation
系统 SHALL 以本次明确结果范围的实际回填与来源关联判定整理完成，支持文字、数值、表格及文件结果。仅日期等无关更正不撤销完成；相关输入、参数或证据变化只使对应分析和整理任务待复核，无法定位时要求明确范围。

#### Scenario: Text-only final result
- **WHEN** 用户明确提交不带附件的文字结果
- **THEN** 系统可根据输入来源与记录中的实际回填核验整理完成，不强制编造一个结果文件

#### Scenario: Change one result source
- **WHEN** 多个结果任务中仅一个的证据被更改
- **THEN** 仅相应任务及明确关联任务失效，其他已完成任务及时间保留

### Requirement: Source-faithful editable reporting
用户明确要求汇报时，系统 SHALL 按既有科研汇报规则输出可编辑 PPT，内容来自记录与选定结果；精选汇报仅使用用户选中的版本。科研原图 SHALL 原样呈现，结论及后续计划只采用用户提供内容，不新增统计分析。

#### Scenario: No user-provided conclusion
- **WHEN** 用户请求汇报但未提供结论或后续计划
- **THEN** 系统省略该部分，不生成填空式结论，图片及数值保持来源一致

