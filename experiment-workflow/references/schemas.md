# 数据结构定义

v3 工作流语义见 record-module/result-module/archive-module；库存确认指纹和事务日志见 [inventory-transactions.md](inventory-transactions.md)。下列示例展示基础字段，库存提交以脚本生成的完整 v2 计划为准。

YAML 配置和样品属性使用 YAML 子集；内部 workflow 与日历状态采用 JSON。脚本自带解析器，**不要用 PyYAML**（目标环境可能没有）。

## YAML 子集约束

允许：缩进映射与序列（2 空格）、行内列表 `[a, b]`、字符串/整数/浮点/true/false/null、`#` 注释、`|` 块字面量、双引号转义。

禁止：制表符缩进、锚点与别名、多文档、流式映射 `{a: b}`、复杂键。违反时脚本报错并给出行号，不会静默猜解。

**含冒号的值必须加引号**，否则会被解析成映射。日期建议写成 `"2026-10-31"`（带引号），避免被当成数字。

## 编号格式

| 对象 | 格式 | 示例 | 基准时间 |
|---|---|---|---|
| 实验执行 | `YYYYMMDD-HHmmss` | `20261031-143012` | 记录首次创建（北京时间） |
| 样本基础 | `YYYYMMDD-<字母>` | `20261031-A` | 实际形成日期 |
| 分装 | `<来源编号>-<数字>` | `20261031-A-1`、`20261031-A-1-1` | 继承来源 |
| 结果项 | `R-<实验编号>-<NN>` | `R-20261031-143012-01` | — |

字母进位：A…Z、AA…AZ、BA…（Excel 列风格，不跳字母）。

两套编号的时间基准不同，属有意设计：实验编号用创建时间便于审计，样本编号用形成日期便于排序。

## experiment-project.yaml

```yaml
version: 3
analysis_skill_repository: skills/analysis
project: 示例课题                      # 显示名
knowledge_base: ../kb                 # 相对项目根
sample_library: samples               # 相对知识库根
ppt_template: templates/report.pptx   # 可空
method_templates:
  - name: 细胞培养
    path: templates/cell-culture.md   # 相对项目根
    version: "2026-10-01"
    default: true
analysis_map:
  - match:
      experiment_type: 流式
    skill: flow-analysis
units:
  convert:                            # 显式声明的可换算对
    - [uL, mL]
    - [mg, g]
```

约束：`default: true` 至多一个；`knowledge_base` 必填；`sample_library` 默认 `samples`。

## 样本台账 `<知识库>/<样本库>/<编号>.md`

```yaml
id: 20261031-A
kind: base                # base | aliquot | mixed
status: in_stock          # in_stock | depleted | discarded
location: 4℃冰箱 A2
quantity: 12.5
unit: mL
concentrations:
  - value: 10
    unit: mM
    analyte: 葡萄糖
    origin: measured      # measured | calculated
    basis: null           # origin 为 calculated 时填依据
treatment: 药物X 10 µM, 24 h
formed_on: "2026-10-31"
parent: null              # 分装时为来源编号
sources: []               # 混合样本列全部来源
experiments: []           # 双向关联的实验编号
history:
  - at: 2026-10-31T15:30:00+08:00
    type: create
    delta: 12.5
    unit: mL
    experiment: null
    key: 8f3a1c2d5e6b7a90   # 幂等键
    note: 初始入库
```

`quantity` 为 `null` 表示起始量未知——此时**禁止扣减**，必须先询问。

正文表格由脚本重绘，**手工修改请只改 frontmatter**。

## 库存变更计划 `<实验>/.experiment-workflow-plan.yaml`

```yaml
experiment: 20261031-143012
created: 2026-10-31T16:00:00+08:00
items:
  - sample: 20261031-A
    event_id: draw-1
    type: consume          # create|consume|return|aliquot_out|aliquot_in|mixed_out|mixed_in|deplete|discard|transfer
    delta: -2
    unit: mL
    location: 4℃冰箱 A2
    note: 本次取用
    key: 8f3a1c2d5e6b7a90
    before: 10
    after: 8
```

`delta` 符号：正向类型（create/return/aliquot_in/mixed_in）为正，负向类型（consume/deplete/discard/aliquot_out/mixed_out）为负，`transfer` 为 0 且必须给 `location`。

## 结果项 `results/<编号>/index.yaml`

```yaml
id: R-20261031-143012-01
title: 增殖曲线
experiment: 20261031-143012
created: 2026-10-31T16:00:00+08:00
versions:
  - version: 1
    params: t 检验, α=0.05
    params_hash: 3f9c2a1b7e45
    files:
      - name: curve.png
        path: v1/curve.png
        sha256: 9a1b...
    marked: false
    marked_at: null
    created: 2026-10-31T16:00:00+08:00
```

## 知识库结果登记表 `<知识库>/_results-index.yaml`

```yaml
projects:
  - projects/demo        # 相对知识库根；库外用绝对路径
```

只用于跨项目筛选，由脚本维护。

## 脚本状态目录 `.experiment-workflow/`

| 文件 | 内容 |
|---|---|
| `experiments.yaml` | 已分配的实验编号 |
| `ids.lock` | 编号分配锁 |
| `committed.yaml` | 已提交的变更批次 |

v2 使用 OS 文件锁，进程退出后释放；不按时间删除锁文件。库存日志和新字段见 `inventory-transactions.md`。

## v3 文档属性与内部状态（历史兼容）

实验记录只自动维护 completed、completed_at，表示结果整理完成，不表示分析完成或已归档。没有整理任务时为 false/null。status 不再是文档的自动属性；已有其他自定义属性保留。

内部 workflow.json 的 result_tasks 保存整理任务状态、完成时间、结果证据及 analysis_tasks 关联；analysis 保存实际分析进度；archived/archived_at 保存归档状态；inventory 保存本轮库存核查状态。新存储的本项目文件路径相对项目根，随项目目录迁移。

记录轮次每次 record 增加，库存变为 review_pending；原有结果是否失效按受影响任务判断，不全量重置。
## v4 阶段与日历扩展

workflow.json 的 version 为 4，保留旧字段并增加 template_snapshot、stage_progress（样品→阶段→尝试及 steps）、attempts、segments、confirmations、actual_date、execution、archive_request、followups、corrections、review_links 和 actions。未知未来版本拒绝降级；v2/v3 显式备份迁移，不反推历史阶段。

模板快照同时核验原文、解析内容及哈希，显式升级保留旧快照与进度。步骤分别保存 executed、complete、values、missing；本次暂停 segments.completed 不代表未做步骤 complete。字段及格式见 [模板规范](stage-template-rules.md)。

记录管理 completed、completed_at、important，其他执行／同步状态留内部。整理任务可有 files 或 text_evidence（text、request_id、sha256、source_sha256），文字结果不要求文件。

样品增加 material_type、produced_by（experiment、stage、attempt、inputs、operation_id）及可选 provenance，保留 parent 分装和 sources 混合语义。新材料独立编号；库存 adjust 提供 note 及 correction_of 或 basis，metadata 可更正材料来源，concentrations 纳入计划确认。

calendar.json 仅保存 provider、calendar_id、capabilities、timezone、status，不含凭据。followups 保存稳定 id、阶段、样品、剩余内容、排期、远端事项及动作收据。待办由日历管理，内部映射只负责恢复和防重复。命令见 [交互模块](stage-record-module.md) 与 [日历接入](calendar-integration.md)。
