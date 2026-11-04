"""Read-only multi-table plan validation; never creates sample identities."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
from calculate import calculate


def validate(plan):
    issues, calculations = [], {}
    def issue(scope, reason):
        issues.append({'scope':scope,'reason':reason})
    def table(name):
        result={}
        for row in plan.get(name, []):
            key=row.get('id')
            if not isinstance(key,str) or not key or key in result:
                issue(name+'/'+str(key),'缺失或重复 ID'); continue
            result[key]=row
        return result
    samples,templates,assays,recipes,blocks,runs=[table(n) for n in ('samples','templates','assays','recipes','blocks','runs')]
    if not samples:
        issue('samples','细胞实验须有关联真实样品；不能为 NTC 伪造生物样品')
    for sid,sample in samples.items():
        if not sample.get('cell_origin'):
            issue('samples/'+sid,'缺少细胞来源依据')
    for tid,t in templates.items():
        if t.get('sample') not in samples or t.get('material_type') not in ('cdna','nrt_control') or not t.get('source'):
            issue('templates/'+tid,'缺少真实样品、cDNA/-RT 类型或来源')
    for aid,a in assays.items():
        if not a.get('gene') or not a.get('source'):
            issue('assays/'+aid,'缺少基因或 assay 来源')
    def run_calc(key,name,values,params):
        from calculate import MANIFEST
        d=json.loads(MANIFEST.read_text(encoding='utf-8'))['calculations'][name]
        request={'calculation':name,'inputs':{k:{'value':x,'unit':d['inputs'][k]['unit'],'source':'confirmed_parameter'} for k,x in values.items()},
                 'params':dict(params,confirmed=plan.get('confirmed') is True)}
        answer=calculate(request)
        calculations[key]=answer
        if answer['status']!='computed':
            issue(key,answer['reason']); return None
        return {k:x['value'] for k,x in answer['outputs'].items()}
    parsed={}
    for rid,r in recipes.items():
        values={k:r.get(k) for k in ('total_volume','premix','template','f_volume','r_volume','rox','dilution')}
        answer=run_calc('recipe/'+rid,'qpcr_recipe',values,{'method_profile':r.get('method_profile'),'rox_basis':r.get('rox_basis')})
        if answer: parsed[rid]=answer
    factors=plan.get('factors',{})
    groups={}
    counts=Counter(); needed_mix2=Counter(); pairs=set(); target_rows={}
    for i,t in enumerate(plan.get('targets',[])):
        bid,aid,n=t.get('block'),t.get('assay'),t.get('wells')
        scope='targets/'+str(i+1)
        if (bid,aid) in pairs:
            issue(scope,'重复配液块-assay'); continue
        pairs.add((bid,aid)); target_rows[(bid,aid)]=t
        if bid not in blocks or aid not in assays:
            issue(scope,'配液块或 assay 不存在'); continue
        block=blocks[bid]; rid=block.get('recipe')
        if rid not in parsed:
            issue(scope,'组成组不可用'); continue
        r,a=recipes[rid],assays[aid]
        if a.get('f_volume')!=r['f_volume'] or a.get('r_volume')!=r['r_volume']:
            issue(scope,'引物体积与组成组不一致'); continue
        answer=run_calc('mix3/'+bid+'/'+aid,'mix3_assay',dict(wells=n,total_volume=r['total_volume'],f_volume=r['f_volume'],r_volume=r['r_volume'],**factors),{})
        if answer:
            counts[bid]+=n; needed_mix2[bid]+=answer['mix2_transfer']
    signature=set(); recipe_wells=Counter(); recipe_needed=Counter()
    for bid,b in blocks.items():
        scope='block/'+bid
        rid,kind,tid=b.get('recipe'),b.get('type'),b.get('template')
        if b.get('run') not in runs or rid not in parsed or kind not in ('RT','NTC','-RT'):
            issue(scope,'运行/组成组缺失或控制类型非法'); continue
        sig=(b['run'],kind,tid,rid)
        if sig in signature: issue(scope,'同板同模板/对照同组成重复块')
        signature.add(sig)
        if kind=='NTC':
            if tid is not None: issue(scope,'NTC 模板须为 null，槽内为水')
        elif tid not in templates:
            issue(scope,'缺少真实模板来源'); continue
        else:
            t=templates[tid]
            expected='cdna' if kind=='RT' else 'nrt_control'
            if t.get('material_type')!=expected: issue(scope,'RT 与 -RT 模板类型不匹配')
            if t.get('volume_basis')=='rna_equivalent':
                answer=run_calc('equivalent/'+bid,'rna_equivalent',{k:t.get(k) for k in ('rna_mass','rt_volume','dilution','target_mass')},{})
                if answer and abs(answer['template_volume']-recipes[rid]['template'])>1e-9:
                    issue(scope,'组成组模板槽与所需当量体积不符')
            elif not t.get('volume_source'):
                issue(scope,'缺少直接指定模板体积的实际依据')
        if counts[bid]<=0:
            issue(scope,'没有可用的实际计划孔数'); continue
        r=recipes[rid]
        answer=run_calc('mix2/'+bid,'mix2_block',dict(wells=counts[bid],base_volume=parsed[rid]['base_volume'],template_volume=r['template'],required=needed_mix2[bid],**factors),{})
        if answer:
            recipe_wells[rid]+=counts[bid]; recipe_needed[rid]+=answer['base_take']
    for rid,r in recipes.items():
        if recipe_wells[rid]<=0:
            issue('recipe/'+rid,'组成组没有有效下游块'); continue
        run_calc('mix1/'+rid,'mix1_recipe',dict(wells=recipe_wells[rid],premix=r['premix'],water=parsed[rid]['water_volume'],rox=r['rox'],required=recipe_needed[rid],**factors),{})
    seen=set(); actual=Counter()
    for i,w in enumerate(plan.get('wells',[])):
        run,well,bid,aid=w.get('run'),w.get('well'),w.get('block'),w.get('assay')
        scope='wells/'+str(i+1)
        if (run,well) in seen: issue(scope,'同运行孔位重复')
        seen.add((run,well))
        layout=runs.get(run,{}).get('layout')
        if layout!='96' or not isinstance(well,str) or not re.fullmatch(r'[A-H](?:[1-9]|1[0-2])',well):
            issue(scope,'初版仅支持明确的96孔布局和合法孔位')
        if (bid,aid) not in pairs or blocks.get(bid,{}).get('run')!=run:
            issue(scope,'孔位与配液块-assay/运行不匹配')
        if w.get('type')!=blocks.get(bid,{}).get('type'):
            issue(scope,'逐孔对照类型与配液块不符')
        actual[(bid,aid)]+=1
    for key,t in target_rows.items():
        if actual[key]!=t['wells']:
            issue('wells/'+str(key),'逐孔数与计划不符: %s != %s' % (actual[key],t['wells']))
    if not plan.get('targets') or not blocks or not recipes or not runs:
        issue('plan','缺少必要配液表/运行')
    return {'status':'valid' if not issues else 'invalid','issues':issues,
            'calculations':calculations,'well_map_kind':plan.get('well_map_kind','planned'),
            'limitations':['体积与身份校验不证明特异性、效率、移液可操作性或实际执行。']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True)
    args=parser.parse_args()
    try:
        result=validate(json.loads(Path(args.input).read_text(encoding='utf-8-sig')))
    except (ValueError,KeyError,TypeError) as exc:
        result={'status':'invalid','issues':[{'scope':'plan','reason':str(exc)}]}
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    sys.exit(0 if result['status']=='valid' else 1)
