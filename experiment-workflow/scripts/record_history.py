"""Project-level record snapshots; callers commit returned writes in one journal."""
from __future__ import annotations

from datetime import timedelta
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

import _common as C


def _relocate(text, source, destination, p):
    links = []

    def target(value):
        angle = value.startswith('<') and value.endswith('>')
        plain = value[1:-1] if angle else value
        parts = urlsplit(plain)
        if parts.scheme or parts.netloc or plain.startswith(('#', '/', '\\')):
            return value
        path = (source.parent / unquote(parts.path)).resolve()
        if not path.is_relative_to(p.root):
            raise C.SkillError('历史附件引用超出项目，需先明确可迁移引用')
        if not path.is_file():
            raise C.SkillError(f'历史附件引用不可定位：{plain}')
        relative = Path(os.path.relpath(path, destination.parent)).as_posix()
        replacement = quote(relative, safe='/._-~')
        if parts.query: replacement += '?' + parts.query
        if parts.fragment: replacement += '#' + parts.fragment
        links.append({'original': plain, 'path': path.relative_to(p.root).as_posix(),
                      'reference': replacement, 'sha256': C.sha256_file(path)})
        return '<' + replacement + '>' if angle else replacement

    # Do not rewrite examples in fenced or inline code. Preserve all other prose verbatim.
    fence = None
    out = []
    for line in text.splitlines(keepends=True):
        marked = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marked:
            if fence is None: fence = marked[1][0]
            elif marked[1][0] == fence: fence = None
            out.append(line); continue
        if fence is not None:
            out.append(line); continue
        chunks = re.split(r'(`+[^`]*`+)', line)
        for i in range(0, len(chunks), 2):
            chunk = chunks[i]
            chunk = re.sub(r'(!?\[[^\]\n]*\]\()(<[^>]+>|[^\s)]+)([^)\n]*\))',
                           lambda m: m[1] + target(m[2]) + m[3], chunk)
            chunk = re.sub(r'^(\s*\[[^\]]+\]:\s*)(<[^>]+>|\S+)(.*)$',
                           lambda m: m[1] + target(m[2]) + m[3], chunk)
            # Obsidian sample/experiment identifiers remain globally resolvable wiki links.
            def wiki(m):
                name, sep, label = m[2].partition('|')
                if '/' not in name and not Path(name.split('#')[0]).suffix:
                    return m[0]
                converted = target(name)
                caption = label if sep else name
                return m[1] + '[' + caption + '](' + converted + ')'
            chunks[i] = re.sub(r'(!?)\[\[([^\]]+)\]\]', wiki, chunk)
        out.append(''.join(chunks))
    return ''.join(out), links


def prepare(p, eid, state, old, new, action_id, reason):
    if old is None or old == new:
        return {}
    history = state.setdefault('record_history', [])
    for item in history:
        if item['action_id'] == action_id:
            if item['original_sha256'] != C.sha256_text(old):
                raise C.SkillError('历史动作标识对应其他旧记录')
            return {}
    at = C.now_cn()
    while True:
        path = p.root / 'history' / f'{eid}_{at.strftime("%Y%m%d-%H%M%S-%f")}.md'
        if not path.exists() and all(h['path'] != path.relative_to(p.root).as_posix() for h in history):
            break
        at += timedelta(microseconds=1)
    source = p.experiment_dir(eid) / C.RECORD_NAME
    rendered, links = _relocate(old, source, path, p)
    history.append({'experiment': eid, 'path': path.relative_to(p.root).as_posix(),
                    'sha256': C.sha256_text(rendered), 'original_sha256': C.sha256_text(old),
                    'modified_at': at.isoformat(), 'action_id': action_id, 'reason': reason,
                    'attachments': links})
    return {path: rendered}


def files(p, eid, state, validate=False):
    result = []
    for item in state.get('record_history', []):
        path = (p.root / item['path']).resolve()
        if item.get('experiment') != eid or path.parent != (p.root / 'history').resolve():
            raise C.SkillError('实验历史归属或路径不一致')
        if not path.is_file() or C.sha256_file(path) != item['sha256']:
            raise C.SkillError(f'实验历史缺失或内容变化：{item["path"]}')
        if validate:
            for link in item.get('attachments', []):
                attachment = (p.root / link['path']).resolve()
                if (not attachment.is_relative_to(p.root) or not attachment.is_file()
                        or C.sha256_file(attachment) != link['sha256']):
                    raise C.SkillError(f'历史附件证据缺失或变化：{link["path"]}')
        result.append(path)
    return result
