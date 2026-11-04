# Spec Delta

## Purpose

分别表达阶段收尾、实验执行结束、结果整理、分析与材料归档，并让明确最终结果指令形成可追溯的自动归档流程，同时保留已有独立归档能力及用户对实验重要性的选择。

## ADDED Requirements

### Requirement: Independent lifecycle meanings
系统 SHALL 分别维护步骤实际状态、本次阶段收尾、执行结束、分析、结果整理和归档。记录的 completed 与 completed_at SHALL 仅表示本次请求的结果整理；暂停、归档或实验结束不得伪造其他完成状态。

#### Scenario: Pause a process-only experiment
- **WHEN** 用户暂停纯过程记录且尚无结果整理请求
- **THEN** 本次已执行部分收尾完成，结果整理属性仍为 false/null，后续步骤保留待办

#### Scenario: Save a preparation calculation
- **WHEN** 用户确认保存上样计算，但没有提交最终结果或完成结果整理
- **THEN** 系统不因计算有数值或技能已加载而将结果整理标完、结束实验或自动归档

### Requirement: Explicit final-result intent and observable completion
只有明确提交本次最终结果 SHALL 触发自动整理与结束流程；普通结果讨论、初步结果、单独上传附件或仅提及关键词不得触发。必要内容回填并建立来源关联后 SHALL 标记该范围整理完成并视为实验结束。

#### Scenario: Mention results without finishing
- **WHEN** 用户说明“实验结果还没出来”或提交初步数据
- **THEN** 系统不因出现关键词而结束实验或自动归档

#### Scenario: Final results still lack required content
- **WHEN** 最终结果请求已明确但仍有必要内容缺失
- **THEN** 系统保留收集进度，不提前标记整理完成或实验结束

### Requirement: Automatic archive with retained authorization
最终结果整理完成后系统 SHALL 自动检查归档；需有效的当前记录、已完成本轮库存核查及可追溯证据。条件不足时 SHALL 保留已达到的结束和整理状态并列明归档待处理，在后续授权工作流动作补齐后沿用原最终结果请求继续归档，不要求重复指令。

#### Scenario: Inventory confirmation is pending
- **WHEN** 结果整理完成但当前库存清单尚待确认
- **THEN** 系统不绕过库存授权，也不撤销已完成整理；清单确认并满足检查后自动完成本次归档

### Requirement: Preserve independent archive and outstanding work
用户明确请求保存当前材料时系统 SHALL 保留独立归档能力，不以全部分析、结果整理或日历待办完成为前提，仍执行记录、库存和证据检查。归档 SHALL 保存待处理事项，不代表科学审核或实验成功；变化后的材料须重新核查。

#### Scenario: Archive before analysis finishes
- **WHEN** 当前材料有效且库存核查完成，用户明确请求归档但分析仍待处理
- **THEN** 系统归档已有材料并保留待分析状态，不强行标记分析或结果已完成

### Requirement: Include associated project history in experiment archives
实验归档 SHALL 包含项目根 history 中归属该实验的历史记录及可核对证据，保留原位置并维护附件追溯；目录位于实验目录之外 SHALL 不成为漏归档理由。系统 SHALL 不混入其他实验历史，也不将 OpenSpec 的 hisotry 变更历史视为实验材料。历史证据改变 SHALL 使相关归档待复核，不影响无关实验或凭此撤销无关分析结果。

#### Scenario: Archive one experiment with shared history storage
- **WHEN** 项目根 history 同时包含多个实验的历史，本次仅归档其中一个实验
- **THEN** 归档清单关联该实验的历史及证据，不遗漏它们，也不纳入其他实验或 OpenSpec 历史

#### Scenario: Associated history evidence is changed
- **WHEN** 已归档实验关联的历史文件缺失或内容被外部改动
- **THEN** 系统报告该归档证据需要复核，不继续报告原证据完整有效，也不重置无关分析任务

### Requirement: Experiment importance independent of result selection
系统 SHALL 允许用户在结果输入、归档或后续修改时设置实验级 important，默认 false，不阻塞自动归档；该属性 SHALL 与结果版本的精选独立，并保留其他自定义属性。

#### Scenario: Important experiment with unselected results
- **WHEN** 用户将实验标为重要而未精选任何结果
- **THEN** important 为 true，结果版本的精选状态不改变

