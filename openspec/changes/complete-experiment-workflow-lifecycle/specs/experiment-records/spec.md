# Spec Delta

## Purpose

为一次实际实验提供稳定身份、事实记录和原始材料追溯，支持多轮输入与人工修改保护，并确保交互收集、明确保存和附件移动具有可辨别的授权边界及可恢复的证据来源。

## ADDED Requirements

### Requirement: Stable experiment identity and input provenance
系统 SHALL 为新实验分配固定编号，实际实验日期单独记录；同一实验补录、暂停续接沿用原编号。相同请求重放 SHALL 不重复创建，内容改变 SHALL 不复用原请求身份。

#### Scenario: Resume a saved experiment
- **WHEN** 用户跨会话继续一个已保存实验
- **THEN** 系统读取该实验状态，沿用编号并保留新输入的独立来源

#### Scenario: Reuse one request identifier for different text
- **WHEN** 已登记请求标识对应的内容被替换
- **THEN** 系统拒绝将其当作同一次输入重放

### Requirement: Fact-based interactive record collection
系统 SHALL 按模板步骤集中提示待填信息，接受自由文本和多步骤输入，只追问缺失或冲突信息。目的、实际方法、结果和附件 SHALL 可追溯，未知数值不得填零或编造，前序继承操作不得冒充本次实际操作。

#### Scenario: User supplies several steps at once
- **WHEN** 一次输入已包含多个步骤及部分用量
- **THEN** 系统整理已有事实，仅询问仍缺少或矛盾的内容

### Requirement: Consistent record presentation
实验记录 SHALL 保留编号、实际日期、目的、实验方案、结果与附件；实验方案包含参考方案来源及实际方法，正文只写实际执行。材料 SHALL 按实验目录组织，实验列表按实际日期而非创建编号排序；阶段流程不得破坏既有正文结构。

#### Scenario: Enter an older experiment retrospectively
- **WHEN** 用户补录早于当前日期的实验
- **THEN** 记录保留新的固定编号和真实发生日期，列表按实际日期排列，不把创建日期冒充实际日期

### Requirement: Explicit persistence boundaries
系统 SHALL 将普通数值回答保留为会话草稿；明确阶段确认、暂停或最终结果指令才授权对应实验记录及恢复状态的写入。未保存草稿 SHALL 不被报告为可跨会话恢复的进度。

#### Scenario: Provide a number without confirming
- **WHEN** 用户只回答一个样品量，尚未发出保存相关指令
- **THEN** 系统更新会话整理内容，不因此创建原始输入文件、库存事件或正式记录

#### Scenario: Pause with incomplete data
- **WHEN** 用户明确输入暂停且仍有数据待补
- **THEN** 系统保存已确认事实与待补进度，正式记录不含伪造数值或 TODO 占位符

### Requirement: Preserve manual content and correction evidence
系统 SHALL 保留正文、自定义属性和原始输入。检测到人工修改时 SHALL 展示合并内容并按当前版本获得授权；事实更正 SHALL 保留更正前后及依据，不抹去真实已发生操作。

#### Scenario: Merge a manually edited record
- **WHEN** 目标记录与上次生成内容不同
- **THEN** 未获得针对当前内容的合并确认前不覆盖正文

### Requirement: Safe and traceable original attachments
系统 SHALL 保持原始附件内容与文件名，在复制校验成功后才删除源；同名异内容及异名同内容 SHALL 返回待处理信息，保留源且不自动覆盖、改名或合并，并继续独立项目。

#### Scenario: Attachment name collision
- **WHEN** 归档目标已有同名但不同内容的文件
- **THEN** 系统保留两端文件并报告冲突，不自动覆盖目标

