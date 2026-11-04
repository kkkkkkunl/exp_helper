# 使用和证据

## 调用

Python 3.9+，基础内核无依赖；XLSX读写需 openpyxl 和 XlsxWriter。独立入口 `python -B scripts/analyze.py --config analysis.json --check` 只读预检，去掉 --check 才分析。输入配置见 input.md。输出目录不得已经存在，以避免覆盖原始数据或上次产物。

成功输出 analysis.xlsx、analysis.json、anomalies.json、report.md、manifest.json 和真实 qpcr-ddcq-basis.zip。后者保存本次实际分析代码/规则依据，manifest记录输入哈希、列和名称映射、参数、实际工具版本、输出及四层验证。analysis_status为computed/partial，不冒充主工作流整理完成。

若由实验级技能调用，可用 experiment_skill_basis 指定本次实际固定的实验技能依据JSON，核对并关联其真实来源/哈希；不把实验技能哈希替代分析技能。主 workflow 使用实际输入输出和参数登记结果任务、回填及版本；仅生成文件不结束实验、不自动扣库存/归档。

## 环境与验证

本包不自动安装依赖或连接远端服务。真实引擎和渲染不可用时，工作簿仍可按实际验证范围提供，但必须指出未验证项。合成样例及验收不属于真实实验结果。主工作流同名安装拒绝覆盖，旧实验续接保持原依据，升级按明确预览和确认操作。
