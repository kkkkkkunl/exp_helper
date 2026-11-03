# 普通记录与补录

本模块不要求分析意图判定，不读结果模块或全量技能库。

## 交互与保存

1. 在会话收集原话与实际信息，集中整理，只问缺项或冲突。普通数值回答不自动写项目文件。
2. 使用 project.py validate --scope record，仅校验相关配置。若用户使用阶段、暂停、继承或提交最终结果，转 [阶段交互模块](stage-record-module.md)。
3. 普通记录也可用阶段交互脚本的 preview/save，提供 method_text 和实际日期；没有阶段模板时维持普通模式，不自动猜测阶段。
4. 阶段确认、暂停或明确最终结果构成对应写入授权。既有显式 CLI 仍可在用户要求保存时使用：
~~~text
py -3.9 -B scripts/workflow.py --project <项目根> start --request-id <输入唯一ID> --input <原话.txt> [--experiment <已有编号>]
py -3.9 -B scripts/workflow.py --project <项目根> record --experiment <编号> --file <候选记录.md>
~~~
5. 重试复用 request-id，新输入使用新 ID。跨会话先 list/status；不能仅凭新会话没有编号重复建实验。
6. 依据 assets/experiment-record.template.md 填写实际日期、目的、参考方案、实际方法、已有结果和附件。模板预设先确认，未知不编造。缺项在交互状态，正式正文不放 TODO。
7. 附件按 archive.py move 的复制校验／冲突规则处理，链接指向归档后文件。命令管理 completed/completed_at/important，保留其他属性。人工修改时先展示合并并确认，再按当前哈希授权写入。
8. 保存后立即加载库存模块，核查本轮真实操作；无变化登记 none 和依据，不询问是否手动管理库存。同事件不因新轮次重复扣账。
9. 普通过程保存不等于实验结束。明确最终结果按交互模块自动整理／归档；单独请求保存当前材料仍可独立 finalize。

## 局部更新

只补日期或操作说明且不影响结果时保留整理完成标记；涉及结果、分析输入或参数的变化必须明确受影响任务。旧 CLI 的 start 支持 affects-results/affects-analysis，record 支持 affects-results。

结果章节多任务变更但范围不明时不能全量猜测重置，先明确范围。外部修改范围未知时保留任务历史并将总体整理状态置为待定位；实际已执行操作不撤销。

状态查询或工作流调用时核查外部证据，没有后台监听。直接显式调用写入命令属于保存动作，不应在普通数值回答后调用。
