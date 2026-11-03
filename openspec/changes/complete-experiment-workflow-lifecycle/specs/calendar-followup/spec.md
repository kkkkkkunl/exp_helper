# Spec Delta

## Purpose

把实验暂停后的后续阶段和待补事项直接安排到用户选择的日历，通过首次安装接入、明确排期和稳定事项更新保持实验与计划可对应，并在连接或远端操作失败时保留可恢复的真实同步状态。

## ADDED Requirements

### Requirement: Calendar onboarding during first installation
首次安装或手动复制后的首次初始化 SHALL 询问用户选择日历服务及具体日历，复用已有连接或引导安装、连接对应插件或 MCP，并核查创建、读取、查找和更新能力。系统 SHALL 不固定绑定当前会话的日历服务，未连接不得报告成功。

#### Scenario: First installation has no calendar connection
- **WHEN** 用户首次初始化尚未选择或连接日历
- **THEN** 宿主会话询问选择并引导对应接入，项目保留待配置状态而不是自动绑定某服务

### Requirement: Save progress before requesting schedule
暂停 SHALL 先保存已执行事实；日期、开始时间或预计时长缺失时集中询问已有信息之外的排期信息，齐全后直接写入所选日历。系统 SHALL 使用明确时区，不自行编造日期。

#### Scenario: Pause without a planned date
- **WHEN** 用户暂停但未说明下一阶段何时开展
- **THEN** 实验进度已保存，系统只补问所缺排期，未创建随意日期的事项

### Requirement: One calendar item per follow-up stage
系统 SHALL 为每个后续阶段维护一条事项，描述包含剩余步骤、相关样品及实验记录位置；缺数据关联对应阶段，系统 SHALL 不另建用户维护的实验待办.md。

#### Scenario: Several steps remain in one stage
- **WHEN** 同一后续阶段仍有多个步骤未做
- **THEN** 步骤集中列在该阶段事项中，不为每个步骤重复创建事件

### Requirement: Stable updates and preserved manual scheduling
相同待办再次暂停、重试或恢复 SHALL 更新原事项，继续后更新剩余内容；实际工作全部完成后 SHALL 增加完成标识并保留事项。用户手工调整的排期 SHALL 保留，日历计划变动不得被当作实际实验执行。

#### Scenario: Update a manually rescheduled event
- **WHEN** 用户手工改过日历时间后再次更新实验进度
- **THEN** 系统更新实验内容并沿用用户排期，不恢复为原计划时间

### Requirement: Recover uncertain remote writes without duplication
远端创建或更新失败 SHALL 如实报告并保留待同步映射；超时后无法确定是否已创建时 SHALL 先查询对应事项再决定重试，不盲目重复创建。连接不足 SHALL 不阻塞独立实验进度保存，也不声称事项已同步。

#### Scenario: Create request times out after remote success
- **WHEN** 服务已创建事项但确认响应丢失
- **THEN** 后续恢复先识别原事项并保存映射，不再创建第二条相同待办

### Requirement: Use host-managed calendar access
日历接入 SHALL 使用用户选定的宿主插件或 MCP 能力，认证由相应连接管理；项目不得保存其认证凭据。同步 SHALL 在会话或明确工作流动作中执行，不将离线状态描述为后台自动监听。

#### Scenario: Host capability is unavailable
- **WHEN** 项目移到没有对应日历能力的宿主
- **THEN** 系统说明需要连接并保留待同步任务，不因配置中仍有日历名称就报告远端写入成功

