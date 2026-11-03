"""安装到明确指定项目；只补缺失配置/目录，不覆盖已有 skill 或配置。"""
import argparse
import shutil
from pathlib import Path
import _common as C
import skill_store


def initialize(root, copy_skill=True):
    root = Path(root).resolve()
    source = Path(__file__).resolve().parent.parent
    planned = (root / 'skills/experiment-workflow').resolve()
    if copy_skill and planned != source and planned.is_relative_to(source):
        raise C.SkillError('目标位于源 skill 内，拒绝递归安装；请选择项目根目录')
    root.mkdir(parents=True, exist_ok=True)
    with C.FileLock(root / C.STATE_DIR / 'install.lock'):
        target = root / 'skills/experiment-workflow'
        source = Path(__file__).resolve().parent.parent
        if copy_skill and target.resolve() != source and target.exists():
            raise C.SkillError('主 skill 目录已存在，拒绝覆盖；仅补齐目录用 --init-only')
        cfg_path = root / C.CONFIG_NAME
        if not cfg_path.exists():
            cfg = {'version': 4, 'project': root.name, 'knowledge_base': '.', 'timezone': 'Asia/Shanghai',
                   'calendar': {'status': 'needs_setup'},
                   'sample_library': 'samples', 'method_templates': [], 'ppt_template': None,
                   'analysis_skill_repository': 'skills/analysis', 'analysis_map': [],
                   'units': {'convert': [['uL', 'mL'], ['mg', 'g']]}}
            C.atomic_write_text(cfg_path, C._yamlish.dumps(cfg))
        p = C.Project(root)
        # Only provision project-owned paths. Existing external vaults remain untouched.
        for folder in (p.kb, p.samples):
            if folder.is_relative_to(root):
                folder.mkdir(parents=True, exist_ok=True)
        repo = skill_store.ensure(p)
        if copy_skill and target.resolve() != source:
            shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '.git'))
        import calendar_bridge
        return {'project': str(root), 'skill': str(target),
                'analysis_skill_repository': repo.relative_to(root).as_posix(),
                'calendar': calendar_bridge.onboarding(p)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--init-only', action='store_true')
    args = parser.parse_args()
    try:
        C.ok(**initialize(args.project, not args.init_only))
    except (C.SkillError, OSError, ValueError, TypeError, KeyError) as exc:
        C.die(str(exc), code='install_error')


if __name__ == '__main__': main()
