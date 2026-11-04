# 实验确定、技能激活与上样计算

## 启动与定位

用户明确开始或继续一次实验，实验类型及模板或用户方案明确后，立即启动对应实验级 skill。讨论备选不启动，所需浓度等输入可启动后收集。只读目标入口及当前步骤说明，不读取全部技能正文，不自动执行所有结果分析。

```text
py -3.9 -B scripts/project.py activate --project <项目根> --started --experiment-type <类型> --template <模板名> [--skill <用户明确指定>]
py -3.9 -B scripts/project.py activate --project <项目根> --started --experiment <已有编号>
```

无配置模板、使用已确定用户方案时以 `--plan <方案名称或内容>` 替代 template。定位顺序为用户明确指定、模板配置的 `experiment_skill`、项目 `experiment_skill_map` 中的 experiment_type；已有 analysis_map 继续用于独立结果分析。技能仍安装在项目现有 skills/analysis，不另迁移技能库。

多候选或绑定冲突先明确选择。指定目标缺失或不适用时报告，不能自动退回其他规则。激活返回 ready 仅代表目标及依据可读取；计算时另检查输入、工具及适用范围。缺失、缺工具、缺输入分开报告，独立记录和无依赖样品继续。

## 计算与保存

模板只提供流程、输入和记录结构，不维护计算。会话遵循目标 skill 的公式、单位、参数和工具要求；参数须有本次方案来源或明确确认，实测量不能默认生成。输入齐全时执行当前计算并立即展示，不要求用户另说一次计算。必要输入缺失、单位不兼容、负补液量或违反技能约束时列出原因，不能补零或将异常值当作执行方案。

阶段 preview/save 的 `calculations` 与 `operations` 独立。每项计算提供：

| 字段 | 含义 |
|---|---|
| id / calculation | 当前计算稳定标识／技能中的计算名 |
| sample / stage / step | 对应具体样品、阶段及步骤，支持操作前计算 |
| inputs | 输入名到 value、unit、source 的映射；source 为 user、confirmed_parameter 或有可追溯依赖的 calculated |
| params | 本次已明确参数；按 skill 要求提供，不静默补默认值 |
| depends_on | 已存在或本轮前面计算的 id 列表，变更只影响依赖下游 |
| reason | 更正已保存计算的依据；也可使用本轮 reason |
| host_execution | 无可执行接口的正文型技能所需的真实宿主计算证据，见下文 |

草稿同时提供 `experiment_type`，可选 `experiment_skill` 或用户 `plan`。`skill_evidence_hash` 可绑定此前激活时取得的依据哈希，源内容变化须重算并展示。preview 返回独立 calculations、skill 状态、拟写记录及确认哈希，不持久化草稿。

阶段确认或暂停 save 后记录计算输入、单位、依据、参数和结果。未执行步骤依然未执行，实际上样量仍由 operations 的实际字段或用户 method_text 记录。仅保存计算不产生库存消耗，不改变 completed/completed_at 或结束意图。实际操作与计算量不同可以并存，库存以实际量及已展示授权清单为准。

## 技能作者的可选可执行契约

技能可以提供 `experiment-skill.json`，使用 version 1、可选 experiment_types 和 tools，以及 calculations 映射。每项 calculation 声明 entrypoint（相对技能目录的 Python 脚本）、basis、inputs 与 outputs；每个数值字段声明 unit，可声明 minimum，输入默认 required，也可明确 required:false。实验公式只能存在于 skill 自己的规则与脚本中，主工作流不解释公式表达式。

脚本从标准输入读取该次计算的 JSON 对象，在标准输出仅返回 JSON：`status: computed` 及 outputs（输出名到 value、unit）；异常应返回原因。使用当前 Python 以 `-B` 执行，超时 30 秒，工作流在临时目录复制目标技能后运行，偶发产物不会写入实验项目。tools 中声明的外部程序须可用；不自动安装。临时测试技能不能冒充已交付的具体专业技能。

没有声明此接口的既有 skill 返回 host_required：宿主仍可按其正文使用实际工具计算，不编造 Python 接口。回填 `host_execution` 须包含：skill_hash、input_hash（对 inputs 与 params 的规范 JSON 指纹）、rule_file、可在该规则原文定位的 basis、实际 tool/tool_version 及 outputs。引用须属于本次固定技能内容，指纹须与当前输入匹配；这是执行来源证据，不是工作流独立完成科学审核的证明。没有真实执行证据时保留待处理，不伪造 computed。

## 依据固定与显式升级

首次授权保存才保存实际使用技能的内容快照（入口、规则、脚本等目标技能文件）、版本、来源、哈希及参数。跨会话 resume 校验原依据，当前安装更新不改变旧实验。缺失原快照则报告 missing_evidence，不以新版本冒充原规则；旧状态没有依据就明确未知。

明确升级在草稿提供 `skill_upgrade: {skill, confirmed: true, reason}`，须先 preview 展示 changed_files、前后依据及 affected，按该次预览确认后 save。未在本轮重算的旧依据计算标为待复核，旧快照和记录历史保留。实际操作及无关任务不被覆盖。已有模板升级继续使用原 mapping 机制，不以技能升级代替模板映射。

## 历史与本次范围

已保存记录的内容或受管属性发生变化时，完整旧记录存入项目根 `history/<实验编号>_<YYYYMMDD-HHMMSS-ffffff>.md`，时间为本次确认保存的北京时间。首次保存、内容不变、纯会话重算及同一动作重试不新建历史。历史中的受管附件引用按新位置转换，附件不重复复制；归档按实验关联纳入历史并核对证据。

既有内部 record-history、模板快照、库存历史和结果版本保留各自语义。OpenSpec 的 `hisotry/` 不迁移、不混作实验材料。细胞 qPCR 专项提供独立 cell-qpcr、qpcr-ddcq 与模板 2.0.0；计算按当前步骤加载 cell-qpcr，明确结果任务才交接 qpcr-ddcq。项目是否已安装、实际工具和分析内容依据分别核查；旧实验沿用冻结内容，不能用旧模板公式替代缺失技能。该专项迁移不重写此前通用更新暂缓迁移的历史决定。
