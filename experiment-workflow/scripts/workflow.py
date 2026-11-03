"""按任务独立记录、整理结果、分析、库存复核与归档。"""
from __future__ import annotations
import argparse
import json
import re
import copy
from datetime import date
from pathlib import Path
import _common as C
import allocate_id
import _record_metadata as metadata

STATE_VERSION = 4


def defaults(state):
    for key, value in {'template_snapshot': None, 'stage_progress': {}, 'attempts': [],
                       'segments': [], 'confirmations': [], 'followups': {}, 'corrections': [],
                       'review_links': [], 'actions': {}, 'actual_date': None,
                       'execution': {'status': 'open'}, 'archive_request': None}.items():
        state.setdefault(key, copy.deepcopy(value))
    return state


def decode_state(state):
    state = copy.deepcopy(state)
    version = state.get('version', 2)
    if version not in (2, 3, 4):
        raise C.SkillError(f'不支持状态版本 {version}，拒绝降级或猜测迁移')
    if version == 2:
        state.update(archived=False, archived_at=None, result_tasks={}, record_round=0)
        state.pop('status', None)
    state['version'] = STATE_VERSION
    state.setdefault('result_tasks', {})
    state.setdefault('record_round', 0)
    return defaults(state)


def peek_state(p, eid):
    """Pure read for conversation previews: no migration, locks, or files written."""
    path = state_path(p, eid)
    if not path.is_file(): raise C.SkillError('实验尚无已保存状态')
    if (p.state / 'workflow-transaction.json').exists():
        raise C.SkillError('本地动作待恢复，请先运行 recover')
    state = decode_state(json.loads(path.read_text(encoding='utf-8')))
    import lineage
    lineage.notices(p, state)
    return state


def recover_actions(p):
    journal = p.state / 'workflow-transaction.json'
    if not journal.is_file(): return
    entries = json.loads(journal.read_text(encoding='utf-8'))['writes']
    for entry in entries:
        target = (p.root / entry['path']).resolve()
        if not target.is_relative_to(p.root): raise C.SkillError('动作日志路径超出项目')
        if entry.get('delete'): target.unlink(missing_ok=True)
        else: C.atomic_write_text(target, entry['text'])
    journal.unlink()


def action_transaction(p, writes, deletes=()):
    entries = []
    for path, text in writes.items():
        path = Path(path).resolve()
        if not path.is_relative_to(p.root): raise C.SkillError('动作写入路径超出项目')
        entries.append({'path': path.relative_to(p.root).as_posix(), 'text': text})
    for path in deletes:
        path = Path(path).resolve()
        if not path.is_relative_to(p.root): raise C.SkillError('删除目标超出项目')
        entries.append({'path': path.relative_to(p.root).as_posix(), 'delete': True})
    C.atomic_write_text(p.state / 'workflow-transaction.json', C.json_text({'writes': entries}))
    recover_actions(p)


def state_path(p, eid):
    return p.experiment_dir(eid) / C.STATE_DIR / 'workflow.json'


def local_path(p, value):
    path = Path(value)
    return path if path.is_absolute() else p.root / path


def stored_path(p, value):
    path = Path(value).resolve()
    return path.relative_to(p.root).as_posix() if path.is_relative_to(p.root) else str(path)


def snapshot_files(paths, project=None):
    out = []
    for raw in paths:
        path = Path(raw).resolve()
        if not path.is_file(): raise C.SkillError(f'文件不存在：{path}')
        out.append({'path': stored_path(project, path) if project else str(path), 'sha256': C.sha256_file(path)})
    return out


def changed(p, entry):
    path = local_path(p, entry['path'])
    return not path.is_file() or C.sha256_file(path) != entry['sha256']


def result_section(text):
    body = metadata.split(text)[1]
    found = re.search(r'^## 结果\s*\n(.*?)(?=^## |\Z)', body, re.M | re.S)
    return (found.group(1) if found else '').strip()


def actual_date_from_record(text):
    values = set(re.findall(r'(?:实际(?:实验)?日期\s*[：:]\s*|\|\s*实际(?:实验)?日期\s*\|\s*)(\d{4}-\d{2}-\d{2})', text))
    if len(values) != 1: return None
    value = values.pop()
    try: date.fromisoformat(value)
    except ValueError: return None
    return value


def invalidate_results(state, task_ids):
    for task_id in task_ids:
        if task_id not in state['result_tasks']:
            raise C.SkillError(f'未知结果整理任务：{task_id}')
        state['result_tasks'][task_id].update(status='pending', completed_at=None)


def properties(state):
    tasks = list(state['result_tasks'].values())
    completed = bool(tasks) and not state.get('result_scope_unknown') and all(t['status'] == 'completed' for t in tasks)
    return ('completed' if completed else 'in_progress',
            max(t['completed_at'] for t in tasks) if completed else None)


def sync_record_properties(p, eid, state):
    target = p.experiment_dir(eid) / C.RECORD_NAME
    record = state.get('record')
    if not record or not target.is_file(): return
    before = C.sha256_file(target)
    text = target.read_text(encoding='utf-8')
    status, at = properties(state)
    updated = metadata.render(text, status, at, important=state.get('important'))
    if updated != text: C.atomic_write_text(target, updated)
    if before == record.get('sha256'):
        record['sha256'] = C.sha256_file(target)
    else:
        record['stale'] = True  # never adopt unrelated manual edits as a generated baseline


def archive_files(base):
    return [f for f in base.rglob('*') if f.is_file()
            and C.STATE_DIR not in f.relative_to(base).parts and f.name != '归档清单.json']


def save_state(p, eid, state, invalidate_archive=True):
    state['updated'] = C.ts_now()
    if invalidate_archive:
        state['archived'] = False
        state['archived_at'] = None
    sync_record_properties(p, eid, state)
    C.atomic_write_text(state_path(p, eid), C.json_text(state))
    manifest = p.experiment_dir(eid) / '归档清单.json'
    if invalidate_archive and manifest.is_file():
        dest = p.experiment_dir(eid) / C.STATE_DIR / 'archive-history' / (C.sha256_file(manifest)+'.json')
        C.atomic_write_text(dest, manifest.read_text(encoding='utf-8'))
        manifest.unlink()


def read_state(p, eid):
    path = state_path(p, eid)
    if not path.is_file(): raise C.SkillError('请先 start 保存原始输入')
    state = json.loads(path.read_text(encoding='utf-8'))
    migrated = state.get('version', 2) != STATE_VERSION
    if migrated:
        decoded = decode_state(state)  # validate before any write
        backup = path.with_name(f'workflow-v{state.get("version", 2)}-backup.json')
        if not backup.exists(): C.atomic_write_text(backup, C.json_text(state))
        state = decoded
    else:
        state = decode_state(state)
    state.setdefault('result_tasks', {})
    state.setdefault('record_round', 0)
    import lineage
    dirty = lineage.notices(p, state) or migrated
    target = p.experiment_dir(eid) / C.RECORD_NAME
    record = state.get('record')
    if record and target.is_file():
        chosen = metadata.importance(target.read_text(encoding='utf-8'))
        if state.get('important') != chosen:
            state['important'] = chosen; dirty = True
        if not state.get('actual_date'):
            actual = actual_date_from_record(target.read_text(encoding='utf-8'))
            if actual: state['actual_date'] = actual; dirty = True
        section_hash = C.sha256_text(result_section(target.read_text(encoding='utf-8')))
        if record.get('results_hash') and section_hash != record['results_hash']:
            if len(state['result_tasks']) == 1:
                invalidate_results(state, list(state['result_tasks']))
            elif state['result_tasks']:
                state['result_scope_unknown'] = True
            dirty = True
        if C.sha256_file(target) != record.get('sha256'):
            record['stale'] = True
    for task_id, task in state.get('analysis', {}).items():
        if task['status'] == 'completed' and any(changed(p, e) for e in task['inputs'] + task['outputs']):
            task['status'] = 'pending'
            invalidate_results(state, [key for key, value in state['result_tasks'].items()
                                       if task_id in value.get('analysis_tasks', [])])
            dirty = True
    for task in state['result_tasks'].values():
        if task['status'] == 'completed' and any(changed(p, e) for e in task.get('files', [])):
            task.update(status='pending', completed_at=None)
            dirty = True
        evidence = task.get('text_evidence')
        if task['status'] == 'completed' and evidence:
            current = result_section(target.read_text(encoding='utf-8')) if target.is_file() else ''
            source = next((i for i in state['inputs'] if i['request_id'] == evidence['request_id']), None)
            if (evidence['text'] not in current or not source or changed(p, source)):
                task.update(status='pending', completed_at=None)
                dirty = True
    if state.get('archived'):
        manifest_path = p.experiment_dir(eid) / '归档清单.json'
        archive_changed = not manifest_path.is_file()
        if not archive_changed:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            archive_changed = any(changed(p, e) for e in manifest['files'])
            expected = {str(local_path(p, e['path']).resolve()) for e in manifest['files']}
            actual = {str(f.resolve()) for f in archive_files(p.experiment_dir(eid))}
            archive_changed |= expected != actual
        if archive_changed:
            state['archive_invalidated'] = '归档后材料变化，需重新归档'
            dirty = True
    if dirty: save_state(p, eid, state, invalidate_archive=not migrated or not state.get('archived'))
    return state


def start(p, request_id, input_file, eid=None, affects_results=(), affects_analysis=()):
    if not request_id.strip(): raise C.SkillError('request-id 不能为空；重试沿用原 ID')
    text = Path(input_file).read_text(encoding='utf-8')
    digest = C.sha256_text(text)
    registry = p.state / 'requests.json'
    known = json.loads(registry.read_text(encoding='utf-8')) if registry.is_file() else {}
    if request_id in known:
        entry = known[request_id]
        if entry['sha256'] != digest or (eid and eid != entry['experiment']):
            raise C.SkillError('request-id 已存在但内容或实验不同')
        eid = entry['experiment']
    else:
        eid = eid or allocate_id.allocate_experiment(p)
        if not p.experiment_dir(eid).is_dir(): raise C.SkillError('补充实验不存在')
    state = read_state(p, eid) if state_path(p, eid).is_file() else {
        'version': STATE_VERSION, 'experiment': eid, 'inputs': [], 'record': None,
        'analysis': {}, 'result_tasks': {}, 'inventory': 'unknown', 'inventory_reason': None,
        'issues': [], 'archived': False, 'archived_at': None, 'record_round': 0}
    defaults(state)
    if any(i['request_id'] == request_id for i in state['inputs']):
        return {'experiment': eid, 'noop': True, 'state': state}
    invalidate_results(state, affects_results)
    for task_id in affects_analysis:
        if task_id not in state['analysis']: raise C.SkillError(f'未知分析任务：{task_id}')
        state['analysis'][task_id]['status'] = 'pending'
        invalidate_results(state, [key for key, task in state['result_tasks'].items()
                                   if task_id in task.get('analysis_tasks', [])])
    known[request_id] = {'experiment': eid, 'sha256': digest}
    C.atomic_write_text(registry, C.json_text(known))
    target = p.experiment_dir(eid) / '原始输入' / (C.sha256_text(request_id)+'.txt')
    C.atomic_write_text(target, text)
    state['inputs'].append({'request_id': request_id, 'path': stored_path(p, target), 'sha256': digest})
    if state['record']: state['record']['stale'] = True
    save_state(p, eid, state)
    return {'experiment': eid, 'state': state}


def write_record(p, eid, source, approve_current_hash=None, affects_results=None):
    state = read_state(p, eid)
    text = Path(source).read_text(encoding='utf-8')
    for heading in ('## 目的', '## 实验方案', '## 结果', '## 附件'):
        if heading not in text: raise C.SkillError(f'记录缺少 {heading}')
    if eid not in text or '{{' in text or re.search(r'\bTODO\b', text, re.I):
        raise C.SkillError('编号不一致或仍有模板占位符/TODO')
    target = p.experiment_dir(eid) / C.RECORD_NAME
    previous = state.get('record') or {}
    if target.exists() and C.sha256_file(target) != previous.get('sha256'):
        current = C.sha256_file(target)
        if approve_current_hash != current:
            raise C.SkillError(f'记录有人工修改；展示合并结果并确认后传 --approve-current-hash {current}')
    old = target.read_text(encoding='utf-8') if target.is_file() else None
    if affects_results is not None:
        invalidate_results(state, affects_results)
        state.pop('result_scope_unknown', None)
    elif state.get('result_scope_unknown') or (old is not None and result_section(text) != result_section(old)):
        if len(state['result_tasks']) > 1:
            raise C.SkillError('结果章节变化但无法确定任务范围；核对后传 --affects-results <受影响任务ID>，不重置全部任务')
        invalidate_results(state, list(state['result_tasks']))
    if old is not None:
        backup = p.experiment_dir(eid) / C.STATE_DIR / 'record-history' / (C.sha256_file(target)+'.md')
        C.atomic_write_text(backup, old)
    status, at = properties(state)
    text = metadata.render(text, status, at, previous=old, important=state.get('important'))
    C.atomic_write_text(target, text)
    state['record'] = {'path': stored_path(p, target), 'sha256': C.sha256_file(target), 'stale': False,
                       'results_hash': C.sha256_text(result_section(text))}
    state['actual_date'] = actual_date_from_record(text) or state.get('actual_date')
    state['record_round'] += 1
    state.update(inventory='review_pending', inventory_reason=None)
    save_state(p, eid, state)
    return {**state['record'], 'record_round': state['record_round'],
            'next_action': 'inventory_review', 'message': '自动读取库存模块，核查本轮样品变化；无变化直接结束，不询问是否手动管理库存'}


def update_analysis(p, eid, task_id, status, skill=None, skill_version=None,
                    inputs=(), outputs=(), params='', reason=None):
    state = read_state(p, eid)
    if status == 'none':
        if not reason or state['analysis']: raise C.SkillError('无需分析须给原因且没有已有分析任务')
        state['analysis_none'] = reason
    else:
        if status == 'completed' and (not skill or not skill_version or not inputs or not outputs):
            raise C.SkillError('分析完成须有 skill、版本、输入、输出')
        if status == 'blocked' and not reason: raise C.SkillError('blocked 须记录原因')
        if status == 'completed' and any(not Path(f).resolve().is_relative_to(p.experiment_dir(eid)) for f in outputs):
            raise C.SkillError('分析输出必须先归入本实验目录')
        task = {'status': status, 'skill': skill, 'skill_version': skill_version,
                'inputs': snapshot_files(inputs, p), 'outputs': snapshot_files(outputs, p),
                'params': params, 'reason': reason}
        old = state['analysis'].get(task_id)
        if old and any(task[k] != old.get(k) for k in ('inputs', 'outputs', 'params', 'skill', 'skill_version')):
            invalidate_results(state, [key for key, value in state['result_tasks'].items()
                                       if task_id in value.get('analysis_tasks', [])])
        state['analysis'][task_id] = task
    save_state(p, eid, state)
    return state


def organize(p, eid, task_id, status, files=(), analysis_tasks=(), text_evidence=None):
    state = read_state(p, eid)
    if not task_id.strip(): raise C.SkillError('整理任务 ID 不能为空')
    if any(key not in state['analysis'] for key in analysis_tasks):
        raise C.SkillError('关联的分析任务不存在')
    if status == 'completed':
        record = state.get('record')
        if not record or record.get('stale') or changed(p, record):
            raise C.SkillError('先将已有结果回填记录再标记整理完成')
        if not files and not text_evidence: raise C.SkillError('结果整理完成须提供文件或已回填文字证据')
        if any(not Path(f).resolve().is_relative_to(p.experiment_dir(eid)) for f in files):
            raise C.SkillError('结果文件须归入本实验目录')
        section = result_section(local_path(p, record['path']).read_text(encoding='utf-8'))
        for f in files:
            if Path(f).name not in section: raise C.SkillError(f'结果尚未回填记录：{Path(f).name}')
        if text_evidence:
            text_evidence = copy.deepcopy(text_evidence)
            text = text_evidence.get('text', '').strip()
            source = next((i for i in state['inputs'] if i['request_id'] == text_evidence.get('request_id')), None)
            if not text or text not in section or not source or changed(p, source):
                raise C.SkillError('文字结果缺少有效输入来源或未实际回填')
            raw = local_path(p, source['path']).read_text(encoding='utf-8')
            if text not in raw: raise C.SkillError('结果文字不在所提供原始输入中')
            text_evidence.update(sha256=C.sha256_text(text), source_sha256=source['sha256'])
    state['result_tasks'][task_id] = {'status': status, 'files': snapshot_files(files, p),
        'analysis_tasks': list(analysis_tasks),
        'completed_at': C.now_cn().strftime('%Y-%m-%dT%H:%M:%S') if status == 'completed' else None}
    if text_evidence: state['result_tasks'][task_id]['text_evidence'] = text_evidence
    save_state(p, eid, state)
    return state


def maybe_archive(p, eid):
    state = read_state(p, eid)
    request = state.get('archive_request')
    if not request or properties(state)[0] != 'completed': return state
    if state.get('archived') and request.get('status') == 'done': return state
    try:
        finalize(p, eid)
    except C.SkillError as exc:
        state = read_state(p, eid)
        state['archive_request'].update(status='pending', reason=str(exc))
        save_state(p, eid, state, invalidate_archive=False)
    else:
        state = read_state(p, eid)
        state['archive_request'].update(status='done', reason=None)
        C.atomic_write_text(state_path(p, eid), C.json_text(state))
    return state


def set_important(p, eid, value):
    if not isinstance(value, bool): raise C.SkillError('important 必须为布尔值')
    state = read_state(p, eid)
    state['important'] = value
    save_state(p, eid, state)
    return maybe_archive(p, eid)


def list_experiments(p):
    states = [read_state(p, f.parent.parent.name) for f in p.experiments.glob('*/.experiment-workflow/workflow.json')]
    return sorted(states, key=lambda s: (bool(s.get('actual_date')), s.get('actual_date') or '', s['experiment']), reverse=True)


def review_inventory(p, eid, mode, reason=None):
    state = read_state(p, eid)
    if mode == 'none' and not reason: raise C.SkillError('无库存变化需记录核查依据，不必询问用户')
    state.update(inventory=mode, inventory_reason=reason, inventory_review_round=state['record_round'])
    if mode == 'required':
        from inventory import plan_path
        path = plan_path(p, eid)
        # Prevent accepting a previous round's receipt as this round's new operations.
        state['inventory_previous_plan'] = C.sha256_file(path) if path.is_file() else None
    save_state(p, eid, state)
    return state


def finalize(p, eid):
    # No analysis or result-completion gate. Inventory checks are only used when requested.
    state = read_state(p, eid)
    if state['inventory'] == 'required':
        with C.StockLock(p):
            return _finalize(p, eid)
    return _finalize(p, eid)


def _finalize(p, eid):
    with C.FileLock(p.experiment_dir(eid) / C.STATE_DIR / 'archive.lock'):
        state = read_state(p, eid)
        problems = []
        record = state.get('record')
        if not record or record.get('stale'): problems.append('先完成本轮记录写入')
        if state['inventory'] == 'required':
            from inventory import plan_path
            path = plan_path(p, eid)
            plan = C._yamlish.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
            if plan.get('status') != 'committed': problems.append('库存尚未提交')
            elif C.sha256_file(path) == state.get('inventory_previous_plan'):
                problems.append('当前仍是上一轮库存计划，请生成本轮计划')
        elif state['inventory'] != 'none': problems.append('记录完成后需自动执行本轮库存核查')
        # Analysis problems remain internal and do not prevent archiving available material.
        for entry in list(state['inputs']) + ([record] if record else []):
            if changed(p, entry): problems.append(f"原始输入或记录变化：{entry['path']}")
        if problems: raise C.SkillError('；'.join(problems))
        at = C.now_cn().strftime('%Y-%m-%dT%H:%M:%S')
        manifest = {'experiment': eid, 'archived_at': at, 'archived': True,
                    'files': snapshot_files(archive_files(p.experiment_dir(eid)), p),
                    'analysis': state['analysis'], 'result_tasks': state['result_tasks'],
                    'inventory': state['inventory'], 'issues': state['issues']}
        C.atomic_write_text(p.experiment_dir(eid) / '归档清单.json', C.json_text(manifest))
        state.update(archived=True, archived_at=at)
        C.atomic_write_text(state_path(p, eid), C.json_text(state))
        return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project')
    sub = parser.add_subparsers(dest='cmd', required=True)
    arg = sub.add_parser('start')
    arg.add_argument('--request-id', required=True); arg.add_argument('--input', required=True)
    arg.add_argument('--experiment')
    arg.add_argument('--affects-results', nargs='*', default=[])
    arg.add_argument('--affects-analysis', nargs='*', default=[])
    sub.add_parser('list')
    sub.add_parser('recover')
    for name in ('status', 'record', 'analysis', 'organize', 'inventory', 'issues', 'finalize', 'important'):
        arg = sub.add_parser(name); arg.add_argument('--experiment', required=True)
        if name == 'record':
            arg.add_argument('--file', required=True); arg.add_argument('--approve-current-hash')
            arg.add_argument('--affects-results', nargs='+')
        elif name == 'analysis':
            arg.add_argument('--task', default='main')
            arg.add_argument('--status', choices=['pending', 'blocked', 'completed', 'none'], required=True)
            arg.add_argument('--skill'); arg.add_argument('--skill-version')
            arg.add_argument('--inputs', nargs='*', default=[]); arg.add_argument('--outputs', nargs='*', default=[])
            arg.add_argument('--params', default=''); arg.add_argument('--reason')
        elif name == 'organize':
            arg.add_argument('--task', required=True)
            arg.add_argument('--status', choices=['pending', 'completed'], required=True)
            arg.add_argument('--files', nargs='*', default=[])
            arg.add_argument('--analysis-tasks', nargs='*', default=[])
            arg.add_argument('--text-evidence', help='JSON 文件：text 和 request_id')
        elif name == 'inventory':
            arg.add_argument('--mode', choices=['required', 'none'], required=True); arg.add_argument('--reason')
        elif name == 'issues': arg.add_argument('--file', required=True)
        elif name == 'important': arg.add_argument('--value', choices=['true', 'false'], required=True)
    args = parser.parse_args()
    try:
        p = C.Project(C.find_project_root(args.project))
        with C.FileLock(p.state / 'workflow.lock'):
            recover_actions(p)
            if args.cmd == 'start':
                result = start(p, args.request_id, args.input, args.experiment, args.affects_results, args.affects_analysis)
            elif args.cmd == 'list':
                result = {'experiments': list_experiments(p)}
            elif args.cmd == 'recover': result = {'recovered': True}
            elif args.cmd == 'status': result = read_state(p, args.experiment)
            elif args.cmd == 'record':
                result = write_record(p, args.experiment, args.file, args.approve_current_hash, args.affects_results)
            elif args.cmd == 'analysis':
                result = update_analysis(p, args.experiment, args.task, args.status, args.skill,
                    args.skill_version, args.inputs, args.outputs, args.params, args.reason)
            elif args.cmd == 'organize':
                evidence = json.loads(Path(args.text_evidence).read_text(encoding='utf-8')) if args.text_evidence else None
                result = organize(p, args.experiment, args.task, args.status, args.files, args.analysis_tasks, evidence)
            elif args.cmd == 'inventory': result = review_inventory(p, args.experiment, args.mode, args.reason)
            elif args.cmd == 'finalize': result = finalize(p, args.experiment)
            elif args.cmd == 'important': result = set_important(p, args.experiment, args.value == 'true')
            else:
                state = read_state(p, args.experiment)
                issues = json.loads(Path(args.file).read_text(encoding='utf-8'))
                if not isinstance(issues, list) or not all(isinstance(x, str) for x in issues):
                    raise C.SkillError('issues 须为字符串数组')
                state['issues'] = issues; save_state(p, args.experiment, state); result = state
            if getattr(args, 'experiment', None) and args.cmd not in ('start', 'finalize'):
                maybe_archive(p, args.experiment)
            C.ok(result=result)
    except (C.SkillError, OSError, ValueError, TypeError, KeyError) as exc:
        C.die(str(exc), code='workflow_error')


if __name__ == '__main__': main()
