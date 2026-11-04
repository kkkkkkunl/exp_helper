"""Compare real recalculated Excel values to the independent per-well model."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from core import sha
from workbook import inspect


def verify(directory,evidence):
    import openpyxl
    directory,evidence=Path(directory),Path(evidence)
    model=json.loads((directory/'analysis.json').read_text(encoding='utf-8'))
    engine=json.loads((evidence/'excel-verification.json').read_text(encoding='utf-8-sig'))
    if engine.get('recalculation')!='passed' or len(engine.get('mutations',[]))<2:
        raise ValueError('Missing real engine mutation evidence')
    for mutation in engine['mutations']:
        if math.isclose(mutation['before'],mutation['after'],rel_tol=1e-10) or not math.isclose(mutation['before'],mutation['restored'],rel_tol=1e-10):
            raise ValueError('Mutation did not update and restore the actual formula')
    structure=inspect(directory/'analysis.xlsx')
    if structure['status']!='passed':raise ValueError(str(structure['issues']))
    w=openpyxl.load_workbook(directory/'analysis.xlsx',data_only=True)
    checked=0
    def compare(expected,actual,label):
        nonlocal checked
        if expected is None:
            if actual not in (None,''):raise ValueError(label+' missing value became '+str(actual))
        elif not isinstance(actual,(int,float)) or not math.isclose(expected,actual,rel_tol=1e-9,abs_tol=1e-10):
            raise ValueError(label+' mismatch: '+str(expected)+' != '+str(actual))
        checked+=1
    for i,q in enumerate(model['qc'],2):
        for col,key in [(9,'n'),(10,'mean'),(11,'spread')]:compare(q[key],w['复孔质控'].cell(i,col).value,'QC '+str(i)+'/'+key)
        if q['state']!=w['复孔质控'].cell(i,12).value:raise ValueError('QC state mismatch '+str(i))
    for i,r in enumerate(model['results'],2):
        for col,key in [(12,'delta'),(13,'baseline'),(14,'dd'),(15,'expression')]:compare(r[key],w['计算过程'].cell(i,col).value,'result '+str(i)+'/'+key)
    for i,s in enumerate(model['summaries'],2):
        for col,key in [(5,'n'),(6,'mean'),(7,'error')]:compare(s[key],w['作图'].cell(i,col).value,'summary '+str(i)+'/'+key)
    w.close()
    report={'status':'passed','checked_numeric_cells':checked,'engine':engine['engine'],'version':engine['version'],
            'mutations':engine['mutations'],'static':structure,'workbook_sha256':sha(directory/'analysis.xlsx')}
    (evidence/'model-comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True);p.add_argument('--evidence',required=True)
    args=p.parse_args()
    print(json.dumps(verify(args.directory,args.evidence),ensure_ascii=False))
