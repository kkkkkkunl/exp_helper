"""编号分配：实验编号、样本基础编号、分装子编号。

编号是全局唯一且不可复用的，因此分配必须原子化：
扫描已有编号 → 取最大值 +1 → 立即落盘，全过程持有文件锁。
并发会话会互相等待，而不是撞号。

用法
----
python allocate_id.py experiment --project <项目根>
python allocate_id.py sample     --project <项目根> --date 2026-10-31
python allocate_id.py aliquot    --project <项目根> --parent 20261031-A --count 3
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import _common as C

LETTER_RE = re.compile(r"^(\d{8})-([A-Z]+)$")
EXP_RE = re.compile(r"^\d{8}-\d{6}$")


def index_to_letters(n: int) -> str:
    """0→A, 25→Z, 26→AA …（Excel 列风格，不跳字母）。"""
    out = ""
    n += 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def letters_to_index(text: str) -> int:
    value = 0
    for ch in text:
        value = value * 26 + (ord(ch) - 64)
    return value - 1


def scan_base_ids(project: C.Project) -> dict[str, int]:
    """返回 {日期: 该日已用的最大字母序号}。"""
    used: dict[str, int] = {}
    for path, front, _ in C.iter_samples(project):
        match = LETTER_RE.match(str(front.get("id")))
        if not match:
            continue
        day, letters = match.groups()
        used[day] = max(used.get(day, -1), letters_to_index(letters))
    return used


def allocate_experiment(project: C.Project, reservation_key=None) -> str:
    """实验编号取首次创建时的北京时间，精确到秒；同秒则等到下一秒。"""
    registry = project.state / "experiments.yaml"
    with C.FileLock(project.state / "ids.lock"):
        known: list[str] = []
        data = {}
        if registry.is_file():
            data = C._yamlish.loads(registry.read_text(encoding="utf-8")) or {}
            known = [str(x.get("id")) for x in (data.get("experiments") or []) if isinstance(x, dict)]
        reservations = data.get('action_experiments') or {}
        if reservation_key and reservation_key in reservations:
            return reservations[reservation_key]
        for _ in range(5):
            candidate = C.now_cn().strftime("%Y%m%d-%H%M%S")
            if candidate not in known and not project.experiment_dir(candidate).exists():
                break
            time.sleep(1.05 - (time.time() % 1))
        else:
            raise C.SkillError("连续 5 次分配都撞号，请稍后重试")

        exp_dir = project.experiment_dir(candidate)
        (exp_dir / C.ATTACH_DIR).mkdir(parents=True, exist_ok=True)
        known.append(candidate)
        if reservation_key: reservations[reservation_key] = candidate
        C.atomic_write_text(
            registry,
            C._yamlish.dumps(
                {"experiments": [{"id": i} for i in known], 'action_experiments': reservations}
            ),
        )
        return candidate


def allocate_sample(project: C.Project, day: str, kind: str = "base", reservation_key=None, material=None) -> str:
    """样本基础编号 = 实际形成日期 + 当日全局递增字母。"""
    if not re.fullmatch(r"\d{8}", day):
        raise C.SkillError(f"日期需为 YYYYMMDD，收到 {day!r}")
    with C.StockLock(project):
        request_path = project.samples / '.sample-requests.json'
        requests = json.loads(request_path.read_text(encoding='utf-8')) if request_path.exists() else {}
        fingerprint = C.sha256_text(C.json_text([day, kind, material]))
        if reservation_key and reservation_key in requests:
            known = requests[reservation_key]
            if known['fingerprint'] != fingerprint: raise C.SkillError('产物操作标识已用于不同材料')
            C.load_sample(project, known['id'])
            return known['id']
        if material:
            if set(material) - {'material_type', 'produced_by', 'provenance'}: raise C.SkillError('非法材料元信息')
            producer = material.get('produced_by')
            if producer:
                if not all(producer.get(k) for k in ('experiment', 'stage', 'attempt', 'inputs')):
                    raise C.SkillError('产物须有实验、阶段、尝试和输入样品')
                if not project.experiment_dir(producer['experiment']).is_dir(): raise C.SkillError('产物实验不存在')
                for sid in producer['inputs']: C.load_sample(project, sid)
        reservations = project.samples / ".allocated-ids.json"
        reserved = json.loads(reservations.read_text(encoding="utf-8")) if reservations.is_file() else []
        used = scan_base_ids(project)
        for known in reserved:
            match = LETTER_RE.match(known)
            if match:
                date, letters = match.groups()
                used[date] = max(used.get(date, -1), letters_to_index(letters))
        next_index = used.get(day, -1) + 1
        sample_id = f"{day}-{index_to_letters(next_index)}"
        if project.sample_path(sample_id).exists():
            raise C.SkillError(f"{sample_id} 已存在，拒绝覆盖")
        formed = f"{day[:4]}-{day[4:6]}-{day[6:]}"
        front = {
            "id": sample_id,
            "kind": kind,
            "status": "in_stock",
            "location": None,
            "quantity": None,
            "unit": None,
            "concentrations": [],
            "treatment": None,
            "formed_on": formed,
            "parent": None,
            "sources": [],
            "experiments": [],
            "history": [],
        }
        front.update(material or {})
        writes = {reservations: C.json_text(reserved + [sample_id]), project.sample_path(sample_id): C.sample_text(front)}
        if reservation_key:
            requests[reservation_key] = {'id': sample_id, 'fingerprint': fingerprint}
            writes[request_path] = C.json_text(requests)
        C.stock_transaction(project, writes)
        return sample_id


def allocate_aliquots(project: C.Project, parent_id: str, count: int) -> list[str]:
    """分装沿用来源编号并追加数字，同层递增且不回收。"""
    if count < 1:
        raise C.SkillError("分装数量必须 ≥ 1")
    with C.StockLock(project):
        parent_path, parent, _ = C.load_sample(project, parent_id)
        child_re = re.compile(rf"^{re.escape(parent_id)}-(\d+)$")
        max_child = 0
        for path, front, _ in C.iter_samples(project):
            match = child_re.match(str(front.get("id")))
            if match:
                max_child = max(max_child, int(match.group(1)))

        reservations = project.samples / ".allocated-ids.json"
        reserved = json.loads(reservations.read_text(encoding="utf-8")) if reservations.is_file() else []
        for known in reserved:
            match = child_re.match(known)
            if match:
                max_child = max(max_child, int(match.group(1)))
        children: list[str] = []
        for offset in range(1, count + 1):
            child_id = f"{parent_id}-{max_child + offset}"
            if project.sample_path(child_id).exists():
                raise C.SkillError(f"{child_id} 已存在，拒绝覆盖")
            reserved.append(child_id)
            C.atomic_write_text(reservations, C.json_text(reserved))
            front = {
                "id": child_id,
                "kind": "aliquot",
                "status": "in_stock",
                "location": parent.get("location"),
                "quantity": None,
                "unit": parent.get("unit"),
                "concentrations": [dict(c) for c in (parent.get("concentrations") or [])],
                "treatment": parent.get("treatment"),
                "formed_on": C.now_cn().strftime("%Y-%m-%d"),
                "parent": parent_id,
                "sources": [parent_id],
                "experiments": [],
                "history": [],
            }
            C.save_sample(project.sample_path(child_id), front)
            children.append(child_id)
        return children


def allocate_product(project, day, experiment, stage, attempt, inputs, material_type, operation_id):
    if not operation_id or not material_type or not inputs or not isinstance(attempt, int) or attempt < 1:
        raise C.SkillError('产物缺少稳定操作、材料类型、输入或有效尝试')
    import workflow as W
    import stage_templates as T
    state = W.peek_state(project, experiment)
    if not state.get('template_snapshot'): raise C.SkillError('产物分配需要已选定的阶段模板')
    definition = T.stage(T.frozen(project, state['template_snapshot']), stage)
    if material_type not in definition['outputs']: raise C.SkillError('材料类型未声明为该阶段产物')
    for sid in inputs:
        progress = state['stage_progress'].get(sid, {}).get(stage)
        if not progress or progress['attempt'] != attempt or not any(x['executed'] for x in progress['steps'].values()):
            raise C.SkillError('输入样品没有对应已执行的阶段尝试')
    return allocate_sample(project, day, reservation_key=f'{experiment}:{operation_id}', material={
        'material_type': material_type, 'produced_by': {'experiment': experiment, 'stage': stage,
        'attempt': attempt, 'inputs': inputs, 'operation_id': operation_id}})


def main() -> None:
    parser = argparse.ArgumentParser(description="实验工作流编号分配")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_exp = sub.add_parser("experiment", help="分配实验编号")
    p_exp.add_argument("--project", default=None)

    p_sample = sub.add_parser("sample", help="分配样本基础编号")
    p_sample.add_argument("--project", default=None)
    p_sample.add_argument("--date", required=True, help="实际形成日期 YYYYMMDD")
    p_sample.add_argument("--kind", default="base", choices=["base", "mixed"])
    p_product = sub.add_parser('product', help='保留已声明阶段产物编号；数量另经库存确认')
    p_product.add_argument('--project'); p_product.add_argument('--date', required=True)
    p_product.add_argument('--experiment', required=True); p_product.add_argument('--stage', required=True)
    p_product.add_argument('--attempt', type=int, required=True); p_product.add_argument('--inputs', nargs='+', required=True)
    p_product.add_argument('--material-type', required=True); p_product.add_argument('--operation-id', required=True)

    p_ali = sub.add_parser("aliquot", help="为来源样本分配分装子编号")
    p_ali.add_argument("--project", default=None)
    p_ali.add_argument("--parent", required=True)
    p_ali.add_argument("--count", type=int, default=1)

    args = parser.parse_args()
    try:
        project = C.Project(C.find_project_root(args.project))
        if args.cmd == "experiment":
            exp_id = allocate_experiment(project)
            C.ok(id=exp_id, dir=str(project.experiment_dir(exp_id)))
        elif args.cmd == "sample":
            sample_id = allocate_sample(project, args.date, args.kind)
            C.ok(id=sample_id, path=str(project.sample_path(sample_id)),
                 warning="初始数量未知，需在对话中向用户确认，不得填 0")
        elif args.cmd == 'product':
            sid = allocate_product(project, args.date, args.experiment, args.stage, args.attempt, args.inputs,
                                   args.material_type, args.operation_id)
            C.ok(id=sid, path=str(project.sample_path(sid)), warning='仅保留产物身份，实际数量与浓度须经库存清单确认')
        else:
            children = allocate_aliquots(project, args.parent, args.count)
            C.ok(children=children, parent=args.parent,
                 warning="分装子管的实际数量需由用户确认后再提交库存变更清单")
    except C.SkillError as exc:
        C.die(str(exc), code="skill_error")
    except C._yamlish.YamlError as exc:
        C.die(f"YAML 解析失败：{exc}", code="yaml_error")


if __name__ == "__main__":
    main()
