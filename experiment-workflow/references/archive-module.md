# 实验记录归档

## 最终结果自动归档

明确最终结果通过 [交互模块](stage-record-module.md) 实际整理完成后，实验视为结束并自动检查归档。普通讨论、初步结果及单独附件不触发。

有效当前记录、本轮库存核查以及原始输入和记录的证据检查必须通过。库存或证据问题未解决时，保留已完成整理、执行结束和 archive_request；后续会话／工作流动作补齐后延续原授权自动归档，无需再发归档指令。

后续步骤、日历未排期、日历连接失败以及分析待完成可以保留，不额外阻塞当前材料归档，不自动勾选待办。没有后台监听。

## 独立保存当前材料

~~~text
py -3.9 -B scripts/workflow.py --project <项目根> finalize --experiment <编号>
~~~

独立归档保留既有行为：允许分析、结果整理尚未完成，仍要求有效记录、当前轮库存核查／提交和证据可追溯。归档保留待分析、待整理及未解决事项，不表示实验成功或科学审核通过。

## 完成与重要性

记录管理的属性为：
~~~yaml
completed: false
completed_at: null
important: false
~~~

completed 和 completed_at 只表示请求范围内的结果是否实际整理完成；纯过程为 false/null。important 表示整次实验，由用户选择重要或普通，未指定默认 false，已有合法选择保留，不等于结果精选。

用户可在最终结果、归档时或以后修改：
~~~text
py -3.9 -B scripts/workflow.py --project <项目根> important --experiment <编号> --value true
~~~

归档状态保存在内部 archived/archived_at，不新增 status、analysis_status 或 archived 文档属性。材料变化后重新核对归档；无关日期、重要性与日历收据更新不使无关结果失效。归档动作不等同于 OpenSpec 项目历史归档或 Git 提交。
