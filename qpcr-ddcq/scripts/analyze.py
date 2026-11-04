"""Explicit file-analysis entry point, independent of workflow scalar execution."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile
sys.dont_write_bytecode=True
from core import analyze, json_ready, sha


def package_evidence(root):
    files={}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():raise ValueError('技能依据不接受符号链接')
        if path.is_file() and '__pycache__' not in path.parts:
            files[path.relative_to(root).as_posix()]=sha(path)
    fingerprint=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()
    return {'skill':root.name,'version':'1.0.0','sha256':fingerprint,'files':files}


def read_inputs(config,base):
    records=[];provenance=[]
    if not config.get('inputs'):raise ValueError('必须提供 inputs')
    for item in config['inputs']:
        path=Path(item['path']);path=path if path.is_absolute() else base/path
        path=path.resolve()
        if path.suffix.lower() not in ('.xlsx','.csv','.tsv'):raise ValueError('不支持输入格式: '+str(path))
        header_row=item.get('header_row',1)
        if not isinstance(header_row,int) or header_row<1:raise ValueError('header_row 须为正整数')
        columns=item['columns']
        if not all(k in columns for k in ('group','gene','cq_raw')):raise ValueError('列映射必须含 group/gene/cq_raw')
        if path.suffix.lower()=='.xlsx':
            import openpyxl
            wb=openpyxl.load_workbook(path,read_only=True,data_only=False)
            sheet=wb[item['sheet']] if item.get('sheet') else wb.worksheets[0]
            stream=sheet.iter_rows(values_only=True)
            for _ in range(header_row-1):next(stream)
            headers=list(next(stream));data=list(stream);sheet_name=sheet.title;wb.close()
        else:
            with path.open(encoding=item.get('encoding','utf-8-sig'),newline='') as f:
                stream=csv.reader(f,delimiter='\t' if path.suffix.lower()=='.tsv' else ',')
                for _ in range(header_row-1):next(stream)
                headers=next(stream);data=list(stream)
            sheet_name=''
        if len(headers)!=len(set(str(h) for h in headers)):raise ValueError('重复表头，须明确转换: '+str(path))
        for col in columns.values():
            if col not in headers:raise ValueError('未找到列: '+str(col))
        provenance.append({'path':str(path),'sha256':sha(path),'sheet':sheet_name,'columns':columns,'header_row':header_row})
        for number,values in enumerate(data,header_row+1):
            if not any(v is not None and str(v).strip() for v in values):continue
            original=dict(zip(headers,values))
            row={k:original.get(v,'') for k,v in columns.items()}
            row.update(file=str(path),sheet=sheet_name,source_row=number,original=original)
            row.setdefault('scope',item.get('scope','default'));row.setdefault('run',item.get('run',str(path)))
            row.setdefault('kind','sample');row.setdefault('assay',row.get('gene',''))
            row['row_id']=str(path)+'#'+sheet_name+'!'+str(number)
            for field in ('scope','run','well','group','sample','bio_id','gene','assay','kind'):
                if field in row:row[field]='' if row[field] is None else str(row[field]).strip()
            if row['kind'] in ('RT','rt'):row['kind']='sample'
            if row['kind'] in ('−RT','NRT'):row['kind']='-RT'
            for field,mapping in config.get('value_maps',{}).items():
                if field in row:row[field]=mapping.get(row[field],row[field])
            records.append(row)
    if not records:raise ValueError('没有可读取的原始检测行')
    return records,provenance


def execute(config,base):
    from workbook import build,inspect
    records,provenance=read_inputs(config,base)
    model=analyze(records,config.get('params',{}))
    destination=Path(config['output_dir']);destination=destination if destination.is_absolute() else base/destination
    destination=destination.resolve()
    if destination.is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('输出目录不能位于分析技能源码内')
    if destination.exists():raise FileExistsError('输出目录已存在，拒绝覆盖: '+str(destination))
    if any(destination==Path(x['path']) or Path(x['path']).is_relative_to(destination) for x in provenance):
        raise ValueError('输出不能覆盖或包含原始数据目录')
    destination.parent.mkdir(parents=True,exist_ok=True)
    scratch=Path(tempfile.mkdtemp(prefix='.qpcr-',dir=str(destination.parent)))
    try:
        evidence=package_evidence(Path(__file__).resolve().parents[1])
        artifacts=build(model,scratch/'analysis.xlsx',provenance)
        static=inspect(scratch/'analysis.xlsx')
        if static['status']!='passed':raise ValueError('文件结构验证失败: '+str(static['issues']))
        (scratch/'analysis.json').write_text(json.dumps(json_ready(model),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        (scratch/'anomalies.json').write_text(json.dumps(json_ready(model['issues']),ensure_ascii=False,indent=2),encoding='utf-8')
        # Archive the actual analysis basis, not just an unverifiable external version label.
        root=Path(__file__).resolve().parents[1]
        with zipfile.ZipFile(scratch/'qpcr-ddcq-basis.zip','w',zipfile.ZIP_DEFLATED) as z:
            for filename in evidence['files']:z.write(root/filename,filename)
        result={'analysis_status':'computed' if all(r['expression'] is not None for r in model['results']) and model['results'] else 'partial',
                'created_at':datetime.now(timezone.utc).isoformat(),'skill':evidence,'inputs':provenance,'params':config.get('params',{}),
                'value_maps':config.get('value_maps',{}),'assumptions':model['assumptions'],'artifacts':artifacts,
                'verification':{'independent_numeric':{'status':'computed','basis':'core.py per-well model; release tests use independent fixed expectations'},
                                'static':static,'engine_recalculation':{'status':'not_run'},'visual':{'status':'not_run'}},
                'tools':{'python':sys.version.split()[0]},'limitations':['曲线、效率和内参稳定性未从Cq表验证','重算/视觉未执行，当前不能宣称全部验收通过']}
        from importlib.metadata import version
        result['tools'].update({n:version(n) for n in ('openpyxl','XlsxWriter')})
        if config.get('experiment_skill_basis'):
            basis=Path(config['experiment_skill_basis']);basis=basis if basis.is_absolute() else base/basis
            payload=json.loads(basis.read_text(encoding='utf-8'))
            import base64
            if payload.get('skill')!='cell-qpcr' or not all(k in payload for k in ('version','source','files','sha256')):
                raise ValueError('experiment_skill_basis 不是实际 cell-qpcr 固定内容包')
            digest=hashlib.sha256(json.dumps({k:payload[k] for k in ('skill','version','source','files')},ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()
            if digest!=payload['sha256']:raise ValueError('实验技能依据整体哈希不匹配')
            for f in payload['files'].values():
                if hashlib.sha256(base64.b64decode(f['base64'],validate=True)).hexdigest()!=f['sha256']:raise ValueError('实验技能依据文件哈希不匹配')
            result['experiment_skill_basis']={'source':str(basis.resolve()),'sha256':sha(basis),'skill':payload.get('skill'),'version':payload.get('version')}
            shutil.copy2(basis,scratch/'experiment-skill-basis.json')
        report=['# qPCR 分析报告','','## 计算与参数',
                '- 分析状态：'+result['analysis_status'],
                '- 实际内参：'+json.dumps(model['reference'],ensure_ascii=False),
                '- 实际校准：'+json.dumps(model['calibrator'],ensure_ascii=False),
                '- QC：'+('全部复孔严格合格' if model['all_pass'] else '存在不合格、复孔不足或无有效 Cq'),
                '- 最大复孔差值：'+str(model['max_spread'])+'；位置：'+json.dumps(model['max_locations'],ensure_ascii=False),
                '', '## 结果与异常','全部逐样本结果见 analysis.json、计算过程与整理数据；全异常见 anomalies.json 与工作簿说明。',
                '', '## 验证','静态结构已核查；实际引擎重算和渲染未运行。详见 manifest.json 各层状态。']
        (scratch/'report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
        result['outputs']={p.name:sha(p) for p in scratch.iterdir() if p.is_file()}
        (scratch/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        scratch.rename(destination)
        return {'status':result['analysis_status'],'output_dir':str(destination),'results':len(model['results']),'issues':len(model['issues']),
                'verification':result['verification']}
    except BaseException:
        # Only the explicitly created task-specific temporary directory is removed.
        if scratch.exists() and scratch.parent==destination.parent and scratch.name.startswith('.qpcr-'):
            shutil.rmtree(scratch)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    try:
        path=Path(args.config).resolve();config=json.loads(path.read_text(encoding='utf-8-sig'))
        missing=[n for n in ('openpyxl','xlsxwriter') if importlib.util.find_spec(n) is None]
        if missing:raise ImportError('缺少依赖: '+', '.join(missing))
        if args.check:
            rows,inputs=read_inputs(config,path.parent)
            response={'status':'ready','rows':len(rows),'inputs':inputs,'note':'只读输入/工具预检，不等于分析或视觉验证通过'}
        else:response=execute(config,path.parent)
        print(json.dumps(response,ensure_ascii=False,allow_nan=False))
    except (ValueError,OSError,ImportError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'blocked','reason':str(exc)},ensure_ascii=False));sys.exit(1)
