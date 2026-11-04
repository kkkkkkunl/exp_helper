# 结果整理与按需分析

本页负责已有结果整理与结果分析／绘图。实验确定后即按 [实验技能模块](experiment-skill-module.md) 启动目标 skill，上样计算在相关步骤输入齐全时执行，不等待新的结果请求。启动不代表运行全部结果分析；已有图片/表格整理不必启动新的数据分析，未明确请求的统计不自行添加。

## 明确最终结果

明确提交本次最终结果时使用 [交互模块](stage-record-module.md) 的 final_results/submission_kind: final。文字、数值、表格和文件均可整理；必要内容回填且附件关联完整后视为实验结束，自动尝试归档。普通讨论和初步结果不触发，此指令不授权额外统计分析。

## 整理已有结果

1. 用 `workflow.py ... organize --experiment <编号> --task <整理任务ID> --status pending` 建立本次要求的整理任务。
2. 用 results.py new/add-version 保存结果及版本；编号、版本和图表引用写入候选实验记录。
3. 调用 workflow.py record 回填记录，按其返回值自动执行库存核查。
4. 已要求的结果确实整理到记录后登记：

```bash
python scripts/workflow.py --project <项目根> organize --experiment <编号> --task <整理任务ID> --status completed --files <本实验内结果文件...> [--analysis-tasks <相关分析任务ID...>]
```

organize 维护结果文件证据、与分析任务的关联及完成时间。所有已请求的整理任务完成才将文档 completed 设为 true；有一个待整理则 false/null。分析任务尚未完成不妨碍整理已有结果，也不阻塞归档。

## 需要实际分析时

已知名称：`skill_store.py --project ... resolve --name <名称>`；直接读取返回的目标 SKILL.md。不读全库正文。

未知名称：先使用配置的 `project.py dispatch --project ... --experiment-type ... --data-type ...`；必要时查询 `skill_store.py ... list` 的短索引。匹配使用规则中所有条件；多候选询问，不猜。缺失目标记录 blocked 并保留记录，不自动下载。安装/索引过期时才读取 setup.md。

加载目标 skill 后遵循它的工具要求，再校验目标：`project.py validate --project ... --scope analysis --skill <名称>`。available 只表示文件可读且索引吻合，不代表工具全部可用。

```bash
python scripts/workflow.py --project <项目根> analysis --experiment <编号> --task <分析任务ID> --status pending
# 不能执行：--status blocked --reason <原因>
# 实际分析执行完成后：
python scripts/workflow.py --project <项目根> analysis --experiment <编号> --task <分析任务ID> --status completed --skill <名称> --skill-version <版本或哈希> --inputs <归档数据...> --outputs <本实验内输出...> --params <参数和工具版本>
```

分析任务与整理任务独立。更新某分析的输入、输出或参数，仅重置通过 --analysis-tasks 关联的整理任务；不重置其他结果。不要把输出文件生成直接解释为已整理到记录。

原始证据留存，结果默认不标记精选，用户决定标记。仅调整日期等无关记录内容时保留已完成状态；修改结果材料或相关数据时重新整理受影响任务。
## 文字证据与重要标记（v4）

文件必须实际回填记录，不能仅凭路径存在标为完成。纯文字结果可用 --text-evidence <JSON文件> 代替 --files，JSON 包含 text 与 request_id；文字须存在于该原始输入及记录结果部分，不制造空附件。

important 表示整次实验重要性，不改变结果版本的 marked。同步只变更对应信息，维持已有任务关联及局部失效规则。
