# 输入映射

## 配置文件

`analysis.json` 含 inputs 数组、params、output_dir。每项 input 提供 path、columns，可提供 sheet、header_row（默认1）、encoding（CSV/TSV默认utf-8-sig）、scope 和 run。路径相对配置文件目录；XLSX 保留原始单元格内容，不执行源文件公式。列名须唯一，缺列报错。

columns 从规范字段映射至真实表头：group、gene、cq_raw 必填；assay、sample、bio_id、scope、run、well、kind、excluded_raw 按实际数据映射。kind 为 sample/RT、NTC、-RT；同名不同引物的 assay 必须显式区分。scope 默认 default，未提供 run 则按源文件身份分开，不能无依据跨文件合并。

params 明确 biological_replicates（true/false）；true 必须同时有 sample 与明确的 bio_id。false 按分组汇总技术孔，不由样本后缀猜独立重复。reference、calibrator 可为单一 assay/组名，或 scope→名称映射。targets 可显式列出目标 assay，error_bar 为 SD（默认）或 SEM。跨运行合并须 `merge_runs: {scope: "本次明确的合并和可比依据"}`，不是无条件批次校正。

value_maps 为字段→原名到规范名的显式映射，原始行另保留；不得自动合并 actin 亚型。人工排除用 params.exclude_rows 的 row_id→理由，row_id 为绝对源路径#工作表!行号；不得只给待删孔而不说明依据。

## 原始证据

每行保留文件、工作表、原始行、原始全部字段、原始 Cq、Excluded 和实际孔位身份。重复导出同一物理孔只纳入一次但不删原行；冲突则明确阻断。未检出、Excluded、原值零与空白分别处理，不把“有数值”等同于 QC 合格。

明确的分析范围、真实样本/独立重复身份、assay 与运行关联是解释前提；缺少时报告受影响部分。已有数据可独立分析，不要求补造细胞提取或 RT 记录。
