# 库存模块

触发：每次记录模块完成后自动进入；或用户直接发出入库、取用、归还、分装、转移、报废指令。无需询问“是否要手动管理仓库”。

核查**本轮新操作**，不重放旧实验过程。新轮次的库存状态为 review_pending。

只计算、展示或确认保存上样拟用量不构成实际取用，不生成消耗事件。实际量可以不同于计算量，必须依据用户报告或明确确认的实际操作再核查具体清单。重算不更改已提交库存，确需更正走独立调整授权；不要把计算结果或 history 旧版重新扣账。

- 没有实际库存变化：`workflow.py ... inventory --experiment <编号> --mode none --reason <核查依据>`，直接结束，不询问。
- 存在变化：先 `workflow.py ... inventory --experiment <编号> --mode required`，再生成本轮计划。已有记录可接受独立库存操作；无实验编号时先保存该库存指令为一次可追溯记录。

```bash
python scripts/project.py validate --project <项目根> --scope inventory
python scripts/inventory.py plan --project <项目根> --experiment <编号> --items <变更.json>
python scripts/inventory.py commit --project <项目根> --experiment <编号> --plan-hash <指纹> --confirmed-by <确认人及授权依据>
```

## 授权规则

从实验描述提取或推导的变更，展示清单，确认后提交。用户已明确给出信息完整的具体指令，例如“报废样品 A，全部报废”，即为该项授权：读取实际库存、生成具体清单后直接提交，不重复确认；在 confirmed-by 记录对应原始输入/request-id。没有推导权限时不扩展到其他样品或操作。

数量、编号或单位不明确时只询问缺失信息；未知起始量不能反推，不按相似名称扣减。

## 事件和数据

每项用稳定 event_id。真实两次相同取样用不同 ID，重试同一操作沿用原 ID。例：

```json
[{"event_id":"draw-1","sample":"20261101-A","type":"consume","delta":-2,"unit":"mL"}]
```

新样品先 allocate_id.py sample；分装先 allocate_id.py aliquot。新增入库用 create；报废用 discard 和实际负数量；归还用 return 和正数量。未登记试剂只记录用量。

分装/混合才读取 [库存细则](inventory-rules.md) 和 [分组与恢复细节](inventory-transactions.md) 的对应段落。group_id 把来源和去向成组校验；无密度依据不跨质量/体积换算；计算浓度不得冒充实测。

脚本整批快照校验、共享锁、事务日志保持不变。清单后库存变化时重算；存储故障后下次访问先恢复，不删除事务日志。提交后可归档；相同事件重试跳过，不重复记账。
