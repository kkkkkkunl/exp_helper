"""Edit managed Obsidian properties without reserializing unrelated YAML/body."""
import json
import re
import _common as C

KEY = re.compile(r'''^(?:([A-Za-z_\u0080-\uffff][\w-]*)|"([^"\\]+)"|'([^']+)'):\s*''')
MANAGED = {'status', 'completed', 'completed_at', 'important'}


def split(text):
    text = text.lstrip('\ufeff')
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != '---':
        return '', text
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            return ''.join(lines[1:i]), ''.join(lines[i+1:])
    raise C.SkillError('记录属性缺少结束的 ---')


def blocks(header):
    """Retain raw YAML blocks (nested values, comments, multiline scalars)."""
    found, prefix, current, content = {}, '', None, []
    for line in header.splitlines(keepends=True):
        match = KEY.match(line)
        if match:
            if current is not None:
                found[current] = ''.join(content)
            else:
                prefix = ''.join(content)
            current = next(x for x in match.groups() if x is not None)
            if current in found:
                raise C.SkillError(f'重复文档属性：{current}')
            content = [line]
        else:
            if current is None and line.strip() and not line.lstrip().startswith('#'):
                raise C.SkillError('文档属性须使用 YAML 顶层映射，不能使用 JSON/流式映射')
            content.append(line)
    if current is not None:
        found[current] = ''.join(content)
    else:
        prefix = ''.join(content)
    return prefix, found


def importance(text):
    _, values = blocks(split(text)[0])
    value = C._yamlish.loads(values.get('important', 'important: false')).get('important')
    if not isinstance(value, bool): raise C.SkillError('important 必须为布尔值')
    return value


def render(text, status, completed_at=None, previous=None, important=None):
    header, body = split(text)
    prefix, values = blocks(header)
    if previous:
        old_header, _ = split(previous)
        old_prefix, old_values = blocks(old_header)
        if not header:
            prefix = old_prefix
        for key, value in old_values.items():
            if key not in values and (key not in MANAGED or key == 'important'):
                values[key] = value
    if important is None:
        raw = values.get('important', 'important: false')
        raw_value = C._yamlish.loads(raw).get('important')
        if not isinstance(raw_value, bool): raise C.SkillError('important 必须为布尔值')
        important = raw_value
    if not isinstance(important, bool): raise C.SkillError('important 必须为布尔值')
    custom = ''.join(value if value.endswith('\n') else value+'\n'
                     for key, value in values.items() if key not in MANAGED)
    timestamp = json.dumps(completed_at, ensure_ascii=False) if completed_at else 'null'
    managed = f'completed: {str(status == "completed").lower()}\ncompleted_at: {timestamp}\nimportant: {str(important).lower()}\n'
    return '---\n' + managed + prefix + custom + '---\n' + body
