"""Publish a prepared method and its blank record layout as one project action."""
import argparse
import json
import sys
from pathlib import Path

import _common as C
import record_format as R
import stage_templates as T
import workflow as W


def publish(root, prepared):
    name = prepared.get('name')
    method = prepared.get('method')
    layout = prepared.get('layout')
    fmt = prepared.get('format', 'plain')
    if not all(isinstance(v, str) and v.strip() for v in (name, method, layout)):
        raise C.SkillError('方法名称、方法内容及空白记录均须提供')
    if fmt not in ('plain', 'staged'):
        raise C.SkillError('未知模板格式')
    if fmt == 'staged':
        T.parse_content(method)
    R.render('20260101-000000', template={'record_layout': layout})
    p = C.Project(root)
    with C.FileLock(p.state / 'workflow.lock'):
        W.recover_actions(p)
        p = C.Project(root)
        entries = p.cfg.setdefault('method_templates', [])
        matches = [entry for entry in entries if entry.get('name') == name]
        if len(matches) > 1:
            raise C.SkillError('存在重名方法，无法确定更新对象')
        old = matches[0] if matches else None
        if old:
            loaded = T.load(p, old)
            if (loaded['content'] == method and loaded.get('record_layout') == layout
                    and loaded['format'] == fmt):
                return {'reused': True, 'version': loaded['version']}
            if str(prepared.get('expected_version')) != loaded['version']:
                raise C.SkillError('模板版本已变化，请重新比较并选择字段')
            old_version = loaded['version']
            if not old.get('record_layout'):
                version = 'generated-1'
            elif old_version.startswith('generated-') and old_version[10:].isdigit():
                version = 'generated-' + str(int(old_version[10:]) + 1)
            elif old_version.isascii() and old_version.isdigit():
                version = str(int(old_version) + 1)
            else:
                raise C.SkillError('已有配套模板版本格式无效')
        else:
            version = 1
        folder = Path('templates') / C.sha256_text(name) / str(version)
        method_path = folder / 'method.md'
        layout_path = folder / 'record.md'
        entry = dict(old or {}, name=name, path=method_path.as_posix(), version=str(version),
                     format=fmt, record_layout=layout_path.as_posix(),
                     record_layout_sha256=C.sha256_text(layout))
        if old:
            entries[entries.index(old)] = entry
        else:
            entries.append(entry)
        targets = [p.root / method_path, p.root / layout_path, p.root / folder / 'pair.json']
        if any(path.exists() for path in targets):
            raise C.SkillError('目标版本文件已存在，拒绝覆盖')
        writes = {
            targets[0]: method,
            targets[1]: layout,
            targets[2]: C.json_text(entry),
            p.root / C.CONFIG_NAME: C._yamlish.dumps(p.cfg),
        }
        if old and not old.get('record_layout'):
            legacy = Path('templates') / C.sha256_text(name) / 'legacy' / C.sha256_text(loaded['version'])
            legacy_method = legacy / 'method.md'
            legacy_manifest = legacy / 'pair.json'
            if (p.root / legacy_method).exists() or (p.root / legacy_manifest).exists():
                raise C.SkillError('旧版本归档已存在，拒绝覆盖')
            legacy_entry = dict(old, path=legacy_method.as_posix(), version=loaded['version'])
            writes[p.root / legacy_method] = loaded['content']
            writes[p.root / legacy_manifest] = C.json_text(legacy_entry)
        W.action_transaction(p, writes)
        return {'reused': False, 'version': str(version), 'template': entry}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--input', required=True)
    args = parser.parse_args()
    try:
        prepared = json.loads(sys.stdin.buffer.read().decode('utf-8-sig')) if args.input == '-' else json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
        C.ok(result=publish(C.find_project_root(args.project), prepared))
    except (C.SkillError, OSError, ValueError, TypeError, KeyError) as exc:
        C.die(str(exc), code='template_publish_error')


if __name__ == '__main__':
    main()
