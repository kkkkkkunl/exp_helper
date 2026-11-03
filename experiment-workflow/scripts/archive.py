"""原始附件归档：保内容、保文件名、去重、冲突暂停。

归档是破坏性操作（移动而非复制），因此：
1. 先复制到目标，校验 sha256 一致，才删除源文件；
2. 同名或同内容已存在时**不覆盖、不改名**，标记为待用户决定；
3. 单项失败不影响其他项，符合"继续其他整理"的要求。

用法
----
python archive.py move --project <根> --experiment <编号> --files a.png b.csv
python archive.py move --project <根> --experiment <编号> --from-dir ./inbox
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import _common as C

MAX_PATH = 250


def _link(project: C.Project, target: Path) -> dict:
    """Obsidian 链接：知识库内用 vault 相对 wikilink；库外退回项目相对路径并标记。"""
    resolved = target.resolve()
    try:
        rel = resolved.relative_to(project.kb)
        return {"link": f"[[{rel.as_posix()}]]", "outside_vault": False}
    except ValueError:
        pass
    try:
        rel = resolved.relative_to(project.root)
        return {
            "link": rel.as_posix(),
            "outside_vault": True,
            "note": "项目目录不在知识库内，Obsidian 无法解析该链接；建议把项目放进 vault",
        }
    except ValueError:
        return {"link": str(resolved), "outside_vault": True,
                "note": "文件在知识库与项目之外，只能使用绝对路径"}


def _archive_one(project: C.Project, exp_id: str, src: Path) -> dict:
    dest_dir = project.experiment_dir(exp_id) / C.ATTACH_DIR
    if not dest_dir.is_dir():
        dest_dir.mkdir(parents=True, exist_ok=True)

    if not src.is_file():
        return {"source": str(src), "status": "blocked", "reason": "源文件不存在"}
    src_hash = C.sha256_file(src)
    target = dest_dir / src.name

    if len(str(target)) > MAX_PATH:
        return {
            "source": str(src),
            "status": "blocked",
            "reason": f"归档后路径长度 {len(str(target))} 超过 {MAX_PATH}，"
            "请与用户确认是否缩短实验编号目录或文件名",
        }

    # 同名冲突
    if target.exists():
        if C.sha256_file(target) == src_hash:
            return {
                "source": str(src),
                "status": "duplicate",
                "target": str(target),
                "reason": "目标已存在内容完全相同的文件，未重复归档；源文件保留",
            }
        return {
            "source": str(src),
            "status": "blocked",
            "reason": f"目标目录已有同名但内容不同的文件 {target.name}，"
            "不得自动改名或覆盖，需用户决定保留哪一个",
        }

    # 同内容不同名
    for existing in dest_dir.iterdir():
        if existing.is_file() and existing.name != src.name and C.sha256_file(existing) == src_hash:
            return {
                "source": str(src),
                "status": "duplicate",
                "target": str(existing),
                "reason": f"与已归档文件 {existing.name} 内容相同（可能重复上传），需用户确认是否仍需保留",
            }

    tmp = target.with_name(target.name + ".part")
    shutil.copy2(src, tmp)
    if C.sha256_file(tmp) != src_hash:
        tmp.unlink(missing_ok=True)
        return {"source": str(src), "status": "blocked", "reason": "复制后校验失败，源文件未删除"}
    tmp.replace(target)

    try:
        src.unlink()
        moved = True
    except OSError as exc:
        moved = False
        C.atomic_write_text(
            dest_dir / "_未删除源文件.txt",
            f"{src}\n原因：{exc}\n请手工确认后删除源文件。\n",
        )

    return {
        "source": str(src),
        "status": "archived",
        "target": str(target),
        "name": target.name,
        "sha256": src_hash,
        "source_removed": moved,
        **_link(project, target),
    }


def archive_one(project, exp_id, src):
    with C.FileLock(project.experiment_dir(exp_id) / C.STATE_DIR / "archive.lock"):
        return _archive_one(project, exp_id, src)


def main() -> None:
    parser = argparse.ArgumentParser(description="原始附件归档")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("move", help="归档原始附件")
    p.add_argument("--project", default=None)
    p.add_argument("--experiment", required=True)
    p.add_argument("--files", nargs="*", default=[])
    p.add_argument("--from-dir", default=None, help="归档该目录下的全部文件")
    args = parser.parse_args()

    try:
        project = C.Project(C.find_project_root(args.project))
        if not project.experiment_dir(args.experiment).is_dir():
            C.die(f"实验目录不存在：{project.experiment_dir(args.experiment)}", code="not_found")

        sources: list[Path] = [Path(f) for f in args.files]
        if args.from_dir:
            sources += [p for p in sorted(Path(args.from_dir).iterdir()) if p.is_file()]
        if not sources:
            C.die("没有待归档文件", code="no_input")

        results = [archive_one(project, args.experiment, src) for src in sources]
        blocked = [r for r in results if r["status"] == "blocked"]
        archived = [r for r in results if r["status"] == "archived"]
        C.ok(
            archived=archived,
            blocked=blocked,
            duplicates=[r for r in results if r["status"] == "duplicate"],
            message=(
                "全部归档完成" if not blocked else
                "部分文件需要用户决定后才能继续，其余已完成归档"
            ),
        )
    except C.SkillError as exc:
        C.die(str(exc), code="skill_error")


if __name__ == "__main__":
    main()
