"""结果项与版本：稳定编号、参数指纹、标记、跨项目筛选。

规则
----
- 结果项编号 `R-<实验编号>-NN`，一经分配固定不变。
- 数据或分析参数变化产生新版本；参数指纹相同且文件相同则视为重复，不再建版本。
- 标记挂在版本上，新版本默认未标记；旧版本的标记保留。
- 标记只表示用户选中，不代表统计显著或质量审核通过。

用法
----
python results.py new         --project <根> --experiment <编号> --title 增殖曲线
python results.py add-version --project <根> --id R-20261031-143012-01 --files a.png --params "对照组 vs 给药组, t 检验"
python results.py mark        --project <根> --id R-20261031-143012-01 [--version 2] [--off]
python results.py list        --project <根> [--marked]
python results.py filter      --kb <知识库根> [--marked]
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import _common as C

INDEX_NAME = "index.yaml"


def results_dir(project: C.Project, exp_id: str) -> Path:
    return project.experiment_dir(exp_id) / C.RESULT_DIR


def load_index(path: Path) -> dict:
    if not path.is_file():
        raise C.SkillError(f"结果项不存在：{path}")
    data = C._yamlish.loads(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise C.SkillError(f"{path} 结构异常")
    return data


def save_index(path: Path, data: dict) -> None:
    C.atomic_write_text(path, C._yamlish.dumps(data))


def find_result(project: C.Project, result_id: str) -> Path:
    C.safe_id(result_id)
    for exp_dir in sorted(project.experiments.glob("*/")):
        candidate = exp_dir / C.RESULT_DIR / result_id / INDEX_NAME
        if candidate.is_file():
            return candidate
    raise C.SkillError(f"未找到结果项 {result_id}，请确认编号")


def register_project(kb: Path, project: C.Project) -> None:
    """在知识库登记项目，供跨项目筛选使用。"""
    registry_path = kb / C.RESULT_INDEX
    data = {}
    if registry_path.is_file():
        data = C._yamlish.loads(registry_path.read_text(encoding="utf-8")) or {}
    projects = data.get("projects") or []
    try:
        rel = project.root.relative_to(kb).as_posix()
    except ValueError:
        rel = str(project.root)
    if rel not in [str(p) for p in projects]:
        projects.append(rel)
        data["projects"] = projects
        C.atomic_write_text(registry_path, C._yamlish.dumps(data))


@C.locked_results
def cmd_new(project: C.Project, exp_id: str, title: str) -> dict:
    if not project.experiment_dir(exp_id).is_dir():
        raise C.SkillError("实验不存在")
    base = results_dir(project, exp_id)
    base.mkdir(parents=True, exist_ok=True)
    used = 0
    for child in base.iterdir():
        if child.is_dir() and child.name.startswith(f"R-{exp_id}-"):
            try:
                used = max(used, int(child.name.rsplit("-", 1)[1]))
            except ValueError:
                continue
    result_id = f"R-{exp_id}-{used + 1:02d}"
    target = base / result_id
    target.mkdir(parents=True, exist_ok=False)
    data = {
        "id": result_id,
        "title": title,
        "experiment": exp_id,
        "created": C.ts_now(),
        "versions": [],
    }
    save_index(target / INDEX_NAME, data)
    register_project(project.kb, project)
    return {"id": result_id, "dir": str(target)}


@C.locked_results
def cmd_add_version(project: C.Project, result_id: str, files: list[str], params: str) -> dict:
    index_path = find_result(project, result_id)
    data = load_index(index_path)
    params_hash = C.sha256_text(params or "")[:12]

    if not files or len({Path(f).name for f in files}) != len(files):
        raise C.SkillError("结果文件不能为空或包含重复文件名；请拆成不同结果项")
    hashes = {}
    for raw in files:
        src = Path(raw)
        if not src.is_file():
            raise C.SkillError(f"结果文件不存在：{src}")
        hashes[src.name] = C.sha256_file(src)

    versions = data.setdefault("versions", [])
    if versions:
        latest = versions[-1]
        latest_files = {f.get("name"): f.get("sha256") for f in latest.get("files") or []}
        if latest.get("params_hash") == params_hash and latest_files == hashes:
            return {
                "id": result_id,
                "version": latest.get("version"),
                "noop": True,
                "message": "参数与文件均未变化，未创建新版本；标记保持不变",
            }

    version_no = max([int(v.get("version") or 0) for v in versions] + [0]) + 1
    version_dir = index_path.parent / f"v{version_no}"
    version_dir.mkdir(parents=True, exist_ok=True)
    recorded = []
    for raw in files:
        src = Path(raw)
        target = version_dir / src.name
        if target.exists() and C.sha256_file(target) != hashes[src.name]:
            raise C.SkillError(f"v{version_no} 已存在同名但内容不同的文件 {src.name}，需用户决定")
        if not target.exists():
            shutil.copy2(src, target)
        if C.sha256_file(target) != hashes[src.name]:
            raise C.SkillError("结果复制后校验失败")
        recorded.append(
            {"name": src.name, "path": f"v{version_no}/{src.name}", "sha256": hashes[src.name]}
        )

    versions.append(
        {
            "version": version_no,
            "params": params,
            "params_hash": params_hash,
            "files": recorded,
            "marked": False,
            "marked_at": None,
            "created": C.ts_now(),
        }
    )
    save_index(index_path, data)
    return {
        "id": result_id,
        "version": version_no,
        "dir": str(version_dir),
        "marked": False,
        "message": "新版本默认未标记，需由用户决定是否标记",
    }


@C.locked_results
def cmd_mark(project: C.Project, result_id: str, version: int | None, on: bool) -> dict:
    index_path = find_result(project, result_id)
    data = load_index(index_path)
    versions = data.get("versions") or []
    if not versions:
        raise C.SkillError(f"{result_id} 还没有版本，无法标记")
    target_no = version if version is not None else max(int(v.get("version") or 0) for v in versions)
    for item in versions:
        if int(item.get("version") or 0) == target_no:
            item["marked"] = bool(on)
            item["marked_at"] = C.ts_now() if on else None
            save_index(index_path, data)
            return {
                "id": result_id,
                "version": target_no,
                "marked": bool(on),
                "message": "标记仅表示用户选中，不代表统计显著或审核通过",
            }
    raise C.SkillError(f"{result_id} 没有 v{target_no}")


def _flatten(project_name: str, index_path: Path, data: dict, only_marked: bool) -> list[dict]:
    rows = []
    for item in data.get("versions") or []:
        if only_marked and not item.get("marked"):
            continue
        rows.append(
            {
                "project": project_name,
                "experiment": data.get("experiment"),
                "id": data.get("id"),
                "title": data.get("title"),
                "version": item.get("version"),
                "marked": bool(item.get("marked")),
                "marked_at": item.get("marked_at"),
                "params": item.get("params"),
                "dir": str(index_path.parent / f"v{item.get('version')}"),
            }
        )
    return rows


@C.locked_results
def cmd_list(project: C.Project, only_marked: bool) -> dict:
    rows = []
    for exp_dir in sorted(project.experiments.glob("*/")):
        for index_path in sorted((exp_dir / C.RESULT_DIR).glob(f"*/{INDEX_NAME}")):
            rows += _flatten(project.name, index_path, load_index(index_path), only_marked)
    return {"count": len(rows), "results": rows}


def cmd_filter(kb: Path, only_marked: bool) -> dict:
    registry_path = kb / C.RESULT_INDEX
    if not registry_path.is_file():
        return {"count": 0, "results": [], "message": "知识库尚未登记任何项目"}
    data = C._yamlish.loads(registry_path.read_text(encoding="utf-8")) or {}
    rows = []
    for rel in data.get("projects") or []:
        root = Path(rel)
        if not root.is_absolute():
            root = (kb / rel).resolve()
        cfg = root / C.CONFIG_NAME
        if not cfg.is_file():
            continue
        try:
            project = C.Project(root)
        except C.SkillError:
            continue
        for exp_dir in sorted(project.experiments.glob("*/")):
            for index_path in sorted((exp_dir / C.RESULT_DIR).glob(f"*/{INDEX_NAME}")):
                rows += _flatten(project.name, index_path, load_index(index_path), only_marked)
    return {"count": len(rows), "results": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="实验工作流结果项与版本")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="新建结果项")
    p_new.add_argument("--project", default=None)
    p_new.add_argument("--experiment", required=True)
    p_new.add_argument("--title", required=True)

    p_ver = sub.add_parser("add-version", help="新增结果版本")
    p_ver.add_argument("--project", default=None)
    p_ver.add_argument("--id", required=True)
    p_ver.add_argument("--files", nargs="+", required=True)
    p_ver.add_argument("--params", default="")

    p_mark = sub.add_parser("mark", help="标记/取消标记版本")
    p_mark.add_argument("--project", default=None)
    p_mark.add_argument("--id", required=True)
    p_mark.add_argument("--version", type=int, default=None)
    p_mark.add_argument("--off", action="store_true")

    p_list = sub.add_parser("list", help="列出本项目结果")
    p_list.add_argument("--project", default=None)
    p_list.add_argument("--marked", action="store_true")

    p_filter = sub.add_parser("filter", help="跨项目筛选")
    p_filter.add_argument("--kb", required=True)
    p_filter.add_argument("--marked", action="store_true")

    args = parser.parse_args()
    try:
        if args.cmd == "filter":
            C.ok(**cmd_filter(Path(args.kb).resolve(), args.marked))
            return
        project = C.Project(C.find_project_root(args.project))
        if args.cmd == "new":
            C.ok(**cmd_new(project, args.experiment, args.title))
        elif args.cmd == "add-version":
            C.ok(**cmd_add_version(project, args.id, args.files, args.params))
        elif args.cmd == "mark":
            C.ok(**cmd_mark(project, args.id, args.version, not args.off))
        else:
            C.ok(**cmd_list(project, args.marked))
    except (C.SkillError, OSError, ValueError, TypeError, KeyError) as exc:
        C.die(str(exc), code="skill_error")
    except C._yamlish.YamlError as exc:
        C.die(f"YAML 解析失败：{exc}", code="yaml_error")


if __name__ == "__main__":
    main()
