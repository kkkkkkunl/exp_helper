# 安装与项目技能库

仅在安装、首次初始化、技能库维护时读取本页。

## 安装主 skill

仓库另交付同级 `exp/SKILL.md` 作为 `$exp` 薄入口。部署时须让 `exp/` 与 `experiment-workflow/` 同级且均可被宿主定位；仅部署入口而缺少主技能时，应明确报告依赖缺失。已有 `$experiment-workflow` 直接调用继续有效。`exp` 不复制主规则，也不自动创建项目或保存实验。

```bash
python <解压目录>/experiment-workflow/scripts/install.py --project <项目根>
```

新项目建立最小配置（knowledge_base 为项目根，sample_library 为 samples），复制主 skill 并建立：

```text
项目根/
├── experiment-project.yaml
├── samples/
└── skills/
    ├── experiment-workflow/
    └── analysis/
        └── index.json
```

安装依赖显式项目路径，不把当前任意目录当成项目。已有配置不覆盖；主 skill 同名目录已存在时拒绝覆盖。

手动复制安装时，首次使用运行：

```bash
python <主skill>/scripts/install.py --project <项目根> --init-only
```

它仅补齐缺失配置、项目内目录和空索引，不复制或覆盖主 skill。已有项目配置的外部知识库不自动新建。此行为由安装命令或首次使用入口执行，不依赖宿主提供安装钩子。

配置 `analysis_skill_repository: skills/analysis`；所有技能索引路径相对项目根。项目技能库不接受绝对路径、越出项目的路径或符号链接。

## 安装、更新实验或分析 skill

```bash
python scripts/skill_store.py --project <项目根> install --source <待安装skill目录>
python scripts/skill_store.py --project <项目根> refresh
```

install 从 SKILL.md frontmatter 读取 name、description、可选 version/input_types，复制到 `<库>/<name>/` 并更新 index.json。同名存在时报错，不自动覆盖。更新已安装内容须先明确更新范围，再执行 refresh；refresh 只在维护阶段枚举元信息并计算文件哈希，检测重复名称后整份拒绝，不留下部分新索引。

不自动下载缺失技能。未提供任何专业分析 skill 时保留空技能库。

实验级 skill 沿用同一技能库，可在 frontmatter 声明 `kind: experiment`、`experiment_types`；旧条目不需要迁移。项目配置 `experiment_skill_map` 各项声明 experiment_type 与 skill；所选方法模板配置可声明 experiment_skill。该启动映射与用于结果分析的 analysis_map 独立，不将记录中的同名文本当配置。技能公式、工具及可选执行契约见 [实验技能模块](experiment-skill-module.md)。

## 日常定位

```bash
python scripts/skill_store.py --project <项目根> resolve --name <skill名称>
```

只查索引并校验该目标的哈希。返回 available:false 时保留当前记录，提示缺失或索引过期，不自动读遍所有正文。

未知名称时 `list` 返回轻量名称/用途索引，或 `project.py dispatch` 按已配置 analysis_map 找名称。只有命中唯一目标才读取该目标 SKILL.md，继续检查它的工具要求。analysis_map 只存名称和匹配条件，不重复配置绝对路径。
## 首次安装日历引导（v4）

安装或 init-only 返回 calendar.status 和 next_action；首次为 needs_setup/choose_calendar_and_connect。宿主会话询问用户选择日历服务和目标，复用已有连接或安装、连接对应插件／MCP，并完成用户登录授权。

仅此时读取 [日历接入](calendar-integration.md)，用真实工具核查创建、读取、查找和更新能力，成功后 configure。脚本本身不安装任意宿主插件，不把名称配置当连接成功，不固定 Outlook，项目不保存凭据。

已配置项目保留目标；未接入可先完成独立实验记录并保留待同步。手动复制后的首次初始化执行相同引导。新配置为 version: 4，默认时区 Asia/Shanghai，已有配置不覆盖。Windows 使用 Python 3.9 或以上，可用 py -3.9 -B，并先确认默认 python 是否属于其他科学软件。
