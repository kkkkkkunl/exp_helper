# project-foundation Specification

## Purpose

为实验工作流提供可迁移的项目安装、配置、技能库和按需入口，使记录、库存、分析及汇报能够在明确的项目范围内独立使用，并保留既有目录与用户主动管理版本历史的约定。

## Requirements

### Requirement: Non-overwriting project initialization
系统 SHALL 在用户明确指定项目后安装主技能、补齐缺失配置及项目内分析技能库，保留已有配置，并拒绝未经授权覆盖已有主技能。手动复制后 SHALL 支持只初始化模式。

#### Scenario: Initialize an existing project
- **WHEN** 项目已有配置并请求只初始化
- **THEN** 已有配置和主技能保持原内容，缺失目录与索引得到补齐

### Requirement: Project-owned named skill resolution
系统 SHALL 使用项目内相对路径维护实验级技能及独立分析技能索引，按名称只解析目标条目并验证其文件哈希，兼容已有分析技能名称和路径；缺失、重名或过期 SHALL 明确返回，不自动下载或覆盖。

#### Scenario: Move a project and resolve one skill
- **WHEN** 项目搬迁后按名称请求已有分析技能
- **THEN** 系统通过相对路径定位该技能，不读取其他技能正文

#### Scenario: Stale skill content
- **WHEN** 目标技能内容与索引哈希不同
- **THEN** 系统报告需要维护索引，不把目标视为已经可用

### Requirement: Progressive routing and scoped validation
系统 SHALL 按用户意图和已确定实验加载相关说明，并仅校验当前任务范围；仅提供过程或原始数据 SHALL 不自动执行结果分析。实验确定后加载技能与执行其全部功能 SHALL 分开。每次明确保存记录后 SHALL 核查本轮库存，无变化时记录依据。

#### Scenario: Record without analysis dependencies
- **WHEN** 用户只记录过程且分析技能缺失
- **THEN** 系统仍能完成记录与相关库存核查，不因无关分析依赖阻塞

### Requirement: Discoverable exp entry delegates to the main workflow skill
系统 SHALL 提供名为 `exp` 的薄入口，保留名为 `experiment-workflow` 的完整主技能及其路由职责。入口 SHALL 读取同级主技能并传递用户意图，后续相对引用以主技能目录为基准，不复制主规则。入口识别 SHALL 不构成保存、库存或日历授权，子技能仍按既有实验确定条件加载。

#### Scenario: Enter through exp
- **WHEN** 用户选中并调用 `$exp`，同级主技能完整可读
- **THEN** 入口读取主技能并传递本次上下文，按需路由，不因入口调用创建实验或保存记录

#### Scenario: Direct main skill invocation remains available
- **WHEN** 用户明确调用 `$experiment-workflow`
- **THEN** 系统沿用主工作流及既有子技能激活规则，不要求绕经 exp

#### Scenario: Main skill dependency is missing
- **WHEN** exp 存在而同级主技能缺失或不可读
- **THEN** 系统报告安装不完整及缺失目标，不假报进入成功，不自动下载或执行替代工作流

### Requirement: Paired host discovery deployment with conflict protection
系统 SHALL 向明确指定项目的 `.agents/skills/` 共同部署同级 exp 与完整主技能，保留全部脚本、参考及资源；个人全局 `.agents/skills/` 部署 SHALL 仅按用户明确选择执行。实验项目内部技能库及索引 SHALL 与宿主发现目录区分，既有初始化与内部索引兼容性 SHALL 保留。安装前 SHALL 检查来源与双目标，未获明确更新授权时任一同名冲突 SHALL 在写入前拒绝部署，不覆盖或留下单边新部署；中断 SHALL 报告实际状态，不假报成功。

#### Scenario: Deploy to a specified project
- **WHEN** 用户明确安装到指定项目，来源完整且双目标均不存在
- **THEN** 两技能共同放入项目 `.agents/skills/`，不写个人全局目录，不修改既有实验配置、记录、库存或日历

#### Scenario: Either destination already exists
- **WHEN** 任一同名目标已存在且未获明确更新授权
- **THEN** 安装在写入前报告冲突，保留已有内容，不新增另一半部署

#### Scenario: Only an internal skill library is populated
- **WHEN** 主技能仅存在于实验项目内部 skills 目录或索引
- **THEN** 系统不据此宣称宿主已发现入口，明确仍需宿主发现目录部署

### Requirement: Evidence-based host selector acceptance
系统 SHALL 分别记录文件检查、真实宿主候选发现及真实调用转交的结果。真实候选验收 SHALL 验证输入 `$exp` 后可识别并选中本入口，不要求改变排序或自动填入。无法访问真实宿主 SHALL 标明未验证，不以静态或模拟检查冒充联想成功。

#### Scenario: Select the workflow in the real composer
- **WHEN** 完成共同部署及宿主重新发现，在目标项目输入 `$exp`
- **THEN** 候选中可识别并选中本入口，随后读取主技能并按需路由；存在其他匹配候选不影响判定

#### Scenario: Only static checks are available
- **WHEN** 已检查文件结构但无法操作真实输入框
- **THEN** 仅报告静态结果，真实候选及调用验收保留未验证，不将本轮整体任务标完

### Requirement: Activate the experiment skill when the experiment is determined
用户已通过主技能明确进入工作流（包括已被会话识别的入口简写），且明确开始或继续某次实验、实验类型及模板或方案已明确后，系统 SHALL 立即定位并加载对应实验级 skill，按当前步骤使用相关内容，不等待另发计算或结果分析请求。技能定位 SHALL 依次采用用户明确指定、所选模板明确绑定、实验类型匹配；未指定技能且存在多个候选或绑定冲突时 SHALL 展示差异并明确选择。缺失技能 SHALL 暂停依赖它的计算，保留独立记录，不自行替代或下载。

#### Scenario: Confirm an experiment before measurements are supplied
- **WHEN** 用户明确按已选方案开始某类实验，但尚未提供上样计算需要的浓度
- **THEN** 系统加载对应 skill，按当前步骤收集缺项，不等到结果阶段才启动，也不因此写入文件或分配编号

#### Scenario: Discuss possible experiments
- **WHEN** 用户仅比较备选实验，尚未确定开始或继续哪次实验
- **THEN** 系统不将讨论视为已确定实验，不自动激活某个实验技能

#### Scenario: Explicit skill selection takes precedence
- **WHEN** 用户明确指定适用 skill，而模板绑定或实验类型匹配提供其他候选
- **THEN** 系统优先使用明确指定的技能；该目标缺失或不适用时报告具体问题，不悄悄退回其他规则

#### Scenario: No unique usable skill is available
- **WHEN** 没有可用目标，或尚未明确选择的匹配有多个候选或冲突
- **THEN** 系统明确列出缺失或冲突，暂停相关计算，仍可整理不依赖该技能的记录

### Requirement: Repository roles and user-controlled project history
系统 SHALL 将说明文档归入 docs、模板资源归入技能 assets、操作参考归入 references、生产可执行工具归入 scripts，所有测试文件归入仓库根 test/。实验记录历史 SHALL 使用实验项目根 history，历史 OpenSpec 变更记录 SHALL 继续遵循项目根 hisotry 约定，两者不得混同或互相迁移；项目历史确认以用户主动 Git 提交为准，系统 SHALL 不自动暂存、提交或推送。

#### Scenario: Finish an authorized planning request
- **WHEN** 用户明确要求生成 OpenSpec 方案
- **THEN** 系统保存当前规划产物，不自动归档本变更或创建 Git 提交，也不将其称为已提交历史

### Requirement: Centralized test files and artifacts
仓库 SHALL 建立根 test/，所有测试脚本、测试辅助文件和测试专用固定数据 SHALL 放在其下，允许按模块分子目录。测试运行产生的临时项目、缓存、日志及输出 SHALL 归入 test/ 专用子目录，不散落生产目录或仓库根。迁移 SHALL 保留测试覆盖及历史验证报告，修复导入、运行入口与引用，并提供统一运行与目录核查入口。

#### Scenario: Run migrated suites from another directory
- **WHEN** 从任意工作目录调用仓库的统一测试入口
- **THEN** 测试定位真实生产模块并执行，临时项目和输出均位于 test/，不依赖旧测试路径

#### Scenario: Detect a test outside the canonical directory
- **WHEN** 主技能 scripts/ 或子技能 tests/ 再次出现测试专用文件
- **THEN** 目录检查失败并列出位置，而非静默接受分散布局

#### Scenario: Preserve historical verification evidence
- **WHEN** 现有测试路径迁移到 test/ 并完成本次验证
- **THEN** 历史报告保留原路径与结果，新验证证据记载迁移后路径与本次结果，不用历史通过状态证明迁移成功
