"""项目配置：定位、校验、模板选择、分析 skill 分发。

skill 本身不写死任何路径；所有位置都从 experiment-project.yaml 读取。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import _common as C
import skill_store


def summary(project: C.Project) -> dict:
    tpls = project.cfg.get("method_templates") or []
    default = project.default_template()
    return {
        "project": project.name,
        "root": str(project.root),
        "knowledge_base": str(project.kb),
        "sample_library": str(project.samples),
        "ppt_template": project.cfg.get("ppt_template"),
        "method_templates": [
            {
                "name": t.get("name"),
                "path": str(project.root / str(t.get("path"))),
                "version": t.get("version"),
                "default": bool(t.get("default")),
            }
            for t in tpls
            if isinstance(t, dict)
        ],
        "default_template": (default or {}).get("name"),
        "needs_template_choice": default is None and len(tpls) > 1,
        "analysis_map": project.cfg.get("analysis_map") or [],
    }


def dispatch(project: C.Project, experiment_type: str | None, data_type: str | None) -> dict:
    mapping = project.cfg.get("analysis_map") or []
    hits = []
    for rule in mapping:
        if not isinstance(rule, dict):
            continue
        match = rule.get("match") or {}
        supplied = {"experiment_type": experiment_type, "data_type": data_type}
        if not match or any(k not in supplied or supplied[k] is None or supplied[k] != v
                            for k, v in match.items()):
            continue
        hits.append({"skill": rule.get("skill"), "match": match})
    if not hits:
        return {
            "skill": None,
            "message": "没有匹配的分析 skill。请在对话中询问用户如何处理，"
            "并继续完成记录、归档等不依赖分析的整理，不得虚构分析结果。",
        }
    if len(hits) > 1:
        return {
            "skill": None,
            "candidates": hits,
            "message": "命中多个分析 skill，需向用户确认使用哪一个。",
        }
    skill = hits[0]["skill"]
    return {**skill_store.resolve(project, skill), "match": hits[0]["match"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="实验工作流项目配置")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_find = sub.add_parser("find", help="向上查找项目根")
    p_find.add_argument("--path", default=None)

    for name, helptext in (("show", "输出配置摘要"), ("validate", "校验配置与目录")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--project", default=None)
        if name == "validate":
            p.add_argument("--scope", choices=["record", "inventory", "analysis", "report", "calendar", "all"], default="record")
            p.add_argument("--skill")

    p_tpl = sub.add_parser("template", help="取方法模板")
    p_tpl.add_argument("--project", default=None)
    p_tpl.add_argument("--name", default=None)

    p_disp = sub.add_parser("dispatch", help="按实验/数据类型找分析 skill")
    p_disp.add_argument("--project", default=None)
    p_disp.add_argument("--experiment-type", default=None)
    p_disp.add_argument("--data-type", default=None)

    args = parser.parse_args()
    try:
        if args.cmd == "find":
            root = C.find_project_root(args.path)
            C.ok(root=str(root), config=str(root / C.CONFIG_NAME))
            return

        project = C.Project(C.find_project_root(args.project))

        if args.cmd == "show":
            C.ok(**summary(project))
        elif args.cmd == "validate":
            problems = project.validate(args.scope, args.skill)
            if problems:
                C.die("配置校验失败", code="invalid_config", problems=problems, ok_to_run=False)
            C.ok(problems=problems, ok_to_run=not problems,
                 message="配置可用" if not problems else "存在配置问题，需先与用户确认")
        elif args.cmd == "template":
            if args.name:
                tpl = project.template_by_name(args.name)
            else:
                tpl = project.default_template()
                if tpl is None:
                    tpls = project.cfg.get("method_templates") or []
                    if not tpls:
                        C.ok(template=None, message="未配置方法模板，按用户提供的实际操作记录")
                        return
                    C.die(
                        "没有默认方法模板且存在多个候选，需向用户确认使用哪一个",
                        code="need_choice",
                        candidates=[t.get("name") for t in tpls if isinstance(t, dict)],
                    )
            C.ok(
                name=tpl.get("name"),
                path=str(project.root / str(tpl.get("path"))),
                version=tpl.get("version"),
                message="创建实验时固定此版本；后续模板变更只影响新实验",
            )
        else:
            C.ok(**dispatch(project, args.experiment_type, args.data_type))
    except (C.SkillError, OSError, ValueError, TypeError, KeyError) as exc:
        C.die(str(exc), code="skill_error")
    except C._yamlish.YamlError as exc:
        C.die(f"YAML 解析失败：{exc}", code="yaml_error")


if __name__ == "__main__":
    main()
