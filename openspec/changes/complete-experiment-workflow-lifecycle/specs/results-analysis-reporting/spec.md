# Spec Delta

## Purpose

让已有结果整理、专业分析和科研汇报各自按请求执行，并通过稳定结果项、版本和证据来源保持可追溯性，避免将生成文件、精选标记、实验结束或归档错误解释为科学结论或分析完成。

## ADDED Requirements

### Requirement: Separate organization from requested analysis
系统 SHALL 区分整理已有结果与执行分析，仅在明确要求分析、计算或绘图时加载目标分析技能。分析缺失或受阻 SHALL 如实记录，不编造结果，也不阻塞独立的记录与已有结果整理。

#### Scenario: Organize provided results without analysis
- **WHEN** 用户提交已有结果且未请求新的数据分析
- **THEN** 系统整理提供的内容，不附加新的统计方法、测量值或科学结论

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

