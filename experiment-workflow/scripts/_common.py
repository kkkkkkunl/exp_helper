"""实验工作流脚本公共层：配置定位、路径、加锁、原子写、frontmatter。

所有脚本都只依赖标准库，避免用户在实验机上 pip install。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import tempfile
import functools
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _yamlish

try:  # 控制台统一 UTF-8，避免 Windows cp936 下中文乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

CN_TZ = timezone(timedelta(hours=8))
CONFIG_NAME = "experiment-project.yaml"
STATE_DIR = ".experiment-workflow"
EXP_DIR = "实验"
RECORD_NAME = "实验记录.md"
ATTACH_DIR = "原始附件"
REPORT_NAME = "汇报.pptx"
RESULT_DIR = "results"
RESULT_INDEX = "_results-index.yaml"

# 单位维度与基准倍数：只用于同维度换算，跨维度必须拒绝
UNIT_BASE = {
    "kg": ("mass", 1e3),
    "g": ("mass", 1.0),
    "mg": ("mass", 1e-3),
    "ug": ("mass", 1e-6),
    "ng": ("mass", 1e-9),
    "L": ("volume", 1.0),
    "mL": ("volume", 1e-3),
    "uL": ("volume", 1e-6),
    "nL": ("volume", 1e-9),
}

TYPE_SIGN = {    "create": +1,
    "consume": -1,
    "return": +1,
    "aliquot_out": -1,
    "aliquot_in": +1,
    "mixed_out": -1,
    "mixed_in": +1,
    "deplete": -1,
    "discard": -1,
    "transfer": 0,
    "adjust": 0,
}
TYPE_LABEL = {
    "create": "新增入库",
    "consume": "取用",
    "return": "归还",
    "aliquot_out": "分装转出",
    "aliquot_in": "分装转入",
    "mixed_out": "混合转出",
    "mixed_in": "混合转入",
    "deplete": "耗尽",
    "discard": "废弃",
    "transfer": "转移",
    "adjust": "事实更正",
}


class SkillError(RuntimeError):
    """可预期的业务错误，脚本以结构化 JSON 报告给模型。"""


# ---------------------------------------------------------------- 时间


def now_cn() -> datetime:
    return datetime.now(CN_TZ)


def fmt_ts(dt: datetime | None = None) -> str:
    dt = (dt or now_cn()).astimezone(CN_TZ)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")


def ts_now() -> str:
    return fmt_ts()


# ---------------------------------------------------------------- 输出


def emit(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def die(message: str, code: str = "error", **extra) -> "None":
    emit({"ok": False, "code": code, "message": message, **extra})
    raise SystemExit(1)


def ok(**payload) -> None:
    emit({"ok": True, **payload})


# ---------------------------------------------------------------- 文件


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FileLock:
    """OS advisory lock, released on process exit; lock file is never unlinked."""
    def __init__(self, path, timeout=15.0, stale=None):
        self.path, self.timeout = Path(path), timeout

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = open(self.path, "a+b")
        self.stream.seek(0, 2)
        if not self.stream.tell():
            self.stream.write(b"0")
            self.stream.flush()
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self.stream.seek(0)
                    msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    self.stream.close()
                    raise SkillError(f"无法获取锁 {self.path}")
                time.sleep(0.05)

    def __exit__(self, *exc):
        if os.name == "nt":
            import msvcrt
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.stream, fcntl.LOCK_UN)
        self.stream.close()


def json_text(data):
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def recover_stock(project):
    """Caller holds stock lock. Finish a durable, fully prevalidated transaction."""
    journal = project.samples / ".transaction.json"
    if journal.is_file():
        data = json.loads(journal.read_text(encoding="utf-8"))
        for entry in data["writes"]:
            atomic_write_text(Path(entry["path"]), entry["text"])
        journal.unlink()


def stock_transaction(project, writes):
    journal = project.samples / ".transaction.json"
    atomic_write_text(journal, json_text({"writes": [
        {"path": str(Path(path).resolve()), "text": value} for path, value in writes.items()
    ]}))
    try:
        recover_stock(project)
    except OSError as exc:
        raise SkillError("提交日志已保存，写入中断；修复存储后重试，脚本将先恢复整批提交") from exc


class StockLock(FileLock):
    def __init__(self, project):
        super().__init__(project.samples / ".stock.lock")
        self.project = project

    def __enter__(self):
        super().__enter__()
        try:
            recover_stock(self.project)
        except Exception:
            super().__exit__(None, None, None)
            raise
        return self


def locked_stock(fn):
    @functools.wraps(fn)
    def wrapped(project, *args, **kwargs):
        with StockLock(project):
            return fn(project, *args, **kwargs)
    return wrapped


def locked_results(fn):
    @functools.wraps(fn)
    def wrapped(project, *args, **kwargs):
        with FileLock(project.kb / ".results.lock"):
            return fn(project, *args, **kwargs)
    return wrapped


def safe_id(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", str(value)):
        raise SkillError(f"非法编号：{value!r}")
    return str(value)


# ---------------------------------------------------------------- frontmatter


def split_frontmatter(text: str) -> tuple[dict | None, str]:
    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return None, text
    lines = text.split("\n")
    if lines[0].strip() != "---":
        return None, text
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            raw = "\n".join(lines[1:idx])
            body = "\n".join(lines[idx + 1 :]).lstrip("\n")
            data = _yamlish.loads(raw) or {}
            if not isinstance(data, dict):
                raise SkillError("frontmatter 必须是映射")
            return data, body
    raise SkillError("frontmatter 缺少结束的 ---")


def read_md(path: Path) -> tuple[dict, str]:
    data, body = split_frontmatter(Path(path).read_text(encoding="utf-8"))
    return (data or {}), body


def write_md(path: Path, front: dict, body: str) -> None:
    text = "---\n" + _yamlish.dumps(front) + "---\n\n" + body.lstrip("\n")
    atomic_write_text(path, text)


# ---------------------------------------------------------------- 项目


def find_project_root(start: Path | str | None = None) -> Path:
    cur = Path(start or os.getcwd()).resolve()
    if cur.is_file():
        cur = cur.parent
    for candidate in [cur, *cur.parents]:
        if (candidate / CONFIG_NAME).is_file():
            return candidate
    raise SkillError(
        f"从 {cur} 向上未找到 {CONFIG_NAME}。"
        "请让用户确认项目根目录，或先按 assets/experiment-project.template.yaml 建立配置。"
    )


class Project:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        cfg_path = self.root / CONFIG_NAME
        if not cfg_path.is_file():
            raise SkillError(f"缺少配置文件 {cfg_path}")
        try:
            cfg = _yamlish.loads(cfg_path.read_text(encoding="utf-8"))
        except _yamlish.YamlError as exc:
            raise SkillError(f"{CONFIG_NAME} 解析失败：{exc}") from exc
        if not isinstance(cfg, dict):
            raise SkillError(f"{CONFIG_NAME} 顶层必须是映射")
        self.cfg = cfg
        self.name = str(cfg.get("project") or self.root.name)

        kb = cfg.get("knowledge_base")
        if not kb:
            raise SkillError("配置缺少 knowledge_base（相对项目根的知识库路径）")
        self.kb = (self.root / str(kb)).resolve()

        lib = cfg.get("sample_library") or "samples"
        self.samples = (self.kb / str(lib)).resolve()

        self.experiments = self.root / EXP_DIR
        self.state = self.root / STATE_DIR

    # -- 校验

    def validate(self, scope="record", skill=None) -> list[str]:
        problems = []
        if scope not in ("record", "inventory", "analysis", "report", "calendar", "all"):
            return ["未知校验范围"]
        if scope in ("inventory", "all"):
            if not self.kb.is_dir(): problems.append(f"知识库不存在：{self.kb}")
            if not self.samples.is_dir(): problems.append(f"样本库不存在：{self.samples}")
        if scope in ("record", "all"):
            import calendar_bridge
            try: calendar_bridge.tz(self.cfg.get('timezone', 'Asia/Shanghai'))
            except SkillError as exc: problems.append(str(exc))
            templates = self.cfg.get("method_templates") or []
            for tpl in templates:
                if not isinstance(tpl, dict) or not tpl.get("path"):
                    problems.append("方法模板缺少 path")
                elif not (self.root / str(tpl["path"])).is_file():
                    problems.append(f"方法模板不存在：{tpl['path']}")
                elif tpl.get('format', 'plain') not in ('plain', 'staged'):
                    problems.append('模板 format 必须为 plain 或 staged')
                elif tpl.get('format') == 'staged':
                    import stage_templates
                    try: stage_templates.load(self, tpl)
                    except (SkillError, ValueError) as exc: problems.append(str(exc))
            if sum(bool(t.get("default")) for t in templates if isinstance(t, dict)) > 1:
                problems.append("存在多个默认方法模板")
        if scope in ("report", "all"):
            ppt = self.cfg.get("ppt_template")
            if ppt and not (self.root / str(ppt)).is_file(): problems.append(f"PPT 模板不存在：{ppt}")
        if scope == "analysis" and not skill:
            problems.append("分析校验需指定 --skill，仅校验目标 skill")
        if scope in ("analysis", "all"):
            import skill_store
            names = [skill] if skill else list(skill_store.read_index(self)["skills"])
            for name in names:
                if not skill_store.resolve(self, name)["available"]:
                    problems.append(f"分析 skill 不可用或索引过期：{name}")
        if scope in ('calendar', 'all'):
            import calendar_bridge
            problems.extend(calendar_bridge.validate_config(self.cfg.get('calendar') or {}))
        return problems

    def default_template(self) -> dict | None:
        tpls = self.cfg.get("method_templates") or []
        flagged = [t for t in tpls if t.get("default")]
        if len(flagged) == 1:
            return flagged[0]
        if len(tpls) == 1:
            return tpls[0]
        return None

    def template_by_name(self, name: str) -> dict:
        for tpl in self.cfg.get("method_templates") or []:
            if str(tpl.get("name")) == name:
                return tpl
        raise SkillError(f"未找到方法模板 {name!r}")

    def experiment_dir(self, exp_id: str) -> Path:
        return self.experiments / safe_id(exp_id)

    def sample_path(self, sample_id: str) -> Path:
        return self.samples / f"{safe_id(sample_id)}.md"

    # -- 单位

    def convert_factor(self, src: str, dst: str) -> float:
        """同维度且配置显式声明时才允许换算；跨质量/体积一律拒绝。"""
        if src == dst:
            return 1.0
        src = str(src).strip()
        dst = str(dst).strip()
        if src not in UNIT_BASE or dst not in UNIT_BASE:
            raise SkillError(f"未知计量单位 {src!r}→{dst!r}，请先确认单位后手工处理")
        dim_s, factor_s = UNIT_BASE[src]
        dim_d, factor_d = UNIT_BASE[dst]
        if dim_s != dim_d:
            raise SkillError(
                f"拒绝把 {src} 换算成 {dst}：质量与体积之间没有密度依据，不得换算。"
                "请向用户确认密度，或改为分别记录。"
            )
        allowed = set()
        for pair in (self.cfg.get("units") or {}).get("convert") or []:
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                allowed.add((str(pair[0]).strip(), str(pair[1]).strip()))
        if (src, dst) not in allowed and (dst, src) not in allowed:
            raise SkillError(
                f"配置未声明 {src} 与 {dst} 可换算。请在 units.convert 中显式声明，或由用户手工确认数量。"
            )
        return factor_s / factor_d


# ---------------------------------------------------------------- 样本台账


def iter_samples(project: Project):
    if not project.samples.is_dir():
        return
    for path in sorted(project.samples.glob("*.md")):
        if path.name.startswith("_"):
            continue
        try:
            front, body = read_md(path)
        except SkillError:
            continue
        if front.get("id"):
            yield path, front, body


def load_sample(project: Project, sample_id: str) -> tuple[Path, dict, str]:
    path = project.sample_path(sample_id)
    if not path.is_file():
        raise SkillError(
            f"样本库中没有 {sample_id}。不得按名称相似推测取用对象，请向用户确认具体编号。"
        )
    front, body = read_md(path)
    if front.get("id") != sample_id:
        raise SkillError(f"{path} 的 frontmatter id 与文件名不一致")
    return path, front, body


def render_sample_body(front: dict) -> str:
    lines = [f"# {front.get('id', '')}", ""]
    concs = front.get("concentrations") or []
    if concs:
        lines += ["## 浓度", "", "| 组分 | 值 | 单位 | 来源 |", "|---|---|---|---|"]
        for c in concs:
            origin = {'measured': '实测', 'calculated': '计算', 'unmeasured': '未测定', 'not_applicable': '不适用'}.get(str(c.get('origin')), '来源未知')
            lines.append(
                f"| {c.get('analyte') or '-'} | {c.get('value')} | {c.get('unit') or '-'} | {origin} |"
            )
        lines.append("")

    lines += ["## 变更历史", "", "| 时间 | 类型 | 数量 | 实验 | 说明 |", "|---|---|---|---|---|"]
    for h in front.get("history") or []:
        delta = h.get("delta")
        qty = "" if delta in (None, 0) else f"{delta:+g} {h.get('unit') or front.get('unit') or ''}".strip()
        lines.append(
            f"| {h.get('at') or '-'} | {TYPE_LABEL.get(str(h.get('type')), h.get('type'))} | "
            f"{qty or '-'} | {h.get('experiment') or '-'} | {h.get('note') or '-'} |"
        )
    if not front.get("history"):
        lines.append("| - | - | - | - | 尚无变更记录 |")
    lines.append("")

    exps = front.get("experiments") or []
    if exps:
        lines += ["## 相关实验", ""]
        lines += [f"- [[{e}]]" for e in exps]
        lines.append("")

    lines += [
        "> 本文件由 experiment-workflow 维护：frontmatter 为准，正文表格由脚本重绘。",
        "> 手工修改请只改 frontmatter；改正文会在下次写入时被覆盖。",
        "",
    ]
    return "\n".join(lines)


def sample_text(front):
    return "---\n" + _yamlish.dumps(front) + "---\n\n" + render_sample_body(front)


def save_sample(path: Path, front: dict) -> None:
    write_md(path, front, render_sample_body(front))
