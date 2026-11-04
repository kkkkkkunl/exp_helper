"""Skill-owned, standard-library scalar arithmetic. No project writes."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
MANIFEST = Path(__file__).resolve().parents[1] / 'experiment-skill.json'


class CalculationError(ValueError):
    pass


def calculate(request):
    definitions = json.loads(MANIFEST.read_text(encoding='utf-8'))['calculations']
    name = request.get('calculation')
    if name not in definitions:
        return {'status': 'invalid_inputs', 'reason': 'Unknown calculation'}
    definition = definitions[name]
    supplied, params, values = request.get('inputs', {}), request.get('params', {}), {}
    if name == 'quantity_sum':
        definition = dict(definition, inputs={k: {'unit': params.get('unit'), 'minimum': 0} for k in ('a', 'b')},
                          outputs={'quantity': {'unit': params.get('unit')}})
    try:
        if params.get('confirmed') is not True:
            raise CalculationError('本次方案参数尚未明确确认: params.confirmed must be true')
        for key, rule in definition['inputs'].items():
            item = supplied.get(key)
            if item is None:
                raise CalculationError('缺少输入: ' + key)
            value = item.get('value')
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value)):
                raise CalculationError('需要有限数值: ' + key)
            if item.get('source') not in ('user', 'confirmed_parameter', 'calculated'):
                raise CalculationError('输入缺少来源: ' + key)
            if item.get('unit') != rule['unit'] or value < rule.get('minimum', -math.inf):
                raise CalculationError('单位或范围无效: ' + key)
            values[key] = value
        v = values
        def pos(*keys):
            if any(v[k] <= 0 for k in keys):
                raise CalculationError('必须为正数: ' + ', '.join(keys))
        def water(total, parts):
            result = total - sum(parts)
            if result < -1e-9:
                raise CalculationError('体系超容: 补水为负')
            return max(0.0, result)
        def counts():
            pos('wells')
            if int(v['wells']) != v['wells']:
                raise CalculationError('技术孔数必须为正整数')
        def factors():
            if not v['k1'] >= v['k2'] >= v['k3'] >= 1:
                raise CalculationError('余量系数须满足 k1>=k2>=k3>=1')
        def supply(made, needed):
            if made + 1e-9 < needed:
                raise CalculationError('上游供液不足: made=%s needed=%s' % (made, needed))
            return max(0.0, made-needed)
        if name == 'treatment_duration':
            for key, numeric in [('start_time', v['start_epoch']), ('end_time', v['end_epoch'])]:
                from datetime import datetime
                dt = datetime.fromisoformat(params.get(key, '').replace('Z', '+00:00'))
                if dt.tzinfo is None or abs(dt.timestamp()-numeric) > 1e-6:
                    raise CalculationError('时间须含时区且与 epoch 输入一致: ' + key)
            if v['end_epoch'] < v['start_epoch']:
                raise CalculationError('收样时间早于开始时间')
            result = {'duration': (v['end_epoch']-v['start_epoch'])/3600}
        elif name == 'rt_reaction':
            pos('rna_mass', 'concentration', 'total_volume')
            rna = v['rna_mass']/v['concentration']
            result = {'rna_volume': rna, 'water_volume': water(v['total_volume'], [rna, v['gdna_mix'], v['rt_mix']])}
            if params.get('reaction_type') not in ('RT', '-RT'):
                raise CalculationError('明确 reaction_type: RT 或 -RT')
            if params['reaction_type'] == '-RT' and not params.get('nrt_source'):
                raise CalculationError('-RT 必须有真实 NRT 试剂/产物来源')
            if params.get('method_profile') != 'AG11728-v6-all-in-one':
                return {'status': 'needs_review', 'reason': '所选 RT 方法未提供已核对约束，候选值不能放行', 'candidate_outputs': result}
            errors = []
            if v['rna_mass']/v['total_volume'] > 50 + 1e-9:
                errors.append('RNA 输入超过所选方法的 1000 ng/20 uL 等比例上限')
            if abs(v['gdna_mix']/v['total_volume']-.1)>1e-9 or abs(v['rt_mix']/v['total_volume']-.2)>1e-9:
                errors.append('所选方法 gDNA/RT 比例须为 0.1/0.2；体积可容纳不等于方法通过')
            if errors:
                return {'status': 'needs_review', 'reason': '; '.join(errors), 'candidate_outputs': result}
        elif name == 'rna_equivalent':
            pos('rna_mass', 'rt_volume', 'dilution', 'target_mass')
            c = v['rna_mass']/v['rt_volume']/v['dilution']
            result = {'equivalent_concentration': c, 'template_volume': v['target_mass']/c,
                      'stock_equivalent': v['target_mass']/c/v['dilution']}
        elif name == 'primer_final':
            pos('f_working', 'r_working', 'total_volume', 'f_volume', 'r_volume')
            result = {'f_final': v['f_working']*v['f_volume']/v['total_volume'],
                      'r_final': v['r_working']*v['r_volume']/v['total_volume']}
        elif name == 'qpcr_recipe':
            pos('total_volume', 'premix', 'template', 'f_volume', 'r_volume', 'dilution')
            w = water(v['total_volume'], [v['premix'],v['template'],v['f_volume'],v['r_volume'],v['rox']])
            result = {'water_volume': w, 'base_volume': v['premix']+v['rox']+w,
                      'stock_equivalent': v['template']/v['dilution']}
            if params.get('method_profile') != 'AG11701-v4e1':
                return {'status': 'needs_review', 'reason': 'qPCR 方法约束尚未核对', 'candidate_outputs': result}
            if abs(v['premix']/v['total_volume']-.5)>1e-9 or result['stock_equivalent']>v['total_volume']*.1+1e-9:
                return {'status': 'needs_review', 'reason': '2x Premix 比例或原液等效 10% 约束不满足', 'candidate_outputs': result}
            if not params.get('rox_basis'):
                raise CalculationError('ROX 需求须有本次仪器核对依据，即使 ROX=0')
        elif name == 'quantity_sum':
            unit = params.get('unit')
            if unit not in ('uL', 'well'):
                raise CalculationError('quantity_sum params.unit 须为 uL 或 well')
            if unit == 'well' and any(int(x)!=x for x in v.values()):
                raise CalculationError('孔数汇总须为整数')
            result = {'quantity': v['a']+v['b']}
        elif name == 'mix3_assay':
            counts(); factors(); pos('total_volume','f_volume','r_volume')
            if v['f_volume']+v['r_volume']>=v['total_volume']:
                raise CalculationError('引物体积无效')
            n=v['wells']*v['k3']
            result={'mix2_transfer':(v['total_volume']-v['f_volume']-v['r_volume'])*n,
                    'f_volume_total':v['f_volume']*n,'r_volume_total':v['r_volume']*n,
                    'total':v['total_volume']*n}
        elif name == 'mix2_block':
            counts(); factors(); pos('base_volume','template_volume')
            base=v['base_volume']*v['wells']*v['k2']; template=v['template_volume']*v['wells']*v['k2']
            result={'base_take':base,'template_total':template,'total':base+template,
                    'required':v['required'],'remaining':supply(base+template,v['required'])}
        elif name == 'mix1_recipe':
            counts(); factors(); pos('premix')
            n=v['wells']*v['k1']
            total=(v['premix']+v['water']+v['rox'])*n
            result={'premix_total':v['premix']*n,'water_total':v['water']*n,'rox_total':v['rox']*n,
                    'total':total,'required':v['required'],'remaining':supply(total,v['required'])}
        outputs={k:{'value':value,'unit':definition['outputs'][k]['unit']} for k,value in result.items()}
        if name=='quantity_sum':
            outputs['quantity']['unit']=params['unit']
        if not all(math.isfinite(item['value']) for item in outputs.values()):
            raise CalculationError('输出超出有限数值范围')
        return {'status':'computed','outputs':outputs,'basis':definition['basis']}
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        return {'status':'invalid_inputs','reason':str(exc)}


if __name__ == '__main__':
    try:
        answer=calculate(json.load(sys.stdin))
    except (ValueError, TypeError) as exc:
        answer={'status':'invalid_inputs','reason':str(exc)}
    print(json.dumps(answer,ensure_ascii=False,allow_nan=False))
