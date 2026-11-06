"""Acceptance tests for the exp entry, canonical records, migration, and concise values."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import _common as C
import install
import record_format as R
import stage_workflow as S
import workflow as W


class RecordFormat(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        install.initialize(self.root, False)
        self.p = C.Project(self.root)

    def draft(self, **changes):
        result = {'action': 'confirm', 'action_id': 'save-1', 'raw_input': '刚刚完成铺板；实际观察已记录',
                  'method_text': '实际观察已记录', 'inventory_review': {'mode': 'none', 'reason': '无样品变化'}}
        result.update(changes)
        return result

    def test_entry_is_thin_and_requires_main_skill(self):
        entry = (R.TEMPLATE.parents[2] / 'exp' / 'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('name: exp', entry)
        self.assertIn('experiment-workflow/SKILL.md', entry)
        self.assertIn('缺少 experiment-workflow 主技能', entry)
        self.assertNotIn('库存计划', entry)

    def test_template_render_and_structure_validation(self):
        text = R.render('E-1')
        self.assertTrue(R.validate(text, 'E-1'))
        self.assertIn('| 实际实验日期 |  |', text)
        self.assertNotIn('{{', text)
        self.assertNotIn('TODO', text)
        self.assertNotIn('填写须知', text)
        for bad in (text.replace('## 结果', '## 错误'),
                    text.replace('### 实验方法', '## 实验方法'),
                    text.replace('## 目的', '## 结果', 1),
                    text.replace('### 参考方案', '### 实验方法', 1)):
            with self.assertRaises(C.SkillError): R.validate(bad, 'E-1')
        extended = text.replace('## 实验方案', '## 实验方案\n\n### 方案补充\n已有依据\n', 1)
        extended = extended.replace('## 结果', '## 上样计算\n\n已确认的计算依据\n\n## 结果', 1)
        self.assertTrue(R.validate(extended, 'E-1'))

    def test_stage_preview_save_and_relative_time_provenance(self):
        draft = self.draft(actual_values=[{'label': '铺板完成时间', 'value': '14:55',
            'raw': '刚刚完成铺板', 'source': 'user', 'time_evidence': {
                'candidate': '14:55', 'read_at': '2026-11-06T14:55:00+08:00',
                'estimated': True, 'confirmed': False}}])
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*') if p.is_file())
        pending = S.preview(self.p, draft)
        self.assertEqual(before, sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*') if p.is_file()))
        self.assertIn('14:55', pending['questions']['questions'][0]['options'])
        self.assertNotIn('铺板完成时间｜', pending['record'])
        with self.assertRaises(C.SkillError): S.save(self.p, draft, pending['preview_hash'], 'user-confirmed')
        draft['actual_values'][0]['time_evidence']['confirmed'] = True
        ready = S.preview(self.p, draft)
        self.assertIn('铺板完成时间｜14:55', ready['record'])
        self.assertNotIn('读取', ready['record'])
        saved = S.save(self.p, draft, ready['preview_hash'], 'user-confirmed')
        state = W.read_state(self.p, saved['experiment'])
        self.assertEqual(state['actual_values'][0]['raw'], '刚刚完成铺板')
        self.assertEqual(state['actual_values'][0]['time_evidence']['candidate'], '14:55')
        record = (self.p.experiment_dir(saved['experiment']) / C.RECORD_NAME).read_text(encoding='utf-8')
        self.assertTrue(R.validate(record, saved['experiment']))
        self.assertIn('铺板完成时间｜14:55', record)
        self.assertNotIn('pending-experiment', record)

    def test_conflict_questions_block_save_and_free_text_stays_available(self):
        draft = self.draft(conflicts=[{'field': '孔数', 'values': [6, 8]}])
        preview = S.preview(self.p, draft)
        self.assertEqual(preview['questions']['questions'][0]['options'], ['6', '8'])
        self.assertTrue(preview['questions']['fallback'][0].startswith('1. '))
        with self.assertRaises(C.SkillError): S.save(self.p, draft, preview['preview_hash'], 'confirmed')
        questions = S.question_plan([{'sample': 'A', 'stage': 'prepare', 'step': 'plate',
            'fields': [{'id': 'concentration', 'label': '浓度', 'required': True},
                       {'id': 'optional_note', 'label': '备注', 'required': False}]}],
            draft['conflicts'])
        self.assertEqual([q['kind'] for q in questions['questions']], ['choice', 'text'])
        self.assertNotIn('备注', '\n'.join(questions['fallback']))

    def test_legacy_edit_and_explicit_migration_history(self):
        eid = 'E-legacy'
        self.p.experiment_dir(eid).mkdir(parents=True)
        old = (f'# {eid}\n实际日期：2026-11-06\n## 目的\n旧目的\n'
               '## 实验方案\n### 参考方案\n旧方案\n### 实验方法\n旧方法\n## 结果\n\n## 附件\n')
        target = self.p.experiment_dir(eid) / C.RECORD_NAME
        target.write_text(old, encoding='utf-8')
        state = S.fresh(eid)
        state['record'] = {'path': W.stored_path(self.p, target), 'sha256': C.sha256_text(old), 'stale': False}
        W.save_state(self.p, eid, state)
        old = target.read_text(encoding='utf-8')
        edit = self.root / 'edit.md'; edit.write_text(old.replace('旧目的', '补充旧目的'), encoding='utf-8')
        W.write_record(self.p, eid, edit, approve_current_hash=C.sha256_file(target))
        self.assertNotIn('| 项 | 内容 |', target.read_text(encoding='utf-8'))
        preview = R.migration_preview(self.p, eid)
        self.assertIn('补充旧目的', preview['record'])
        self.assertIn('旧方法', preview['record'])
        self.assertIn('旧方案', preview['record'])
        self.assertIn('| 项 | 内容 |', preview['record'])
        base = [sys.executable, '-B', str(Path(W.__file__)), '--project', str(self.root)]
        shown = subprocess.run(base + ['migrate-preview', '--experiment', eid], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(shown.returncode, 0, shown.stdout + shown.stderr)
        self.assertEqual(json.loads(shown.stdout)['result']['preview_hash'], preview['preview_hash'])
        history_before = set((self.root / 'history').glob('*.md'))
        command = base + ['migrate', '--experiment', eid, '--preview-hash', preview['preview_hash']]
        first = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        history_after = set((self.root / 'history').glob('*.md'))
        self.assertEqual(len(history_after - history_before), 1)
        replay = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(replay.returncode, 0, replay.stdout + replay.stderr)
        self.assertTrue(json.loads(replay.stdout)['result']['noop'])
        self.assertEqual(history_after, set((self.root / 'history').glob('*.md')))
        self.assertTrue(R.validate(target.read_text(encoding='utf-8'), eid))
        self.assertIn('补充旧目的', next(iter(history_after - history_before)).read_text(encoding='utf-8'))


if __name__ == '__main__': unittest.main()
