# Spec Delta

## Purpose

为可独立取用的样品提供唯一库存台账、明确数量与单位、经授权的可恢复事务及来源追溯，在保留现有分装混合规则的同时支持阶段产物、跨实验继承和更正后的相关信息复核。

## ADDED Requirements

### Requirement: Stable sample ledger and quantities
系统 SHALL 为库存单位维护稳定编号、数量、单位、位置、浓度、处理和历史；初始量未知不推断为零，也不从取用量反推。数量非有限、余额不足或单位依据不足 SHALL 阻塞相关变更。只有显式允许的同维度换算才能自动执行。

#### Scenario: Unknown opening quantity
- **WHEN** 样品当前数量未知且请求取用
- **THEN** 系统要求补充依据，不提交扣减，也不据此阻塞独立记录保存

### Requirement: Concentration evidence and inventory scope
浓度 SHALL 保留值、单位和测量对象，并区分实测与有依据的计算；缺失时由用户明确补充、未测定或不适用，不自动填零。稀释、混合或材料转化后的浓度 SHALL 单独核实。未登记为库存对象的试剂 SHALL 只在方法中记用量，耗尽或废弃样品退出在库视图但保留历史。

#### Scenario: Unregistered reagent appears in a method
- **WHEN** 用户描述使用了未登记试剂
- **THEN** 系统保留方法用量，不因此自动建立试剂库存或扣减未知余额

#### Scenario: Product concentration is unknown
- **WHEN** 阶段形成新材料但未提供浓度
- **THEN** 系统要求明确缺失状态，不继承来源材料浓度或把未知写为零

### Requirement: Specific inventory authorization
由记录推导的变更 SHALL 展示具体样品、数量、单位、前后余额及清单标识后获得确认；明确且信息完整的直接库存指令可作为该项授权。阶段确认 SHALL 只覆盖已展示且信息完整的清单，变化后的清单须重新确认。

#### Scenario: Inventory changes after preview
- **WHEN** 用户确认后提交时台账已不同于展示清单的依据
- **THEN** 系统不按旧授权提交，而是生成更新清单并重新确认

### Requirement: Calculations do not constitute inventory consumption
计算、展示、确认保存拟用上样量或其重算 SHALL 不代表已实际取用，不产生库存消耗。库存核查 SHALL 以用户报告或明确确认的实际操作和实际量为依据，仍要求具体清单授权；历史版本或计算修订不得改写已提交库存事件。

#### Scenario: Save calculated loading before performing it
- **WHEN** 用户保存已有上样计算，但尚未报告或确认实际操作
- **THEN** 记录可保留拟用量，库存没有因计算而扣减，后续实际操作按独立事件核查

#### Scenario: Recalculate after an actual use
- **WHEN** 已实际使用并记账的样品因输入更正得到新的计算量
- **THEN** 原实际消耗保留；确需更正库存时另走已确认的调整清单，不按新计算重复扣账或撤销旧事件

### Requirement: Idempotent recoverable inventory transactions
系统 SHALL 为每次真实操作维护独立事件身份，同事件重放不重复记账，已提交事件内容不得改写。业务校验失败 SHALL 不写入任何台账；已开始的多文件提交中断后 SHALL 在后续访问先恢复，并仅在恢复成功后返回库存状态。

#### Scenario: Replay a committed event
- **WHEN** 同一真实操作以相同身份和内容再次提交
- **THEN** 系统返回已处理结果，不重复扣减或创建产物

#### Scenario: Interrupted batch update
- **WHEN** 一批已获授权库存提交在写入中断后再次访问
- **THEN** 系统先恢复该批内容或明确报错，不把不完整中间状态报告为最终库存

### Requirement: Preserve aliquot and mixing semantics
分装 SHALL 关联原管和子管，核对成组转出转入；混合 SHALL 产生独立样品并关联全部来源。新浓度、损耗和不同材料间的数量关系 SHALL 不凭来源信息自动假定。

#### Scenario: Mixed sample has several sources
- **WHEN** 多份样品实际混合形成新样品
- **THEN** 系统核对全部来源和实际取用，为新样品独立记账，不自动继承某一来源浓度

### Requirement: Material lineage and cross-experiment inheritance
模板声明的新材料产物 SHALL 有独立样品编号、材料类型、来源样品、产生实验和阶段；该转化关系 SHALL 与普通取用、分装及混合明确区分。后续实验选择具体样品继承，来源历史缺失允许如实标明未知，必要继续条件仍须满足。

#### Scenario: Start a new experiment with a prior product
- **WHEN** 用户选择此前实验产物作为本次中间入口输入
- **THEN** 系统创建新的实验关联，保留产物与来源链，不重复登记前序制备或扣账

### Requirement: Corrections retain history and identify affected work
库存事实更正 SHALL 使用可追溯的新调整并展示授权清单，不改写原已提交事件。来源信息或关键数值更正 SHALL 定位相关下游样品、阶段及实验以供复核，不把真实已发生操作改为未发生，不无差别重置无关结果。

#### Scenario: Correct a source used by another experiment
- **WHEN** 已被其他实验继承的样品信息被明确更正
- **THEN** 系统保留原依据和更正依据，并指出受影响的后续工作待复核

