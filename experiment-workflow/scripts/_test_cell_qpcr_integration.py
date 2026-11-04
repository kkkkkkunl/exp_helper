"""Concrete professional skill integration; isolated synthetic project only."""
import copy
import json
from pathlib import Path
import shutil
import sys
import unittest
import _test_experiment_skills as fixtures
import _common as C
import experiment_skills as E
import skill_store as Store
import stage_templates as T
import stage_workflow as S
import workflow as W

ROOT=Path(__file__).resolve().parents[2]
SKILL_ROOT=ROOT/'sub_skill'


class CellIntegration(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ExperimentSkills('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.p,self.sample=self.f.p,self.f.sample
        for name in ('cell-qpcr','qpcr-ddcq'):Store.install(self.p,SKILL_ROOT/name)
        self.template=self.f.root/'qpcr.md';shutil.copy2(ROOT/'experiment-workflow/assets/qPCR.md',self.template)
        self.p.cfg['method_templates']=[{'name':'cell-qpcr','path':'qpcr.md','version':'2.0.0','format':'staged','experiment_skill':'cell-qpcr'}]
        self.p.cfg['analysis_map']=[{'match':{'experiment_type':'cell-qpcr','data_type':'qpcr-cq'},'skill':'qpcr-ddcq'}]
        self.f.config()

    def draft(self,action_id='cell-first',**kwargs):
        d=self.f.draft(action_id,experiment_type='cell-qpcr',template='cell-qpcr',entry='rt')
        d.update(kwargs);return d

    def request(self):
        return {'id':'rt-dose','sample':self.sample,'stage':'rt','step':'reaction','calculation':'rt_reaction',
                'inputs':{k:{'value':v,'unit':u,'source':'user'} for k,v,u in [('rna_mass',1000,'ng'),('concentration',100,'ng/uL'),('total_volume',20,'uL'),('gdna_mix',2,'uL'),('rt_mix',4,'uL')]},
                'params':{'confirmed':True,'reaction_type':'RT','method_profile':'AG11728-v6-all-in-one'}}

    def test_install_frontmatter_references_and_real_execution(self):
        from project import dispatch
        for name in ('cell-qpcr','qpcr-ddcq'):
            resolved=Store.resolve(self.p,name);self.assertTrue(resolved['available'])
            self.assertEqual(resolved['metadata']['version'],'1.0.0')
            with self.assertRaises(C.SkillError):Store.install(self.p,SKILL_ROOT/name)
            import re
            for link in re.findall(r'\]\(([^)]+)\)',(SKILL_ROOT/name/'SKILL.md').read_text(encoding='utf-8')):
                if '://' not in link:self.assertTrue((SKILL_ROOT/name/link).is_file(),link)
        self.assertEqual(Store.resolve(self.p,'cell-qpcr')['metadata']['kind'],'experiment')
        self.assertTrue(dispatch(self.p,'cell-qpcr','qpcr-cq')['available'])
        before=self.f.tree()
        ready=E.activate(self.p,'cell-qpcr',T.select(self.p),started=True);self.assertTrue(ready['available'])
        preview=S.preview(self.p,self.draft(calculations=[self.request()]))
        self.assertEqual(preview['calculations'][0]['status'],'computed')
        self.assertEqual(preview['calculations'][0]['outputs']['water_volume']['value'],4)
        self.assertEqual(before,self.f.tree())

    def test_shared_sum_dependency_and_no_execution(self):
        r=self.request()
        shared={'id':'shared','sample':self.sample,'stage':'qpcr','step':'mixes','calculation':'quantity_sum','depends_on':['rt-dose'],
                'inputs':{k:{'value':v,'unit':'uL','source':'calculated','calculation_id':'rt-dose','output':out} for k,v,out in [('a',10,'rna_volume'),('b',4,'water_volume')]},
                'params':{'confirmed':True,'unit':'uL','scope_id':'synthetic-shared','affected_samples':[self.sample],'plan_report':'synthetic plan only'}}
        stock=C.sha256_file(C.load_sample(self.p,self.sample)[0])
        d=self.draft(calculations=[r,shared]);preview=S.preview(self.p,d)
        self.assertEqual(preview['calculations'][1]['outputs']['quantity']['value'],14)
        saved=S.save(self.p,d,preview['preview_hash'],'合成测试确认');eid=saved['experiment']
        state=W.read_state(self.p,eid)
        self.assertEqual(stock,C.sha256_file(C.load_sample(self.p,self.sample)[0]))
        self.assertFalse(state['archived']);self.assertFalse(C.read_md(self.f.target(eid))[0]['completed'])
        self.assertFalse(state['stage_progress'][self.sample]['rt']['steps'])
        self.assertEqual(set(state['stage_progress']),{self.sample})
        bad=copy.deepcopy(shared);bad['inputs']['a']['value']=99
        p=S.preview(self.p,self.draft('invalid',experiment=eid,reason='合成错误输入',calculations=[bad]))
        self.assertEqual(p['calculations'][1]['status'],'invalid_inputs')

    def test_frozen_legacy_and_explicit_template_upgrade(self):
        legacy=ROOT/'experiment-workflow/assets/legacy/qPCR-1.0.0.md'
        self.template.write_bytes(legacy.read_bytes());self.p.cfg['method_templates'][0]['version']='1.0.0';self.f.config()
        d=self.draft('legacy',method_text='合成仅记录，不执行旧公式')
        pv=S.preview(self.p,d);saved=S.save(self.p,d,pv['preview_hash'],'合成确认');eid=saved['experiment']
        old=W.read_state(self.p,eid)['template_snapshot']
        shutil.copy2(ROOT/'experiment-workflow/assets/qPCR.md',self.template)
        self.assertEqual(T.frozen(self.p,old)['version'],'1.0.0')
        self.assertIn('calc-js',T.frozen(self.p,old)['content'])
        self.p.cfg['method_templates'][0]['version']='2.0.0';self.f.config()
        data=T.select(self.p)['data']
        mapping={'stages':{s['id']:s['id'] for s in data['stages']},'steps':{s['id']+'/'+st['id']:s['id']+'/'+st['id'] for s in data['stages'] for st in s['steps']}}
        upgrade=self.draft('migrate',experiment=eid,action='upgrade',target_template='cell-qpcr',mapping=mapping,method_text='本次明确将模板升级为2.0.0，已核对技能依据与字段映射；不代表执行操作。')
        pv=S.preview(self.p,upgrade);S.save(self.p,upgrade,pv['preview_hash'],'合成确认升级')
        state=W.read_state(self.p,eid)
        self.assertEqual(T.frozen(self.p,state['template_snapshot'])['version'],'2.0.0')
        self.assertTrue(state['template_history']);self.assertTrue(state['record_history'])

    def test_real_analysis_versions_and_record_handoff(self):
        import csv
        import importlib.util
        import results as R
        sys.path.insert(0,str(SKILL_ROOT/'qpcr-ddcq/scripts'))
        from analyze import execute
        spec=importlib.util.spec_from_file_location('cell_fixture',SKILL_ROOT/'qpcr-ddcq/tests/create_fixture.py')
        fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
        d=self.draft('analysis-entry',entry='results',method_text='仅整理已有细胞qPCR，不补写前序操作。')
        p=S.preview(self.p,d);saved=S.save(self.p,d,p['preview_hash'],'合成确认');eid=saved['experiment']
        config_path=fixture.create(self.f.root/'synthetic-inputs')
        source=config_path.parent/'synthetic.csv'
        with source.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f);headers=reader.fieldnames;rows=[r for r in reader if r['Sample'] not in ('t2','m1')]
        with source.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=headers);writer.writeheader();writer.writerows(rows)
        config=json.loads(config_path.read_text(encoding='utf-8'))
        state=W.read_state(self.p,eid)
        config['experiment_skill_basis']=str(self.p.root/state['skill_snapshot']['path'])
        config['output_dir']=str(self.p.experiment_dir(eid)/'qpcr-analysis')
        answer=execute(config,config_path.parent);self.assertEqual(answer['status'],'computed')
        out=Path(answer['output_dir']);manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['experiment_skill_basis']['skill'],'cell-qpcr')
        self.assertEqual(manifest['skill']['skill'],'qpcr-ddcq')
        self.assertNotEqual(manifest['skill']['sha256'],state['skill_snapshot']['sha256'])
        files=[str(out/'analysis.xlsx'),str(out/'manifest.json'),str(out/'qpcr-ddcq-basis.zip')]
        W.update_analysis(self.p,eid,'qpcr','completed','qpcr-ddcq',manifest['skill']['sha256'],[str(source)],files,json.dumps(config['params']))
        W.organize(self.p,eid,'qpcr-result','pending',analysis_tasks=['qpcr'])
        with self.assertRaises(C.SkillError):W.organize(self.p,eid,'qpcr-result','completed',[files[0]],['qpcr'])
        result=R.cmd_new(self.p,eid,'合成qPCR')
        first=R.cmd_add_version(self.p,result['id'],files,json.dumps(config['params']))
        self.assertEqual(first['version'],1)
        self.assertTrue(R.cmd_add_version(self.p,result['id'],files,json.dumps(config['params']))['noop'])
        target=self.f.target(eid);candidate=self.f.root/'filled.md'
        candidate.write_text(target.read_text(encoding='utf-8').replace('## 结果\n','## 结果\n\n[合成工作簿](qpcr-analysis/analysis.xlsx)\n'),encoding='utf-8')
        W.write_record(self.p,eid,candidate,affects_results=['qpcr-result'])
        W.organize(self.p,eid,'qpcr-result','completed',[files[0]],['qpcr'])
        self.assertTrue(C.read_md(target)[0]['completed']);self.assertFalse(W.read_state(self.p,eid)['archived'])
        config['params']['error_bar']='SEM';config['output_dir']=str(self.p.experiment_dir(eid)/'qpcr-sem')
        execute(config,config_path.parent);out2=Path(config['output_dir'])
        files2=[str(out2/name) for name in ('analysis.xlsx','manifest.json','qpcr-ddcq-basis.zip')]
        self.assertEqual(R.cmd_add_version(self.p,result['id'],files2,json.dumps(config['params']))['version'],2)
        W.update_analysis(self.p,eid,'qpcr','completed','qpcr-ddcq',manifest['skill']['sha256'],[str(source)],files2,json.dumps(config['params']))
        self.assertEqual(W.read_state(self.p,eid)['result_tasks']['qpcr-result']['status'],'pending')

if __name__=='__main__':unittest.main()
