import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from calculate import calculate
from validate_plan import validate

def request(name,values,**params):
    d=json.loads((ROOT/'experiment-skill.json').read_text(encoding='utf-8'))['calculations'][name]
    return {'calculation':name,'inputs':{k:{'value':v,'unit':d['inputs'].get(k,{}).get('unit',params.get('unit')),'source':'user'} for k,v in values.items()},'params':dict(confirmed=True,**params)}

class Scalars(unittest.TestCase):
    def test_rt_zero_and_changed_components(self):
        v=dict(rna_mass=1000,concentration=100,total_volume=20,gdna_mix=2,rt_mix=4)
        r=request('rt_reaction',v,reaction_type='RT',method_profile='AG11728-v6-all-in-one')
        x=calculate(r);self.assertEqual(x['status'],'computed');self.assertEqual(x['outputs']['water_volume']['value'],4)
        r['inputs']['gdna_mix']['value']=3;r['inputs']['rt_mix']['value']=5
        x=calculate(r);self.assertEqual(x['status'],'needs_review');self.assertEqual(x['candidate_outputs']['water_volume'],2)
        r=request('rt_reaction',dict(v,concentration=1000/14),reaction_type='RT',method_profile='AG11728-v6-all-in-one')
        self.assertAlmostEqual(calculate(r)['outputs']['water_volume']['value'],0)
        r['inputs']['concentration']['value']=0;self.assertEqual(calculate(r)['status'],'invalid_inputs')
        r['inputs']['concentration']['value']=50;self.assertEqual(calculate(r)['status'],'invalid_inputs')
    def test_equivalent_and_primer(self):
        x=calculate(request('rna_equivalent',dict(rna_mass=800,rt_volume=20,dilution=2,target_mass=25)))
        self.assertEqual([x['outputs'][k]['value'] for k in ('equivalent_concentration','template_volume','stock_equivalent')],[20,1.25,.625])
        x=calculate(request('primer_final',dict(f_working=10,r_working=10,f_volume=.4,r_volume=.4,total_volume=20)))
        self.assertEqual(x['outputs']['f_final']['value'],.2)
    def test_sources_confirmations_and_time(self):
        r=request('quantity_sum',dict(a=2,b=3),unit='well')
        self.assertEqual(calculate(r)['outputs']['quantity'],{'value':5,'unit':'well'})
        r['inputs']['a']['value']=1.5;self.assertEqual(calculate(r)['status'],'invalid_inputs')
        r['params']['confirmed']=False;self.assertEqual(calculate(r)['status'],'invalid_inputs')
        r=request('treatment_duration',dict(start_epoch=0,end_epoch=3600),start_time='1970-01-01T00:00:00+00:00',end_time='1970-01-01T01:00:00+00:00')
        self.assertEqual(calculate(r)['outputs']['duration']['value'],1)
        r['params']['end_time']='1970-01-01T01:00:00';self.assertEqual(calculate(r)['status'],'invalid_inputs')
    def test_complete_plan_and_independent_volume_expectations(self):
        plan=json.loads((ROOT/'assets/synthetic-plan.json').read_text(encoding='utf-8'))
        r=validate(plan);self.assertEqual(r['status'],'valid',r['issues'])
        get=lambda name,k:r['calculations'][name]['outputs'][k]['value']
        self.assertAlmostEqual(get('mix3/sample/TARGET','mix2_transfer'),20.24)
        self.assertAlmostEqual(get('mix2/sample','total'),42.32)
        self.assertAlmostEqual(get('mix1/standard','total'),90.48)
        self.assertAlmostEqual(get('mix1/standard','remaining'),10.44)
        bad=copy.deepcopy(plan);bad['wells'][1]['well']='A1';self.assertEqual(validate(bad)['status'],'invalid')
        bad=copy.deepcopy(plan);bad['factors']['k2']=1.05;self.assertEqual(validate(bad)['status'],'invalid')
        bad=copy.deepcopy(plan);bad['templates'][1]['material_type']='cdna';self.assertEqual(validate(bad)['status'],'invalid')
        bad=copy.deepcopy(plan);bad['targets'][0]['wells']=1.5;self.assertEqual(validate(bad)['status'],'invalid')

    def test_rox_recipe_and_two_compositions(self):
        values=dict(total_volume=10,premix=5,template=.5,f_volume=.4,r_volume=.4,rox=.2,dilution=1)
        r=calculate(request('qpcr_recipe',values,method_profile='AG11701-v4e1',rox_basis='Synthetic checked no actual instrument'))
        self.assertAlmostEqual(r['outputs']['water_volume']['value'],3.5)
        self.assertAlmostEqual(r['outputs']['base_volume']['value'],8.7)
        plan=json.loads((ROOT/'assets/synthetic-plan.json').read_text(encoding='utf-8'))
        plan['recipes'].append(dict(plan['recipes'][0],id='diluted',template=1.25,rox=.2,dilution=2))
        plan['blocks'].append(dict(id='diluted',run='plate2',type='RT',template='synthetic-cdna',recipe='diluted'))
        plan['runs'].append(dict(id='plate2',layout='96'))
        plan['targets'].append(dict(block='diluted',assay='TARGET',wells=3))
        plan['wells'].extend(dict(run='plate2',well='A'+str(i+1),block='diluted',assay='TARGET',type='RT') for i in range(3))
        r=validate(plan);self.assertEqual(r['status'],'valid',r['issues'])
        o=r['calculations']['mix1/diluted']['outputs']
        self.assertAlmostEqual(o['premix_total']['value'],19.5)
        self.assertAlmostEqual(o['water_total']['value'],10.725)
        self.assertAlmostEqual(o['rox_total']['value'],.78)
        self.assertAlmostEqual(r['calculations']['mix1/standard']['outputs']['total']['value'],90.48)
        bad=copy.deepcopy(plan);bad['assays'][0]['f_volume']=.2;self.assertEqual(validate(bad)['status'],'invalid')
        bad=copy.deepcopy(plan);bad['blocks'].append(dict(plan['blocks'][0]));self.assertEqual(validate(bad)['status'],'invalid')

if __name__=='__main__':unittest.main()
