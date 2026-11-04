from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from core import analyze

def row(group,sample,gene,cq,well,**kwargs):
    return dict(scope='s',run='p',well=well,group=group,sample=sample,bio_id=sample,gene=gene,assay=gene,cq_raw=cq,**kwargs)

class Analysis(unittest.TestCase):
    def test_strict_boundaries(self):
        for difference,expected in [('0.499','严格合格'),('0.500','未达到严格标准'),('0.999','未达到严格标准'),('1.000','严重不合格')]:
            from decimal import Decimal
            r=analyze([row('Control','c','GAPDH','20','A1'),row('Control','c','GAPDH',str(Decimal(20)+Decimal(difference)),'A2')],{})
            self.assertEqual(r['qc'][0]['state'],expected)
    def test_calibration_is_sample_weighted(self):
        rows=[]
        for sample,mean,n in [('c1',24,2),('c2',26,3)]:
            for gene,m in [('GAPDH',20),('FLG',mean)]:
                for i in range(n):rows.append(row('Control',sample,gene,m,str(len(rows)+1)))
        r=analyze(rows,{'biological_replicates':True})
        self.assertEqual([x['expression'] for x in r['results']],[2,.5]);self.assertEqual(r['summaries'][0]['mean'],1.25)
    def test_fixed_reference_missing_and_single(self):
        rows=[row('Control','c','GAPDH',20,'A1'),row('Control','c','FLG',24,'A2'),row('Treatment','t','FLG',24,'A3'),row('Treatment','t','actin',20,'A4')]
        r=analyze(rows,{'biological_replicates':True,'targets':['FLG']})
        self.assertEqual(r['reference']['s'],'GAPDH');self.assertEqual(r['results'][0]['expression'],1)
        self.assertIsNone(r['results'][1]['expression']);self.assertIn('复孔不足',';'.join(r['results'][0]['qc']))
    def test_excluded_missing_duplicate_and_conflict(self):
        rows=[row('Control','c','GAPDH','20','A1'),row('Control','c','GAPDH','30','A2',excluded_raw=True),row('Control','c','GAPDH','Undetermined','A3')]
        r=analyze(rows+[dict(rows[0])],{})
        self.assertEqual(r['qc'][0]['n'],1);self.assertEqual(len(r['rows']),4)
        r=analyze(rows+[dict(rows[0],cq_raw=21)],{});self.assertTrue(r['qc'][0]['blocking'])
    def test_ambiguous_calibration_and_first_group(self):
        rows=[]
        for group in ['D0','NC']:
            rows.extend([row(group,group,'GAPDH',20,str(len(rows)+1)),row(group,group,'FLG',24,str(len(rows)+2))])
        r=analyze(rows,{});self.assertIsNone(r['calibrator']['s']);self.assertTrue(all(x['expression'] is None for x in r['results']))
        for x in rows:x['group']='first' if x['group']=='D0' else 'next'
        r=analyze(rows,{});self.assertEqual(r['calibrator']['s'],'first');self.assertTrue(r['assumptions'])

    def test_calibration_qc_propagates_and_sem_uses_biological_n(self):
        rows=[]
        for sample,delta in [('c1',4),('c2',6),('t1',3)]:
            group='Control' if sample.startswith('c') else 'Treatment'
            for gene,mean in [('GAPDH',20),('FLG',20+delta)]:
                for j in range(2):
                    shift=(-.5 if j==0 else .5) if sample=='c1' and gene=='GAPDH' else 0
                    rows.append(row(group,sample,gene,mean+shift,str(len(rows)+1)))
        r=analyze(rows,{'biological_replicates':True,'error_bar':'SEM'})
        self.assertTrue(any('校准内参' in x for x in r['results'][-1]['qc']))
        self.assertAlmostEqual(r['summaries'][0]['error'],.75)
        self.assertIsNone(r['summaries'][1]['error']);self.assertEqual(r['summaries'][1]['n'],1)
        r=analyze(rows+[dict(rows[0],run='p2',well='B1')],{'biological_replicates':True})
        self.assertTrue(any(q['blocking'] for q in r['qc']))

    def test_entire_missing_assay_is_reported_without_fabricating_wells(self):
        rows=[row('Control','c','GAPDH',20,'A1'),row('Control','c','FLG',24,'A2'),row('Treatment','t','GAPDH',20,'A3')]
        r=analyze(rows,{'biological_replicates':True})
        self.assertEqual(len(r['rows']),3)
        self.assertEqual(len(r['results']),2)
        self.assertIsNone(r['results'][1]['expression'])
        missing=[q for q in r['qc'] if q['expected_missing']]
        self.assertEqual(len(missing),1);self.assertEqual(missing[0]['indexes'],[])

    def test_assay_identity_conflict_blocks_only_affected_scope(self):
        rows=[row('Control','c','GAPDH',20,'A1'),row('Control','c','FLG',24,'A2'),dict(row('Control','c','OTHER',25,'A3'),assay='FLG')]
        r=analyze(rows,{'biological_replicates':True})
        self.assertTrue(any(q['blocking'] for q in r['qc']))
        self.assertTrue(all(x['expression'] is None for x in r['results']))
        self.assertEqual([x['gene'] for x in r['rows']],['GAPDH','FLG','OTHER'])

if __name__=='__main__':unittest.main()
