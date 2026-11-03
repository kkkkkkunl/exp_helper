"""Pure conversational previews and explicitly confirmed, replay-safe stage actions."""
from __future__ import annotations
import argparse
import sys
sys.dont_write_bytecode = True
import copy
import json
import re
from datetime import date
from pathlib import Path
import _common as C
import workflow as W
import stage_templates as T
import calendar_bridge as B
import allocate_id as A
import inventory as I


def digest(value): return C.sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False))


def fresh(eid):
    return W.defaults({'version': 4, 'experiment': eid, 'inputs': [], 'record': None, 'analysis': {},
                       'result_tasks': {}, 'inventory': 'unknown', 'inventory_reason': None, 'issues': [],
                       'archived': False, 'archived_at': None, 'record_round': 0})


def receipt_path(p, action_id): return p.state / 'actions' / (C.sha256_text(action_id) + '.json')


def template_for(p, draft, state):
    snapshot = state.get('template_snapshot')
    if snapshot:
        template = T.frozen(p, snapshot)
        if draft.get('template') and draft['template'] != template['name'] and draft['action'] != 'upgrade':
            raise C.SkillError('继续实验不得静默切换模板')
        return template
    # Old ordinary records do not acquire a staged template from a changed project default.
    if draft.get('experiment') and not draft.get('template'): return None
    return T.select(p, draft.get('template'))


def _stages(template): return {s['id']: s for s in ((template or {}).get('data') or {}).get('stages', [])}


def _sample_ids(draft, state):
    result = set(state.get('stage_progress', {}))
    for raw in draft.get('samples', []): result.add(raw if isinstance(raw, str) else raw['id'])
    result.update(op['sample'] for op in draft.get('operations', []))
    return sorted(result)


def _advance(p, draft, state, template, sample_data):
    stages = _stages(template)
    lines, conditions = [], []
    branches = state.setdefault('branches', {})
    for sid, target in draft.get('branches', {}).items():
        if sid not in stages or target not in stages[sid]['next']: raise C.SkillError('分支不在模板允许路径中')
        branches[sid] = target
    adjustment = draft.get('adjustment')
    if adjustment and (adjustment.get('confirmed') is not True or not adjustment.get('reason')):
        raise C.SkillError('超模板调整须明确确认及理由')
    if draft.get('entry'):
        definition = stages.get(draft['entry'])
        if not definition or not definition['entry']: raise C.SkillError('无效初始入口')
        for sample in sample_data:
            if not state['stage_progress'].get(sample):
                state['stage_progress'][sample] = {definition['id']: {'attempt': 1, 'steps': {},
                    'input': copy.deepcopy(sample_data[sample].get('produced_by'))}}
                origin = sample_data[sample].get('produced_by')
                lines.append(f'- 输入样品 [[{sample}]]' + (f'；来源实验 [[{origin["experiment"]}]]；来源阶段 {origin["stage"]}' if origin else ''))
    for retry in draft.get('retry', []):
        sid, stage_id = retry['sample'], retry['stage']
        progress = state['stage_progress'].get(sid, {}).get(stage_id)
        if not progress or not retry.get('reason'): raise C.SkillError('重做须有原尝试和理由')
        state['attempts'].append({'sample': sid, 'stage': stage_id, 'previous': copy.deepcopy(progress), 'reason': retry['reason']})
        state['stage_progress'][sid][stage_id] = {'attempt': progress['attempt'] + 1, 'steps': {}}
    for op in draft.get('operations', []):
        sample, stage_id, step_id = op['sample'], op['stage'], op['step']
        definition = stages.get(stage_id)
        if not definition: raise C.SkillError(f'未知阶段 {stage_id}')
        step = next((s for s in definition['steps'] if s['id'] == step_id), None)
        if not step: raise C.SkillError(f'未知步骤 {step_id}')
        if not isinstance(op.get('executed'), bool): raise C.SkillError('须明确步骤是否实际执行')
        progress = state['stage_progress'].setdefault(sample, {})
        if stage_id not in progress:
            if not progress:
                if not definition['entry'] and not adjustment: raise C.SkillError('该阶段不是允许的初始入口')
                if draft.get('entry') and draft['entry'] != stage_id: raise C.SkillError('操作阶段与所选入口不符')
            else:
                predecessors = [s for s in stages.values() if stage_id in s['next'] and s['id'] in progress]
                ready = [s for s in predecessors if all(progress[s['id']]['steps'].get(x['id'], {}).get('complete') for x in s['steps'])
                         and (len(s['next']) == 1 or branches.get(s['id']) == stage_id)]
                if not ready and not adjustment: raise C.SkillError('前序步骤尚未满足，或分支尚未明确选择')
            progress[stage_id] = {'attempt': 1, 'steps': {}, 'input': copy.deepcopy(sample_data[sample].get('produced_by'))}
        current = progress[stage_id]
        material = sample_data[sample]
        unmet = [key for key in definition['requires'] if material.get(key) is None]
        if definition['input_types'] and material.get('material_type') not in definition['input_types']:
            unmet.append('material_type')
        if material.get('status') in ('discarded', 'depleted'): unmet.append('available_sample')
        if current.get('needs_review'): unmet.append('source_review')
        current['conditions'] = unmet
        conditions.extend(f'{sample}/{stage_id}: {key}' for key in unmet)
        values, missing = T.values(p, step, op.get('values', {}), op.get('confirmed_fields', []))
        old = current['steps'].get(step_id)
        info = {'executed': op['executed'], 'values': values, 'missing': missing,
                'complete': op['executed'] and not missing, 'source': draft['action_id']}
        if old and old.get('executed') and (old['values'] != values or not op['executed']):
            if draft['action'] != 'correct' or not draft.get('reason'):
                raise C.SkillError('已执行事实变化须使用 correct 并说明依据')
            state['corrections'].append({'sample': sample, 'stage': stage_id, 'step': step_id,
                                         'before': old, 'after': info, 'reason': draft['reason'], 'source': draft['action_id']})
            state['review_links'].append({'samples': [sample], 'stage': stage_id, 'reason': draft['reason']})
        current['steps'][step_id] = info
        if op['executed'] and (not old or old.get('values') != values or not old.get('executed') or draft.get('retry')):
            rendered = []
            for key, value in values.items():
                label = next(f['label'] for f in step['fields'] if f['id'] == key)
                actual = {'unmeasured': '未测定', 'not_applicable': '不适用'}.get(value.get('status')) or str(value['value']) + (' ' + str(value['unit']) if value.get('unit') else '')
                rendered.append(f'{label}：{actual}')
            prefix = '更正记载：' if draft['action'] == 'correct' else ''
            lines.append(f'- {prefix}{definition["title"]} / {step["title"]}；样品 [[{sample}]]；' + '；'.join(rendered))
    for review in draft.get('resolve_reviews', []):
        if review.get('confirmed') is not True or not review.get('reason'): raise C.SkillError('复核完成须明确确认及依据')
        progress = state['stage_progress'].get(review['sample'], {}).get(review['stage'])
        if not progress: raise C.SkillError('复核对象不存在')
        definition = stages[review['stage']]
        for step in definition['steps']:
            if step['id'] in progress['steps']:
                info = progress['steps'][step['id']]
                actual = copy.deepcopy(info['values'])
                for value in actual.values(): value['source'] = 'user'
                checked, missing = T.values(p, step, actual)
                if missing: raise C.SkillError('新模板必填数据仍缺失，不能结束复核')
                info.update(values=checked, missing=[], needs_review=False, complete=info['executed'])
        progress['needs_review'] = False
        state.setdefault('reviews', []).append(copy.deepcopy(review))
    if adjustment: state.setdefault('adjustments', []).append(copy.deepcopy(adjustment))
    return lines, conditions


def prompts(state, template, sample_data):
    out = []
    for sample, stages in state['stage_progress'].items():
        for sid, progress in stages.items():
            definition = T.stage(template, sid)
            material = sample_data[sample]
            conditions = [k for k in definition['requires'] if material.get(k) is None]
            if definition['input_types'] and material.get('material_type') not in definition['input_types']:
                conditions.append('material_type')
            if progress.get('needs_review'): conditions.append('source_review')
            if material.get('status') in ('discarded', 'depleted'): conditions.append('available_sample')
            if conditions:
                out.append({'sample': sample, 'stage': sid, 'conditions': conditions}); continue
            for step in definition['steps']:
                info = progress['steps'].get(step['id'], {})
                if not info.get('complete'):
                    fields = [dict(f, needs_confirmation=True) for f in step['fields']
                              if f['id'] not in info.get('values', {})]
                    out.append({'sample': sample, 'stage': sid, 'step': step['id'], 'title': step['title'],
                                'fields': fields, 'executed': info.get('executed', False)})
                    break
            else:
                if definition['next']:
                    out.append({'sample': sample, 'stage': sid, 'choose_next_stage': definition['next'],
                                'guidance': '核对或选择下一阶段的实际输入样品，不把来源样品自动当作新产物'})
    return out


def refresh_followups(state, eid, template, entry=None):
    stages = _stages(template)
    if not stages: return
    grouped = {}
    for sample, progress in state['stage_progress'].items():
        roots = list(progress) or ([entry] if entry else [])
        visited = set()
        def walk(sid):
            if sid in visited: return
            visited.add(sid); definition = stages[sid]
            info = progress.get(sid, {}).get('steps', {})
            remaining = [f'{sample}: {step["title"]}' for step in definition['steps'] if not info.get(step['id'], {}).get('executed')]
            missing = [f'{sample}/{step}: {field}' for step, value in info.items() for field in value.get('missing', [])]
            group = grouped.setdefault(sid, {'samples': [], 'remaining': [], 'missing': []})
            group['samples'].append(sample); group['remaining'].extend(remaining); group['missing'].extend(missing)
            nxt = definition['next']
            if len(nxt) > 1:
                choice = state.get('branches', {}).get(sid)
                if choice:
                    inherited = any(choice in other and (other[choice].get('input') or {}).get('stage') == sid and
                                    sample in (other[choice].get('input') or {}).get('inputs', [])
                                    for other in state['stage_progress'].values())
                    if not inherited: walk(choice)
                else: group['missing'].append('需选择后续分支：' + '、'.join(nxt))
            elif nxt:
                inherited = any(nxt[0] in other and (other[nxt[0]].get('input') or {}).get('stage') == sid and
                                sample in (other[nxt[0]].get('input') or {}).get('inputs', [])
                                for other in state['stage_progress'].values())
                if not inherited: walk(nxt[0])
        for sid in roots: walk(sid)
    existing_stages = {x['stage'] for x in state['followups'].values()}
    for sid, group in grouped.items():
        if group['remaining'] or group['missing'] or sid in existing_stages:
            B.enqueue(state, eid, sid, stages[sid]['title'], group['samples'], group['remaining'], group['missing'])


def _insert(text, heading, addition):
    if not addition: return text
    if heading not in text: raise C.SkillError(f'记录缺少 {heading}')
    start = text.index(heading) + len(heading)
    match = re.search(r'^## ', text[start:], re.M)
    end = start + match.start() if match else len(text)
    return text[:end].rstrip() + '\n' + addition + '\n\n' + text[end:]


def _results(p, draft, state, record, eid):
    results = draft.get('results', [])
    if not isinstance(results, list): raise C.SkillError('results 须为结果数组')
    seen = set()
    for item in results:
        key = C.safe_id(item['id'])
        if key in seen: raise C.SkillError('结果任务 ID 重复')
        seen.add(key)
        text = item.get('text', '').strip()
        files = item.get('files', [])
        if text and text not in draft['raw_input']: raise C.SkillError('结果文字须可在本次原话中追溯')
        file_entries = []
        for raw in files:
            path = W.local_path(p, raw).resolve()
            if not path.is_relative_to(p.experiment_dir(eid)) or not path.is_file():
                raise C.SkillError('结果附件须先按附件规则归入本实验')
            file_entries.extend(W.snapshot_files([path], p))
        section = W.result_section(record)
        additions = []
        if text and text not in section: additions.append(text)
        for f in file_entries:
            path = W.local_path(p, f['path'])
            if path.name not in section: additions.append(f'- [{path.name}]({path.relative_to(p.experiment_dir(eid)).as_posix()})')
        record = _insert(record, '## 结果', '\n'.join(additions))
        complete = bool(text or files) and not item.get('missing')
        task = {'status': 'completed' if complete else 'pending', 'files': file_entries, 'analysis_tasks': [],
                'completed_at': C.ts_now() if complete else None, 'missing': list(item.get('missing', []))}
        if text:
            task['text_evidence'] = {'text': text, 'request_id': draft.get('request_id', draft['action_id']),
                                     'sha256': C.sha256_text(text), 'source_sha256': C.sha256_text(draft['raw_input'])}
        state['result_tasks'][key] = task
    if draft['action'] == 'final_results':
        if draft.get('submission_kind') != 'final': raise C.SkillError('最终结果动作须有明确 final 意图，不能仅由关键词推断')
        scope = draft.get('result_scope') or list(state['result_tasks'])
        if set(state['result_tasks']) - set(scope): raise C.SkillError('已有请求结果尚在范围外，需先明确处理，不能静默丢弃')
        complete = bool(scope) and all(state['result_tasks'].get(k, {}).get('status') == 'completed' for k in scope)
        state['execution'] = {'status': 'ended' if complete else 'collecting_results', 'request_id': draft['action_id'], 'scope': scope}
        state['archive_request'] = {'status': 'pending', 'request_id': draft['action_id'], 'scope': scope,
                                    'reason': None if complete else '结果范围或必要信息待补'}
    return record


def preview(p, draft):
    if not isinstance(draft, dict) or draft.get('action') not in ('confirm', 'pause', 'final_results', 'correct', 'upgrade'):
        raise C.SkillError('保存动作须为 confirm/pause/final_results/correct/upgrade')
    if not isinstance(draft.get('action_id'), str) or not draft['action_id'].strip() or not draft.get('raw_input'):
        raise C.SkillError('动作需要稳定 action_id 和用户原话 raw_input')
    eid = draft.get('experiment') or 'pending-experiment'
    state = W.peek_state(p, eid) if draft.get('experiment') else fresh(eid)
    state_before = copy.deepcopy(state)
    template = template_for(p, draft, state)
    actual_date = draft.get('actual_date', state.get('actual_date'))
    if actual_date:
        try: date.fromisoformat(actual_date)
        except (ValueError, TypeError) as exc: raise C.SkillError('实际日期须为 YYYY-MM-DD') from exc
        state['actual_date'] = actual_date
    sample_data, sample_hashes = {}, {}
    if (p.samples / '.transaction.json').exists(): raise C.SkillError('库存事务待恢复，不能预览未完成台账')
    for sid in _sample_ids(draft, state):
        path, data, _ = C.load_sample(p, sid)
        sample_data[sid] = data; sample_hashes[sid] = C.sha256_file(path)
    old_record = p.experiment_dir(eid) / C.RECORD_NAME
    text = old_record.read_text(encoding='utf-8') if old_record.is_file() else (
        f'# {eid}\n\n实际实验日期：{actual_date or ""}\n\n## 目的\n{draft.get("purpose", "")}\n\n'
        '## 实验方案\n### 参考方案\n\n### 实验方法\n\n## 结果\n\n## 附件\n')
    if template and not state_before.get('template_snapshot'):
        text = _insert(text, '## 实验方案', f'参考模板：{template["name"]}；版本：{template["version"]}；来源：{template["source"]}')
    if draft.get('actual_date') and state_before.get('actual_date') != actual_date:
        lines = []
        for line in text.splitlines(keepends=True):
            if re.match(r'^实际(?:实验)?日期[：:]', line):
                line = f'实际实验日期：{actual_date}\n'
            elif re.match(r'^\|\s*实际(?:实验)?日期\s*\|', line):
                cells = line.split('|'); cells[2] = ' ' + actual_date + ' '; line = '|'.join(cells)
            lines.append(line)
        text = ''.join(lines)
    if draft['action'] == 'upgrade':
        if not draft.get('mapping'): raise C.SkillError('升级须提供阶段和步骤映射')
        target = T.select(p, draft.get('target_template'))
        mapping = T.upgrade_preview(state, template, target, draft['mapping'].get('stages', {}), draft['mapping'].get('steps', {}))
        state.setdefault('template_history', []).append({'snapshot': state.get('template_snapshot'), 'progress': copy.deepcopy(state['stage_progress'])})
        state['stage_progress'] = mapping['mapped']; template = target
        state['template_snapshot'] = None
    method_lines, conditions = _advance(p, draft, state, template, sample_data) if template and template['format'] == 'staged' else ([], [])
    if draft.get('operations') and (not template or template['format'] != 'staged'):
        raise C.SkillError('阶段操作需要显式选择阶段模板；普通记录可提供 method_text')
    if draft.get('method_text'): method_lines.append(draft['method_text'])
    text = _insert(text, '## 实验方案', '\n'.join(method_lines))
    if draft['action'] == 'pause':
        state['segments'].append({'action_id': draft['action_id'], 'status': 'completed', 'steps': copy.deepcopy(draft.get('operations', []))})
    if draft['action'] == 'pause' or state['followups']:
        refresh_followups(state, eid, template, draft.get('entry'))
    text = _results(p, draft, state, text, eid)
    if 'important' in draft:
        if not isinstance(draft['important'], bool): raise C.SkillError('important 须为布尔值')
        state['important'] = draft['important']
    elif old_record.is_file(): state['important'] = W.metadata.importance(old_record.read_text(encoding='utf-8'))
    status, at = W.properties(state)
    text = W.metadata.render(text, status, at, previous=old_record.read_text(encoding='utf-8') if old_record.is_file() else None,
                             important=state.get('important'))
    if '{{' in text or re.search(r'\bTODO\b', text, re.I): raise C.SkillError('正式记录不能包含模板占位符或 TODO')
    if draft['action'] == 'correct' and not draft.get('reason'): raise C.SkillError('更正缺少依据')
    if W.result_section(text) != (W.result_section(old_record.read_text(encoding='utf-8')) if old_record.is_file() else ''):
        affected = draft.get('affects_results')
        old_tasks = set(state_before['result_tasks']) - {r['id'] for r in draft.get('results', [])}
        if old_tasks and affected is None: raise C.SkillError('结果章节变动须明确 affects_results（无影响时显式 []）')
        for task_id in affected or []: W.invalidate_results(state, [task_id])
    inventory_plan = None
    if draft.get('inventory_items'):
        inventory_plan = I.preview_plan(p, eid, draft['inventory_items'], require_experiment=bool(draft.get('experiment')))
    # Bind the complete current state, record, sample snapshots, template content and action.
    token = digest({'draft': draft, 'state': state_before, 'record': C.sha256_file(old_record) if old_record.is_file() else None,
                    'samples': sample_hashes, 'template': (template or {}).get('sha256'),
                    'inventory': inventory_plan['hash'] if inventory_plan else None})
    return {'preview_hash': token, 'record': text, 'state': state, 'template': template,
            'inventory': inventory_plan, 'conditions': conditions,
            'next_action': 'resolve_conditions' if conditions else 'review_and_confirm',
            'prompts': prompts(state, template, sample_data) if template and template['format'] == 'staged' else [],
            'remaining': list(state['followups'].values())}


def save(p, draft, preview_hash, confirmed_by, inventory_hash=None):
    if not confirmed_by or not confirmed_by.strip(): raise C.SkillError('保存须记录明确确认来源')
    action_id = draft.get('action_id', '')
    path = receipt_path(p, action_id)
    W.recover_actions(p)
    if path.exists():
        receipt = json.loads(path.read_text(encoding='utf-8'))
        if receipt['draft_hash'] != digest(draft): raise C.SkillError('同动作标识不能重解释为其他操作')
        return continue_action(p, receipt)
    prepared = preview(p, draft)
    if prepared['preview_hash'] != preview_hash: raise C.SkillError('预览后记录、样品或模板发生变化，请重读并确认')
    if inventory_hash is not None and (not prepared['inventory'] or prepared['inventory']['hash'] != inventory_hash):
        raise C.SkillError('库存确认与已展示清单不符')
    eid = draft.get('experiment') or A.allocate_experiment(p, reservation_key=action_id)
    state = prepared['state']; state['experiment'] = eid
    state['template_snapshot'] = T.freeze(p, eid, prepared['template'])
    text = prepared['record'].replace('# pending-experiment\n', f'# {eid}\n', 1)
    # New follow-up identity must use the allocated experiment id, not preview placeholder.
    if not draft.get('experiment'):
        state['followups'] = {}
        if draft['action'] == 'pause': refresh_followups(state, eid, prepared['template'], draft.get('entry'))
    request_id = draft.get('request_id', action_id)
    raw_path = p.experiment_dir(eid) / '原始输入' / (C.sha256_text(request_id) + '.txt')
    registry_path = p.state / 'requests.json'
    registry = json.loads(registry_path.read_text(encoding='utf-8')) if registry_path.is_file() else {}
    source_entry = {'experiment': eid, 'sha256': C.sha256_text(draft['raw_input'])}
    if request_id in registry and registry[request_id] != source_entry: raise C.SkillError('请求标识已用于不同内容或实验')
    registry[request_id] = source_entry
    if not any(x['request_id'] == request_id for x in state['inputs']):
        state['inputs'].append({'request_id': request_id, 'path': W.stored_path(p, raw_path), 'sha256': source_entry['sha256']})
    state['record_round'] += 1
    if draft.get('inventory_items'):
        state['inventory'] = 'required'
        plan_path = I.plan_path(p, eid)
        state['inventory_previous_plan'] = C.sha256_file(plan_path) if plan_path.exists() else None
    elif (draft.get('inventory_review') or {}).get('mode') == 'none' and draft['inventory_review'].get('reason'):
        state.update(inventory='none', inventory_reason=draft['inventory_review']['reason'], inventory_review_round=state['record_round'])
    else: state['inventory'] = 'review_pending'
    state['record'] = {'path': f'实验/{eid}/{C.RECORD_NAME}', 'sha256': C.sha256_text(text),
                       'results_hash': C.sha256_text(W.result_section(text)), 'stale': False}
    state.update(updated=C.ts_now(), archived=False, archived_at=None)
    state['confirmations'].append({'action_id': action_id, 'preview_hash': preview_hash, 'confirmed_by': confirmed_by,
                                   'inventory_hash': inventory_hash})
    state['actions'][action_id] = {'status': 'record_saved', 'round': state['record_round']}
    receipt = {'action_id': action_id, 'experiment': eid, 'draft_hash': digest(draft), 'draft': draft,
               'inventory_authorized': inventory_hash is not None, 'confirmed_by': confirmed_by,
               'inventory_snapshots': (prepared['inventory'] or {}).get('snapshots'),
               'status': 'record_saved' if draft.get('inventory_items') else 'done'}
    target = p.experiment_dir(eid) / C.RECORD_NAME
    writes = {raw_path: draft['raw_input'], target: text, W.state_path(p, eid): C.json_text(state),
              registry_path: C.json_text(registry), path: C.json_text(receipt)}
    if target.exists(): writes[p.experiment_dir(eid) / C.STATE_DIR / 'record-history' / (C.sha256_file(target) + '.md')] = target.read_text(encoding='utf-8')
    manifest = p.experiment_dir(eid) / '归档清单.json'
    if manifest.exists(): writes[p.experiment_dir(eid) / C.STATE_DIR / 'archive-history' / (C.sha256_file(manifest) + '.json')] = manifest.read_text(encoding='utf-8')
    if draft['action'] == 'correct':
        import lineage
        changed_samples = sorted({op['sample'] for op in draft.get('operations', [])})
        writes[p.state / 'review-notices' / (C.sha256_text(action_id) + '.json')] = C.json_text({
            'id': action_id, 'samples': changed_samples, 'affected': lineage.affected_work(p, changed_samples), 'reason': draft['reason']})
    W.action_transaction(p, writes, deletes=[manifest] if manifest.exists() else [])
    return continue_action(p, receipt)


def continue_action(p, receipt):
    eid, draft = receipt['experiment'], receipt['draft']
    if draft.get('inventory_items') and receipt['status'] == 'record_saved':
        try:
            plan = I.build_plan(p, eid, draft['inventory_items'], receipt.get('inventory_snapshots'))
        except C.SkillError as exc:
            receipt.update(status='inventory_needs_review', reason=str(exc), inventory_authorized=False)
            C.atomic_write_text(receipt_path(p, receipt['action_id']), C.json_text(receipt))
            state = W.maybe_archive(p, eid)
            return {'experiment': eid, 'status': receipt['status'], 'reason': receipt['reason'],
                    'record_round': state['record_round'], 'inventory': state['inventory'], 'archived': state['archived']}
        if receipt['inventory_authorized']:
            I.commit(p, eid, plan['hash'], receipt['confirmed_by'])
            receipt['status'] = 'done'
        else: receipt['status'] = 'awaiting_inventory'
        receipt['plan_hash'] = plan['hash']
        C.atomic_write_text(receipt_path(p, receipt['action_id']), C.json_text(receipt))
    elif receipt['status'] in ('awaiting_inventory', 'inventory_needs_review'):
        path = I.plan_path(p, eid)
        plan = C._yamlish.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        completed_events = {h.get('key'): h for _, f, _ in C.iter_samples(p) for h in f.get('history', [])}
        all_done = all(completed_events.get(I.idempotency_key(eid, raw), {}).get('fingerprint') == I.event_fingerprint(raw)
                       for raw in draft['inventory_items'])
        if plan.get('status') == 'committed' and all_done:
            receipt['status'] = 'done'
            C.atomic_write_text(receipt_path(p, receipt['action_id']), C.json_text(receipt))
    state = W.maybe_archive(p, eid)
    return {'experiment': eid, 'action_id': receipt['action_id'], 'status': receipt['status'],
            'record_round': state['record_round'], 'inventory': state['inventory'],
            'plan_hash': receipt.get('plan_hash'), 'archived': state['archived'], 'execution': state['execution'],
            'followups': list(state['followups'].values())}


def resume(p, eid):
    state = W.peek_state(p, eid)
    template = T.frozen(p, state['template_snapshot']) if state['template_snapshot'] else None
    sample_data = {sid: C.load_sample(p, sid)[1] for sid in state['stage_progress']}
    return {'state': state, 'template': template, 'followups': list(state['followups'].values()),
            'prompts': prompts(state, template, sample_data) if template and template['format'] == 'staged' else [],
            'guidance': '依据已保存步骤和样品继续条件提示下一步；日历排期不是实际执行证据'}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--project', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    for cmd in ('preview', 'save'):
        arg = sub.add_parser(cmd); arg.add_argument('--file', required=True)
        if cmd == 'save':
            arg.add_argument('--preview-hash', required=True); arg.add_argument('--confirmed-by', required=True)
            arg.add_argument('--inventory-hash')
    arg = sub.add_parser('resume'); arg.add_argument('--experiment', required=True)
    args = parser.parse_args()
    try:
        p = C.Project(args.project)
        if args.command == 'resume': result = resume(p, args.experiment)
        else:
            data = json.loads(sys.stdin.buffer.read().decode('utf-8-sig') if args.file == '-' else Path(args.file).read_text(encoding='utf-8'))
            if args.command == 'preview': result = preview(p, data)
            else:
                with C.FileLock(p.state / 'workflow.lock'):
                    result = save(p, data, args.preview_hash, args.confirmed_by, args.inventory_hash)
        C.ok(result=result)
    except (C.SkillError, ValueError, OSError, KeyError, TypeError) as exc: C.die(str(exc), code='stage_error')


if __name__ == '__main__': main()
