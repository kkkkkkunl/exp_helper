"""Read-only experiment activation, skill-owned calculations and frozen evidence."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import _common as C
import skill_store


def digest(value):
    return C.sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False))


def binding(template):
    if not template:
        return None
    return template.get('experiment_skill')


def activate(p, experiment_type=None, template=None, skill=None, started=False, state=None):
    """No writes, locks, dependency installation, or experiment allocation."""
    if not started:
        return {'status': 'inactive', 'available': False, 'reason': '尚未明确开始或继续实验'}
    if state and state.get('skill_snapshot'):
        try:
            package = frozen(p, state['skill_snapshot'])
        except (C.SkillError, OSError, ValueError, KeyError, TypeError) as exc:
            return {'status': 'missing_evidence', 'available': False, 'reason': str(exc)}
        if skill and skill != package['skill']:
            return {'status': 'needs_upgrade', 'available': False, 'reason': '续接不得静默更换技能'}
        return {'status': 'ready', 'available': True, 'skill': package['skill'],
                'evidence_hash': package['sha256'], 'frozen': True, 'package': package}
    if not experiment_type or not template:
        return {'status': 'undetermined', 'available': False, 'reason': '实验类型及模板或方案尚未明确'}
    selected, source = skill, 'explicit'
    if not selected:
        selected, source = binding(template), 'template'
    if not selected:
        source = 'experiment_type'
        hits = [r.get('skill') for r in (p.cfg.get('experiment_skill_map') or [])
                if isinstance(r, dict) and r.get('experiment_type') == experiment_type]
        hits = list(dict.fromkeys(hits))
        if len(hits) > 1:
            return {'status': 'need_choice', 'available': False, 'candidates': hits,
                    'reason': '命中多个实验技能，请明确选择'}
        selected = hits[0] if hits else None
    if isinstance(selected, list):
        if len(selected) != 1:
            return {'status': 'need_choice', 'available': False, 'candidates': selected,
                    'reason': '模板技能绑定有多个候选，请明确选择'}
        selected = selected[0]
    if not selected:
        return {'status': 'missing_skill', 'available': False, 'reason': '没有匹配的实验 skill；保留独立记录'}
    if not isinstance(selected, str):
        raise C.SkillError('实验技能名称须为字符串，不能使用普通记录字段代替绑定')
    resolved = skill_store.resolve(p, selected)
    if not resolved['available']:
        return {**resolved, 'status': 'missing_skill', 'source': source, 'reason': resolved['message']}
    try:
        package = capture(p, selected)
    except (C.SkillError, OSError, ValueError) as exc:
        return {'skill': selected, 'available': False, 'status': 'invalid_skill', 'reason': str(exc)}
    applicable = package['manifest'].get('experiment_types') or resolved['metadata'].get('experiment_types') or []
    if applicable and experiment_type not in applicable:
        return {'skill': selected, 'available': False, 'status': 'inapplicable', 'reason': '技能声明不适用于本实验类型'}
    return {**resolved, 'status': 'ready', 'source': source, 'evidence_hash': package['sha256'],
            'frozen': False, 'package': package}


def capture(p, name):
    selected = skill_store.resolve(p, name)
    if not selected['available']:
        raise C.SkillError(selected['message'])
    root = Path(selected['skill_path']).parent
    files = {}
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if any(x in ('.git', '__pycache__') for x in rel.parts):
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise C.SkillError('技能内容不接受符号链接或越界引用')
        if path.is_file():
            raw = path.read_bytes()
            files[rel.as_posix()] = {'base64': base64.b64encode(raw).decode('ascii'),
                                    'sha256': hashlib.sha256(raw).hexdigest()}
    package = {'skill': name, 'version': selected['metadata']['version'],
               'source': selected['metadata']['path'], 'files': files}
    package['sha256'] = digest(package)
    package['manifest'] = _manifest(package)
    return package


def _manifest(package):
    raw = package['files'].get('experiment-skill.json')
    if not raw:
        return {}
    data = json.loads(base64.b64decode(raw['base64']).decode('utf-8-sig'))
    if not isinstance(data, dict) or data.get('version') != 1:
        raise C.SkillError('experiment-skill.json 须为 version: 1')
    if not isinstance(data.get('calculations', {}), dict):
        raise C.SkillError('calculations 须为计算定义映射')
    for key in ('tools', 'experiment_types'):
        if key in data and (not isinstance(data[key], list) or not all(isinstance(v, str) for v in data[key])):
            raise C.SkillError(f'{key} 须为字符串列表')
    for name, definition in data.get('calculations', {}).items():
        if not isinstance(definition, dict): raise C.SkillError(f'{name} 计算定义须为映射')
        for group in ('inputs', 'outputs'):
            fields = definition.get(group, {})
            if not isinstance(fields, dict): raise C.SkillError(f'{name}.{group} 须为字段映射')
            for field, rule in fields.items():
                if not isinstance(rule, dict) or 'unit' not in rule:
                    raise C.SkillError(f'{name}.{field} 须明确单位，无单位为 null')
                if rule['unit'] is not None and not isinstance(rule['unit'], str):
                    raise C.SkillError('计算字段单位须为字符串或 null')
                if 'minimum' in rule and (isinstance(rule['minimum'], bool) or
                        not isinstance(rule['minimum'], (int, float)) or not math.isfinite(rule['minimum'])):
                    raise C.SkillError('计算范围须为有限数值')
                if 'required' in rule and not isinstance(rule['required'], bool):
                    raise C.SkillError('required 须为布尔值')
    return data


def verify(package):
    raw = {k: package[k] for k in ('skill', 'version', 'source', 'files')}
    if digest(raw) != package['sha256']:
        raise C.SkillError('技能快照整体哈希不匹配')
    for name, item in package['files'].items():
        if Path(name).is_absolute() or Path(name).drive or '..' in Path(name).parts:
            raise C.SkillError('技能快照文件路径越界')
        if hashlib.sha256(base64.b64decode(item['base64'], validate=True)).hexdigest() != item['sha256']:
            raise C.SkillError('技能快照文件哈希不匹配')
    if package.get('manifest') != _manifest(package):
        raise C.SkillError('技能快照计算声明不匹配')
    return package


def snapshot_writes(p, eid, package):
    verify(package)
    path = p.experiment_dir(eid) / C.STATE_DIR / 'skills' / (package['sha256'] + '.json')
    if path.exists() and json.loads(path.read_text(encoding='utf-8')) != package:
        raise C.SkillError('同哈希技能快照内容不一致')
    return {'skill': package['skill'], 'version': package['version'], 'sha256': package['sha256'],
            'path': path.relative_to(p.root).as_posix()}, {path: C.json_text(package)}


def frozen(p, reference):
    path = skill_store.inside(p.root, reference['path'])
    package = verify(json.loads(path.read_text(encoding='utf-8')))
    if any(reference[k] != package[k] for k in ('skill', 'version', 'sha256')):
        raise C.SkillError('技能快照引用不匹配')
    return package


def execute(package, request):
    """A skill owns the executable formula. The coordinator never evaluates expressions."""
    verify(package)
    name = request.get('calculation')
    definition = package['manifest'].get('calculations', {}).get(name)
    if not definition:
        if request.get('host_execution'):
            return host_result(package, request)
        return {'status': 'host_required', 'reason': '目标 skill 未提供此计算的可执行契约；按其正文由宿主处理，不编造接口'}
    missing, errors = [], []
    supplied = request.get('inputs', {})
    if not isinstance(supplied, dict):
        raise C.SkillError('计算 inputs 须为映射')
    for key, rule in definition.get('inputs', {}).items():
        value = supplied.get(key)
        if value is None:
            if rule.get('required', True): missing.append(key)
            continue
        if not isinstance(value, dict) or value.get('source') not in ('user', 'confirmed_parameter', 'calculated'):
            errors.append(f'{key}: 缺少明确输入来源'); continue
        number = value.get('value')
        if isinstance(number, bool) or not isinstance(number, (float, int)) or not math.isfinite(number):
            errors.append(f'{key}: 需要有限数值'); continue
        if value.get('unit') != rule.get('unit'):
            errors.append(f'{key}: 单位不一致')
        if 'minimum' in rule and number < rule['minimum']:
            errors.append(f'{key}: 低于技能允许范围')
    if missing: return {'status': 'missing_inputs', 'missing': missing, 'reason': '当前计算必要输入待补'}
    if errors: return {'status': 'invalid_inputs', 'errors': errors, 'reason': '输入不满足技能约束'}
    if request.get('host_execution'):
        return host_result(package, request, definition)
    tools = package['manifest'].get('tools', [])
    unavailable = [tool for tool in tools if not shutil.which(tool)]
    if unavailable:
        return {'status': 'tools_unavailable', 'reason': '缺少计算工具', 'tools': unavailable}
    entry = definition.get('entrypoint')
    if not entry or entry not in package['files'] or Path(entry).suffix != '.py':
        return {'status': 'host_required', 'reason': '没有可用 Python 计算入口；由宿主遵循技能工具要求'}
    # Running a copy isolates incidental outputs from the project and keeps the frozen imports available.
    with tempfile.TemporaryDirectory(prefix='experiment-skill-') as tmp:
        root = Path(tmp)
        for filename, item in package['files'].items():
            dest = root / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(base64.b64decode(item['base64']))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
        try:
            result = subprocess.run([sys.executable, '-B', str(root / entry)], input=C.json_text(request),
                                    text=True, encoding='utf-8', capture_output=True, cwd=root, env=env, timeout=30)
            if result.returncode:
                return {'status': 'tool_error', 'reason': result.stderr.strip() or '技能计算入口失败'}
            answer = json.loads(result.stdout)
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            return {'status': 'tool_error', 'reason': str(exc)}
    if not isinstance(answer, dict):
        return {'status': 'invalid_result', 'reason': '技能返回值须为 JSON 对象'}
    if answer.get('status') != 'computed':
        return {'status': 'invalid_result', 'reason': answer.get('reason') or '技能未返回可用计算',
                'details': answer}
    outputs = answer.get('outputs', {})
    if not isinstance(outputs, dict) or not outputs:
        return {'status': 'invalid_result', 'reason': '技能未返回输出映射'}
    for key, item in outputs.items():
        if (not isinstance(item, dict) or 'unit' not in item or isinstance(item.get('value'), bool)
                or not isinstance(item.get('value'), (int, float)) or not math.isfinite(item['value'])):
            return {'status': 'invalid_result', 'reason': f'{key}: 输出不是带单位的有限数值'}
    for key, rule in definition.get('outputs', {}).items():
        item = outputs.get(key, {})
        value = item.get('value')
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                or item.get('unit') != rule.get('unit') or ('minimum' in rule and value < rule['minimum'])):
            return {'status': 'invalid_result', 'reason': f'{key}: 输出缺失、单位错误或违反技能范围'}
    return {'status': 'computed', 'outputs': outputs, 'basis': definition.get('basis', name),
            'tool_version': sys.version.split()[0]}


def host_result(package, request, definition=None):
    """Record an actual host/tool execution using the skill's prose rules, not a made-up runner."""
    evidence = request['host_execution']
    if not isinstance(evidence, dict): raise C.SkillError('host_execution 须为证据对象')
    if (evidence.get('skill_hash') != package['sha256'] or evidence.get('input_hash') !=
            digest({'inputs': request.get('inputs', {}), 'params': request.get('params', {})})):
        return {'status': 'invalid_result', 'reason': '宿主计算依据或输入指纹不匹配'}
    rule = package['files'].get(evidence.get('rule_file'))
    basis = evidence.get('basis')
    if (not rule or not isinstance(basis, str) or not basis.strip()
            or basis not in base64.b64decode(rule['base64']).decode('utf-8-sig')):
        return {'status': 'invalid_result', 'reason': '计算规则不能从所固定的技能正文追溯'}
    if not evidence.get('tool') or not evidence.get('tool_version'):
        return {'status': 'invalid_result', 'reason': '缺少实际计算工具及版本证据'}
    outputs = evidence.get('outputs')
    if not isinstance(outputs, dict) or not outputs:
        return {'status': 'invalid_result', 'reason': '宿主尚未提供计算结果'}
    for key, item in outputs.items():
        if (not isinstance(item, dict) or 'unit' not in item or isinstance(item.get('value'), bool)
                or not isinstance(item.get('value'), (int, float)) or not math.isfinite(item['value']) or item['value'] < 0):
            return {'status': 'invalid_result', 'reason': f'{key}: 不是有效的非负上样计算量'}
    for key, rule in (definition or {}).get('outputs', {}).items():
        item = outputs.get(key, {})
        if key not in outputs or item.get('unit') != rule.get('unit') or item['value'] < rule.get('minimum', 0):
            return {'status': 'invalid_result', 'reason': f'{key}: 与技能输出约束不符'}
    return {'status': 'computed', 'outputs': outputs, 'basis': basis,
            'tool_version': str(evidence['tool_version']), 'host_execution': copy.deepcopy(evidence)}


def prepare(p, draft, state, template):
    """Pure calculation preview. Saved calculations are separate from executed operations."""
    requests = draft.get('calculations', [])
    upgrade = draft.get('skill_upgrade')
    if upgrade and (upgrade.get('confirmed') is not True or not upgrade.get('reason')):
        raise C.SkillError('技能升级须展示差异影响并明确确认与依据')
    previous = state.get('skill_snapshot')
    resolution = activate(p, draft.get('experiment_type') or state.get('experiment_type'), template,
                          (upgrade or {}).get('skill') or draft.get('experiment_skill'),
                          started=True, state=None if upgrade else state)
    package = resolution.get('package')
    if draft.get('skill_evidence_hash') and (not package or package['sha256'] != draft['skill_evidence_hash']):
        raise C.SkillError('技能依据在计算或预览后变化，须重新计算并确认')
    if draft.get('experiment_type'): state['experiment_type'] = draft['experiment_type']
    if upgrade and not package:
        raise C.SkillError('升级目标技能不可用')
    calculations = state.setdefault('calculations', {})
    changed = set()
    seen = set()
    for request in requests:
        key = C.safe_id(request.get('id', ''))
        if key in seen: raise C.SkillError('本次计算 id 重复')
        seen.add(key)
        for field in ('sample', 'stage', 'step'):
            if not request.get(field): raise C.SkillError(f'计算缺少 {field}')
        expected_attempt = state.get('stage_progress', {}).get(request['sample'], {}).get(request['stage'], {}).get('attempt', 1)
        info = {k: copy.deepcopy(request[k]) for k in ('sample', 'stage', 'step', 'calculation', 'inputs', 'params', 'depends_on') if k in request}
        info.update(id=key, attempt=expected_attempt, source='calculated')
        dependencies = info.get('depends_on', [])
        if key in dependencies or any(dep not in calculations for dep in dependencies):
            raise C.SkillError('计算依赖须先存在且不得引用自身')
        if package:
            invalid_source = []
            for input_name, value in info.get('inputs', {}).items():
                if isinstance(value, dict) and value.get('source') == 'calculated':
                    upstream = calculations.get(value.get('calculation_id'), {})
                    output = upstream.get('outputs', {}).get(value.get('output'), {})
                    if (value.get('calculation_id') not in dependencies or upstream.get('status') != 'computed'
                            or value.get('value') != output.get('value') or value.get('unit') != output.get('unit')):
                        invalid_source.append(input_name)
            if invalid_source:
                answer = {'status': 'invalid_inputs', 'reason': '计算输入无法匹配已声明依赖的实际输出', 'errors': invalid_source}
            elif any(calculations[dep].get('status') != 'computed' for dep in dependencies):
                answer = {'status': 'needs_review', 'reason': '依赖计算尚不可用，须复核输入'}
            else: answer = execute(package, request)
            info.update(skill=package['skill'], skill_hash=package['sha256'], skill_version=package['version'])
        else:
            answer = {'status': resolution['status'], 'reason': resolution.get('reason') or resolution.get('message')}
        info.update(answer)
        old = calculations.get(key)
        if old != info:
            if old and not (request.get('reason') or draft.get('reason') or upgrade):
                raise C.SkillError('已保存计算变化须说明更正或重算依据')
            if old:
                state.setdefault('calculation_changes', []).append({'id': key, 'before': old,
                    'reason': request.get('reason') or draft.get('reason') or upgrade['reason'], 'action_id': draft['action_id']})
            calculations[key] = info
            changed.add(key)
    visiting, visited = set(), set()
    def visit(key):
        if key in visiting: raise C.SkillError('计算依赖存在循环')
        if key in visited: return
        visiting.add(key)
        for dep in calculations[key].get('depends_on', []): visit(dep)
        visiting.remove(key); visited.add(key)
    for key in calculations: visit(key)
    # Explicit upgrades invalidate all calculations which used the old evidence unless recalculated now.
    if upgrade and previous:
        for key, info in calculations.items():
            if key not in changed and info.get('skill_hash') == previous['sha256']:
                info.update(status='needs_review', reason='技能依据升级，需按新依据复核'); changed.add(key)
    pending = set(changed)
    while pending:
        current = pending.pop()
        for key, info in calculations.items():
            if current in info.get('depends_on', []) and key not in changed:
                info.update(status='needs_review', reason=f'依赖计算 {current} 已变化')
                changed.add(key); pending.add(key)
    if upgrade:
        state.setdefault('skill_history', []).append({'snapshot': previous, 'reason': upgrade['reason'],
                                                     'action_id': draft['action_id']})
    old_files = frozen(p, previous)['files'] if upgrade and previous else {}
    return {'resolution': {k: v for k, v in resolution.items() if k != 'package'},
            'package': package, 'calculations': calculations, 'changed': sorted(changed),
            'upgrade': {'before': previous, 'after': package['sha256'], 'affected': sorted(changed),
                        'changed_files': sorted(k for k in set(old_files) | set(package['files'])
                                                if old_files.get(k) != package['files'].get(k))} if upgrade else None}


def render(calculations):
    if not calculations: return ''
    lines = ['## 上样计算', '', '以下为计算用量；实际执行与实际用量另见实验方法。', '']
    for key, item in calculations.items():
        lines += [f'### {key}（{item["sample"]} / {item["stage"]} / {item["step"]}）', '',
                  f'- 状态：{item["status"]}；来源：skill 计算；尝试：{item["attempt"]}',
                  f'- 技能：{item.get("skill", "未解析")}；依据哈希：{item.get("skill_hash", "未知")}',
                  f'- 规则：{item.get("basis", item.get("calculation", ""))}',
                  '- 输入：' + json.dumps(item.get('inputs', {}), ensure_ascii=False),
                  '- 参数：' + json.dumps(item.get('params', {}), ensure_ascii=False)]
        if item.get('status') == 'computed':
            lines.append('- 计算用量：' + json.dumps(item.get('outputs', {}), ensure_ascii=False))
        else:
            lines.append('- 待处理：' + str(item.get('reason', '需复核')))
        lines.append('')
    return '\n'.join(lines)
