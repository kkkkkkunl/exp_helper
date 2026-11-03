"""库存事件：稳定 event_id、整批快照校验、确认指纹和可恢复提交。

plan 生成待确认清单；commit 必须携带 plan-hash 与 confirmed-by。
样品库共享锁覆盖读写与恢复。已提交事件重试不会重复扣减。
分装/混合需 group_id。示例和迁移见 references/v2-operations.md。
"""

from __future__ import annotations

import argparse
import json
import math
import copy
from pathlib import Path

import _common as C

PLAN_NAME = "库存变更清单.md"
NEGATIVE_TYPES = {"consume", "deplete", "discard", "aliquot_out", "mixed_out"}


def _round(value: float) -> float:
    return round(float(value), 6)


def load_items(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise C.SkillError("items 文件必须是变更项数组且不能为空")
    return data


def idempotency_key(exp, item):
    event = item.get("event_id")
    if not isinstance(event, str) or not event.strip():
        raise C.SkillError("每项必须有 event_id；真实新操作用新 ID，重试沿用原 ID")
    return C.sha256_text(C.json_text([exp, event]))


def event_fingerprint(raw):
    return C.sha256_text(json.dumps(raw, ensure_ascii=False, sort_keys=True, allow_nan=False))


def concentrations(values):
    if not isinstance(values, list): raise C.SkillError('concentrations 须为数组')
    for value in values:
        if not isinstance(value, dict) or not value.get('analyte'):
            raise C.SkillError('浓度缺少测量对象')
        origin = value.get('origin')
        if origin in ('unmeasured', 'not_applicable'):
            if value.get('value') is not None: raise C.SkillError('未测定浓度不得同时填写数值')
            continue
        raw = value.get('value')
        if origin not in ('measured', 'calculated') or isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw) or raw < 0 or not value.get('unit'):
            raise C.SkillError('浓度须有非负有限值、单位及实测/计算来源')
        if origin == 'calculated' and not value.get('basis'):
            raise C.SkillError('计算浓度必须提供计算依据')
    return copy.deepcopy(values)


def normalize(project: C.Project, exp_id: str, raw: dict, projection: dict) -> tuple[dict, dict]:
    """把一条原始变更项校验成可执行项，并返回该样本的批内投影状态。"""
    sample_id = str(raw.get("sample") or "").strip()
    if not sample_id:
        raise C.SkillError(f"变更项缺少 sample：{raw!r}")
    kind = str(raw.get("type") or "").strip()
    if kind not in C.TYPE_SIGN:
        raise C.SkillError(f"未知变更类型 {kind!r}，允许：{'、'.join(C.TYPE_SIGN)}")

    _, front, _ = C.load_sample(project, sample_id)
    event_key = idempotency_key(exp_id, raw)

    # 批内投影优先：同一份清单里先入库、后取用是正常写法
    proj = projection.get(sample_id) or {}
    current = proj.get("quantity", front.get("quantity"))
    stock_unit = proj.get("unit", front.get("unit"))
    location = proj.get("location", front.get("location"))
    status = proj.get("status", front.get("status"))

    unit = str(raw.get("unit") or stock_unit or "").strip() or None
    delta = raw.get("delta")

    if kind == 'adjust':
        if not raw.get('note') or not (raw.get('correction_of') or raw.get('basis')):
            raise C.SkillError('更正必须有理由及原事件或来源依据')
        original = raw.get('correction_of')
        if original and not any(h.get('event_id') == original.get('event_id') and h.get('experiment') == original.get('experiment') for h in front.get('history', [])):
            raise C.SkillError('更正引用的原事件不在该样品历史中')
        after = raw.get('quantity', current)
        unknown_metadata_only = after is None and 'quantity' not in raw and ('metadata' in raw or 'concentrations' in raw)
        if not unknown_metadata_only and (isinstance(after, bool) or not isinstance(after, (int, float)) or not math.isfinite(after) or after < 0):
            raise C.SkillError('更正后数量必须为非负有限值')
        if not unit and not unknown_metadata_only: raise C.SkillError('更正数量缺少单位')
        if stock_unit and unit != stock_unit and not unknown_metadata_only:
            after *= project.convert_factor(unit, stock_unit)
        unit = stock_unit or unit
        delta = 0 if unknown_metadata_only else after - current if current is not None else after
    elif kind == "transfer":
        if not raw.get("location"):
            raise C.SkillError("transfer 必须给出 location")
        delta = 0.0
    else:
        if delta is None:
            raise C.SkillError(f"{sample_id} 的 {kind} 缺少 delta")
        if isinstance(delta, bool):
            raise C.SkillError("delta 不能为布尔值")
        delta = float(delta)
        if not math.isfinite(delta):
            raise C.SkillError("delta 必须是有限数值")

    if C.TYPE_SIGN[kind] > 0 and delta <= 0:
        raise C.SkillError(f"{sample_id} 的 {C.TYPE_LABEL[kind]} 数量必须为正，收到 {delta}")
    if C.TYPE_SIGN[kind] < 0 and delta >= 0:
        raise C.SkillError(f"{sample_id} 的 {C.TYPE_LABEL[kind]} 数量必须为负，收到 {delta}")

    if kind == 'adjust':
        new_unit, new_location = unit, raw.get('location') or location
        new_status = status if 'quantity' not in raw else 'in_stock' if after > 0 else 'depleted'
    elif kind in ("create", "aliquot_in", "mixed_in") and current is None:
        if current is not None:
            raise C.SkillError(
                f"{sample_id} 已有起始量 {current} {stock_unit or ''}，不能重复新增；"
                "请改用 return 或先与用户核对原记录"
            )
        if not unit:
            raise C.SkillError(f"{sample_id} 新增入库缺少单位")
        after = delta
        new_status = "in_stock"
        new_unit = unit
        new_location = raw.get("location") or location
    elif kind == "transfer":
        after = current
        new_status = status
        new_unit = stock_unit
        new_location = raw.get("location")
    else:
        if kind == "create":
            raise C.SkillError("已有起始量，不能再次 create")
        if status == "discarded":
            raise C.SkillError("废弃样品不能直接恢复或取用，需单独核查")
        if current is None:
            raise C.SkillError(
                f"{sample_id} 的起始量未知，不能扣减。请向用户确认现有数量，"
                "不得从取用量反推起始量。"
            )
        if unit and stock_unit and unit != stock_unit:
            delta = delta * project.convert_factor(unit, stock_unit)
        after = _round(float(current) + delta)
        if after < 0:
            raise C.SkillError(
                f"{sample_id} 库存不足：现有 {current} {stock_unit or ''}，"
                f"本次需要 {abs(delta):g}。请向用户确认实际用量或是否有未登记入库。"
            )
        new_status = "in_stock" if after > 0 else status
        if after <= 0 and kind in NEGATIVE_TYPES:
            new_status = "discarded" if kind == "discard" else "depleted"
        new_unit = stock_unit
        new_location = location

    item = {
        "sample": sample_id,
        "type": kind,
        "delta": 0 if kind == "transfer" else _round(delta),
        "unit": new_unit or unit,
        "location": new_location,
        "note": raw.get("note"),
        "key": event_key,
        "event_id": raw["event_id"],
        "fingerprint": event_fingerprint(raw),
        "status": new_status,
        "sources": raw.get("sources"),
        "before": current,
        "after": _round(after) if after is not None else None,
    }
    if 'concentrations' in raw: item['concentrations'] = concentrations(raw['concentrations'])
    if 'metadata' in raw:
        if kind != 'adjust' or not isinstance(raw['metadata'], dict) or set(raw['metadata']) - {'material_type', 'provenance', 'produced_by'}:
            raise C.SkillError('样品来源元信息只能通过明确的事实更正修改')
        producer = raw['metadata'].get('produced_by')
        if producer:
            if not all(producer.get(k) for k in ('experiment', 'stage', 'attempt', 'inputs')):
                raise C.SkillError('更正来源缺少实验、阶段、尝试或输入')
            import lineage
            for source in producer['inputs']:
                C.load_sample(project, source)
                if source == sample_id or source in lineage.descendants(project, [sample_id]):
                    raise C.SkillError('样品来源关系不能形成循环')
        item['metadata'] = copy.deepcopy(raw['metadata'])
        item['metadata_before'] = {k: copy.deepcopy(front.get(k)) for k in raw['metadata']}
    if kind == 'adjust':
        item.update(correction_of=raw.get('correction_of'), basis=raw.get('basis'))
    if 'operation' in raw: item['operation'] = copy.deepcopy(raw['operation'])
    if raw.get('type') == 'create' and front.get('produced_by'):
        producer = front['produced_by']
        if producer['experiment'] != exp_id or not raw.get('operation') or any(raw['operation'].get(k) != producer.get(k) for k in ('stage', 'attempt')):
            raise C.SkillError('产物入库缺少一致的阶段操作关联')
        if producer.get('operation_id') and raw['operation'].get('id') != producer['operation_id']:
            raise C.SkillError('产物操作标识与编号保留依据不一致')
        item['produced_by'] = producer
    state = {
        "quantity": _round(after) if after is not None else None,
        "unit": new_unit,
        "location": new_location,
        "status": new_status,
    }
    return item, state


def check_groups(project, items):
    """Require source debits and destination credits together; no assumed mixing yield."""
    groups = {}
    for raw in items:
        front = C.load_sample(project, raw['sample'])[1]
        if raw['type'] == 'create' and front.get('produced_by'):
            producer, operation = front['produced_by'], raw.get('operation') or {}
            if not operation.get('id'): raise C.SkillError('产物转化须有稳定操作标识')
            for source in producer['inputs']:
                existing = C.load_sample(project, source)[1].get('history', [])
                debit = any(row.get('sample') == source and row.get('type') == 'consume' and row.get('operation') == operation for row in items)
                debit |= any(row.get('type') == 'consume' and row.get('experiment') == producer['experiment'] and row.get('operation') == operation for row in existing)
                if not debit: raise C.SkillError('产物入库缺少对应来源的实际使用事件')
    for raw in items:
        if raw["type"] in ("aliquot_in", "aliquot_out", "mixed_in", "mixed_out"):
            if not raw.get("group_id"):
                raise C.SkillError("分装/混合项必须提供 group_id")
            groups.setdefault(raw["group_id"], []).append(raw)
    for group in groups.values():
        kinds = {i["type"] for i in group}
        if kinds == {"aliquot_in", "aliquot_out"}:
            outgoing = [i for i in group if i["type"] == "aliquot_out"]
            incoming = [i for i in group if i["type"] == "aliquot_in"]
            if len(outgoing) != 1:
                raise C.SkillError("一组分装应有一个来源转出事件")
            source = outgoing[0]
            parent = C.load_sample(project, source["sample"])[1]
            unit = source.get("unit") or parent.get("unit")
            total = 0
            for row in incoming:
                child = C.load_sample(project, row["sample"])[1]
                if child.get("parent") != source["sample"]:
                    raise C.SkillError("分装子管的 parent 与来源不一致")
                total += float(row["delta"]) * project.convert_factor(row.get("unit") or child.get("unit"), unit)
            if not math.isclose(total, -float(source["delta"]), rel_tol=1e-9, abs_tol=1e-6):
                raise C.SkillError("分装转入合计必须等于转出；实际损耗另列事件")
        elif kinds == {"mixed_in", "mixed_out"}:
            incoming = [i for i in group if i["type"] == "mixed_in"]
            sources = {i["sample"] for i in group if i["type"] == "mixed_out"}
            if len(incoming) != 1 or set(incoming[0].get("sources") or []) != sources:
                raise C.SkillError("混合入库须列出与所有转出项一致的 sources")
            if incoming[0]["sample"] in sources:
                raise C.SkillError("混合产物必须使用独立新样品")
            target = C.load_sample(project, incoming[0]["sample"])[1]
            if target.get("kind") != "mixed" or target.get("quantity") is not None:
                raise C.SkillError("混合产物须为新建 mixed 样品")
        else:
            raise C.SkillError("分装或混合组必须同时包含对应转入、转出")


def plan_path(project, exp_id):
    return project.experiment_dir(exp_id) / (C.STATE_DIR + "-plan.yaml")


def plan_digest(plan):
    return C.sha256_text(json.dumps({k: plan[k] for k in
        ("experiment", "items", "snapshots")}, sort_keys=True, ensure_ascii=False, allow_nan=False))


@C.locked_stock
def build_plan(project, exp_id, items, expected_snapshots=None):
    plan = preview_plan(project, exp_id, items)
    if expected_snapshots is not None and plan['items'] and plan['snapshots'] != expected_snapshots:
        raise C.SkillError('库存已不同于阶段预览，须展示新清单并重新确认')
    C.atomic_write_text(plan_path(project, exp_id), C._yamlish.dumps(plan))
    C.atomic_write_text(project.experiment_dir(exp_id) / PLAN_NAME, render_plan_markdown(plan))
    return plan


def preview_plan(project, exp_id, items, require_experiment=True):
    """Pure calculation. A pending transaction must be recovered by an explicit action first."""
    if (project.samples / '.transaction.json').exists(): raise C.SkillError('库存事务待恢复')
    exp_dir = project.experiment_dir(exp_id)
    if require_experiment and not exp_dir.is_dir():
        raise C.SkillError(f"实验目录不存在：{exp_dir}")
    if not isinstance(items, list) or not items or not all(isinstance(i, dict) for i in items):
        raise C.SkillError("items 必须是非空对象数组")
    keys = [idempotency_key(exp_id, i) for i in items]
    if len(keys) != len(set(keys)):
        raise C.SkillError("一批内 event_id 不可重复；两次真实取用使用不同 ID")
    history = {str(h.get("key")): h for _, f, _ in C.iter_samples(project)
               for h in f.get("history", [])}
    projection, normalized, snapshots, pending = {}, [], {}, []
    for raw, key in zip(items, keys):
        if key in history:
            if history[key].get("fingerprint") != event_fingerprint(raw):
                raise C.SkillError("event_id 已存在但内容变更，拒绝重新解释历史事件")
            continue
        pending.append(raw)
    check_groups(project, pending)
    for raw in pending:
        item, state = normalize(project, exp_id, raw, projection)
        projection[item["sample"]] = state
        snapshots[item["sample"]] = C.sha256_file(project.sample_path(item["sample"]))
        normalized.append(item)
    plan = {"experiment": exp_id, "created": C.ts_now(), "items": normalized,
            "snapshots": snapshots, "status": "pending" if normalized else "committed",
            "skipped_events": len(items)-len(pending)}
    plan["hash"] = plan_digest(plan)
    return plan


def render_plan_markdown(plan: dict) -> str:
    rows = []
    for item in plan["items"]:
        before = "-" if item["before"] is None else f"{item['before']:g}"
        after = "-" if item["after"] is None else f"{item['after']:g}"
        delta = "" if item["type"] == "transfer" else f"{item['delta']:+g}"
        rows.append(
            f"| {item['sample']} | {C.TYPE_LABEL[item['type']]} | {delta} {item['unit'] or ''} | "
            f"{before} → {after} | {item['location'] or '-'} | {item['note'] or '-'} |"
        )
        if 'concentrations' in item:
            rows.append(f'| {item["sample"]} | 浓度变更 | {json.dumps(item["concentrations"], ensure_ascii=False)} | - | - | 纳入本次确认 |')
        if item.get('correction_of') or item.get('basis'):
            rows.append(f'| {item["sample"]} | 更正依据 | {json.dumps(item.get("correction_of") or item.get("basis"), ensure_ascii=False)} | - | - | 保留原事件 |')
        if item.get('produced_by'):
            rows.append(f'| {item["sample"]} | 产物来源 | {json.dumps(item["produced_by"], ensure_ascii=False)} | - | - | 独立新材料 |')
        if 'metadata' in item:
            rows.append(f'| {item["sample"]} | 来源更正 | {json.dumps(item["metadata"], ensure_ascii=False)} | 原值：{json.dumps(item["metadata_before"], ensure_ascii=False)} | - | 纳入本次确认 |')
    return f"""# 库存变更清单

实验：{plan['experiment']}
生成时间：{plan['created']}
状态：**{'已提交' if plan.get('status') == 'committed' else '待用户确认'}**
清单指纹：{plan.get('hash', '')}
确认人：{plan.get('confirmed_by') or '-'}

| 样本编号 | 变更类型 | 数量 | 余量变化 | 位置 | 说明 |
|---|---|---|---|---|---|
{chr(10).join(rows)}

## 待确认事项

- 以上数量、单位、存放位置是否与实际情况一致？
- 是否存在清单外的损耗或未登记入库？
- 确认后执行 `inventory.py commit`；未确认前台账保持不变。
"""


@C.locked_stock
def commit(project, exp_id, plan_hash=None, confirmed_by=None):
    path = plan_path(project, exp_id)
    if not path.is_file():
        raise C.SkillError("没有变更清单，请先执行 plan")
    plan = C._yamlish.loads(path.read_text(encoding="utf-8"))
    if plan.get("hash") != plan_digest(plan):
        raise C.SkillError("清单内容与指纹不一致，请重新生成")
    if not plan_hash or plan_hash != plan["hash"] or not confirmed_by or not confirmed_by.strip():
        raise C.SkillError("提交必须提供已确认的 --plan-hash 与 --confirmed-by")
    if plan.get("status") == "committed":
        return {"committed": [], "skipped": plan["items"], "noop": True, "experiment": exp_id}
    # Validate every snapshot before any write. Manual edits also invalidate approval.
    for sid, digest in plan["snapshots"].items():
        if C.sha256_file(project.sample_path(sid)) != digest:
            raise C.SkillError(f"{sid} 在清单生成后发生变化，请重新 plan 并确认")
    fronts, committed = {}, []
    for item in plan["items"]:
        sid = item["sample"]
        if sid not in fronts:
            fronts[sid] = copy.deepcopy(C.load_sample(project, sid)[1])
        front = fronts[sid]
        front.update(quantity=item["after"], unit=item["unit"],
                     location=item["location"], status=item["status"])
        if item.get("sources") is not None:
            front["sources"] = item["sources"]
        if 'concentrations' in item: front['concentrations'] = item['concentrations']
        if 'metadata' in item: front.update(item['metadata'])
        front.setdefault("history", []).append({
            **{k: item.get(k) for k in ("event_id", "key", "fingerprint", "type", "delta", "unit", "note", 'operation', 'correction_of', 'basis', 'concentrations', 'metadata', 'metadata_before')},
            "at": C.ts_now(), "experiment": exp_id,
            "plan_hash": plan_hash, "confirmed_by": confirmed_by})
        if exp_id not in front.setdefault("experiments", []):
            front["experiments"].append(exp_id)
        committed.append({"sample": sid, "event_id": item["event_id"], "quantity": item["after"]})
    plan.update(status="committed", confirmed_by=confirmed_by, committed_at=C.ts_now())
    writes = {project.sample_path(sid): C.sample_text(front) for sid, front in fronts.items()}
    writes[path] = C._yamlish.dumps(plan)
    writes[project.experiment_dir(exp_id) / PLAN_NAME] = render_plan_markdown(plan)
    receipt = project.experiment_dir(exp_id) / C.STATE_DIR / "commits" / (plan_hash + ".json")
    writes[receipt] = C.json_text(plan)
    affected = []
    corrected = [i['sample'] for i in plan['items'] if i['type'] == 'adjust']
    if corrected:
        import lineage
        affected = lineage.affected_work(project, corrected)
        writes[project.state / 'review-notices' / (plan_hash + '.json')] = C.json_text({
            'id': plan_hash, 'samples': corrected, 'affected': affected, 'reason': '已确认库存事实更正'})
    C.stock_transaction(project, writes)
    return {"committed": committed, "skipped": [], "experiment": exp_id, 'affected': affected}


@C.locked_stock

def list_stock(project: C.Project) -> dict:
    rows = []
    for path, front, _ in C.iter_samples(project):
        if str(front.get("status")) != "in_stock":
            continue
        if front.get("quantity") in (None, 0):
            continue
        concs = []
        for c in front.get("concentrations") or []:
            origin = {'measured': '', 'calculated': '（计算值）', 'unmeasured': '（未测定）', 'not_applicable': '（不适用）'}.get(str(c.get('origin')), '（来源未知）')
            analyte = f"{c.get('analyte')} " if c.get("analyte") else ""
            concs.append(f"{analyte}{c.get('value')} {c.get('unit') or ''}{origin}".strip())
        rows.append(
            {
                "id": front.get("id"),
                "treatment": front.get("treatment"),
                "location": front.get("location"),
                "quantity": front.get("quantity"),
                "unit": front.get("unit"),
                "concentrations": "；".join(concs),
            }
        )
    return {"count": len(rows), "samples": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="实验工作流库存台账")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="生成待确认的库存变更清单")
    p_plan.add_argument("--project", default=None)
    p_plan.add_argument("--experiment", required=True)
    p_plan.add_argument("--items", required=True, help="变更项 JSON 文件")

    p_commit = sub.add_parser("commit", help="提交已确认的清单")
    p_commit.add_argument("--project", default=None)
    p_commit.add_argument("--experiment", required=True)
    p_commit.add_argument("--plan-hash", required=True)
    p_commit.add_argument("--confirmed-by", required=True)

    p_list = sub.add_parser("list", help="在库列表")
    p_list.add_argument("--project", default=None)

    p_hist = sub.add_parser("history", help="单个样本的变更历史")
    p_hist.add_argument("--project", default=None)
    p_hist.add_argument("--sample", required=True)

    args = parser.parse_args()
    try:
        project = C.Project(C.find_project_root(args.project))
        if args.cmd == "plan":
            plan = build_plan(project, args.experiment, load_items(args.items))
            C.ok(
                experiment=args.experiment,
                items=len(plan["items"]),
                plan_hash=plan["hash"],
                status=plan["status"],
                checklist=str(project.experiment_dir(args.experiment) / PLAN_NAME),
                message="清单已生成，必须等用户确认后再 commit",
            )
        elif args.cmd == "commit":
            C.ok(**commit(project, args.experiment, args.plan_hash, args.confirmed_by))
        elif args.cmd == "list":
            C.ok(**list_stock(project))
        else:
            with C.StockLock(project):
                path, front, _ = C.load_sample(project, args.sample)
            C.ok(
                id=front.get("id"),
                quantity=front.get("quantity"),
                unit=front.get("unit"),
                status=front.get("status"),
                location=front.get("location"),
                history=front.get("history") or [],
            )
    except (C.SkillError, OSError, ValueError, TypeError, KeyError) as exc:
        C.die(str(exc), code="skill_error")
    except C._yamlish.YamlError as exc:
        C.die(f"YAML 解析失败：{exc}", code="yaml_error")


if __name__ == "__main__":
    main()
