# 阶段模板作者规范

仅在编写、检查、选用或升级阶段模板时读取。本规范对应 `stage_templates.py`，采用项目自带 YAML 子集，不依赖 PyYAML。

## 文件与配置

模板负责阶段、步骤、输入及记录结构，不提供计算实现。项目 method_templates 条目可用 `experiment_skill` 明确绑定一个 skill 名，或列出待明确选择的候选；此字段是配置元信息，不从同名普通记录字段推断。计算和校验统一由 [实验级技能](experiment-skill-module.md) 承担。细胞 qPCR 模板 2.0.0 绑定 cell-qpcr，专业计算已迁出模板；旧 1.0.0 的真实源内容见 assets/legacy，已冻结实验保持原状，显式升级才映射，不以旧公式作为缺失技能的自动后备。

阶段模板是 YAML 文档，根字段 `version: 1` 与 `stages`；也支持在 Markdown 中用唯一的 `yaml experiment-workflow` 围栏代码块嵌入相同定义。其他 YAML 代码块和 Markdown frontmatter 不作为阶段定义。标记块缺少闭合围栏或出现多个标记块时报错，不猜选。项目 `method_templates` 配置该文件的 name、path、version、`format: staged`。省略 format 或设 plain 表示普通方法文档，不自动推断阶段。

单文件示例为 [细胞 qPCR 模板](../assets/qPCR.md)。其 frontmatter 是模板元信息，标记代码块是阶段定义；首次保存仍固定整份 Markdown 原文、版本与哈希，续接时从原文重新提取并校验阶段定义。实际保存记录只收录用户提供或确认的已执行内容，不复制模板中的全部参考步骤与空表。使用嵌入式模板需配套含此读取能力的 workflow 版本。

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
