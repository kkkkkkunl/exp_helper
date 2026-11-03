# v2 → v3 迁移说明

本页仅用于升级，不是日常入口。

- v2 的 status/completed 表示整体流程状态；v3 的 completed/completed_at 只表示结果整理完成。首次读取旧内部状态时先备份 workflow-v2-backup.json，再按新语义建立任务；不把旧“流程完成”自动当成“结果整理完成”。原文档正文和自定义属性保留，自动 status 字段移除。
- v3 的项目技能库由 install.py 或首次使用的 --init-only 建立，analysis_skill_repository 默认 skills/analysis。旧 analysis_skills 路径映射不再参与日常路由；按 setup.md 把实际技能安装进项目技能库，更新索引。
- 库存事件及确认指纹兼容 v2，规则见 inventory-transactions.md。旧 v1 计划缺少事件 ID/快照，不能直接提交；先核对历史，避免重复登记已发生操作。
- 旧文件可能仍记录绝对路径；迁移机器前保留旧目录或重新登记相应证据。新写入的项目内证据使用相对路径。
- 普通过程记录不再要求分析任务或 analysis_none；分析未完成可以归档。每次 record 后仍须自动执行当轮库存核查。
