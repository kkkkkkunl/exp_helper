"""Validated stage templates, immutable snapshots, and explicit upgrade mappings."""
from __future__ import annotations
import argparse
import copy
import json
import math
import re
from pathlib import Path
import _common as C


def validate(data):
    if not isinstance(data, dict) or data.get('version') != 1:
        raise C.SkillError('阶段模板须为 version: 1 的映射')
    stages = data.get('stages')
    if not isinstance(stages, list) or not stages:
        raise C.SkillError('阶段模板缺少 stages')
    ids = []
    for stage in stages:
        if not isinstance(stage, dict): raise C.SkillError('stage 须为映射')
        sid = C.safe_id(stage.get('id', ''))
        if sid in ids: raise C.SkillError(f'重复阶段：{sid}')
        ids.append(sid)
        for key in ('title', 'entry', 'pause_after', 'requires', 'input_types', 'outputs', 'next', 'steps'):
            if key not in stage: raise C.SkillError(f'{sid} 缺少 {key}')
        if not stage['title'] or not isinstance(stage['entry'], bool) or not isinstance(stage['pause_after'], bool):
            raise C.SkillError(f'{sid} 标题或入口/暂停声明不合法')
        for key in ('requires', 'input_types', 'outputs', 'next'):
            if not isinstance(stage[key], list) or not all(isinstance(x, str) for x in stage[key]):
                raise C.SkillError(f'{sid}.{key} 须为字符串数组')
        if not isinstance(stage['steps'], list) or not stage['steps']:
            raise C.SkillError(f'{sid} 缺少步骤')
        step_ids = set()
        for step in stage['steps']:
            if not isinstance(step, dict): raise C.SkillError('step 须为映射')
            step_id = C.safe_id(step.get('id', ''))
            if step_id in step_ids: raise C.SkillError(f'{sid} 重复步骤 {step_id}')
            step_ids.add(step_id)
            if not step.get('title') or not isinstance(step.get('fields'), list):
                raise C.SkillError(f'{sid}/{step_id} 缺少 title/fields')
            field_ids = set()
            for field in step['fields']:
                if not isinstance(field, dict): raise C.SkillError('field 须为映射')
                fid = C.safe_id(field.get('id', ''))
                if fid in field_ids: raise C.SkillError(f'{sid}/{step_id} 重复字段 {fid}')
                field_ids.add(fid)
                if not field.get('label') or field.get('type') not in ('number', 'integer', 'string', 'boolean'):
                    raise C.SkillError(f'{fid} 缺少 label 或类型非法')
                if not isinstance(field.get('required'), bool) or not isinstance(field.get('measurement'), bool):
                    raise C.SkillError(f'{fid} 须声明 required/measurement')
                if 'unit' not in field: raise C.SkillError(f'{fid} 须声明 unit（无单位可为 null）')
                if not isinstance(field.get('allow_unknown'), list) or any(x not in ('unmeasured', 'not_applicable') for x in field['allow_unknown']):
                    raise C.SkillError(f'{fid} 须声明 allow_unknown')
                if field['measurement'] and 'default' in field:
                    raise C.SkillError(f'{fid} 实测字段不得有模板默认值')
    if not any(s['entry'] for s in stages): raise C.SkillError('至少声明一个合法入口')
    by_id = {s['id']: s for s in stages}
    for stage in stages:
        if any(x not in by_id for x in stage['next']):
            raise C.SkillError(f'{stage["id"]} 的 next 引用了不存在阶段')
    visiting, visited = set(), set()
    def visit(sid):
        if sid in visiting: raise C.SkillError('静态阶段路径含循环；真实重做请使用尝试记录')
        if sid in visited: return
        visiting.add(sid)
        for nxt in by_id[sid]['next']: visit(nxt)
        visiting.remove(sid); visited.add(sid)
    for sid in ids: visit(sid)
    return data


def parse_content(content):
    """Read standalone YAML or one explicitly marked YAML fence in Markdown."""
    blocks = []
    fence = None
    marked = False
    lines = []
    for line in content.splitlines():
        if fence is not None:
            if re.fullmatch(r' {0,3}' + re.escape(fence[0]) + r'{' + str(len(fence)) + r',}[ \t]*', line):
                if marked: blocks.append('\n'.join(lines))
                fence, marked, lines = None, False, []
            elif marked:
                lines.append(line)
            continue
        match = re.fullmatch(r' {0,3}(`{3,}|~{3,})(.*)', line)
        if match:
            fence = match[1]
            marked = match[2].strip() == 'yaml experiment-workflow'
    if marked:
        raise C.SkillError('Markdown 阶段 YAML 代码块未闭合')
    if len(blocks) > 1:
        raise C.SkillError('Markdown 只能包含一个 yaml experiment-workflow 代码块')
    return validate(C._yamlish.loads(blocks[0] if blocks else content))


def load(p, config):
    path = (p.root / str(config['path'])).resolve()
    if not path.is_file(): raise C.SkillError(f'模板不存在：{path}')
    content = path.read_text(encoding='utf-8')
    fmt = config.get('format', 'plain')
    if fmt not in ('plain', 'staged'): raise C.SkillError('未知模板格式')
    data = parse_content(content) if fmt == 'staged' else None
    return {'name': config.get('name'), 'format': fmt, 'version': str(config.get('version', 'unspecified')),
            'experiment_skill': config.get('experiment_skill'),
            'source': path.relative_to(p.root).as_posix() if path.is_relative_to(p.root) else str(path),
            'sha256': C.sha256_text(content), 'content': content, 'data': data}


def select(p, name=None):
    config = p.template_by_name(name) if name else p.default_template()
    if not config:
        if p.cfg.get('method_templates'): raise C.SkillError('需要明确选择模板')
        return None
    return load(p, config)


def freeze(p, eid, template):
    if template is None: return None
    path = p.experiment_dir(eid) / C.STATE_DIR / 'templates' / (template['sha256'] + '.json')
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != template:
            raise C.SkillError('已有模板快照与同哈希内容不一致')
    else: C.atomic_write_text(path, C.json_text(template))
    return {k: template[k] for k in ('name', 'format', 'version', 'source', 'sha256')} | {
        'path': path.relative_to(p.root).as_posix(), 'experiment_skill': template.get('experiment_skill')}


def frozen(p, snapshot):
    path = (p.root / snapshot['path']).resolve()
    if not path.is_relative_to(p.root): raise C.SkillError('快照路径超出项目')
    template = json.loads(path.read_text(encoding='utf-8'))
    if C.sha256_text(template['content']) != snapshot['sha256'] or template['sha256'] != snapshot['sha256']:
        raise C.SkillError('模板快照内容校验失败')
    if any(template[k] != snapshot[k] for k in ('name', 'version', 'format', 'source')):
        raise C.SkillError('模板快照元信息校验失败')
    if 'experiment_skill' in snapshot and template.get('experiment_skill') != snapshot['experiment_skill']:
        raise C.SkillError('模板快照技能绑定校验失败')
    if template['format'] == 'staged':
        parsed = parse_content(template['content'])
        if parsed != template['data']: raise C.SkillError('模板解析内容与原文不一致')
    return template


def stage(template, stage_id):
    for item in ((template or {}).get('data') or {}).get('stages', []):
        if item['id'] == stage_id: return item
    raise C.SkillError(f'不存在阶段：{stage_id}')


def values(p, step, supplied, confirmed=()):
    if not isinstance(supplied, dict): raise C.SkillError('values 须为字段映射')
    fields = {f['id']: f for f in step['fields']}
    if set(supplied) - fields.keys() or set(confirmed) - fields.keys(): raise C.SkillError('存在未知字段')
    out, missing = {}, []
    for fid, field in fields.items():
        value = copy.deepcopy(supplied.get(fid))
        if value is None and fid in confirmed:
            if field['measurement'] or 'default' not in field:
                raise C.SkillError(f'{fid} 不允许用模板生成实测数据')
            value = {'value': field['default'], 'unit': field['unit'], 'source': 'confirmed_default'}
        if value is None:
            if field['required']: missing.append(fid)
            continue
        if not isinstance(value, dict): raise C.SkillError(f'{fid} 须提供 value/unit/source')
        source = value.get('source')
        if source not in ('user', 'confirmed_default') or (field['measurement'] and source != 'user'):
            raise C.SkillError(f'{fid} 缺少实际来源确认')
        if source == 'confirmed_default' and (fid not in confirmed or field.get('default') != value.get('value')):
            raise C.SkillError(f'{fid} 默认值未经本次明确确认')
        if value.get('status') in ('unmeasured', 'not_applicable'):
            if value['status'] not in field['allow_unknown'] or source != 'user':
                raise C.SkillError(f'{fid} 不允许该未知类别')
        else:
            raw = value.get('value')
            typ = field['type']
            valid = ((typ == 'number' and isinstance(raw, (int, float)) and not isinstance(raw, bool)) or
                     (typ == 'integer' and isinstance(raw, int) and not isinstance(raw, bool)) or
                     (typ == 'string' and isinstance(raw, str) and bool(raw.strip())) or
                     (typ == 'boolean' and isinstance(raw, bool)))
            if not valid or (typ in ('number', 'integer') and not math.isfinite(raw)):
                raise C.SkillError(f'{fid} 数值类型不合法')
            if field['unit']:
                if not value.get('unit'): raise C.SkillError(f'{fid} 缺少单位')
                if value['unit'] != field['unit']:
                    value['value'] = raw * p.convert_factor(value['unit'], field['unit'])
                    value['source_unit'] = value['unit']; value['unit'] = field['unit']
        out[fid] = value
    return out, missing


def upgrade_preview(state, old, new, stage_map, step_map):
    if not new or new['format'] != 'staged': raise C.SkillError('目标须为阶段模板')
    mapped = {}
    for sample, stages in state.get('stage_progress', {}).items():
        mapped[sample] = {}
        for sid, progress in stages.items():
            target = stage_map.get(sid)
            if not target: raise C.SkillError(f'缺少阶段映射：{sid}')
            new_stage = stage(new, target)
            if target in mapped[sample]: raise C.SkillError('多个阶段不能静默合并')
            dest = copy.deepcopy(progress); dest['steps'] = {}; dest['needs_review'] = True
            for step_id, info in progress.get('steps', {}).items():
                key = f'{sid}/{step_id}'
                step_target = step_map.get(key)
                ns = next((s for s in new_stage['steps'] if s['id'] == step_target), None)
                if not ns: raise C.SkillError(f'缺少或无效步骤映射：{key}')
                if step_target in dest['steps']: raise C.SkillError('步骤映射重复')
                copied = copy.deepcopy(info)
                # Validate target field compatibility; never silently drop old values.
                values_dummy = {f['id'] for f in ns['fields']}
                if set(copied.get('values', {})) - values_dummy: raise C.SkillError(f'{key} 有目标缺失字段')
                copied['needs_review'] = True
                dest['steps'][step_target] = copied
            mapped[sample][target] = dest
    return {'from': (old or {}).get('sha256'), 'to': new['sha256'], 'mapped': mapped,
            'impact': '保留旧模板与进度历史；映射后的已有值需按新定义复核'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True); parser.add_argument('--name')
    args = parser.parse_args()
    try:
        p = C.Project(args.project); C.ok(template=select(p, args.name))
    except (C.SkillError, ValueError, OSError) as exc: C.die(str(exc), code='template_error')


if __name__ == '__main__': main()
