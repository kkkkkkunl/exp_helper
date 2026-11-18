---
name: expmodel
description: 用户输入 /expmodel 或请求从附件生成实验方法模板时，提取来源并发布配套空白记录模板。
---

# 实验模板生成

用户输入字面 `/expmodel` 时进入本技能，保留当前消息的附件和上下文；也支持宿主通过技能名称显式调用。读取同级 experiment-workflow/references/template-generation.md，按用户选定的项目和来源处理。相对脚本路径以同级 experiment-workflow 目录为准。
