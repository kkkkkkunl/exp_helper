"""Synthetic skill calculations and history acceptance tests; no laboratory procedure."""
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import _common as C
import allocate_id as A
import experiment_skills as E
import install
import inventory as I
import record_history as H
import skill_store as Store
import stage_templates as T
import stage_workflow as S
import workflow as W
from _test_v4 import template_data


class ExperimentSkills(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        install.initialize(self.root, False)
        self.p = C.Project(self.root)
        self.template_path = self.root / 'template.yaml'
        self.template_path.write_text(C._yamlish.dumps(template_data()), encoding='utf-8')
        self.p.cfg['method_templates'] = [{'name': 'structural', 'path': 'template.yaml', 'version': 'one',
                                           'format': 'staged', 'experiment_skill': 'synthetic-calc'}]
        self.p.cfg['experiment_skill_map'] = [{'experiment_type': 'synthetic', 'skill': 'synthetic-calc'}]
        self.config()
        self.source = Path(self.tmp.name) / 'synthetic-calc'
        self.source.mkdir()
        (self.source / 'SKILL.md').write_text('---\nname: synthetic-calc\ndescription: Synthetic test arithmetic only\nversion: one\nkind: experiment\n---\nRead experiment-skill.json and rules.md.\n', encoding='utf-8')
        (self.source / 'rules.md').write_text('Synthetic arithmetic only, not a scientific protocol.', encoding='utf-8')
        rule = {'entrypoint': 'calculate.py', 'basis': 'Synthetic x and total arithmetic',
                'inputs': {'x': {'unit': 'uL', 'minimum': 0}, 'total': {'unit': 'uL', 'minimum': 0}},
                'outputs': {'volume': {'unit': 'uL', 'minimum': 0}, 'water': {'unit': 'uL', 'minimum': 0}}}
        (self.source / 'experiment-skill.json').write_text(C.json_text({'version': 1, 'experiment_types': ['synthetic'],
                                        'calculations': {'loading': rule}}), encoding='utf-8')
        self.script = "import json,sys\nr=json.load(sys.stdin)\nx=r['inputs']['x']['value']\nt=r['inputs']['total']['value']\njson.dump({'status':'computed','outputs':{'volume':{'value':x*1,'unit':'uL'},'water':{'value':t-x,'unit':'uL'}}},sys.stdout)\n"
        (self.source / 'calculate.py').write_text(self.script, encoding='utf-8')
        Store.install(self.p, self.source)
        self.sample = A.allocate_sample(self.p, '20261104')
        path, data, _ = C.load_sample(self.p, self.sample)
        data.update(quantity=20, unit='uL', material_type='source')
        C.save_sample(path, data)

    def config(self):
        (self.root / C.CONFIG_NAME).write_text(C._yamlish.dumps(self.p.cfg), encoding='utf-8')

    def tree(self):
        return {f.relative_to(self.root).as_posix(): C.sha256_file(f) for f in self.root.rglob('*') if f.is_file()}

    def request(self, key='dose', value=2, **kw):
        result = {'id': key, 'calculation': 'loading', 'sample': self.sample, 'stage': 'prepare', 'step': 'one',
                  'inputs': {'x': {'value': value, 'unit': 'uL', 'source': 'user'},
                             'total': {'value': 10, 'unit': 'uL', 'source': 'confirmed_parameter'}}, 'params': {}}
        result.update(kw)
        return result

    def draft(self, action_id='first', **kw):
        result = {'action_id': action_id, 'action': 'confirm', 'raw_input': '合成测试记录确认；观察为测试结果。',
                  'experiment_type': 'synthetic', 'template': 'structural', 'entry': 'prepare',
                  'actual_date': '2026-11-04', 'samples': [self.sample],
                  'inventory_review': {'mode': 'none', 'reason': '仅计算或记录，不涉及实际取用'}}
        result.update(kw)
        return result

    def save(self, draft):
        preview = S.preview(self.p, draft)
        return S.save(self.p, draft, preview['preview_hash'], '测试明确确认')

    def target(self, eid): return self.p.experiment_dir(eid) / C.RECORD_NAME

    def test_priority_missing_choice_and_experiment_matching(self):
        template = T.select(self.p)
        self.assertEqual(E.activate(self.p, 'synthetic', template, started=False)['status'], 'inactive')
        self.assertEqual(E.activate(self.p, None, template, started=True)['status'], 'undetermined')
        ready = E.activate(self.p, 'synthetic', template, started=True)
        self.assertEqual(ready['source'], 'template'); self.assertTrue(ready['available'])
        missing = E.activate(self.p, 'synthetic', template, 'missing', True)
        self.assertEqual(missing['status'], 'missing_skill')
        unbound = {'name': 'user plan'}
        self.assertEqual(E.activate(self.p, 'synthetic', unbound, started=True)['source'], 'experiment_type')
        self.p.cfg['experiment_skill_map'].append({'experiment_type': 'synthetic', 'skill': 'another'})
        self.assertEqual(E.activate(self.p, 'synthetic', unbound, started=True)['status'], 'need_choice')
        template['experiment_skill'] = ['synthetic-calc', 'another']
        self.assertEqual(E.activate(self.p, 'synthetic', template, started=True)['status'], 'need_choice')
        self.assertTrue(E.activate(self.p, 'synthetic', template, 'synthetic-calc', True)['available'])
        self.assertEqual(E.activate(self.p, 'other', template, 'synthetic-calc', True)['status'], 'inapplicable')

    def test_activation_and_preview_are_read_only_including_cli(self):
        before = self.tree()
        preview = S.preview(self.p, self.draft(calculations=[self.request()]))
        self.assertEqual(preview['calculations'][0]['outputs']['volume']['value'], 2)
        self.assertEqual(before, self.tree())
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('project.py')), 'activate',
                                 '--project', str(self.root), '--started', '--experiment-type', 'synthetic',
                                 '--template', 'structural'], text=True, encoding='utf-8', capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)['available'])
        self.assertEqual(before, self.tree())

    def test_missing_invalid_tools_and_unrelated_sample_calculations(self):
        good, absent, invalid = self.request('good'), self.request('absent'), self.request('invalid', 20)
        del absent['inputs']['x']
        unit = self.request('unit'); unit['inputs']['x']['unit'] = 'mL'
        preview = S.preview(self.p, self.draft(calculations=[good, absent, invalid, unit]))
        states = {c['id']: c['status'] for c in preview['calculations']}
        self.assertEqual(states, {'good': 'computed', 'absent': 'missing_inputs', 'invalid': 'invalid_result', 'unit': 'invalid_inputs'})
        package = E.capture(self.p, 'synthetic-calc')
        with patch.object(E.shutil, 'which', return_value=None):
            manifest = package['manifest']; manifest['tools'] = ['synthetic-unavailable']
            # Build a real changed package instead of forging the manifest cache.
            path = Store.repository(self.p) / 'synthetic-calc' / 'experiment-skill.json'
            path.write_text(C.json_text(manifest), encoding='utf-8')
            package = E.capture(self.p, 'synthetic-calc')
            self.assertEqual(E.execute(package, good)['status'], 'tools_unavailable')

    def test_missing_skill_and_nonexecutable_skill_do_not_fabricate(self):
        preview = S.preview(self.p, self.draft(experiment_skill='missing', calculations=[self.request()]))
        self.assertEqual(preview['calculations'][0]['status'], 'missing_skill')
        (Store.repository(self.p) / 'synthetic-calc' / 'experiment-skill.json').unlink()
        preview = S.preview(self.p, self.draft(calculations=[self.request()]))
        self.assertEqual(preview['calculations'][0]['status'], 'host_required')
        result = self.save(self.draft(experiment_skill='missing', method_text='独立过程记录'))
        self.assertIn('独立过程记录', self.target(result['experiment']).read_text(encoding='utf-8'))

    def test_calculation_saves_before_execution_without_stock_or_completion(self):
        initial_stock = C.sha256_file(C.load_sample(self.p, self.sample)[0])
        result = self.save(self.draft(calculations=[self.request()]))
        eid = result['experiment']; state = W.read_state(self.p, eid)
        self.assertIn('## 上样计算', self.target(eid).read_text(encoding='utf-8'))
        self.assertEqual(state['calculations']['dose']['source'], 'calculated')
        self.assertFalse(state['stage_progress'][self.sample]['prepare']['steps'])
        self.assertFalse(C.read_md(self.target(eid))[0]['completed'])
        self.assertEqual(state['execution']['status'], 'open'); self.assertFalse(state['archived'])
        self.assertEqual(initial_stock, C.sha256_file(C.load_sample(self.p, self.sample)[0]))
        self.assertFalse((self.root / 'history').exists())
        self.assertTrue(state['skill_snapshot'])
        with self.assertRaises(C.SkillError):
            T.values(self.p, T.select(self.p)['data']['stages'][0]['steps'][0],
                     {'reading': {'value': 2, 'unit': 'uL', 'source': 'calculated'}})

    def test_actual_difference_and_recalculate_only_related_work(self):
        result = self.save(self.draft(calculations=[self.request(), self.request('downstream', depends_on=['dose']), self.request('other')]))
        eid = result['experiment']
        op = {'sample': self.sample, 'stage': 'prepare', 'step': 'one', 'executed': True,
              'values': {'amount': {'value': 3, 'unit': 'uL', 'source': 'user'},
                         'reading': {'value': 7, 'unit': 'uL', 'source': 'user'}}}
        self.save(self.draft('actual', experiment=eid, operations=[op]))
        changed = self.draft('recalc', experiment=eid, reason='更正测试输入', calculations=[self.request(value=4)])
        self.save(changed)
        state = W.read_state(self.p, eid)
        self.assertEqual(state['calculations']['dose']['outputs']['volume']['value'], 4)
        self.assertEqual(state['calculations']['downstream']['status'], 'needs_review')
        self.assertEqual(state['calculations']['other']['status'], 'computed')
        actual = state['stage_progress'][self.sample]['prepare']['steps']['one']
        self.assertEqual(actual['values']['amount']['value'], 3)
        self.assertTrue(actual['executed']); self.assertTrue(state['record_history'])
        self.assertIn('2', (self.root / state['record_history'][0]['path']).read_text(encoding='utf-8'))

    def test_frozen_skill_pause_resume_explicit_upgrade_and_missing_evidence(self):
        result = self.save(self.draft(action='pause', calculations=[self.request()]))
        eid = result['experiment']; state = W.read_state(self.p, eid)
        old_hash = state['skill_snapshot']['sha256']
        installed = Store.repository(self.p) / 'synthetic-calc' / 'calculate.py'
        installed.write_text(self.script.replace('x*1', 'x*2'), encoding='utf-8')
        # Even a non-SKILL dependency change must not alter continuation.
        self.assertTrue(S.resume(self.p, eid)['skill']['frozen'])
        result = S.preview(self.p, self.draft('continued', experiment=eid, calculations=[self.request('next')]))
        self.assertEqual(result['state']['calculations']['next']['outputs']['volume']['value'], 2)
        upgrade = self.draft('upgrade', experiment=eid, skill_upgrade={'skill': 'synthetic-calc', 'confirmed': True,
                       'reason': '采用新测试规则'}, calculations=[self.request(value=2)])
        preview = S.preview(self.p, upgrade)
        self.assertIn('calculate.py', preview['skill_upgrade']['changed_files'])
        self.assertEqual(preview['calculations'][0]['outputs']['volume']['value'], 4)
        self.save(upgrade)
        state = W.read_state(self.p, eid)
        self.assertNotEqual(state['skill_snapshot']['sha256'], old_hash)
        self.assertEqual(state['skill_history'][0]['snapshot']['sha256'], old_hash)
        (self.root / state['skill_snapshot']['path']).unlink()
        self.assertEqual(S.resume(self.p, eid)['skill']['status'], 'missing_evidence')

    def test_stale_skill_or_result_preview_is_rejected(self):
        draft = self.draft(calculations=[self.request()])
        preview = S.preview(self.p, draft)
        (Store.repository(self.p) / 'synthetic-calc' / 'rules.md').write_text('Changed basis', encoding='utf-8')
        with self.assertRaises(C.SkillError): S.save(self.p, draft, preview['preview_hash'], '确认')
        draft['skill_evidence_hash'] = preview['skill']['evidence_hash']
        with self.assertRaises(C.SkillError): S.preview(self.p, draft)

    def test_prose_skill_host_execution_has_traceable_evidence(self):
        (Store.repository(self.p) / 'synthetic-calc' / 'experiment-skill.json').unlink()
        package = E.capture(self.p, 'synthetic-calc')
        request = self.request()
        request['host_execution'] = {'skill_hash': package['sha256'],
            'input_hash': E.digest({'inputs': request['inputs'], 'params': request['params']}),
            'rule_file': 'rules.md', 'basis': 'Synthetic arithmetic only',
            'tool': 'synthetic arithmetic execution', 'tool_version': 'one',
            'outputs': {'volume': {'value': 2, 'unit': 'uL'}}}
        result = self.save(self.draft(calculations=[request]))
        state = W.read_state(self.p, result['experiment'])
        self.assertEqual(state['calculations']['dose']['status'], 'computed')
        self.assertEqual(state['calculations']['dose']['host_execution']['rule_file'], 'rules.md')
        request['host_execution']['input_hash'] = 'wrong'
        self.assertEqual(E.execute(package, request)['status'], 'invalid_result')

    def test_snapshot_tamper_dependency_failures_and_no_other_skill_body_reads(self):
        unrelated = Store.repository(self.p) / 'unrelated'; unrelated.mkdir()
        # Intentionally invalid/unreadable as a skill: resolving another name must ignore it.
        (unrelated / 'SKILL.md').write_bytes(b'not frontmatter')
        self.assertTrue(E.activate(self.p, 'synthetic', T.select(self.p), started=True)['available'])
        result = self.save(self.draft(calculations=[self.request()]))
        eid = result['experiment']; reference = W.read_state(self.p, eid)['skill_snapshot']
        snapshot = self.root / reference['path']
        data = json.loads(snapshot.read_text(encoding='utf-8'))
        data['files']['rules.md']['sha256'] = 'tampered'
        snapshot.write_text(C.json_text(data), encoding='utf-8')
        self.assertEqual(S.resume(self.p, eid)['skill']['status'], 'missing_evidence')

    def test_contract_validation_and_template_binding_integrity(self):
        path = Store.repository(self.p) / 'synthetic-calc' / 'experiment-skill.json'
        original = json.loads(path.read_text(encoding='utf-8'))
        for malformed in ('not-a-rule', {'unit': 'uL', 'minimum': 'not-a-number'}, {'unit': False}):
            broken = copy.deepcopy(original)
            broken['calculations']['loading']['inputs']['x'] = malformed
            path.write_text(C.json_text(broken), encoding='utf-8')
            self.assertEqual(E.activate(self.p, 'synthetic', T.select(self.p), started=True)['status'], 'invalid_skill')
        path.write_text(C.json_text(original), encoding='utf-8')
        eid = self.save(self.draft())['experiment']
        reference = W.read_state(self.p, eid)['template_snapshot']
        snapshot = self.root / reference['path']
        data = json.loads(snapshot.read_text(encoding='utf-8')); data['experiment_skill'] = 'different'
        snapshot.write_text(C.json_text(data), encoding='utf-8')
        with self.assertRaises(C.SkillError): T.frozen(self.p, reference)

    def test_history_properties_noop_naming_and_frozen_clock_collision(self):
        eid = self.save(self.draft(calculations=[self.request()]))['experiment']
        clock = C.now_cn()
        with patch.object(C, 'now_cn', return_value=clock):
            W.set_important(self.p, eid, True)
            W.set_important(self.p, eid, False)
        state = W.read_state(self.p, eid)
        self.assertEqual(len(state['record_history']), 2)
        names = [Path(h['path']).name for h in state['record_history']]
        self.assertEqual(len(set(names)), 2)
        for name in names:
            self.assertRegex(name, '^' + eid + r'_\d{8}-\d{6}-\d{6}\.md$')
        before = len(names); W.set_important(self.p, eid, False)
        self.assertEqual(len(W.read_state(self.p, eid)['record_history']), before)
        source = self.root / 'same.md'; source.write_text(self.target(eid).read_text(encoding='utf-8'), encoding='utf-8')
        round_before = W.read_state(self.p, eid)['record_round']
        W.write_record(self.p, eid, source)
        self.assertEqual(W.read_state(self.p, eid)['record_round'], round_before)
        self.assertEqual(len(W.read_state(self.p, eid)['record_history']), before)

    def test_completed_property_and_legacy_history_recovery(self):
        eid = self.save(self.draft())['experiment']
        final = self.draft('final', experiment=eid, action='final_results', submission_kind='final',
                           results=[{'id': 'one', 'text': '测试结果。'}])
        self.save(final)
        self.assertTrue(C.read_md(self.target(eid))[0]['completed'])
        count = len(W.read_state(self.p, eid)['record_history'])
        W.organize(self.p, eid, 'one', 'pending')
        self.assertEqual(len(W.read_state(self.p, eid)['record_history']), count + 1)
        source = self.root / 'edit.md'
        source.write_text(self.target(eid).read_text(encoding='utf-8').replace('## 目的', '## 目的\n更正目的'), encoding='utf-8')
        original = C.atomic_write_text
        def fail(path, text):
            if Path(path) == self.target(eid): raise OSError('synthetic record interruption')
            original(path, text)
        with patch.object(C, 'atomic_write_text', side_effect=fail):
            with self.assertRaises(OSError): W.write_record(self.p, eid, source)
        journal = json.loads((self.p.state / 'workflow-transaction.json').read_text(encoding='utf-8'))
        histories = [w['path'] for w in journal['writes'] if w['path'].startswith('history/')]
        W.recover_actions(self.p)
        state = W.read_state(self.p, eid)
        self.assertEqual(state['record_history'][-1]['path'], histories[0])
        self.assertIn('更正目的', self.target(eid).read_text(encoding='utf-8'))

    def test_stage_recovery_at_each_history_boundary_and_replay(self):
        eid = self.save(self.draft(calculations=[self.request()]))['experiment']
        draft = self.draft('second', experiment=eid, reason='测试更正', calculations=[self.request(value=3)])
        preview = S.preview(self.p, draft)
        original = C.atomic_write_text
        def fail(path, text):
            if Path(path).parent == self.root / 'history': raise OSError('synthetic history interruption')
            original(path, text)
        with patch.object(C, 'atomic_write_text', side_effect=fail):
            with self.assertRaises(OSError): S.save(self.p, draft, preview['preview_hash'], '确认')
        journal = json.loads((self.p.state / 'workflow-transaction.json').read_text(encoding='utf-8'))
        history_path = journal['writes'][0]['path']
        self.assertTrue(history_path.startswith('history/'))
        self.assertIn('"value": 2', self.target(eid).read_text(encoding='utf-8'))
        W.recover_actions(self.p)
        first = S.save(self.p, draft, preview['preview_hash'], '重试原确认')
        again = S.save(self.p, draft, preview['preview_hash'], '重试原确认')
        self.assertEqual(first['record_round'], again['record_round'])
        state = W.read_state(self.p, eid)
        self.assertEqual(len(state['record_history']), 1)
        self.assertEqual(state['record_history'][0]['path'], history_path)

    def test_history_links_move_and_single_experiment_archive(self):
        eid = self.save(self.draft())['experiment']
        attachment = self.p.experiment_dir(eid) / '附件 图.txt'; attachment.write_text('original', encoding='utf-8')
        candidate = self.root / 'linked.md'
        candidate.write_text(self.target(eid).read_text(encoding='utf-8') + '\n[源附件](<附件 图.txt>)\n![图](<附件 图.txt>)\n', encoding='utf-8')
        W.write_record(self.p, eid, candidate)
        W.set_important(self.p, eid, True)
        history = W.read_state(self.p, eid)['record_history'][-1]
        content = (self.root / history['path']).read_text(encoding='utf-8')
        self.assertIn('../', content); self.assertNotIn('](<附件 图.txt>)', content)
        other = self.save(self.draft('other'))['experiment']
        W.set_important(self.p, other, True)
        W.review_inventory(self.p, eid, 'none', '无实际取用')
        manifest = W.finalize(self.p, eid)
        history_files = [f['path'] for f in manifest['files'] if f['path'].startswith('history/')]
        self.assertTrue(history_files); self.assertTrue(all(eid + '_' in f for f in history_files))
        moved = Path(self.tmp.name) / 'moved'; shutil.copytree(self.root, moved)
        p2 = C.Project(moved); st = W.read_state(p2, eid)
        self.assertTrue(st['archived']); self.assertTrue(H.files(p2, eid, st, validate=True))
        self.assertTrue(Store.resolve(p2, 'synthetic-calc')['available'])
        (self.root / history['path']).write_text('changed externally', encoding='utf-8')
        self.assertFalse(W.read_state(self.p, eid)['archived'])
        with self.assertRaises(C.SkillError): W.finalize(self.p, eid)

    def test_old_state_unknown_evidence_and_future_version_rejected(self):
        eid = self.save(self.draft())['experiment']
        path = W.state_path(self.p, eid)
        state = W.read_state(self.p, eid)
        for key in ('skill_snapshot', 'calculations', 'record_history'): state.pop(key, None)
        state['version'] = 3
        path.write_text(C.json_text(state), encoding='utf-8')
        migrated = W.read_state(self.p, eid)
        self.assertIsNone(migrated['skill_snapshot']); self.assertEqual(migrated['calculations'], {})
        migrated['version'] = 99; path.write_text(C.json_text(migrated), encoding='utf-8')
        before = self.tree()
        with self.assertRaises(C.SkillError): W.read_state(self.p, eid)
        self.assertEqual(before, self.tree())

    def test_calculated_inputs_require_matching_dependency_and_acyclic_graph(self):
        first = self.request()
        second = self.request('derived', depends_on=['dose'])
        second['inputs']['x'].update(source='calculated', calculation_id='dose', output='volume')
        draft = self.draft(calculations=[first, second])
        self.assertEqual(S.preview(self.p, draft)['state']['calculations']['derived']['status'], 'computed')
        second['inputs']['x']['value'] = 9
        self.assertEqual(S.preview(self.p, draft)['state']['calculations']['derived']['status'], 'invalid_inputs')
        eid = self.save(self.draft(calculations=[first, self.request('derived', depends_on=['dose'])]))['experiment']
        cycle = self.request(depends_on=['derived'], reason='测试依赖循环')
        with self.assertRaises(C.SkillError): S.preview(self.p, self.draft('cycle', experiment=eid, calculations=[cycle]))

    def test_end_to_end_actual_inventory_recalculation_pause_upgrade_and_archive(self):
        eid = self.save(self.draft(calculations=[self.request()]))['experiment']
        op = {'sample': self.sample, 'stage': 'prepare', 'step': 'one', 'executed': True,
              'values': {'amount': {'value': 3, 'unit': 'uL', 'source': 'user'},
                         'reading': {'value': 7, 'unit': 'uL', 'source': 'user'}}}
        item = {'sample': self.sample, 'type': 'consume', 'delta': -3, 'unit': 'uL', 'event_id': 'actual-draw'}
        actual = self.draft('actual-draw', experiment=eid, operations=[op], inventory_items=[item])
        preview = S.preview(self.p, actual)
        S.save(self.p, actual, preview['preview_hash'], '实际用量与具体清单确认', preview['inventory']['hash'])
        self.assertEqual(C.load_sample(self.p, self.sample)[1]['quantity'], 17)
        self.save(self.draft('recalc', experiment=eid, reason='更正输入', calculations=[self.request(value=4)]))
        self.save(self.draft('pause', experiment=eid, action='pause'))
        self.assertTrue(S.resume(self.p, eid)['skill']['frozen'])
        (Store.repository(self.p) / 'synthetic-calc' / 'calculate.py').write_text(self.script.replace('x*1', 'x*2'), encoding='utf-8')
        self.save(self.draft('upgrade', experiment=eid, skill_upgrade={'skill': 'synthetic-calc', 'confirmed': True,
                             'reason': '明确升级合成规则'}, calculations=[self.request(value=4)]))
        final = self.draft('final', experiment=eid, action='final_results', submission_kind='final',
                           results=[{'id': 'final', 'text': '测试结果。'}])
        result = self.save(final)
        self.assertTrue(result['archived'])
        self.assertEqual(C.load_sample(self.p, self.sample)[1]['quantity'], 17)
        state = W.read_state(self.p, eid)
        self.assertEqual(state['calculations']['dose']['outputs']['volume']['value'], 8)
        self.assertTrue(state['record_history']); self.assertTrue(state['followups'])
        self.assertEqual(C.read_md(self.target(eid))[0]['completed'], True)
        manifest = json.loads((self.p.experiment_dir(eid) / '归档清单.json').read_text(encoding='utf-8'))
        self.assertTrue(any(f['path'].startswith('history/') for f in manifest['files']))

    def test_history_is_saved_before_replacement_and_property_recovery_reuses_identity(self):
        eid = self.save(self.draft())['experiment']
        initial = self.target(eid).read_text(encoding='utf-8')
        original = C.atomic_write_text
        def fail(path, text):
            if Path(path) == self.target(eid): raise OSError('property replacement interruption')
            original(path, text)
        with patch.object(C, 'atomic_write_text', side_effect=fail):
            with self.assertRaises(OSError): W.set_important(self.p, eid, True)
        journal = json.loads((self.p.state / 'workflow-transaction.json').read_text(encoding='utf-8'))
        history = journal['writes'][0]['path']
        self.assertEqual((self.root / history).read_text(encoding='utf-8'), initial)
        self.assertEqual(self.target(eid).read_text(encoding='utf-8'), initial)
        W.recover_actions(self.p)
        W.set_important(self.p, eid, True)
        state = W.read_state(self.p, eid)
        self.assertEqual(len(state['record_history']), 1)
        self.assertEqual(state['record_history'][0]['path'], history)


if __name__ == '__main__': unittest.main(verbosity=2)
