# 阶段模板作者规范

仅在编写、检查、选用或升级阶段模板时读取。本规范对应 `stage_templates.py`，采用项目自带 YAML 子集，不依赖 PyYAML。

## 文件与配置

阶段模板是 YAML 文档，根字段 `version: 1` 与 `stages`。项目 `method_templates` 配置该文件的 name、path、version、`format: staged`。省略 format 或设 plain 表示普通方法文档，不自动推断阶段。

结构示例见 [workflow-structure.example.yaml](../assets/workflow-structure.example.yaml)。它只描述用户给出的阶段和记录入口，没有实验操作参数，也没有声明任何安全暂停条件；真实方法和继续依据必须来自用户的实际规程。

校验所选模板：

```text
py -3.9 -B scripts/stage_templates.py --project <项目根> --name <模板名>
```

## 阶段与步骤

每个阶段必须包含：

| 字段 | 用途 |
|---|---|
| id / title | 稳定标识与展示名称；阶段 id 不重复 |
| entry | 是否允许从此阶段开始 |
| pause_after | 规程是否声明可在阶段后暂停；没有依据时 false |
| requires | 继续前须具备的样品台账字段，未知时只提示缺项 |
| input_types / outputs | 接受的材料类型与声明的新材料产物类型 |
| next | 允许的后续阶段 id；多个后继须用户选分支 |
| steps | 有序步骤列表，每步包含 id、title、fields |

步骤 id 在阶段内唯一，字段 id 在步骤内唯一。next 和入口须有效，静态路径不设循环；真实重做产生新尝试。未知样品、不足的继续依据和未经确认的路径调整不能转为自动操作指令；已经实际发生的偏离仍如实记录。

## 字段

字段必须有 id、label、type、unit、required、measurement、allow_unknown。

- type 为 number、integer、string 或 boolean。数值拒绝布尔值、NaN 和无穷；有单位的实际值须提供单位，仅按项目声明进行同维度换算。
- unit 无单位时写 null；allow_unknown 为允许的 `unmeasured`、`not_applicable` 数组，不允许时写空数组。
- measurement 为 true 表示实测字段，不得配置 default。实测结果由用户提供。
- 可选 default 只是操作参数参考。会话先展示，用户可输入实际值或集中确认所列参数；确认不产生未提供的测量值。
- 缺必填值可以暂停保存，数据保持待补；未知不填零，未做步骤不能因保存变为已执行。

## 内容固定与升级

首次保存实验时存下原文、版本、哈希及来源，后续读取内部快照。更改源模板只影响新选择；快照解析内容与原文均须校验。

升级动作使用 `action: upgrade`、target_template，以及 mapping.stages、mapping.steps。步骤键采用 `原阶段/原步骤`。会话展示映射与影响后确认，历史快照及进度保留，映射后数据先待复核。缺失映射、丢失字段或隐式合并均报错。用 resolve_reviews 明确记录复核对象、确认与依据，按新字段定义验证后继续。

旧实验没有真实旧模板内容时，不追溯伪造快照；普通模式可继续使用，需要阶段模式时明确选择模板及入口。
