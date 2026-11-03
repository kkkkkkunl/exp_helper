# Spec Delta

## Purpose

为不同类型实验提供可复用的阶段模板和交互执行规范，使用户能按已有方案从适当入口开始、暂停后继续及分样品推进，同时区分本次记录收尾、实际步骤执行和模板整体完成状态。

## ADDED Requirements

### Requirement: Stage template authoring contract
阶段模板 SHALL 声明稳定的阶段与步骤标识、顺序或允许分支、入口、暂停点、继续条件、输入与产物及字段规范。字段 SHALL 说明含义、数据类型、单位要求、必填性和允许的未知类别；系统 SHALL 拒绝不完整或引用无效的阶段结构，并允许旧普通模板继续使用。

#### Scenario: Template refers to a missing next stage
- **WHEN** 新模板的后继或入口指向不存在的阶段
- **THEN** 系统报告具体结构错误，不按该错误路径提示操作

### Requirement: Confirm template parameters and preserve actual measurements
模板预设值 SHALL 先作为参考展示，实际操作参数须由用户提供或明确确认所列值；用户 SHALL 能集中确认本阶段所列参数。实测结果 SHALL 有用户提供的实际来源。该规则 SHALL 同样适用于旧普通模板。

#### Scenario: Confirm listed operating parameters
- **WHEN** 用户明确确认本阶段按已展示参数执行
- **THEN** 对应参数得到确认，但没有提供的测量结果仍保持未知

### Requirement: Freeze and explicitly migrate template content
实验开始保存时 SHALL 固定模板版本及内容，跨会话继续不自动采用更新模板。升级 SHALL 展示阶段及字段映射和影响，经明确确认后执行，并保留原版本来源。

#### Scenario: Template file changes after pause
- **WHEN** 原模板文件更新后继续已有实验
- **THEN** 实验继续使用已固定内容，不因文件路径相同而切换版本

### Requirement: Per-sample progress and inherited entry
系统 SHALL 按具体样品维护阶段与步骤进度，允许集中填写同一步骤。新实验从中间入口使用既有样品时 SHALL 关联来源，前序内容标明承接而非本次已执行，并核对模板继续条件。

#### Scenario: Only one sample proceeds
- **WHEN** A 和 B 完成同一步骤后仅 A 继续
- **THEN** B 的实际进度保持原样，系统不将其后续步骤标为已执行

### Requirement: Pause closes only the executed portion
明确暂停 SHALL 保存已执行部分并视为本次阶段完成；未执行步骤 SHALL 保持未执行并进入日历待办，缺数据另列待补。意外中断或会话停止 SHALL 不自动证明已满足模板继续条件。

#### Scenario: Pause after two of three steps
- **WHEN** 三步阶段仅前两步已做并输入暂停
- **THEN** 已做部分完成收尾，第三步仍未执行并保留待办，阶段收尾不自动完成对应剩余日历事项

### Requirement: Explicit branches and real retry attempts
用户 SHALL 能选择模板允许的分支；超出模板的调整须先展示确认，实际偏离如实记录。同一实验真实阶段重做 SHALL 新增尝试并保留原尝试及消耗，仅改变涉及样品；完整重复实验使用新编号。

#### Scenario: Retry one failed sample
- **WHEN** 仅 A 样品阶段失败后真实重做
- **THEN** 系统为 A 保留新的尝试和实际消耗，B 的进度不变，原失败尝试保留

