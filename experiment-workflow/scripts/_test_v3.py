"""V3 behavior: scoped loading, local installation, independent archive and completion."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import _common as C
import workflow as W
import install as Installer
import skill_store as Store
import record_format as Format


class V3(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        Installer.initialize(self.root, False)
        self.p = C.Project(self.root)
        self.eid = '20261101-120000'
        self.p.experiment_dir(self.eid).mkdir(parents=True)
        self.source = self.root / 'input.txt'; self.source.write_text('实验实际记录', encoding='utf-8')
        W.start(self.p, 'request-1', self.source, self.eid)
        self.result_links = []

    def draft(self, date='2026-11-01', result='已有测量表', custom=''):
        path = self.root / 'draft.md'
        result += ''.join('\n' + link for link in self.result_links)
        text = Format.render(self.eid, actual_date=date, project=self.root.name, purpose='测量',
                             method='实际操作', results=result, attachments='见附件')
        if custom: text = custom + Format.metadata.split(text)[1]
        path.write_text(text, encoding='utf-8')
        return path

    def record(self, **kw):
        return W.write_record(self.p, self.eid, self.draft(**kw))

    def no_stock(self):
        W.review_inventory(self.p, self.eid, 'none', '本轮无库存变化')

    def result_file(self, name='table.csv'):
        path = self.p.experiment_dir(self.eid) / name
        path.write_text('value\n1\n'); return path

    def complete_results(self, task='table', name='table.csv', links=()):
        path = self.result_file(name)
        # V4 requires actual backfill, not merely passing a path to organize.
        link = f'[{name}]({name})'
        if link not in self.result_links:
            self.result_links.append(link)
            target = self.p.experiment_dir(self.eid) / C.RECORD_NAME
            candidate = self.root / 'backfill.md'
            candidate.write_text(target.read_text(encoding='utf-8').replace('## 附件', link+'\n## 附件'), encoding='utf-8')
            W.write_record(self.p, self.eid, candidate, affects_results=[])
            self.no_stock()
        W.organize(self.p, self.eid, task, 'completed', [path], links)
        return path

    def front(self):
        return C.read_md(self.p.experiment_dir(self.eid) / C.RECORD_NAME)[0]

    def test_record_only_ignores_analysis_dependencies_and_archives(self):
        self.p.cfg.update(analysis_map=[{'match': {'data_type': 'csv'}, 'skill': 'missing'}],
                          ppt_template='missing.pptx')
        with patch.object(Store, 'read_index', side_effect=AssertionError('must not read index')):
            self.assertEqual(self.p.validate('record'), [])
            result = self.record()
            self.assertEqual(result['next_action'], 'inventory_review')
            self.assertEqual(W.read_state(self.p,self.eid)['inventory'], 'review_pending')
            self.no_stock(); self.assertTrue(W.finalize(self.p,self.eid)['archived'])
        self.assertFalse(self.front()['completed'])
        self.assertEqual(set(self.front()), {'completed','completed_at','important'})

    def test_pending_analysis_and_pending_results_do_not_block_archive(self):
        self.record(); self.no_stock()
        W.update_analysis(self.p,self.eid,'pending-analysis','blocked',reason='缺少工具')
        W.organize(self.p,self.eid,'pending-results','pending')
        self.assertTrue(W.finalize(self.p,self.eid)['archived'])
        self.assertFalse(self.front()['completed'])

    def test_organizing_existing_results_completes_without_analysis(self):
        self.record(); self.no_stock()
        W.update_analysis(self.p,self.eid,'analysis','pending')
        self.complete_results(links=['analysis'])
        at=self.front()['completed_at']
        self.assertTrue(self.front()['completed'])
        self.assertIsNotNone(at)
        W.finalize(self.p,self.eid)
        self.assertEqual(self.front()['completed_at'], at)
        self.assertEqual(W.read_state(self.p,self.eid)['analysis']['analysis']['status'],'pending')

    def test_unrelated_supplement_keeps_results_and_time(self):
        self.record(); self.complete_results(); before=self.front()
        self.source.write_text('更正日期')
        W.start(self.p,'request-2',self.source,self.eid)
        self.record(date='2026-10-31')
        self.assertEqual(self.front(),before)
        self.assertEqual(W.read_state(self.p,self.eid)['inventory'],'review_pending')

    def test_targeted_invalidation_preserves_other_task(self):
        self.record(); self.complete_results('a','a.csv'); self.complete_results('b','b.csv')
        self.source.write_text('更新 A 的输入')
        W.start(self.p,'update-a',self.source,self.eid,affects_results=['a'])
        state=W.read_state(self.p,self.eid)
        self.assertEqual(state['result_tasks']['a']['status'],'pending')
        self.assertEqual(state['result_tasks']['b']['status'],'completed')
        self.assertFalse(self.front()['completed']); self.assertIsNone(self.front()['completed_at'])

    def test_result_evidence_changes_invalidate_only_owner(self):
        self.record(); a=self.complete_results('a','a.csv'); self.complete_results('b','b.csv')
        a.write_text('changed')
        state=W.read_state(self.p,self.eid)
        self.assertEqual(state['result_tasks']['a']['status'],'pending')
        self.assertEqual(state['result_tasks']['b']['status'],'completed')

    def test_analysis_changes_invalidate_only_linked_organization(self):
        self.record(); raw=self.result_file('raw.csv'); out=self.result_file('out.csv')
        W.update_analysis(self.p,self.eid,'calc','completed','test','1',[raw],[out],'v1')
        self.complete_results('linked','linked.csv',['calc']); self.complete_results('other','other.csv')
        W.update_analysis(self.p,self.eid,'calc','completed','test','1',[raw],[out],'v2')
        state=W.read_state(self.p,self.eid)
        self.assertEqual(state['result_tasks']['linked']['status'],'pending')
        self.assertEqual(state['result_tasks']['other']['status'],'completed')

    def test_custom_properties_preserved_legacy_status_removed(self):
        self.record(custom='---\nstatus: in_progress\nproject: biology\ntags: [lab]\n---\n')
        self.complete_results()
        self.record(date='2026-10-31')
        self.assertNotIn('status',self.front())
        self.assertEqual(self.front()['tags'],['lab'])
        self.assertEqual(self.front()['project'],'biology')
        self.assertTrue(self.front()['completed'])

    def test_manual_edit_guard_and_unchanged_result_completion(self):
        self.record(); self.complete_results(); self.no_stock(); W.finalize(self.p,self.eid)
        target=self.p.experiment_dir(self.eid)/C.RECORD_NAME
        target.write_text(target.read_text().replace('| 实际实验日期 | 2026-11-01 |','| 实际实验日期 | 2026-10-31 |'))
        W.read_state(self.p,self.eid)
        self.assertTrue(self.front()['completed'])
        with self.assertRaises(C.SkillError): self.record()

    def fake_skill(self, directory, name='csv-analysis'):
        directory.mkdir(parents=True)
        (directory/'SKILL.md').write_text(f'---\nname: {name}\ndescription: 整理CSV\nversion: "1"\n---\nRead only when selected.\n')
        return directory

    def test_install_init_only_and_non_overwrite(self):
        other=Path(self.tmp.name)/'install-project'
        Installer.initialize(other)
        self.assertTrue((other/'skills/experiment-workflow/SKILL.md').is_file())
        self.assertTrue((other/'skills/analysis/index.json').is_file())
        before=(other/C.CONFIG_NAME).read_bytes()
        Installer.initialize(other,False)
        self.assertEqual((other/C.CONFIG_NAME).read_bytes(),before)
        with self.assertRaises(C.SkillError): Installer.initialize(other)

    def test_name_lookup_does_not_scan_other_bodies_and_moves_with_project(self):
        skill=self.fake_skill(Path(self.tmp.name)/'source')
        Store.install(self.p,skill)
        other=self.p.root/'skills/analysis/unrelated'; other.mkdir()
        (other/'SKILL.md').write_text('malformed and intentionally unindexed')
        with patch.object(Store,'metadata',side_effect=AssertionError('no scan')):
            self.assertTrue(Store.resolve(self.p,'csv-analysis')['available'])
            self.assertFalse(Store.resolve(self.p,'unknown')['available'])
        moved=Path(self.tmp.name)/'moved'; shutil.move(str(self.root),moved)
        self.assertTrue(Store.resolve(C.Project(moved),'csv-analysis')['available'])
        entry=json.loads((moved/'skills/analysis/index.json').read_text())['skills']['csv-analysis']
        self.assertFalse(Path(entry['path']).is_absolute())

    def test_duplicate_names_and_changed_target_require_refresh(self):
        source=self.fake_skill(Path(self.tmp.name)/'source')
        Store.install(self.p,source)
        with self.assertRaises(C.SkillError): Store.install(self.p,source)
        target=self.root/'skills/analysis/csv-analysis/SKILL.md'
        target.write_text(target.read_text()+'updated')
        self.assertFalse(Store.resolve(self.p,'csv-analysis')['available'])
        Store.refresh(self.p); self.assertTrue(Store.resolve(self.p,'csv-analysis')['available'])
        self.fake_skill(self.root/'skills/analysis/duplicate')
        before=(self.root/'skills/analysis/index.json').read_bytes()
        with self.assertRaises(C.SkillError): Store.refresh(self.p)
        self.assertEqual((self.root/'skills/analysis/index.json').read_bytes(),before)

    def test_inventory_review_is_retriggered_each_record(self):
        self.record(); self.no_stock(); W.finalize(self.p,self.eid)
        self.record(date='2026-10-31')
        with self.assertRaises(C.SkillError): W.finalize(self.p,self.eid)
        self.no_stock(); self.assertTrue(W.finalize(self.p,self.eid)['archived'])

    def test_ambiguous_result_edit_needs_scope_without_resetting_all(self):
        self.record(); self.complete_results('a','a.csv'); self.complete_results('b','b.csv')
        candidate=self.draft(result='修改 A 的结果')
        with self.assertRaises(C.SkillError): W.write_record(self.p,self.eid,candidate)
        self.assertTrue(all(t['status']=='completed' for t in W.read_state(self.p,self.eid)['result_tasks'].values()))
        W.write_record(self.p,self.eid,candidate,affects_results=['a'])
        state=W.read_state(self.p,self.eid)
        self.assertEqual(state['result_tasks']['a']['status'],'pending')
        self.assertEqual(state['result_tasks']['b']['status'],'completed')

    def test_external_ambiguous_result_edit_keeps_task_history(self):
        self.record(); self.complete_results('a','a.csv'); self.complete_results('b','b.csv')
        target=self.p.experiment_dir(self.eid)/C.RECORD_NAME
        target.write_text(target.read_text().replace('已有测量表','人工更正测量表'))
        state=W.read_state(self.p,self.eid)
        self.assertTrue(state['result_scope_unknown'])
        self.assertTrue(all(t['status']=='completed' for t in state['result_tasks'].values()))
        self.assertFalse(self.front()['completed'])
        candidate=self.draft(result='人工更正测量表')
        W.write_record(self.p,self.eid,candidate,approve_current_hash=C.sha256_file(target),affects_results=['a'])
        state=W.read_state(self.p,self.eid)
        self.assertEqual(state['result_tasks']['a']['status'],'pending')
        self.assertEqual(state['result_tasks']['b']['status'],'completed')

    def test_recursive_install_targets_are_rejected_before_mutation(self):
        source=Path(self.tmp.name)/'package'
        (source/'scripts').mkdir(parents=True)
        with patch.object(Installer,'__file__',str(source/'scripts/install.py')):
            with self.assertRaises(C.SkillError): Installer.initialize(source)
        self.assertFalse((source/C.CONFIG_NAME).exists())
        (self.root/'SKILL.md').write_text('---\nname: project-as-skill\ndescription: test\n---\n')
        with self.assertRaises(C.SkillError): Store.install(self.p,self.root)
        self.assertFalse((self.root/'skills/analysis/project-as-skill').exists())


    def test_cli_closed_record_round_without_analysis_calls(self):
        script=Path(W.__file__)
        def run(*args):
            proc=subprocess.run([sys.executable,str(script),'--project',str(self.root),*args],capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
            return json.loads(proc.stdout)['result']
        record=run('record','--experiment',self.eid,'--file',str(self.draft()))
        self.assertEqual(record['next_action'],'inventory_review')
        run('inventory','--experiment',self.eid,'--mode','none','--reason','无变化')
        self.assertTrue(run('finalize','--experiment',self.eid)['archived'])
        self.assertTrue(run('status','--experiment',self.eid)['archived'])
        self.assertFalse(self.front()['completed'])


if __name__=='__main__': unittest.main(verbosity=2)
