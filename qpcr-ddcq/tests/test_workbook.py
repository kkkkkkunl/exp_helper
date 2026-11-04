import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze import execute,read_inputs
from workbook import inspect
from create_fixture import create

class Workbook(unittest.TestCase):
    def test_file_flow_and_formula_structure(self):
        import openpyxl
        work=Path(__file__).resolve().parents[2]/'.qpcr-work'
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work) as temp:
            config_path=create(temp);config=json.loads(config_path.read_text(encoding='utf-8'))
            answer=execute(config,config_path.parent);self.assertEqual(answer['results'],10)
            out=Path(answer['output_dir']);self.assertEqual(inspect(out/'analysis.xlsx')['status'],'passed')
            values=openpyxl.load_workbook(out/'analysis.xlsx',data_only=True)
            formulas=openpyxl.load_workbook(out/'analysis.xlsx',data_only=False)
            self.assertEqual(formulas['整理数据']['A1'].value,"='计算过程'!B2")
            self.assertEqual(formulas['整理数据'].max_column,3)
            found=[]
            for row in values['计算过程'].iter_rows(min_row=2,values_only=True):
                if row[1]=='Control' and row[3]=='FLG':found.append(row[14])
            self.assertEqual(found,[2,.5])
            self.assertEqual(len(formulas['作图']._charts),2)
            for chart in formulas['作图']._charts:
                self.assertIsNone(chart.legend);self.assertIsNone(chart.title)
                self.assertEqual(chart.y_axis.scaling.min,0)
                # Control n=2 has an error object; treatment n=1 does not.
                self.assertEqual(sum(s.errBars is not None for s in chart.series),1)
                for series in chart.series:
                    if series.errBars is not None:self.assertIsNotNone(series.errBars.plus.numRef)
            self.assertTrue((out/'qpcr-ddcq-basis.zip').is_file())
            with self.assertRaises(FileExistsError):execute(config,config_path.parent)
            values.close();formulas.close()

    def test_xlsx_tsv_import_and_technical_only_charts(self):
        import csv
        import openpyxl
        import xlsxwriter
        work=Path(__file__).resolve().parents[2]/'.qpcr-work'
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work) as temp:
            p=create(temp);config=json.loads(p.read_text(encoding='utf-8'))
            records,provenance=read_inputs(config,p.parent)
            with (p.parent/'synthetic.csv').open(encoding='utf-8-sig',newline='') as f:data=list(csv.reader(f))
            with (p.parent/'source.tsv').open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f,delimiter='\t').writerows(data)
            w=xlsxwriter.Workbook(p.parent/'source.xlsx');s=w.add_worksheet('Raw')
            for i,row in enumerate(data):s.write_row(i,0,row)
            w.close()
            for name in ['source.tsv','source.xlsx']:
                cfg=dict(config,inputs=[dict(config['inputs'][0],path=name)])
                new,_=read_inputs(cfg,p.parent)
                self.assertEqual([r['cq_raw'] for r in records],[r['cq_raw'] for r in new])
                self.assertEqual(len(new),29)
            config['params']['biological_replicates']=False
            result=execute(config,p.parent)
            w=openpyxl.load_workbook(Path(result['output_dir'])/'analysis.xlsx')
            self.assertTrue(all(s.errBars is None for c in w['作图']._charts for s in c.series));w.close()

if __name__=='__main__':unittest.main()
