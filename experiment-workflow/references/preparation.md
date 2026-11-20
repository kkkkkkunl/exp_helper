# 铺板与试剂配制

## 铺板

按确认可共用的混合液分组。一份混合液下的组别共用细胞悬液，目标接种与配液条件兼容。每份先合计计划铺板数，然后增加 0.5 当量。分别配制的混合液各算一次。容器与默认终体积如下。

| 容器 | 默认终体积 |
|---|---:|
| 96 孔板 | 100 μL/孔 |
| 48 孔板 | 200 μL/孔 |
| 24 孔板 | 500 μL/孔 |
| 12 孔板 | 500 μL/孔 |
| 6 孔板 | 1,000 μL/孔 |
| T25 培养瓶 | 1,000 μL/瓶 |

将每份混合液作为一个计算项，`rule_type` 和 `calculation` 都用 `cell_seeding`。在 `params.container` 传上表规格编号或 `T25`，在 `params.group_sizes` 传同份混合液各组的计划数，例如 `{"A": 2, "B": 2}`。输入使用计算契约的 `value`、`unit` 和 `source`。

- `cells_per_unit` 接收 `cells/unit`。
- `suspension_concentration` 接收 `cells/mL` 或 `cells/uL`。
- 方案有明确终体积时，在 `final_volume_per_unit` 提供 `uL/unit` 或 `mL/unit`。否则采用上述工作流默认值。

用阶段预览可关联样品、阶段与步骤。尚未登记样品时，可将该计算项的 JSON 经标准输入交给 `scripts/preparation.py --input -`，立即取得计划数、配制当量、目标细胞数、应取悬液、补加培养基及终体积。缺少输入或出现异常时只暂停对应混合液。按正式保存流程留存计算依据，实际操作与库存按实际量登记。

## 试剂清单

新发布的普通或阶段方法在 Markdown 正文放置一个 `json experiment-reagents` 围栏。清单是 JSON 列表，下列为合成验证示例。空清单写 `[]`。旧发布版本沿用原文。

```json experiment-reagents
[
  {
    "id": "demo",
    "name": "合成验证用配制条目",
    "kind": "prepare",
    "source": "合成验收材料",
    "inputs": {"total": "uL", "fraction": "1"},
    "outputs": {
      "part_a": {"unit": "uL", "formula": "total * fraction"},
      "part_b": {"unit": "uL", "formula": "total - part_a"}
    }
  },
  {"id": "ready", "name": "合成验证用成品", "kind": "ready_to_use", "amount": "按当步现行用量记录"}
]
```

每个条目使用不重复的稳定 id。配制输出可引用声明的输入或排在前面的输出，表达式支持有限数值、变量、括号和加减乘除。输入单位按声明传入，`1` 表示无量纲。公式的数值与适用条件来自已选来源；用量单位换算应有供核对的输入或公式依据。

执行到相应步骤时，在阶段预览的 `calculations` 中传 `rule_type: reagent_formula`，`calculation` 填入试剂 id，并沿用样品、阶段、步骤、输入及依赖字段。内置配制计算读取当前实验所选或已冻结的方法版本，按该版本的公式执行与校验。计算记录显示方法版本、公式及来源。新版发布后，现有实验继续用原快照。

尚未登记样品时，可经标准输入只读预览。新实验调用 `scripts/preparation.py --project 项目根 --template 方法名 --template-version 所选版本 --input -`。续接实验用 `--experiment 实验编号` 代替模板名和版本，只读该实验快照。

显式升级时指定 `action: upgrade`、`target_template` 及需要时的 `target_template_version`。阶段方法继续提供阶段与步骤映射。预览中的 `template_upgrade` 列出公式差异及受影响的计算，确认后固定新版本并将尚未重算的相关项标记待复核。普通及阶段方法的原有实际操作留在记录和历史中。
