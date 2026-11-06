"""Regression tests use synthetic samples and a temporary filesystem only."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import _common as C
import allocate_id as A
import inventory as I
import project as P
import workflow as W
import record_format as Format
import results as R


class Regression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'kb/samples').mkdir(parents=True)
        cfg = {'knowledge_base': 'kb', 'units': {'convert': [['uL','mL']]}, 'analysis_map': [
            {'match': {'experiment_type': '流式'}, 'skill': 'flow'},
            {'match': {'data_type': 'qpcr'}, 'skill': 'qpcr'}]}
        (self.root/C.CONFIG_NAME).write_text(C._yamlish.dumps(cfg), encoding='utf-8')
        self.p = C.Project(self.root)
        self.eid = '20261101-120000'
        self.p.experiment_dir(self.eid).mkdir(parents=True)

    def sample(self, quantity=10):
        sid = A.allocate_sample(self.p, '20261101')
        path, f, _ = C.load_sample(self.p, sid)
        f.update(quantity=quantity, unit='mL')
        C.save_sample(path, f)
        return sid

    def state(self, sid):
        return C.load_sample(self.p, sid)[1]

    def row(self, sid, event='event-1', delta=-2, kind='consume', **kw):
        return dict(sample=sid, event_id=event, delta=delta, type=kind, unit='mL', **kw)

    def commit(self, plan):
        return I.commit(self.p, plan['experiment'], plan['hash'], 'synthetic-test')

    def test_dispatch_missing_field_never_matches(self):
        self.assertEqual(P.dispatch(self.p, '流式', None)['skill'], 'flow')
        self.assertIsNone(P.dispatch(self.p, '未知', None)['skill'])
        self.assertEqual(P.dispatch(self.p, None, 'qpcr')['skill'], 'qpcr')
        self.assertFalse(P.dispatch(self.p, '流式', None)['available'])

    def test_distinct_events_and_replays(self):
        sid = self.sample()
        rows = [self.row(sid, 'first'), self.row(sid, 'second')]
        plan = I.build_plan(self.p, self.eid, rows)
        self.commit(plan); self.commit(plan)
        self.assertEqual(self.state(sid)['quantity'], 6)
        replay = I.build_plan(self.p, self.eid, rows)
        self.assertEqual(replay['items'], [])
        self.commit(replay)
        self.assertEqual(self.state(sid)['quantity'], 6)
        with self.assertRaises(C.SkillError):
            I.build_plan(self.p, self.eid, [self.row(sid, 'first', -1)])

    def test_duplicate_event_rejected(self):
        sid = self.sample()
        with self.assertRaises(C.SkillError):
            I.build_plan(self.p, self.eid, [self.row(sid), self.row(sid)])

    def test_return_restores_stock(self):
        sid = self.sample(2)
        self.commit(I.build_plan(self.p, self.eid, [self.row(sid), self.row(sid, 'return', 1, 'return')]))
        self.assertEqual(self.state(sid)['status'], 'in_stock')
        self.assertEqual(I.list_stock(self.p)['samples'][0]['quantity'], 1)

    def test_stale_batch_writes_nothing(self):
        a,b = self.sample(), self.sample()
        plan = I.build_plan(self.p, self.eid, [self.row(a, 'a'), self.row(b, 'b')])
        path, f, _ = C.load_sample(self.p,b); f['quantity'] = 1; C.save_sample(path, f)
        with self.assertRaises(C.SkillError): self.commit(plan)
        self.assertEqual(self.state(a)['quantity'], 10)
        self.assertEqual(self.state(a)['history'], [])

    def test_unit_change_invalidates_plan(self):
        sid = self.sample()
        plan = I.build_plan(self.p,self.eid,[self.row(sid)])
        path,f,_=C.load_sample(self.p,sid); f.update(quantity=10000,unit='uL'); C.save_sample(path,f)
        with self.assertRaises(C.SkillError): self.commit(plan)
        plan=I.build_plan(self.p,self.eid,[self.row(sid)])
        self.commit(plan)
        self.assertEqual(self.state(sid)['quantity'],8000)

    def test_confirmation_bound_to_plan(self):
        sid = self.sample(); plan=I.build_plan(self.p,self.eid,[self.row(sid)])
        with self.assertRaises(C.SkillError): I.commit(self.p,self.eid)
        with self.assertRaises(C.SkillError): I.commit(self.p,self.eid,'wrong','user')
        self.assertEqual(self.state(sid)['quantity'],10)
        self.commit(plan)
        self.assertIn('已提交', (self.p.experiment_dir(self.eid)/I.PLAN_NAME).read_text())

    def test_grouped_aliquot_initialization(self):
        sid = self.sample(); child=A.allocate_aliquots(self.p,sid,1)[0]
        rows=[self.row(sid,'out',-2,'aliquot_out',group_id='g'),
              self.row(child,'in',2,'aliquot_in',group_id='g')]
        self.commit(I.build_plan(self.p,self.eid,rows))
        self.assertEqual(self.state(sid)['quantity'],8)
        self.assertEqual(self.state(child)['quantity'],2)
        with self.assertRaises(C.SkillError):
            I.build_plan(self.p,self.eid,[self.row(child,'alone',1,'aliquot_in',group_id='bad')])

    def test_mixed_sources(self):
        a,b=self.sample(),self.sample()
        child=A.allocate_sample(self.p,'20261101','mixed')
        rows=[self.row(a,'a',-1,'mixed_out',group_id='g'),
              self.row(b,'b',-1,'mixed_out',group_id='g'),
              self.row(child,'in',2,'mixed_in',group_id='g',sources=[a,b])]
        self.commit(I.build_plan(self.p,self.eid,rows))
        self.assertEqual(self.state(child)['sources'],[a,b])

    def test_recovery_after_interrupted_writes(self):
        a,b=self.sample(),self.sample()
        plan=I.build_plan(self.p,self.eid,[self.row(a,'a'),self.row(b,'b')])
        original=C.atomic_write_text
        def fail(path,text):
            if Path(path)==self.p.sample_path(b): raise OSError('simulated disk failure')
            original(path,text)
        with patch.object(C,'atomic_write_text',side_effect=fail):
            with self.assertRaises(C.SkillError): self.commit(plan)
        self.assertTrue((self.p.samples/'.transaction.json').exists())
        stock=I.list_stock(self.p) # recovery happens before any supported reader
        self.assertEqual([r['quantity'] for r in stock['samples']],[8,8])
        self.assertTrue(self.commit(plan)['noop'])
        self.assertFalse((self.p.samples/'.transaction.json').exists())

    def test_concurrent_commits_one_wins_other_replans(self):
        sid=self.sample()
        other='20261101-120001'; self.p.experiment_dir(other).mkdir()
        plans=[I.build_plan(self.p,eid,[self.row(sid,eid)]) for eid in [self.eid,other]]
        script=Path(I.__file__)
        processes=[subprocess.Popen([sys.executable,str(script),'commit','--project',str(self.root),
            '--experiment',p['experiment'],'--plan-hash',p['hash'],'--confirmed-by','test'],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for p in plans]
        outputs=[json.loads(proc.communicate(timeout=20)[0]) for proc in processes]
        self.assertEqual(sum(o['ok'] for o in outputs),1)
        self.assertEqual(self.state(sid)['quantity'],8)
        failed=plans[next(i for i,o in enumerate(outputs) if not o['ok'])]['experiment']
        self.commit(I.build_plan(self.p,failed,[self.row(sid,failed)]))
        self.assertEqual(self.state(sid)['quantity'],6)

    def start_workflow(self):
        source=self.root/'input.txt'; source.write_text('实际实验输入',encoding='utf-8')
        W.start(self.p,'request-1',source,self.eid)
        return source

    def record(self):
        path=self.root/'draft.md'
        path.write_text(Format.render(self.eid, project=self.root.name, purpose='测试',
                                     method='实际操作', results='无分析数值', attachments='无'), encoding='utf-8')
        return path

    def test_resume_and_manual_edit_guard(self):
        source=self.start_workflow()
        self.assertTrue(W.start(self.p,'request-1',source)['noop'])
        W.write_record(self.p,self.eid,self.record())
        target=self.p.experiment_dir(self.eid)/C.RECORD_NAME
        target.write_text(target.read_text()+'\n人工补充',encoding='utf-8')
        with self.assertRaises(C.SkillError): W.write_record(self.p,self.eid,self.record())
        self.assertIn('人工补充',target.read_text())



    def test_reserved_ids_survive_deleted_sample_file(self):
        sid = self.sample()
        self.p.sample_path(sid).unlink()
        self.assertNotEqual(self.sample(), sid)






    def test_same_name_result_files_rejected(self):
        a=self.root/'a'; b=self.root/'b'; a.mkdir(); b.mkdir()
        for base in [a,b]: (base/'result.csv').write_text(base.name)
        rid=R.cmd_new(self.p,self.eid,'结果')['id']
        with self.assertRaises(C.SkillError):
            R.cmd_add_version(self.p,rid,[str(a/'result.csv'),str(b/'result.csv')],'')

    def test_nonfinite_and_path_ids_rejected(self):
        sid=self.sample()
        for value in [float('nan'),float('inf')]:
            with self.assertRaises((C.SkillError,ValueError)):
                I.build_plan(self.p,self.eid,[self.row(sid,delta=value)])
        with self.assertRaises(C.SkillError): self.p.sample_path('../escape')


if __name__=='__main__': unittest.main(verbosity=2)
