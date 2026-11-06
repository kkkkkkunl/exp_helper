"""Lifecycle acceptance tests: all projects, samples, and calendar services are synthetic."""
import copy
import json
import tempfile
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import _common as C
import workflow as W
import install
import stage_templates as T
import calendar_bridge as B
import allocate_id as A
import inventory as I
import stage_workflow as S
import lineage as L
import results as R
import record_format as F


def template_data():
    def field(fid, measured=False):
        f = {'id': fid, 'label': fid, 'type': 'number', 'unit': 'uL', 'required': True,
             'measurement': measured, 'allow_unknown': ['unmeasured'] if measured else []}
        if not measured: f['default'] = 2
        return f
    def step(sid): return {'id': sid, 'title': sid, 'fields': [field('amount'), field('reading', True)]}
    return {'version': 1, 'stages': [
        {'id': 'prepare', 'title': '结构示例准备', 'entry': True, 'pause_after': True,
         'requires': ['quantity', 'unit'], 'input_types': ['source'], 'outputs': ['prepared'],
         'next': ['measure'], 'steps': [step('one'), step('two'), step('three')]},
        {'id': 'measure', 'title': '结构示例测量', 'entry': True, 'pause_after': True,
         'requires': ['quantity', 'unit'], 'input_types': ['prepared'], 'outputs': [],
         'next': [], 'steps': [step('read')]}
    ]}


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        install.initialize(self.root, False)
        cfg_path = self.root / C.CONFIG_NAME
        cfg = C._yamlish.loads(cfg_path.read_text(encoding='utf-8'))
        cfg['method_templates'] = [{'name': 'structural', 'path': 'template.yaml', 'version': 'one', 'format': 'staged'}]
        cfg_path.write_text(C._yamlish.dumps(cfg), encoding='utf-8')
        self.template_path = self.root / 'template.yaml'
        self.template_path.write_text(C._yamlish.dumps(template_data()), encoding='utf-8')
        self.p = C.Project(self.root)
        self.eid = '20261101-120000'
        self.p.experiment_dir(self.eid).mkdir(parents=True)
        self.input = self.root / 'input.txt'; self.input.write_text('真实来源：结果为合成观察。', encoding='utf-8')
        W.start(self.p, 'source', self.input, self.eid)

    def record(self, results='合成观察。', custom=''):
        path = self.root / 'draft.md'
        text = F.render(self.eid, project=self.root.name, purpose='结构测试', reference='示例',
                        method='实际记录', results=results)
        if custom:
            text = custom + F.metadata.split(text)[1]
        path.write_text(text, encoding='utf-8')
        W.write_record(self.p, self.eid, path)
        return self.p.experiment_dir(self.eid) / C.RECORD_NAME

    def sample(self, material='source'):
        sid = A.allocate_sample(self.p, '20261101')
        path, data, _ = C.load_sample(self.p, sid)
        data.update(quantity=10, unit='uL', material_type=material)
        C.save_sample(path, data)
        return sid

    def tree(self):
        return {x.relative_to(self.root).as_posix(): C.sha256_file(x) for x in self.root.rglob('*') if x.is_file()}

    def test_migration_preserves_unknown_fields_and_rejects_future(self):
        path = W.state_path(self.p, self.eid)
        state = W.read_state(self.p, self.eid); state.update(version=3, custom={'x': [1]})
        path.write_text(C.json_text(state), encoding='utf-8')
        migrated = W.read_state(self.p, self.eid)
        self.assertEqual(migrated['version'], 4); self.assertEqual(migrated['custom'], {'x': [1]})
        backup = path.with_name('workflow-v3-backup.json'); digest = C.sha256_file(backup)
        W.read_state(self.p, self.eid); self.assertEqual(digest, C.sha256_file(backup))
        migrated['version'] = 90; path.write_text(C.json_text(migrated), encoding='utf-8')
        before = self.tree()
        with self.assertRaises(C.SkillError): W.read_state(self.p, self.eid)
        self.assertEqual(before, self.tree())

    def test_template_validation_parameters_and_frozen_content(self):
        original = T.select(self.p)
        snap = T.freeze(self.p, self.eid, original)
        self.template_path.write_text(C._yamlish.dumps({'version': 1, 'stages': []}), encoding='utf-8')
        self.assertEqual(T.frozen(self.p, snap), original)
        bad = template_data(); bad['stages'][0]['next'] = ['missing']
        with self.assertRaises(C.SkillError): T.validate(bad)
        bad = template_data(); bad['stages'][0]['steps'].append(copy.deepcopy(bad['stages'][0]['steps'][0]))
        with self.assertRaises(C.SkillError): T.validate(bad)
        step = original['data']['stages'][0]['steps'][0]
        values, missing = T.values(self.p, step, {}, ['amount'])
        self.assertEqual(values['amount']['source'], 'confirmed_default')
        self.assertEqual(missing, ['reading'])
        with self.assertRaises(C.SkillError): T.values(self.p, step, {}, ['reading'])

    def test_local_action_transaction_recovers_after_failure(self):
        a, b = self.root / 'a', self.root / 'b'
        original = C.atomic_write_text
        def fail(path, text):
            if Path(path) == b: raise OSError('synthetic failure')
            original(path, text)
        with patch.object(C, 'atomic_write_text', side_effect=fail):
            with self.assertRaises(OSError): W.action_transaction(self.p, {a: 'one', b: 'two'})
        W.recover_actions(self.p)
        self.assertEqual(a.read_text(), 'one'); self.assertEqual(b.read_text(), 'two')
        self.assertFalse((self.p.state / 'workflow-transaction.json').exists())

    def test_text_results_and_importance_preserve_custom_data(self):
        target = self.record(custom='---\nimportant: true\ntags: [custom]\nnested:\n  key: value\n---\n')
        W.organize(self.p, self.eid, 'text', 'completed', text_evidence={'text': '合成观察。', 'request_id': 'source'})
        front, _ = C.read_md(target)
        self.assertTrue(front['important']); self.assertTrue(front['completed'])
        W.set_important(self.p, self.eid, False)
        front, _ = C.read_md(target)
        self.assertFalse(front['important']); self.assertEqual(front['nested'], {'key': 'value'})
        self.assertTrue(front['completed'])
        with self.assertRaises(C.SkillError):
            W.organize(self.p, self.eid, 'bad', 'completed', text_evidence={'text': '编造', 'request_id': 'source'})

    def test_calendar_pending_schedule_and_manual_time(self):
        self.record()
        for provider in ('synthetic-one', 'synthetic-two'):
            B.configure(self.p, provider, 'calendar', B.CAPABILITIES)
            self.assertEqual(B.binding(self.p)['provider'], provider)
        state = W.read_state(self.p, self.eid)
        fid = B.enqueue(state, self.eid, 'prepare', '准备', ['sample'], ['third'])['id']
        W.save_state(self.p, self.eid, state)
        self.assertEqual(B.prepare(self.p, self.eid, fid)['status'], 'needs_schedule')
        req = B.prepare(self.p, self.eid, fid, {'date': '2026-11-05', 'time': '10:00', 'minutes': 30})['request']
        self.assertEqual(req['operation'], 'find')
        B.receipt(self.p, self.eid, fid, {'request_id': req['id'], 'tool_call_id': 't1', 'ok': True,
                                         'lookup_complete': True, 'matches': []})
        req = B.prepare(self.p, self.eid, fid)['request']; self.assertEqual(req['operation'], 'create')
        B.receipt(self.p, self.eid, fid, {'request_id': req['id'], 'tool_call_id': 't2', 'ok': False, 'error': 'timeout'})
        req = B.prepare(self.p, self.eid, fid)['request']; self.assertEqual(req['operation'], 'find')
        event = {'id': 'remote-one', 'subject': 'manual', 'start': 'changed-time', 'body': B.marker(fid)}
        B.receipt(self.p, self.eid, fid, {'request_id': req['id'], 'tool_call_id': 't3', 'ok': True,
                                         'lookup_complete': True, 'matches': [event]})
        req = B.prepare(self.p, self.eid, fid)['request']; self.assertEqual(req['operation'], 'read')
        B.receipt(self.p, self.eid, fid, {'request_id': req['id'], 'tool_call_id': 't4', 'ok': True, 'event': event})
        req = B.prepare(self.p, self.eid, fid)['request']; self.assertEqual(req['operation'], 'update')
        self.assertNotIn('start', req['payload']); self.assertNotIn('end', req['payload'])
        event['body'] = req['payload']['body']
        B.receipt(self.p, self.eid, fid, {'request_id': req['id'], 'tool_call_id': 't5', 'ok': True, 'event': event})
        self.assertEqual(B.prepare(self.p, self.eid, fid)['status'], 'synced')

    def operation(self, sample, step='one', stage='prepare', amount=2):
        return {'sample': sample, 'stage': stage, 'step': step, 'executed': True,
                'values': {'amount': {'value': amount, 'unit': 'uL', 'source': 'user'},
                           'reading': {'value': 3, 'unit': 'uL', 'source': 'user'}}}

    def draft(self, action='pause', **kw):
        return {'action': action, 'action_id': 'action-' + action, 'experiment': self.eid,
                'template': 'structural', 'entry': 'prepare', 'raw_input': '实际输入，结果为合成观察。',
                'inventory_review': {'mode': 'none', 'reason': '合成项目本轮无库存变化'}, **kw}

    def save(self, draft, inventory=False):
        preview = S.preview(self.p, draft)
        return S.save(self.p, draft, preview['preview_hash'], 'synthetic user approval',
                      preview['inventory']['hash'] if inventory else None)

    def test_pause_is_pure_preview_and_closes_only_executed_steps(self):
        a, b = self.sample(), self.sample()
        draft = self.draft(samples=[a, b], operations=[self.operation(a), self.operation(a, 'two'), self.operation(b)])
        before = self.tree(); preview = S.preview(self.p, draft)
        self.assertEqual(before, self.tree())
        result = S.save(self.p, draft, preview['preview_hash'], 'approved')
        state = W.read_state(self.p, self.eid)
        self.assertEqual(state['segments'][-1]['status'], 'completed')
        self.assertNotIn('three', state['stage_progress'][a]['prepare']['steps'])
        self.assertNotIn('two', state['stage_progress'][b]['prepare']['steps'])
        self.assertFalse(C.read_md(self.p.experiment_dir(self.eid) / C.RECORD_NAME)[0]['completed'])
        self.assertTrue(result['followups'])
        self.assertTrue(any('three' in str(x['remaining']) for x in result['followups']))
        round_no = state['record_round']; self.save(draft)
        self.assertEqual(W.read_state(self.p, self.eid)['record_round'], round_no)
        resume = S.resume(self.p, self.eid); self.assertEqual(resume['state']['experiment'], self.eid)

    def test_stale_preview_rejected_then_manual_text_preserved(self):
        sample = self.sample(); self.record()
        draft = self.draft(samples=[sample], operations=[self.operation(sample)])
        preview = S.preview(self.p, draft)
        target = self.p.experiment_dir(self.eid) / C.RECORD_NAME
        target.write_text(target.read_text(encoding='utf-8') + '\n人工备注\n', encoding='utf-8')
        with self.assertRaises(C.SkillError): S.save(self.p, draft, preview['preview_hash'], 'old')
        self.save(draft); self.assertIn('人工备注', target.read_text(encoding='utf-8'))

    def test_real_retry_and_correction_do_not_rewrite_prior_attempt(self):
        sample = self.sample()
        self.save(self.draft(samples=[sample], operations=[self.operation(sample)]))
        retry = self.draft(action_id='retry-one', retry=[{'sample': sample, 'stage': 'prepare', 'reason': '真实重做'}],
                           operations=[self.operation(sample, amount=4)])
        self.save(retry)
        state = W.read_state(self.p, self.eid)
        self.assertEqual(state['attempts'][0]['previous']['steps']['one']['values']['amount']['value'], 2)
        self.assertEqual(state['stage_progress'][sample]['prepare']['attempt'], 2)
        correction = self.draft('correct', reason='核对原始记录', operations=[self.operation(sample, amount=5)])
        self.save(correction)
        state = W.read_state(self.p, self.eid)
        self.assertEqual(state['corrections'][-1]['before']['values']['amount']['value'], 4)
        self.assertTrue(state['stage_progress'][sample]['prepare']['steps']['one']['executed'])

    def test_new_experiment_allocates_only_when_saving_and_freezes_template(self):
        sample = self.sample()
        draft = self.draft(samples=[sample], operations=[self.operation(sample)])
        draft.pop('experiment')
        before = self.tree(); preview = S.preview(self.p, draft)
        self.assertEqual(before, self.tree())
        result = S.save(self.p, draft, preview['preview_hash'], 'approved')
        self.assertNotEqual(result['experiment'], self.eid)
        saved = W.read_state(self.p, result['experiment'])
        self.template_path.write_text('changed', encoding='utf-8')
        self.assertEqual(T.frozen(self.p, saved['template_snapshot'])['data'], template_data())
        again = S.save(self.p, draft, preview['preview_hash'], 'approved')
        self.assertEqual(again['experiment'], result['experiment'])

    def test_final_text_results_autoarchive_and_nonfinal_rejected(self):
        draft = self.draft('final_results', submission_kind='final', results=[{'id': 'observation', 'text': '合成观察。'}])
        result = self.save(draft)
        self.assertTrue(result['archived']); self.assertEqual(result['execution']['status'], 'ended')
        front = C.read_md(self.p.experiment_dir(self.eid) / C.RECORD_NAME)[0]
        self.assertTrue(front['completed']); self.assertFalse(front['important'])
        bad = self.draft('final_results', submission_kind='preliminary', action_id='prelim')
        with self.assertRaises(C.SkillError): S.preview(self.p, bad)

    def test_pending_inventory_preserves_completion_then_archives(self):
        sample = self.sample()
        rows = [{'sample': sample, 'type': 'consume', 'delta': -2, 'unit': 'uL', 'event_id': 'use'}]
        draft = self.draft('final_results', submission_kind='final', results=[{'id': 'observation', 'text': '合成观察。'}],
                           inventory_items=rows)
        result = self.save(draft)
        self.assertFalse(result['archived']); self.assertEqual(result['execution']['status'], 'ended')
        self.assertTrue(C.read_md(self.p.experiment_dir(self.eid) / C.RECORD_NAME)[0]['completed'])
        I.commit(self.p, self.eid, result['plan_hash'], 'approved actual plan')
        self.assertTrue(W.maybe_archive(self.p, self.eid)['archived'])
        self.save(draft)
        self.assertEqual(C.load_sample(self.p, sample)[1]['quantity'], 8)

    def test_material_product_replay_correction_and_cross_experiment_review(self):
        source = self.sample()
        material = {'material_type': 'prepared', 'produced_by': {'experiment': self.eid, 'stage': 'prepare',
                    'attempt': 1, 'inputs': [source]}}
        product = A.allocate_sample(self.p, '20261101', reservation_key='produce-one', material=material)
        self.assertEqual(A.allocate_sample(self.p, '20261101', reservation_key='produce-one', material=material), product)
        self.assertIsNone(C.load_sample(self.p, product)[1]['parent'])
        rows = [{'sample': source, 'type': 'consume', 'delta': -1, 'unit': 'uL', 'event_id': 'conversion-out',
                 'operation': {'id': 'conversion', 'stage': 'prepare', 'attempt': 1}},
                {'sample': product, 'type': 'create', 'delta': 7, 'unit': 'uL', 'event_id': 'conversion-in',
                 'operation': {'id': 'conversion', 'stage': 'prepare', 'attempt': 1},
                 'concentrations': [{'analyte': 'test', 'origin': 'unmeasured'}]}]
        plan = I.build_plan(self.p, self.eid, rows); I.commit(self.p, self.eid, plan['hash'], 'approved')
        I.build_plan(self.p, self.eid, rows)
        other = '20261101-120001'; self.p.experiment_dir(other).mkdir()
        W.start(self.p, 'other', self.input, other)
        inherited = self.draft(experiment=other, action_id='inherit', entry='measure', samples=[product],
                                operations=[self.operation(product, 'read', 'measure')])
        self.save(inherited)
        self.assertIn(other, {x['experiment'] for x in L.affected_work(self.p, [source])})
        original_history = copy.deepcopy(C.load_sample(self.p, source)[1]['history'])
        correction = [{'sample': source, 'type': 'adjust', 'quantity': 8, 'unit': 'uL', 'event_id': 'correction',
                       'note': '根据实际余额更正', 'correction_of': {'experiment': self.eid, 'event_id': 'conversion-out'}}]
        plan = I.build_plan(self.p, self.eid, correction); I.commit(self.p, self.eid, plan['hash'], 'approved correction')
        front = C.load_sample(self.p, source)[1]
        self.assertEqual(front['history'][:-1], original_history)
        state = W.read_state(self.p, other)
        self.assertTrue(state['review_links']); self.assertTrue(state['stage_progress'][product]['measure']['needs_review'])
        self.assertTrue(state['stage_progress'][product]['measure']['steps']['read']['executed'])

    def test_upgrade_mapping_explicit_and_missing_fields_not_dropped(self):
        sample = self.sample(); self.save(self.draft(samples=[sample], operations=[self.operation(sample)]))
        state = W.read_state(self.p, self.eid); old = T.frozen(self.p, state['template_snapshot'])
        new = copy.deepcopy(old); new['sha256'] = 'new'
        with self.assertRaises(C.SkillError): T.upgrade_preview(state, old, new, {}, {})
        mapping = T.upgrade_preview(state, old, new, {'prepare': 'prepare'}, {'prepare/one': 'one'})
        self.assertTrue(mapping['mapped'][sample]['prepare']['steps']['one']['needs_review'])

    def test_record_action_recovery_reuses_round_and_experiment(self):
        sample = self.sample(); draft = self.draft(samples=[sample], operations=[self.operation(sample)])
        preview = S.preview(self.p, draft); receipt = S.receipt_path(self.p, draft['action_id'])
        original = C.atomic_write_text
        def fail(path, text):
            if Path(path) == receipt: raise OSError('interrupt after record and state')
            original(path, text)
        with patch.object(C, 'atomic_write_text', side_effect=fail):
            with self.assertRaises(OSError): S.save(self.p, draft, preview['preview_hash'], 'approved')
        result = S.save(self.p, draft, preview['preview_hash'], 'approved')
        self.assertEqual(result['record_round'], 1)
        self.assertEqual(len(W.read_state(self.p, self.eid)['segments']), 1)

    def test_installed_cli_stdin_preview_has_no_project_writes(self):
        installed = self.root / 'installed'
        shutil.copytree(Path(S.__file__).parent, installed, ignore=shutil.ignore_patterns('__pycache__'))
        (self.root / 'assets').mkdir(exist_ok=True)
        shutil.copy2(F.TEMPLATE, self.root / 'assets' / F.TEMPLATE.name)
        sample = self.sample(); draft = self.draft(samples=[sample], operations=[self.operation(sample)])
        before = self.tree()
        result = subprocess.run([sys.executable, '-B', str(installed / 'stage_workflow.py'), '--project', str(self.root),
                                 'preview', '--file', '-'], input=json.dumps(draft, ensure_ascii=False),
                                text=True, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['ok'])
        self.assertEqual(before, self.tree())

    def test_inventory_changes_after_record_save_need_new_authorization(self):
        sample = self.sample()
        draft = self.draft(inventory_items=[{'sample': sample, 'type': 'consume', 'delta': -2, 'unit': 'uL', 'event_id': 'actual-use'}])
        preview = S.preview(self.p, draft)
        with patch.object(S, 'continue_action', side_effect=lambda p, receipt: receipt):
            receipt = S.save(self.p, draft, preview['preview_hash'], 'approved old preview', preview['inventory']['hash'])
        path, front, _ = C.load_sample(self.p, sample); front['quantity'] = 9; C.save_sample(path, front)
        result = S.continue_action(self.p, receipt)
        self.assertEqual(result['status'], 'inventory_needs_review')
        self.assertEqual(C.load_sample(self.p, sample)[1]['quantity'], 9)
        plan = I.build_plan(self.p, self.eid, draft['inventory_items']); I.commit(self.p, self.eid, plan['hash'], 'new preview approved')
        self.assertEqual(C.load_sample(self.p, sample)[1]['quantity'], 7)

    def host_cycle(self, fid, events, schedule=None, limit=8):
        for _ in range(limit):
            result = B.prepare(self.p, self.eid, fid, schedule)
            schedule = None
            if result['status'] == 'synced': return
            self.assertEqual(result['status'], 'dispatch')
            req = result['request']; payload = req['payload']; op = req['operation']
            response = {'request_id': req['id'], 'tool_call_id': 'synthetic-' + req['id'], 'ok': True}
            if op == 'find':
                response.update(lookup_complete=True, matches=[copy.deepcopy(e) for e in events.values() if payload['marker'] in e['body']])
            elif op == 'create':
                remote = 'event-' + str(len(events) + 1)
                events[remote] = {'id': remote, **{k: v for k, v in payload.items() if k != 'marker'}}
                response['event'] = copy.deepcopy(events[remote])
            elif op == 'read': response['event'] = copy.deepcopy(events[payload['id']])
            else:
                events[payload['id']].update({k: v for k, v in payload.items() if k != 'marker'})
                response['event'] = copy.deepcopy(events[payload['id']])
            B.receipt(self.p, self.eid, fid, response)
        self.fail('日历协议未收敛')

    def test_full_lifecycle_with_calendar_and_material_conversion(self):
        sample = self.sample(); operation = {'id': 'convert', 'stage': 'prepare', 'attempt': 1}
        rows = [{'sample': sample, 'type': 'consume', 'delta': -2, 'unit': 'uL', 'event_id': 'use-real', 'operation': operation}]
        first = self.save(self.draft(samples=[sample], operations=[self.operation(sample), self.operation(sample, 'two')], inventory_items=rows), inventory=True)
        B.configure(self.p, 'synthetic', 'selected', B.CAPABILITIES)
        events = {}
        for item in first['followups']:
            self.host_cycle(item['id'], events, {'date': '2026-11-06', 'time': '10:00', 'minutes': 20})
        self.assertEqual(len(events), 2)
        self.assertTrue(S.resume(self.p, self.eid)['prompts'])
        self.save(self.draft('confirm', action_id='last-prepare', operations=[self.operation(sample, 'three')]))
        product = A.allocate_product(self.p, '20261101', self.eid, 'prepare', 1, [sample], 'prepared', 'convert')
        self.assertEqual(product, A.allocate_product(self.p, '20261101', self.eid, 'prepare', 1, [sample], 'prepared', 'convert'))
        W.review_inventory(self.p, self.eid, 'required')
        plan = I.build_plan(self.p, self.eid, [{'sample': product, 'type': 'create', 'delta': 7, 'unit': 'uL', 'event_id': 'product',
                                               'operation': operation}])
        I.commit(self.p, self.eid, plan['hash'], 'actual product approval')
        self.save(self.draft('confirm', action_id='measure-product', entry='measure', samples=[product],
                              operations=[self.operation(product, 'read', 'measure')]))
        state = W.read_state(self.p, self.eid)
        for item in state['followups'].values():
            self.assertTrue(item['completed'])
            remote = item['remote_id']; events[remote]['start'] = 'user-rescheduled'
            self.host_cycle(item['id'], events)
            self.assertEqual(events[remote]['start'], 'user-rescheduled')
            self.assertTrue(events[remote]['subject'].startswith('[已完成]'))
        final = self.save(self.draft('final_results', submission_kind='final', important=True,
                                     results=[{'id': 'final', 'text': '合成观察。'}]))
        self.assertTrue(final['archived']); self.assertEqual(len(events), 2)
        self.assertEqual(C.load_sample(self.p, sample)[1]['quantity'], 8)
        self.assertTrue(C.read_md(self.p.experiment_dir(self.eid) / C.RECORD_NAME)[0]['important'])
        self.assertFalse(list(self.p.experiment_dir(self.eid).glob('待办.md')))

    def test_dates_upgrade_and_calendar_metadata_preserve_results(self):
        sample = self.sample(); self.save(self.draft(samples=[sample], actual_date='2020-01-01', operations=[self.operation(sample)]))
        data = template_data(); data['stages'][0]['title'] = '新标题'
        self.template_path.write_text(C._yamlish.dumps(data), encoding='utf-8')
        upgrade = self.draft('upgrade', target_template='structural', mapping={'stages': {'prepare': 'prepare'}, 'steps': {'prepare/one': 'one'}})
        self.save(upgrade)
        state = W.read_state(self.p, self.eid)
        self.assertTrue(state['template_history']); self.assertTrue(state['stage_progress'][sample]['prepare']['needs_review'])
        review = self.draft('correct', reason='明确复核模板映射', resolve_reviews=[{'sample': sample, 'stage': 'prepare', 'confirmed': True, 'reason': '已核对'}])
        self.save(review)
        self.assertFalse(W.read_state(self.p, self.eid)['stage_progress'][sample]['prepare']['needs_review'])
        other = '20261101-120099'; self.p.experiment_dir(other).mkdir()
        W.start(self.p, 'dated', self.input, other)
        s = W.read_state(self.p, other); s['actual_date'] = '2019-01-01'; W.save_state(self.p, other, s)
        self.assertEqual(W.list_experiments(self.p)[0]['experiment'], self.eid)
        final = self.save(self.draft('final_results', submission_kind='final', results=[{'id': 'final', 'text': '合成观察。'}]))
        B.configure(self.p, 'synthetic', 'calendar', B.CAPABILITIES)
        fid = final['followups'][0]['id']; before = C.read_md(self.p.experiment_dir(self.eid) / C.RECORD_NAME)[0]
        B.prepare(self.p, self.eid, fid)
        self.assertEqual(C.read_md(self.p.experiment_dir(self.eid) / C.RECORD_NAME)[0], before)
        self.assertTrue(W.read_state(self.p, self.eid)['archived'])

    def test_invalid_fields_branches_and_result_versions(self):
        for change in ('cycle', 'entry', 'missing'):
            bad = template_data()
            if change == 'cycle': bad['stages'][1]['next'] = ['prepare']
            if change == 'entry':
                for stage in bad['stages']: stage['entry'] = False
            if change == 'missing': del bad['stages'][0]['steps'][0]['fields'][0]['unit']
            with self.assertRaises(C.SkillError): T.validate(bad)
        with self.assertRaises(C.SkillError):
            I.concentrations([{'analyte': 'x', 'origin': 'calculated', 'value': 2, 'unit': 'u'}])
        sample = self.sample(); bad = self.draft(samples=[sample], branches={'prepare': 'no-stage'})
        with self.assertRaises(C.SkillError): S.preview(self.p, bad)
        rid = R.cmd_new(self.p, self.eid, '合成结果')['id']
        result_file = self.p.experiment_dir(self.eid) / 'data.csv'; result_file.write_text('a\n1\n', encoding='utf-8')
        v1 = R.cmd_add_version(self.p, rid, [str(result_file)], 'one')
        R.cmd_mark(self.p, rid, v1['version'], True)
        W.set_important(self.p, self.eid, True)
        v2 = R.cmd_add_version(self.p, rid, [str(result_file)], 'two')
        self.assertFalse(v2['marked'])
        self.assertEqual(len(R.cmd_filter(self.p.kb, True)['results']), 1)


if __name__ == '__main__': unittest.main(verbosity=2)
