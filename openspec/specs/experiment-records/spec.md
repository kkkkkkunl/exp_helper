# experiment-records Specification

## Purpose

为一次实际实验提供稳定身份、事实记录和原始材料追溯，支持多轮输入与人工修改保护，并确保交互收集、明确保存和附件移动具有可辨别的授权边界及可恢复的证据来源。

## Requirements

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

### Requirement: Question UI for blocking gaps and conflicts
系统 SHALL 对当前步骤阻断性的缺失值和互相冲突的信息优先使用宿主问答框集中核对；可核对的候选值 SHALL 供选择，无法可靠预列的实验数据 SHALL 使用开放输入，不得猜测。系统 SHALL 接受用户自由文本，不重复询问已提供的信息；有依赖的问题按先决条件分轮提出。问答框不可用时 SHALL 以集中、编号的文本问题保留相同核对边界，未解决冲突不得写成既定事实。非阻断性的空白不因本要求变为保存门槛。

#### Scenario: Resolve a missing measurement and a conflict
- **WHEN** 当前步骤缺少不能可靠推定的浓度，且两条输入给出不同孔数
- **THEN** 系统用问答框开放输入浓度并让用户选择或改写孔数；已有明确值不重问，冲突解决前不保存任一孔数为事实

#### Scenario: Question UI is unavailable
- **WHEN** 宿主不能显示问答框而当前步骤仍有阻断性缺项
- **THEN** 系统集中列出编号问题并等待自由文本，不自动补值或跳过冲突

### Requirement: Consistent record presentation
实验记录 SHALL 保留编号、实际日期、目的、实验方案、结果与附件；实验方案包含参考方案来源及实际方法，实际方法只写实际执行。已确认保存的操作前计算 SHALL 在独立标明的计算内容中呈现，不得冒充已执行方法或实测结果。当前材料 SHALL 按实验目录组织，历史版本按项目级 history 规则关联；实验列表按实际日期而非创建编号排序，阶段流程不得破坏既有正文结构。

#### Scenario: Enter an older experiment retrospectively
- **WHEN** 用户补录早于当前日期的实验
- **THEN** 记录保留新的固定编号和真实发生日期，列表按实际日期排列，不把创建日期冒充实际日期

### Requirement: Canonical structure for new formal records
新正式实验记录 SHALL 以 `assets/experiment-record.template.md` 为结构来源，保留元信息、基本信息表及必需顶层章节和“参考方案／实验方法”子章节的名称、层级与顺序；保存前 SHALL 校验这些结构。系统 MAY 在对应章节下增加有事实依据的小节，`## 上样计算` MAY 置于“实验方案”之后、“结果”之前。各章节内容 MAY 为空，不得把模板占位符、说明文字或未知值当作实验事实。旧格式记录 SHALL 在普通编辑中保留原排版，仅在用户明确要求迁移时预览转换并按历史规则保存旧版。

#### Scenario: Save a new record with empty sections
- **WHEN** 新实验已有确认操作，但目的、结果或附件尚未填写
- **THEN** 正式记录具有模板规定的结构，空章节保留为空，不插入占位符或虚构数据

#### Scenario: Reject a malformed new record
- **WHEN** 新记录缺失必需章节，或章节标题层级与顺序不符合模板
- **THEN** 保存被拒绝并指出具体结构错误

#### Scenario: Edit an older record without migration
- **WHEN** 用户补充一份旧格式记录且未要求结构迁移
- **THEN** 系统保留其原排版并应用既有语义与人工修改保护，不自动重排全文

### Requirement: Concise displayed values with internal provenance
正式记录中的单项实际值 SHALL 仅呈现已提供或确认的值及必要单位，不附带从消息读取、取值推断或系统时间读取过程的逐值说明。原话、确认、时间读取及估计依据 SHALL 保留在内部可核查状态；样本链接、来源实验与阶段、模板名称及版本、上样计算输入与依据等用于辨认材料和复核方法的结构化关联 SHALL 继续保留。对“刚刚完成”等相对时间，系统 SHALL 以本次会话可获得的北京时间提出候选并要求用户确认或修改；正式记录中的确认时间 SHALL 统一写成 `HH:mm`，不显示“约”。

#### Scenario: Record a recently completed plating step
- **WHEN** 用户说“刚刚完成铺板”，系统提出北京时间候选 `14:55`，用户确认该时刻
- **THEN** 正文写“铺板完成时间｜14:55”，不附加取值说明；内部状态保留该候选及确认依据

#### Scenario: Preserve a necessary source link
- **WHEN** 记录中的一个 RNA 样本继承自此前实验
- **THEN** 正文保留样本及来源实验的链接，同时实际数值后不拼接用户消息或系统读取过程

### Requirement: Explicit persistence boundaries
系统 SHALL 将普通数值回答及会话内计算保留为会话草稿；明确阶段确认、暂停或最终结果指令才授权对应实验记录及恢复状态的写入。阶段确认或暂停保存 SHALL 覆盖已展示的计算输入、单位、依据和结果，包含尚未实际执行的拟用量；保存计算不得改变步骤实际执行状态。未保存草稿 SHALL 不被报告为可跨会话恢复的进度。

#### Scenario: Provide a number without confirming
- **WHEN** 用户只回答一个样品量，尚未发出保存相关指令
- **THEN** 系统更新会话整理内容，不因此创建原始输入文件、库存事件或正式记录

#### Scenario: Pause with incomplete data
- **WHEN** 用户明确输入暂停且仍有数据待补
- **THEN** 系统保存已确认事实与待补进度，正式记录不含伪造数值或 TODO 占位符

### Requirement: Distinguish calculated loading from actual use
系统 SHALL 在会话即时展示 skill 生成的计算上样量，并明确区分用户输入、计算来源、计算用量与用户报告或明确确认的实际使用量。已授权保存的计算 SHALL 保留输入、单位、skill 依据和结果及所属样品与步骤，实际量可与计算量不同；系统 SHALL 不因用户确认计算内容就推定操作已经发生。

#### Scenario: Save a loading calculation before execution
- **WHEN** skill 已计算上样量，用户确认阶段记录，但对应上样操作尚未执行
- **THEN** 记录保存计算依据及拟用量，步骤仍为未执行，没有虚构实测或实际用量

#### Scenario: Actual use differs from the calculation
- **WHEN** 用户报告实际上样量与此前计算量不同
- **THEN** 系统分别保留计算量及实际量，并以实际操作信息作为后续库存核查依据

### Requirement: Project-level timestamped record history
系统 SHALL 在实验项目根 history 目录保存修改前的完整实验记录，文件名为 `<实验编号>_<YYYYMMDD-HHMMSS-ffffff>.md`，时间为本次确认保存修改的北京时间。已有记录正文或受管属性在获授权保存中发生实际变化时 SHALL 先留存旧版再更新当前记录，保留修改依据及实验关联；首次保存、未保存会话重算、内容不变和同一动作重试 SHALL 不新增历史。历史附件引用 SHALL 仍可定位原附件，原始附件不为每个历史重复复制，既有内部历史 SHALL 保留且不伪造原修改时间。

#### Scenario: Correct a saved calculation
- **WHEN** 用户确认修改已保存计算的输入，并保存新的计算结果
- **THEN** history 出现以实验编号和本次修改时刻命名的完整旧记录，当前记录展示新值，旧计算依据与实际操作仍可追溯

#### Scenario: Change only a managed property
- **WHEN** 用户明确修改已有实验的重要性且正文操作信息不变
- **THEN** 系统仍为实际发生变化的旧记录属性保留完整历史，不因只改属性而遗漏

#### Scenario: Save for the first time or replay without a change
- **WHEN** 首次保存、仅在会话内重算，或相同内容和相同保存动作被重放
- **THEN** 系统不生成无旧版依据或重复的历史文件

#### Scenario: Resume an interrupted replacement
- **WHEN** 已确定历史文件名的保存动作中断后恢复
- **THEN** 恢复复用原历史身份，旧记录已留存才替换当前记录，不另按恢复时间生成历史，也不覆盖其他修改的历史

#### Scenario: Follow an attachment link in an old record
- **WHEN** 用户从项目根 history 中打开某次修改前的记录
- **THEN** 历史中的附件引用仍定位到原实验材料，内容与归属可核对，不依赖复制全部附件

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

### Requirement: Omit absent information and nonessential negative operations
系统 SHALL 在正式正文中默认省略未提供的信息，不补值或自动追加“未记录”“未提供”等缺项说明；明确报告的未执行操作 SHALL 默认省略，仅在有依据的关键方法差异或用户明确要求时保留。未提及某操作 SHALL 不被解释为未执行。必要缺项 SHALL 仅在影响当前操作、计算或必要记录完整性时集中核对。

#### Scenario: Concise medium replacement record
- **WHEN** 用户提供“三组去除处理液并更换培养基；未清洗、未裂解；体积未记录”，未说明关键方法差异且未要求保留否定操作
- **THEN** 正文只记录三组去除处理液并更换培养基，不补体积，不追加否定操作或缺项说明

#### Scenario: Retain an explicit exception
- **WHEN** 用户明确要求保留“未清洗”，或已确定方案及用户说明表明它是关键方法差异
- **THEN** 正文保留该有依据的否定事实，不因默认省略规则删除

### Requirement: Presentation omission preserves provenance and state
正文省略 SHALL 不删除授权保存范围内的原始输入、已有追溯依据、真实步骤状态、必要分析质控信息或明确声明的未测定、不适用状态。系统 SHALL 不把未提及状态改为未执行，不把未执行步骤改为已完成，也不为保存追溯依据绕过原有保存授权。

#### Scenario: Save concise text with original evidence
- **WHEN** 用户确认保存精简正文，而原始输入明确说明未裂解及体积未知
- **THEN** 原始输入可恢复，对应已声明的步骤保持未执行，体积仍未知；正文省略不导致反向补值或完成步骤

#### Scenario: A missing value blocks a calculation
- **WHEN** 后续计算必须使用尚未提供的体积
- **THEN** 系统在交互中核对该值并暂停相关计算，不因正文省略而伪造结果；必要质控信息仍在相应分析范围呈现
