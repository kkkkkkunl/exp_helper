"""Canonical record structure loaded from the formal record template."""
from __future__ import annotations
import re
from pathlib import Path
import _common as C
import _record_metadata as metadata

TEMPLATE = Path(__file__).resolve().parents[1] / 'assets' / 'experiment-record.template.md'
TOKEN = re.compile(r'{{([^{}]+)}}')
HEADING = re.compile(r'^(#{1,6})\s+(.+?)\s*$', re.M)


def template_text():
    return TEMPLATE.read_text(encoding='utf-8-sig')


def render(eid, actual_date=None, project=None, purpose=None, reference=None, template=None,
           method=None, results=None, attachments=None):
    values = {'实验编号': eid, '实际实验日期': actual_date or '', '项目名': project or '',
              '目的': purpose or '', '参考方案': reference or '', '实验方法': method or '', '结果': results or '',
              '附件': attachments or '', '模板名': (template or {}).get('name') or '',
              '模板版本': (template or {}).get('version') or '',
              '模板文件': (template or {}).get('source') or ''}
    lines = []
    for line in template_text().splitlines():
        names = TOKEN.findall(line)
        if any(name not in values for name in names):
            raise C.SkillError('正式记录模板存在未知字段：' + '、'.join(n for n in names if n not in values))
        if line.lstrip().startswith('- ') and any(not values[name] for name in names):
            continue
        lines.append(TOKEN.sub(lambda m: str(values[m.group(1)]), line))
    output = '\n'.join(lines).rstrip() + '\n'
    validate(output, eid)
    return output


def is_canonical(text):
    body = metadata.split(text)[1]
    return all(re.search(pattern, body, re.M) for pattern in (
        r'^\|\s*项\s*\|\s*内容\s*\|', r'^###\s+参考方案\s*$', r'^###\s+实验方法\s*$'))


def validate(text, eid):
    header, body = metadata.split(text)
    if not header:
        raise C.SkillError('新记录缺少模板元信息')
    props = metadata.blocks(header)[1]
    for key in ('completed', 'completed_at', 'important'):
        if key not in props: raise C.SkillError(f'新记录缺少元信息 {key}')
    if TOKEN.search(text) or re.search(r'\bTODO\b', text, re.I):
        raise C.SkillError('正式记录不能包含模板占位符或 TODO')
    required = [(len(m.group(1)), m.group(2)) for m in HEADING.finditer(metadata.split(template_text())[1])
                if len(m.group(1)) > 1]
    headings = [(len(m.group(1)), m.group(2)) for m in HEADING.finditer(body)]
    if not headings or headings[0] != (1, eid) or sum(level == 1 for level, _ in headings) != 1:
        raise C.SkillError(f'新记录首标题须为 # {eid}')
    expected_top = [name for level, name in required if level == 2]
    top = [(index, name) for index, (level, name) in enumerate(headings) if level == 2]
    top_names = [name for _, name in top]
    allowed_top = expected_top[:2] + ['上样计算'] + expected_top[2:]
    if top_names not in (expected_top, allowed_top):
        raise C.SkillError('新记录顶层章节缺失、层级或顺序错误：应为 ' + ' → '.join(expected_top) + '（上样计算可位于实验方案与结果之间）')
    for index, (level, name) in enumerate(headings[1:], 1):
        if level > 3: raise C.SkillError(f'新记录标题层级错误：{name}')
        if level == 3:
            parent = next((n for j, n in reversed(top) if j < index), None)
            if parent is None: raise C.SkillError(f'子章节缺少顶层章节：{name}')
    plan_start = next(i for i, name in top if name == '实验方案')
    plan_end = next((i for i, name in top if i > plan_start), len(headings))
    plan_children = [name for level, name in headings[plan_start+1:plan_end] if level == 3]
    expected_children = [name for level, name in required if level == 3]
    positions = [plan_children.index(name) if name in plan_children else -1 for name in expected_children]
    if any(i < 0 for i in positions) or positions != sorted(positions):
        raise C.SkillError('实验方案缺少必需子章节，或参考方案／实验方法层级与顺序错误')
    for name in expected_children:
        if plan_children.count(name) != 1: raise C.SkillError(f'实验方案子章节重复：{name}')
    expected_rows = [re.match(r'^\|\s*([^|]+?)\s*\|', line).group(1).strip()
                     for line in metadata.split(template_text())[1].splitlines()
                     if re.match(r'^\|\s*[^|]+?\s*\|', line) and not line.startswith('|---')]
    first_section = re.search(r'^##\s+', body, re.M)
    table_area = body[:first_section.start()] if first_section else body
    table_lines = [line.strip() for line in table_area.splitlines() if line.lstrip().startswith('|')]
    rows = [re.match(r'^\|\s*([^|]+?)\s*\|', line).group(1).strip()
            for line in table_lines if re.match(r'^\|\s*[^|]+?\s*\|', line) and not line.startswith('|---')]
    if (len(table_lines) < len(expected_rows) + 1 or
            not re.fullmatch(r'\|\s*:?-{3,}:?\s*\|\s*:?-{3,}:?\s*\|', table_lines[1]) or
            rows[:len(expected_rows)] != expected_rows):
        raise C.SkillError('新记录基本信息表缺失或行序错误')
    return True


def migration_preview(p, eid):
    """Preview a lossless mapping of a known legacy section layout."""
    path = p.experiment_dir(eid) / C.RECORD_NAME
    if not path.is_file(): raise C.SkillError('旧记录不存在')
    old = path.read_text(encoding='utf-8')
    if is_canonical(old): raise C.SkillError('记录已经采用正式模板结构')
    body = metadata.split(old)[1]
    headings = list(re.finditer(r'^##\s+(.+?)\s*$\n?', body, re.M))
    if not headings: raise C.SkillError('旧记录没有可映射的章节')
    names = [m.group(1).strip() for m in headings]
    if len(names) != len(set(names)): raise C.SkillError('旧记录章节重复，须先明确归属')
    preamble = body[:headings[0].start()]
    preamble = re.sub(r'^#\s+' + re.escape(eid) + r'\s*$', '', preamble, flags=re.M)
    preamble = re.sub(r'^实际(?:实验)?日期[：:]\s*\d{4}-\d{2}-\d{2}\s*$', '', preamble, flags=re.M)
    if preamble.strip(): raise C.SkillError('旧记录开头有未归属内容，须先明确迁移位置')
    content = {m.group(1).strip(): body[m.end():headings[i+1].start() if i+1 < len(headings) else len(body)].strip()
               for i, m in enumerate(headings)}
    required = ('目的', '实验方案', '结果', '附件')
    missing = [name for name in required if name not in content]
    extras = [name for name in content if name not in required and name != '上样计算']
    if missing or extras:
        raise C.SkillError('旧记录迁移须先核对章节归属；缺少：' + '、'.join(missing) + '；未映射：' + '、'.join(extras))
    plan = content['实验方案']
    child = list(re.finditer(r'^###\s+(.+?)\s*$\n?', plan, re.M))
    if child:
        prefix = plan[:child[0].start()].strip()
        if prefix: raise C.SkillError('旧实验方案有未归属的前置文字，须先明确迁移位置')
        parts = {m.group(1).strip(): plan[m.end():child[i+1].start() if i+1 < len(child) else len(plan)].strip()
                 for i, m in enumerate(child)}
        if set(parts) - {'参考方案', '实验方法'}:
            raise C.SkillError('旧实验方案有未归属的子章节，须先明确迁移位置')
        reference, method = parts.get('参考方案', ''), parts.get('实验方法', '')
    else:
        reference, method = '', plan
    candidate = render(eid, actual_date=_legacy_date(body), project=p.root.name,
                       purpose=content['目的'], reference=reference, method=method,
                       results=content['结果'], attachments=content['附件'])
    if '上样计算' in content:
        candidate = candidate.replace('## 结果', '## 上样计算\n\n' + content['上样计算'] + '\n\n## 结果', 1)
    header = metadata.split(old)[0]
    if header:
        old_props = C._yamlish.loads(header)
        candidate = metadata.render(candidate, 'completed' if old_props.get('completed') else 'in_progress',
                                    old_props.get('completed_at'), previous=old, important=metadata.importance(old))
    validate(candidate, eid)
    source_hash = C.sha256_text(old)
    preview_hash = C.sha256_text(source_hash + '\n' + candidate)
    return {'record': candidate, 'source_hash': source_hash, 'preview_hash': preview_hash,
            'mapping': {'目的': '目的', '实验方案': '参考方案／实验方法', '结果': '结果', '附件': '附件',
                        '上样计算': '上样计算' if '上样计算' in content else None}}


def _legacy_date(body):
    match = re.search(r'^实际(?:实验)?日期[：:]\s*(\d{4}-\d{2}-\d{2})\s*$', body, re.M)
    return match.group(1) if match else None
