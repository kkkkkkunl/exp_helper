# exp 入口注册实施与验证

## 范围与结论

2026-11-13 按 `complete-experiment-workflow-lifecycle` 第 16 组实施。恢复 `exp/SKILL.md` 独立薄入口，主技能保持 `experiment-workflow` 名称及路由职责；入口传递当前上下文，同级依赖缺失时报告安装不完整。真实输入框候选及入口转交验收已完成：用户确认能看到并选中 exp，本次消息携带实际技能调用，助手随后读取了部署入口与同级主技能。

## 实施内容

1. `host_install.py` 提供指定项目或明确个人全局范围的成对部署，完整复制主技能 scripts、references、assets；部署前核验来源和双目标冲突，暂存完整后发布，中断时报告实际已发布路径。
2. `install.py --project <路径> --host-only` 仅部署到 `.agents/skills/`，不创建实验配置、内部技能索引或日历接入状态。旧初始化命令及 `--init-only` 保留原用途。个人全局使用须明确传入 `--user --host-only`。
3. 主技能、README、安装说明及索引同步本轮契约；本地部署副本和安装暂存文件在 Git 中忽略。历史验证报告与完成项保留，不改写为本轮证据。

## 当前项目部署

已运行 `py -3.9 -B experiment-workflow/scripts/install.py --project F:/experiment-workflow --host-only`。首次因受保护技能目录写权限不足而未发布，随后经执行权限审核运行成功，返回 `ok: true`、`scope: project`、`selector_verified: false`。

两项目标为 `F:/experiment-workflow/.agents/skills/exp/` 与 `F:/experiment-workflow/.agents/skills/experiment-workflow/`。未执行个人全局安装、实验初始化、库存或日历操作，也未执行 Git 暂存、提交、推送或 OpenSpec 归档。

## 验证证据

| 检查 | 结果 | 证据 |
|---|---|---|
| 成对安装专项 | 7 项通过 | `test/artifacts/host-install-final.log` |
| 工作流回归 | 5 组全部通过 | `test/artifacts/20261113T062739350441Z/summary.json` 及同目录日志 |
| OpenSpec 严格校验 | 通过 | `openspec validate complete-experiment-workflow-lifecycle --strict` |
| Git 差异空白检查 | 通过 | `git diff --check` |
| 真实宿主候选与调用 | 通过 | 用户确认候选可见、可选中；实际 exp 调用后读取同级主技能 |

专项测试覆盖完整资源复制、主技能名称保留、同级引用存在、从已部署副本在其他工作目录再部署、重复安装和任一目标冲突、源入口或资源缺失、复制失败无半成品、发布中断实际状态报告、明确个人范围。技能正文的依赖缺失行为经过契约走读；正常入口转交另由本次实际 exp 调用及主技能读取验证，不据此宣称真实实验操作已经测试。原入口断言按本轮 D14 修订，未删除其他记录格式覆盖。

## 任务与规格对应

| 任务 | 契约 | 状态 |
|---|---|---|
| 16.1 | Discoverable exp entry delegates to the main workflow skill | 入口及依赖规则已实现 |
| 16.2—16.3 | Paired host discovery deployment with conflict protection | 部署及冲突测试通过 |
| 16.4 | 安装与发现路径职责分离 | 使用文档已同步 |
| 16.5 | 安装、资源及旧入口兼容 | 专项与工作流回归通过 |
| 16.6 | Evidence-based host selector acceptance | 用户选中入口并实际调用，主技能读取通过 |
| 16.7 | 本轮证据与任务一致性 | 严格校验通过，本组全部完成 |

## 真实宿主验收补记

2026-11-13，用户在验收回复中确认“已看到并能选中 exp”，并在随后消息实际调用项目部署的 exp 技能。助手读取 `F:/experiment-workflow/.agents/skills/exp/SKILL.md` 及同级 `experiment-workflow/SKILL.md`，将当前上下文识别为入口验收，按主技能规则未激活无关实验子技能、未预读全部模块。

这组证据分别覆盖候选可见与可选中、实际入口调用、同级主技能读取和按当前任务处理。第 16.6 项据此完成，整体进度为 96/96；不将本次入口验收扩大为真实实验计算、保存、库存或日历的端到端验收。用户操作输入框，助手没有使用 Windows 自动化操作应用。

发现目录与刷新依据：[OpenAI 官方技能文档](https://learn.chatgpt.com/docs/build-skills)。
