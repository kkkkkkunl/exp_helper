"""Raw Cq normalization and independent analysis model. Standard library only."""
from __future__ import annotations
from collections import defaultdict, Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import statistics

CONTROL_LABELS={'d0','0h','control','con','nc','vehicle'}
ERRORS={'#REF!','#DIV/0!','#VALUE!','#NAME?','#N/A','#NUM!','#NULL!','#SPILL!','#CALC!'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decimal(value):
    if value is None or isinstance(value,bool) or str(value).strip()=='': return None
    try:
        n=Decimal(str(value).strip())
        return n if n.is_finite() else None
    except InvalidOperation: return None


def exclude(value):
    if value is None or str(value).strip().lower() in ('','false','no','0','否','not excluded'): return False
    if value is True or str(value).strip().lower() in ('true','yes','1','excluded','是'): return True
    return None


def analyze(records, params):
    rows=[dict(r) for r in records]
    biological=params.get('biological_replicates',False)
    if not isinstance(biological,bool): raise ValueError('biological_replicates 必须为明确布尔值')
    if params.get('error_bar','SD') not in ('SD','SEM'): raise ValueError('error_bar 须为 SD 或 SEM')
    issues=[]; seen={}; groups=defaultdict(list); order=[]; scopes=[]
    manual=params.get('exclude_rows',{})
    if not isinstance(manual,dict) or any(not reason for reason in manual.values()): raise ValueError('人工排除须逐行提供理由')
    for i,r in enumerate(rows):
        r['index']=i; r.setdefault('scope','default'); r.setdefault('kind','sample')
        r.setdefault('sample',''); r.setdefault('bio_id',''); r.setdefault('run',''); r.setdefault('well','')
        r.setdefault('assay',r.get('gene','')); r.setdefault('excluded_raw',''); r.setdefault('cq_raw','')
        r['row_id']=r.get('row_id','row-'+str(i+1)); r['reason']=''
        r['value']=decimal(r['cq_raw']); flag=exclude(r['excluded_raw'])
        r['manual_reason']=manual.get(r['row_id'],'')
        r['included']=flag is False and r['value'] is not None and not r['manual_reason']
        if flag is True:r['reason']='仪器 Excluded'
        elif flag is None:r['reason']='Excluded 状态不明确'; r['included']=False
        elif r['value'] is None:r['reason']='未检出/缺失/非数值 Cq'
        if r['manual_reason']:r['reason']='人工排除: '+r['manual_reason']
        if any(not str(r.get(k,'')).strip() for k in ('scope','group','gene','assay')):
            r['included']=False; r['reason']='缺少 scope/group/gene/assay 映射'
        if biological and (not r['sample'] or not r['bio_id']) and r['kind']=='sample':
            r['included']=False;r['reason']='缺少明确生物学样本或独立重复 ID'
        if r['kind'] not in ('sample','NTC','-RT'):
            r['included']=False;r['reason']='检测类型未知'
        r['unit_sample']=r['bio_id'] if biological and r['kind']=='sample' else r.get('group','')
        r['key']=(r['scope'],r.get('group',''),r['unit_sample'],r['assay'],r['kind'])
        if r['scope'] not in scopes:scopes.append(r['scope'])
        pair=(r['scope'],r.get('group',''))
        if pair not in order:order.append(pair)
        if r['run'] and r['well']:
            physical=(r['run'],r['well'])
            if physical in seen:
                old=rows[seen[physical]]
                fields=('scope','group','sample','bio_id','assay','gene','kind','cq_raw','excluded_raw')
                if all(str(old.get(k,''))==str(r.get(k,'')) for k in fields):
                    r['included']=False;r['reason']='重复导出，同一物理孔仅计一次'
                else:
                    r['included']=False;r['reason']='同一物理孔导出冲突'
                    old['included']=False;old['reason']=r['reason'];old['conflict']=True;r['conflict']=True
            else:seen[physical]=i
        groups[r['key']].append(i)
    # One assay ID cannot silently identify different genes within one scope.
    assay_genes=defaultdict(set)
    for r in rows:
        if r['kind']=='sample':assay_genes[(r['scope'],r['assay'])].add(r['gene'])
    for r in rows:
        if len(assay_genes[(r['scope'],r['assay'])])>1:
            r['mapping_error']=True;r['included']=False;r['reason']='同一 assay 对应不同基因，映射不明确'
    # Expected assay/sample combinations are explicit missing groups, never synthetic wells.
    catalog=defaultdict(dict)
    for r in rows:
        if r['kind']=='sample':catalog[r['scope']][r['assay']]='身份待明确' if r.get('mapping_error') else r['gene']
    for scope in scopes:
        for assay in params.get('targets',[]):
            if assay not in catalog[scope]:
                gene=params.get('assay_genes',{}).get(assay)
                if not gene:raise ValueError('目标 assay 完全缺失且没有 assay_genes 名称映射: '+assay)
                catalog[scope][assay]=gene
    units=list(dict.fromkeys((r['scope'],r.get('group',''),r['unit_sample']) for r in rows if r['kind']=='sample'))
    for scope,group,sample in units:
        for assay in catalog[scope]:groups.setdefault((scope,group,sample,assay,'sample'),[])
    qc=[]; keymap={}
    for key,indexes in groups.items():
        rs=[rows[i] for i in indexes]; active=[r for r in rs if r['included']]
        blocking=[]
        if any(r.get('conflict') or '不明确' in r['reason'] or '缺少' in r['reason'] for r in rs):
            blocking.append('原始行身份或状态未明确')
        runs={r['run'] for r in active}
        if len(runs)>1 and not params.get('merge_runs',{}).get(key[0]):blocking.append('跨运行合并关系未明确')
        sample_ids={r['sample'] for r in active if r['sample']}
        if biological and len(sample_ids)>1:blocking.append('同一生物学 ID 对应多个样本，需明确映射')
        values=[r['value'] for r in active]
        n=len(values); avg=float(sum(values)/n) if n else None
        spread=max(values)-min(values) if n>=2 else None
        state='无有效 Cq' if n==0 else '复孔不足' if n==1 else '严格合格' if spread<Decimal('.5') else '未达到严格标准' if spread<1 else '严重不合格'
        q={'key':key,'indexes':indexes,'active_indexes':[r['index'] for r in active], 'n':n,'mean':avg,
           'spread':float(spread) if spread is not None else None,'state':state,'blocking':blocking,
           'precision':min(14,max([max(0,-r['value'].as_tuple().exponent) for r in active]+[0])),
           'gene':catalog[key[0]].get(key[3],rs[0]['gene'] if rs else key[3]),'expected_missing':not indexes}
        keymap[key]=len(qc);qc.append(q)
        if state!='严格合格' or blocking:issues.append({'type':'replicate','scope':key[0],'group':key[1],'sample':key[2],'assay':key[3],'state':state,'blocking':blocking,
                                                       'wells':[rows[i].get('well') for i in indexes], 'cq':[rows[i]['cq_raw'] for i in indexes],'spread':q['spread']})
    refs={};calibrators={};assumptions=[]
    results=[];assay_order=defaultdict(list)
    def scoped(name,scope):
        setting=params.get(name,{})
        return setting.get(scope) if isinstance(setting,dict) else setting
    for scope in scopes:
        sample_q=[q for q in qc if q['key'][0]==scope and q['key'][4]=='sample']
        assays=list(dict.fromkeys(q['key'][3] for q in sample_q))
        gene_for={a:catalog[scope][a] for a in assays}
        explicit=scoped('reference',scope)
        if explicit:ref=explicit if explicit in assays else None
        else:
            gap=[a for a in assays if gene_for[a].casefold()=='gapdh']
            act=[a for a in assays if gene_for[a].casefold() in ('actin','actb','beta-actin','β-actin')]
            candidates=gap if gap else act
            ref=candidates[0] if len(candidates)==1 else None
        refs[scope]=ref
        group_order=[g for s,g in order if s==scope and any(q['key'][1]==g for q in sample_q)]
        control=scoped('calibrator',scope)
        if not control:
            candidates=[g for g in group_order if str(g).casefold().replace(' ','') in CONTROL_LABELS]
            if len(candidates)==1:control=candidates[0]
            elif not candidates and group_order:
                control=group_order[0];assumptions.append({'scope':scope,'assumption':'无明确对照，采用输入首组','group':control})
        if control not in group_order: control=None
        calibrators[scope]=control
        # Group-first export order; assays remain first-seen order within each group.
        for group in group_order:
            for q in sample_q:
                if q['key'][1]!=group or q['key'][3]==ref:continue
                if params.get('targets') and q['key'][3] not in params['targets']:continue
                assay=q['key'][3]
                if assay not in assay_order[scope]:assay_order[scope].append(assay)
                rq=keymap.get((scope,group,q['key'][2],ref,'sample'))
                refq=qc[rq] if rq is not None else None
                target_index=keymap[q['key']]
                status='可计算';delta=None
                if ref is None:status='内参 assay 缺失或不唯一，无法计算'
                elif refq is None or refq['mean'] is None:status='缺少匹配内参，无法计算'
                elif q['mean'] is None:status='无有效目标 Cq，无法计算'
                elif q['blocking'] or refq['blocking']:status='样本/运行/状态映射未明确，无法计算'
                else:delta=q['mean']-refq['mean']
                result={'scope':scope,'group':group,'sample':q['key'][2],'assay':assay,'gene':gene_for[assay],
                        'target_qc':target_index,'reference_qc':rq,'reference':ref,'delta':delta,
                        'calibrator':control,'calibration_rows':[],'baseline':None,'dd':None,'expression':None,'status':status,'qc':[]}
                results.append(result)
    for ri,r in enumerate(results):
        r['index']=ri
        matches=[j for j,x in enumerate(results) if x['scope']==r['scope'] and x['assay']==r['assay'] and x['group']==r['calibrator'] and x['delta'] is not None]
        r['calibration_rows']=matches
        if matches:r['baseline']=statistics.mean(results[j]['delta'] for j in matches)
        if r['delta'] is not None:
            if not r['calibrator']:r['status']='校准关系不明确，无法计算'
            elif not matches:r['status']='缺少可计算校准样本，无法计算'
            else:
                r['dd']=r['delta']-r['baseline']
                try:r['expression']=2**(-r['dd'])
                except OverflowError:r['status']='表达量超出数值范围'
                if r['expression'] is not None and not math.isfinite(r['expression']):r['expression']=None;r['status']='表达量超出数值范围'
        for label,qi in [('目标',r['target_qc']),('内参',r['reference_qc'])]:
            if qi is not None and qc[qi]['state']!='严格合格':r['qc'].append(label+':'+qc[qi]['state'])
        for j in matches:
            for label,qi in [('校准目标',results[j]['target_qc']),('校准内参',results[j]['reference_qc'])]:
                if qi is not None and qc[qi]['state']!='严格合格':r['qc'].append(label+':'+qc[qi]['state'])
        r['qc']=list(dict.fromkeys(r['qc']))
        if r['status']!='可计算' or r['qc']:issues.append({'type':'result','scope':r['scope'],'group':r['group'],'sample':r['sample'],'assay':r['assay'],'state':r['status'],'qc':r['qc']})
    # Keep one target-assay sequence per scope in every group, then sample order.
    results.sort(key=lambda r:(scopes.index(r['scope']),[g for s,g in order if s==r['scope']].index(r['group']),assay_order[r['scope']].index(r['assay']),r['index']))
    # Calibration references were positional before ordering; remap once.
    remap={r['index']:i for i,r in enumerate(results)}
    for i,r in enumerate(results):r['calibration_rows']=[remap[j] for j in r['calibration_rows']];r['index']=i
    summaries=[]
    for scope in scopes:
        for assay in assay_order[scope]:
            for s,group in order:
                if s!=scope:continue
                ids=[i for i,r in enumerate(results) if r['scope']==scope and r['group']==group and r['assay']==assay]
                if not ids:continue
                values=[results[i]['expression'] for i in ids if results[i]['expression'] is not None]
                mean=statistics.mean(values) if values else None
                sd=statistics.stdev(values) if biological and len(values)>=2 else None
                error=sd if params.get('error_bar','SD')=='SD' or sd is None else sd/math.sqrt(len(values))
                summaries.append({'scope':scope,'assay':assay,'group':group,'gene':results[ids[0]]['gene'],'rows':ids,'n':len(values),'mean':mean,'error':error,
                                  'qc':list(dict.fromkeys(x for i in ids for x in results[i]['qc']))})
    for r in rows:
        if r['reason']:issues.append({'type':'raw','row_id':r['row_id'],'run':r['run'],'well':r['well'],'cq':r['cq_raw'],'reason':r['reason']})
    sample_q=[q for q in qc if q['key'][4]=='sample']
    all_pass=bool(sample_q) and all(q['state']=='严格合格' and not q['blocking'] for q in sample_q)
    max_spread=max([q['spread'] for q in sample_q if q['spread'] is not None],default=None)
    return {'rows':rows,'qc':qc,'results':results,'summaries':summaries,'issues':issues,'params':params,'reference':refs,'calibrator':calibrators,
            'assumptions':assumptions,'all_pass':all_pass,'max_spread':max_spread,
            'max_locations':[list(q['key']) for q in sample_q if max_spread is not None and q['spread']==max_spread]}


def json_ready(value):
    if isinstance(value,Decimal):return str(value)
    if isinstance(value,dict):return {str(k):json_ready(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [json_ready(v) for v in value]
    return value
