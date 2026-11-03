# 库存事件、分组与恢复

## 库存事件

每项必须有 event_id，唯一性范围为一次实验。它对应一次真实操作，不是内容哈希。重放同一 ID/内容跳过，修改已提交 ID 的内容报错；同一批重复 ID 报错。数量和单位在输入事件中应保持原始表达，重试不要把 2 mL 改写成 2000 uL；需更正时单独核查并保留历史。

新增字段：event_id、fingerprint、status；计划增加 snapshots（台账内容哈希）、hash（计划指纹）、status、confirmed_by、committed_at。提交需传计划 hash 和确认依据。确认参数仅是留痕，并不是用户身份验证系统。

提交后保留已提交计划，更新 Markdown 清单状态，并将完整收据保存在实验 `.experiment-workflow/commits/<计划哈希>.json`。再次 commit 同一计划返回 noop:true。再次 plan 已提交事件生成空的已提交计划，不重复记账。

### 分装

先 allocate_id.py aliquot 建子管；新管数量 null 可由 aliquot_in 初始化。示例：

```json
[
  {"event_id":"split-out","group_id":"split-1","sample":"20261101-A","type":"aliquot_out","delta":-2,"unit":"mL"},
  {"event_id":"split-in","group_id":"split-1","sample":"20261101-A-1","type":"aliquot_in","delta":2,"unit":"mL"}
]
```

每组恰好一个来源转出，子管 parent 必须一致，同维度换算后转入合计须等于转出。实际损耗另列独立 consume 事件并注明依据。不要用“create 子管”绕过分装成组检查。

### 混合

先 `allocate_id.py sample --kind mixed` 建新样品，使用同一 group_id 把 mixed_out 和一个 mixed_in 组成一组。mixed_in 的 sources 列出所有转出样品编号；提交写回来源关系。新样品数量由用户实际信息确定，不假设混合总体积必然等于各成分相加。新浓度仍需核实，不能自动继承某一来源。

## 一致性与恢复范围

库存 plan、commit、list、history 以及编号分配共用样品库 `.stock.lock`。使用 OS 锁，进程退出后由系统释放，不按 120 秒删除仍有效的锁。不能靠删除锁文件解锁。

提交先验证所有样品快照，再生成 `.transaction.json`，其中保存本批所有目标内容（台账、收据、清单）。随后逐文件原子替换。若中途存储失败或进程退出，后续脚本访问先按日志完成提交，恢复失败就报错而不返回库存数据。业务校验失败不会开始写任何台账。

这提供脚本访问范围内的整批验证和可恢复提交，不声称多个 Markdown 文件在文件系统层面同时替换。外部 Obsidian/编辑器可能看到恢复前的中间文件，不受脚本锁约束；事务待恢复时不要手改样品文件或删除日志。不同机器/网络共享文件系统的锁行为及 Windows 分支未在本次 Linux 环境验证。
## v4 材料产物与事实更正

阶段产物用独立基础编号及 produced_by 关联实际实验、阶段、尝试和 inputs。产物 create 事件提供 operation（id、stage、attempt），来源 consume 必须有同一关联，可在本批或既有历史中；已提交来源不重复扣减。不同材料不套用分装体积等式，也不自动继承浓度。

更正使用新的 event_id、type: adjust、note，以及 correction_of（experiment、event_id）或外部 basis。quantity 为实际核实的更正后余额；只改 metadata/concentrations 时可省略 quantity，原余额保持原值或未知。仍须展示指纹清单及获得授权，原事件不改写。

metadata 仅允许 material_type、provenance、produced_by，保存前后依据，来源禁止自引用及成环。concentrations 每项有 analyte、origin；measured/calculated 须有非负有限 value 及 unit，calculated 还需 basis；unmeasured/not_applicable 不得同时填值。

更正后生成相关实验复核通知，按可重建的来源关系定位样品和阶段，不抹去实际操作，不无差别重置结果。具体复核由交互模块明确确认。上文 Linux／Windows 限制是 v2 历史验证范围，本轮结果以当前实施报告为准。

