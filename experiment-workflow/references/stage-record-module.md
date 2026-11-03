# 阶段式交互记录

仅在用户使用阶段模板、暂停、继续、继承样品或提交最终结果时读取。结构定义按需读 [模板规范](stage-template-rules.md)，有日历动作时才读 [日历接入](calendar-integration.md)。

## 会话行为

1. 识别已有实验或新实验。已有实验先 resume；新实验预览阶段不分配编号。使用旧样品开展新实验另建编号，前序操作只链接来源。
2. 按模板步骤集中提示相关字段。用户自由文本或多步骤输入由会话整理为结构化 values，只追问缺项和冲突；返回的 prompts 提供模板字段与条件依据，不补造流程。
3. 普通参数回答保留在会话内。不要为了预览在项目中保存草稿 JSON、原话文件、调用 start、分配编号或生成库存计划。可用 Python API 内存对象，或 CLI `--file -` 从标准输入传入 JSON；执行加 `-B` 避免生成字节码文件。
4. 预览展示完整拟写记录、待补项、真实步骤和具体库存清单。用户确认后才 save，携带该次 preview_hash 和确认来源；若清单已明确获确认，另外携带所展示 inventory.hash。没有清单确认也可保存独立记录，库存保持等待。
5. 用户说“暂停”：保存已做部分并完成本次阶段收尾，剩余步骤仍未执行，转入日历待办。没有规程依据时不把记录暂停解释为可以直接继续实际操作。
6. 每个后续阶段维护一个日历事项。先保存，再集中补问日期、开始时间和预计时长；读日历模块执行真实远端动作，不能仅据本地状态报告已排期。

## 动作输入

`stage_workflow.py` 的 preview/save 接受相同 JSON。输入文件只能在已获对应保存授权后写入项目；纯预览使用标准输入或会话内对象。

| 字段 | 内容 |
|---|---|
| action_id | 稳定动作标识；重放沿用，真实新操作使用新值 |
| action | confirm、pause、final_results、correct、upgrade |
| raw_input | 该次用户原话，保存时作为来源；不得用模型编造的输入替代 |
| experiment | 已有编号；新实验省略 |
| template / entry | 明确选择的方法模板和合法入口 |
| actual_date / purpose | 用户提供或可追溯的实际日期及目的 |
| samples | 已有具体样品编号列表 |
| operations | sample、stage、step、executed 和 values；只对实际执行设 true |
| values | 字段 id → value、unit、source；实际输入为 user |
| confirmed_fields | 当前步骤中用户已明确确认的模板操作参数 id；不能确认缺失实测值 |
| inventory_items | 本轮实际库存事件，保持稳定 event_id；未登记试剂不自动建账 |
| inventory_review | 无变化时 mode: none 和实际核查 reason；不能因没列事件就假定无变化 |
| results / result_scope | 本次结果 id、text、files、missing 及明确范围 |
| submission_kind | 只有 final 才能进入最终结果流程 |
| important | 可选布尔值；缺失默认普通，已有选择保留 |

声明未测定或不适用使用 `status: unmeasured/not_applicable`、`source: user`，并满足模板允许类别。操作数据不能单独靠预设生成；缺项记录在交互状态，不把 TODO 或模板占位符放进正文。

```text
py -3.9 -B scripts/stage_workflow.py --project <项目根> preview --file -
py -3.9 -B scripts/stage_workflow.py --project <项目根> save --file - --preview-hash <预览哈希> --confirmed-by <用户确认依据> [--inventory-hash <已展示清单哈希>]
py -3.9 -B scripts/stage_workflow.py --project <项目根> resume --experiment <已有编号>
```

预览哈希绑定实际记录、状态、样品和模板。预览后有变化须重新展示确认。首次保存才分配新编号；动作日志覆盖本地记录与收据，失败后重放原动作恢复，不重复增加记录轮次。需要恢复中断本地动作时显式调用 `workflow.py --project ... recover`。

## 样品、分支与更正

- 同一次实验可有不同样品进度，按相同步骤集中询问。普通取用沿原样品，分装沿用原分装规则；模板产生新材料使用独立产物编号。
- 保存实际阶段后，可用 `allocate_id.py product --project ... --date <实际形成日YYYYMMDD> --experiment ... --stage ... --attempt ... --inputs <来源编号...> --material-type <模板产物类型> --operation-id <真实转化ID>` 保留产物身份。数量仍未知，入库另展示清单。
- 产物 create 和来源 consume 的 operation.id/stage/attempt 对应同一真实转化；来源扣减已在历史提交时不再扣一次。不同材料不强加同体积或浓度继承。
- branches 映射阶段到模板允许后继；超出模板的 adjustment 必须有 confirmed: true 和 reason。真实偏离如实记载，不据此推导未提供的实验可行性。
- retry 数组列 sample、stage、reason，生成新尝试，保留原尝试及消耗。correct 需要 reason，保留前后事实；关联下游待复核，不把实际操作撤销为未执行。
- resolve_reviews 数组明确 sample、stage、confirmed: true、reason，重新核对来源及映射字段后解除复核；不能凭继续指令跳过复核。

## 最终结果

只有明确提交本次最终结果（例如“实验结果：……”或“整理本次最终结果”）才使用 action: final_results、submission_kind: final。普通讨论、初步数据、单独附件或“结果还没出来”不触发结束。宿主负责识别用户意图，脚本不以包含关键词自动判断。

文字结果 text 须能从 raw_input 追溯；文件先按附件规则归入本实验，保存时回填实际链接。result_scope 覆盖本次明确请求范围，不能静默排除既有未完成请求。缺必要内容则 missing 列明并继续收集。

内容已实际回填、必要附件关联完整后，结果整理完成并视为实验结束；随后自动尝试归档。当前库存或证据检查未过时保留已完成状态及原归档授权，后续调用补齐后自动继续。仍待分析、未排期或未完成日历事项可保留，不能伪标完成。
