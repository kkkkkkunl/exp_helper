"""项目内技能索引：仅安装/刷新时读取元信息，resolve 不扫描其他正文。"""
from __future__ import annotations
import argparse
import json
import re
import shutil
from pathlib import Path
import _common as C


def inside(root, relative):
    path = Path(relative)
    if path.is_absolute() or not path.parts or '..' in path.parts:
        raise C.SkillError('技能库路径必须是项目内相对路径')
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise C.SkillError('技能库路径超出项目')
    return target


def repository(project):
    return inside(project.root, project.cfg.get('analysis_skill_repository', 'skills/analysis'))


def ensure(project):
    repo = repository(project)
    repo.mkdir(parents=True, exist_ok=True)
    with C.FileLock(repo / '.index.lock'):
        index = repo / 'index.json'
        if not index.exists():
            C.atomic_write_text(index, C.json_text({'version': 1, 'skills': {}}))
    return repo


def read_index(project):
    path = repository(project) / 'index.json'
    if not path.is_file():
        return {'version': 1, 'skills': {}}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data.get('skills'), dict):
        raise C.SkillError('技能索引结构不正确')
    return data


def metadata(directory, root):
    path = directory / 'SKILL.md'
    if not path.is_file():
        raise C.SkillError(f'缺少 SKILL.md：{directory}')
    # Stop at frontmatter; do not read the instructions into the routing context.
    with path.open(encoding='utf-8-sig') as stream:
        if stream.readline().strip() != '---':
            raise C.SkillError('SKILL.md 缺少 frontmatter')
        header = []
        for line in stream:
            if line.strip() == '---':
                break
            header.append(line)
        else:
            raise C.SkillError('SKILL.md frontmatter 未闭合')
    front = C._yamlish.loads(''.join(header))
    name = front.get('name')
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name):
        raise C.SkillError('skill name 须使用小写字母、数字和连字符')
    if not front.get('description'):
        raise C.SkillError('skill 缺少 description')
    return {'name': name, 'description': front['description'],
            'kind': front.get('kind', 'analysis'), 'experiment_types': front.get('experiment_types') or [],
            'input_types': front.get('input_types') or [], 'version': str(front.get('version') or 'unspecified'),
            'path': path.relative_to(root).as_posix(), 'sha256': C.sha256_file(path)}


def resolve(project, name):
    entry = read_index(project)['skills'].get(name)
    if not entry:
        return {'skill': name, 'available': False, 'message': '索引中无此名称；保留记录并提示缺少 skill，不扫描其他正文'}
    path = inside(project.root, entry['path'])
    if not path.is_relative_to(repository(project)):
        raise C.SkillError('索引条目不在项目分析技能库内')
    available = path.is_file() and C.sha256_file(path) == entry['sha256']
    return {'skill': name, 'available': available, 'skill_path': str(path), 'metadata': entry,
            'message': '只读取该 SKILL.md 并核查其工具要求' if available else '目标缺失或已变化；请刷新索引'}


def refresh(project):
    repo = ensure(project)
    with C.FileLock(repo / '.index.lock'):
        entries = {}
        for directory in sorted(repo.iterdir()):
            if directory.is_dir() and not directory.name.startswith('.'):
                if directory.is_symlink():
                    raise C.SkillError('技能库不接受符号链接目录')
                entry = metadata(directory, project.root)
                if entry['name'] in entries:
                    raise C.SkillError(f"同名 skill 冲突：{entry['name']}")
                entries[entry['name']] = entry
        C.atomic_write_text(repo / 'index.json', C.json_text({'version': 1, 'skills': entries}))
    return {'count': len(entries)}


def install(project, source):
    source = Path(source).resolve()
    if any(f.is_symlink() for f in source.rglob('*')):
        raise C.SkillError('安装目录不接受符号链接')
    entry = metadata(source, source.parent)
    planned = repository(project) / entry['name']
    if planned.resolve().is_relative_to(source):
        raise C.SkillError('目标位于源 skill 内，拒绝递归安装')
    repo = ensure(project)
    with C.FileLock(repo / '.index.lock'):
        data = read_index(project)
        dest = repo / entry['name']
        if dest.exists() or entry['name'] in data['skills']:
            raise C.SkillError('同名 skill 已存在，不自动覆盖；明确编辑后使用 refresh 更新索引')
        shutil.copytree(source, dest, ignore=shutil.ignore_patterns('__pycache__', '.git'))
        entry = metadata(dest, project.root)
        data['skills'][entry['name']] = entry
        C.atomic_write_text(repo / 'index.json', C.json_text(data))
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project')
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init'); sub.add_parser('refresh'); sub.add_parser('list')
    sub.add_parser('resolve').add_argument('--name', required=True)
    sub.add_parser('install').add_argument('--source', required=True)
    args = parser.parse_args()
    try:
        p = C.Project(C.find_project_root(args.project))
        if args.cmd == 'init': result = {'repository': str(ensure(p))}
        elif args.cmd == 'resolve': result = resolve(p, args.name)
        elif args.cmd == 'install': result = install(p, args.source)
        elif args.cmd == 'refresh': result = refresh(p)
        else: result = read_index(p)
        C.ok(**result)
    except (C.SkillError, OSError, ValueError, TypeError, KeyError) as exc:
        C.die(str(exc), code='skill_store_error')


if __name__ == '__main__': main()
