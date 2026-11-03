# Spec Delta

## Purpose

为实验工作流提供可迁移的项目安装、配置、技能库和按需入口，使记录、库存、分析及汇报能够在明确的项目范围内独立使用，并保留既有目录与用户主动管理版本历史的约定。

## ADDED Requirements

### Requirement: Non-overwriting project initialization
系统 SHALL 在用户明确指定项目后安装主技能、补齐缺失配置及项目内分析技能库，保留已有配置，并拒绝未经授权覆盖已有主技能。手动复制后 SHALL 支持只初始化模式。

#### Scenario: Initialize an existing project
- **WHEN** 项目已有配置并请求只初始化
- **THEN** 已有配置和主技能保持原内容，缺失目录与索引得到补齐

### Requirement: Project-owned named skill resolution
系统 SHALL 使用项目内相对路径维护分析技能索引，按名称只解析目标条目并验证其文件哈希；缺失、重名或过期 SHALL 明确返回，不自动下载或覆盖。

#### Scenario: Move a project and resolve one skill
- **WHEN** 项目搬迁后按名称请求已有分析技能
- **THEN** 系统通过相对路径定位该技能，不读取其他技能正文

#### Scenario: Stale skill content
- **WHEN** 目标技能内容与索引哈希不同
- **THEN** 系统报告需要维护索引，不把目标视为已经可用

### Requirement: Progressive routing and scoped validation
系统 SHALL 按用户意图加载记录、库存、结果、安装或汇报说明，并仅校验相关范围；仅提供过程或原始数据 SHALL 不启动分析。每次明确保存记录后 SHALL 核查本轮库存，无变化时记录依据。

#### Scenario: Record without analysis dependencies
- **WHEN** 用户只记录过程且分析技能缺失
- **THEN** 系统仍能完成记录与相关库存核查，不因无关分析依赖阻塞

### Requirement: Repository roles and user-controlled project history
系统 SHALL 将说明文档归入 docs、模板资源归入技能 assets、操作参考归入 references、可执行工具归入 scripts。历史 OpenSpec 变更记录 SHALL 遵循项目根 hisotry 约定；项目历史确认以用户主动 Git 提交为准，系统 SHALL 不自动暂存、提交或推送。

#### Scenario: Finish an authorized planning request
- **WHEN** 用户明确要求生成 OpenSpec 方案
- **THEN** 系统保存当前规划产物，不自动归档本变更或创建 Git 提交，也不将其称为已提交历史

