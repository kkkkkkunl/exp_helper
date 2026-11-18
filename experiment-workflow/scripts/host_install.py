"""Deploy the paired Codex skills without initializing an experiment project."""
import os
from pathlib import Path
import shutil
import tempfile

import _common as C


def deploy(project=None, user=False, source=None):
    if (project is None) == (not user):
        raise C.SkillError('请选择明确项目或个人全局部署，二者不可同时使用')
    main = Path(source or Path(__file__).resolve().parent.parent).resolve()
    entry = main.parent / 'exp'
    origins = (entry, main, main.parent / 'expmodel')
    for folder, name in ((main, 'experiment-workflow'), (entry, 'exp'), (origins[2], 'expmodel')):
        manifest = folder / 'SKILL.md'
        if not manifest.is_file() or not os.access(manifest, os.R_OK):
            raise C.SkillError('安装源不完整：' + str(manifest))
        metadata, _ = C.split_frontmatter(manifest.read_text(encoding='utf-8'))
        if not metadata or metadata.get('name') != name or not metadata.get('description'):
            raise C.SkillError('技能名称或描述无效：' + str(manifest))
    for name in ('scripts', 'references', 'assets'):
        if not (main / name).is_dir():
            raise C.SkillError('主技能资源缺失：' + str(main / name))
    base = Path.home() if user else Path(project).resolve()
    destination = base / '.agents' / 'skills'
    # Reject recursion and symlink redirects before any writes.
    for parent in (base, base / '.agents', destination):
        if parent.is_symlink():
            raise C.SkillError('部署目录不能是符号链接：' + str(parent))
    for origin in origins:
        if destination.resolve().is_relative_to(origin):
            raise C.SkillError('目标位于技能源内，拒绝递归安装')
    targets = [destination / origin.name for origin in origins]
    def check_targets():
        for target in targets:
            if os.path.lexists(target):
                raise C.SkillError('技能目标已存在，拒绝覆盖：' + str(target))
    check_targets()
    destination.mkdir(parents=True, exist_ok=True)
    with C.FileLock(destination / '.experiment-workflow-install.lock'):
        check_targets()
        # Copy completely before publishing either skill. Keep recovery evidence
        # on a publication failure rather than deleting uncertain destinations.
        with tempfile.TemporaryDirectory(prefix='.exp-install-', dir=str(destination)) as stage:
            stage = Path(stage)
            for origin in origins:
                shutil.copytree(origin, stage / origin.name,
                                ignore=shutil.ignore_patterns('__pycache__', '.git', '*.pyc'))
            published = []
            try:
                for target in targets:
                    (stage / target.name).rename(target)
                    published.append(str(target))
            except OSError as exc:
                raise C.SkillError('共同部署中断；已发布=' + repr(published)
                                   + '；请核对目标后恢复，未完成部分需重新部署：' + str(exc)) from exc
    return {'scope': 'user' if user else 'project',
            'skills': [str(p) for p in targets], 'selector_verified': False,
            'next_action': '在目标项目输入 $exp 并选择入口；未出现时重新发现或重启 Codex。'}
