# 接入与分发

## 项目安装

使用现有主 workflow 的 `skill_store.py --project <实际实验项目> install --source <cell-qpcr目录>`，独立安装 qpcr-ddcq。按名称解析，两个技能都在项目 skills/analysis 索引中，不另迁移库，不初始化任意源码目录为实验项目。同名拒绝覆盖，明确更新才 refresh。

模板使用 qPCR.md 2.0.0，项目 method_templates 条目 name=cell-qpcr、format=staged、version=2.0.0、experiment_skill=cell-qpcr；路径相对项目根。独立 analysis_map 可将 experiment_type=cell-qpcr、data_type=qpcr-cq 映射到 qpcr-ddcq。仅合并所需条目，不覆盖其他配置。

## 运行边界

激活准备技能不执行全部分析。数值通过现有临时计算接口，文件输出通过独立分析入口。qpcr-ddcq 未安装时保留待分析；可用仅表示目标可读取，另核查工具。分析版本、内容哈希、输入输出及参数独立登记；保存可恢复的分析包依据，不用 cell-qpcr 快照代替。

旧实验沿用旧模板/技能快照。源模板更新不自动切换；显式升级分别展示模板映射和技能差异，保留历史、复核下游，不倒改实际操作。Git 提交、变更归档与真实项目安装由用户指示。
