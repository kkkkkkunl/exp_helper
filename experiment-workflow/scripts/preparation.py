"""Read formula definitions and calculate planned preparation quantities."""
import argparse
import ast
import json
import math
import operator
import re
import sys
from pathlib import Path

import _common as C


MARKER = 'json experiment-reagents'
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
SIGNS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
VOLUMES = {'96': 100, '48': 200, '24': 500, '12': 500, '6': 1000, 'T25': 1000}


def text(value):
    return isinstance(value, str) and bool(value.strip())


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def syntax(formula, names):
    if not text(formula) or len(formula) > 256:
        raise C.SkillError('缺少有效配制公式')
    try:
        node = ast.parse(formula.strip(), mode='eval').body
    except SyntaxError as exc:
        raise C.SkillError('配制公式语法无效') from exc
    for part in ast.walk(node):
        if isinstance(part, ast.Name):
            if part.id not in names:
                raise C.SkillError(f'未声明公式变量 {part.id}')
        elif isinstance(part, ast.Constant):
            if not finite(part.value):
                raise C.SkillError('公式常量须为有限数值')
        elif type(part) not in (ast.Load, ast.BinOp, ast.UnaryOp, *OPS, *SIGNS):
            raise C.SkillError('公式只支持变量、数字、括号和加减乘除')
    return node


def evaluate(node, values):
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.UnaryOp):
        return SIGNS[type(node.op)](evaluate(node.operand, values))
    return OPS[type(node.op)](evaluate(node.left, values), evaluate(node.right, values))


def unique_mapping(pairs):
    values = dict(pairs)
    if len(values) != len(pairs):
        raise C.SkillError('试剂清单或公式中有重复字段')
    return values


def catalog(content, required=False):
    blocks = C.marked_blocks(content, MARKER)
    if not blocks and not required:
        return {}
    if len(blocks) != 1:
        raise C.SkillError('须提供唯一试剂清单；无试剂时使用空列表')
    try:
        entries = json.loads(blocks[0], object_pairs_hook=unique_mapping)
    except ValueError as exc:
        raise C.SkillError('试剂清单须为有效 JSON') from exc
    if not isinstance(entries, list):
        raise C.SkillError('试剂清单须为列表')
    result = {}
    for entry in entries:
        if not isinstance(entry, dict) or not text(entry.get('name')):
            raise C.SkillError('试剂条目须提供名称')
        key = C.safe_id(entry.get('id', ''))
        if key in result:
            raise C.SkillError(f'试剂编号重复：{key}')
        try:
            kind = entry.get('kind')
            if kind == 'prepare':
                validate_formula(entry)
            elif kind != 'ready_to_use':
                raise C.SkillError('须明确配制型或即用型')
            elif {'inputs', 'outputs', 'formula'} & entry.keys():
                raise C.SkillError('即用型只登记必要用量')
        except C.SkillError as exc:
            raise C.SkillError(f'{entry["name"]}：{exc}') from exc
        result[key] = entry
    return result


def validate_formula(entry):
    inputs, outputs = entry.get('inputs'), entry.get('outputs')
    if not text(entry.get('source')):
        raise C.SkillError('缺少配制公式来源')
    if not isinstance(inputs, dict) or not isinstance(outputs, dict) or not outputs:
        raise C.SkillError('配制公式须声明输入及至少一个输出')
    for name, unit in inputs.items():
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) or not text(unit):
            raise C.SkillError(f'{name}：输入须声明有效名称与单位')
    names = set(inputs)
    for name, spec in outputs.items():
        if name in names or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
            raise C.SkillError(f'{name}：变量重复或未声明有效名称与单位')
        if not isinstance(spec, dict) or not text(spec.get('unit')):
            raise C.SkillError(f'{name}：输出须声明单位')
        syntax(spec.get('formula'), names)
        names.add(name)


def issue(status, reason, **details):
    return {'status': status, 'reason': reason, **details}


def read_inputs(supplied, units):
    if not isinstance(supplied, dict):
        raise C.SkillError('计算 inputs 须为映射')
    missing = [name for name in units if supplied.get(name) is None]
    if missing:
        return {}, issue('missing_inputs', '当前计算必要输入待补', missing=missing)
    values = {}
    for name, expected in units.items():
        item = supplied[name]
        allowed = expected if isinstance(expected, tuple) else (expected,)
        if (not isinstance(item, dict) or item.get('source') not in ('user', 'confirmed_parameter', 'calculated')
                or not finite(item.get('value')) or item.get('unit') not in allowed):
            return {}, issue('invalid_inputs', f'{name} 须提供有来源的有限数值及相容单位')
        values[name] = float(item['value'])
    return values, None


def quantity(value, unit):
    return {'value': value, 'unit': unit}


def seeding(request):
    params = request.get('params', {})
    if not isinstance(params, dict):
        raise C.SkillError('计算 params 须为映射')
    sizes, container = params.get('group_sizes'), str(params.get('container', '')).upper()
    if (not isinstance(sizes, dict) or not sizes
            or any(not text(key) or type(size) is not int or not finite(size) or size <= 0 for key, size in sizes.items())):
        return issue('invalid_inputs', '同一份混合液须提供每组的正整数计划铺板数')
    if container not in VOLUMES:
        return issue('invalid_inputs', '容器须为 96、48、24、12、6 或 T25')
    supplied = request.get('inputs', {})
    units = {'cells_per_unit': 'cells/unit', 'suspension_concentration': ('cells/mL', 'cells/uL')}
    if isinstance(supplied, dict) and 'final_volume_per_unit' in supplied:
        units['final_volume_per_unit'] = ('uL/unit', 'mL/unit')
    values, problem = read_inputs(supplied, units)
    if problem:
        return problem
    target, density = values['cells_per_unit'], values['suspension_concentration']
    per_unit = values.get('final_volume_per_unit', VOLUMES[container])
    if supplied['suspension_concentration']['unit'] == 'cells/mL':
        density /= 1000
    if supplied.get('final_volume_per_unit', {}).get('unit') == 'mL/unit':
        per_unit *= 1000
    planned = sum(sizes.values())
    if min(target, density, per_unit) <= 0 or not all(map(finite, (planned, per_unit))):
        return issue('invalid_inputs', '目标细胞数、悬液浓度与终体积须为正数且处于可表示范围')
    equivalent = planned + 0.5
    cells = equivalent * target
    suspension = cells / density
    total = equivalent * per_unit
    medium = total - suspension
    if not all(map(finite, (cells, suspension, medium))) or (medium < 0 and not math.isclose(total, suspension, rel_tol=1e-12)):
        return issue('invalid_result', '悬液超过目标总体积或计算超出可表示范围')
    return {'status': 'computed', 'basis': '铺板配制 v1，按份增加 0.5 当量，先算悬液再算培养基',
            'outputs': {'planned_units': quantity(planned, 'unit'),
                        'preparation_units': quantity(equivalent, 'unit'),
                        'required_cells': quantity(cells, 'cells'),
                        'suspension_volume': quantity(suspension, 'uL'),
                        'medium_volume': quantity(max(0, medium), 'uL'),
                        'final_volume_per_unit': quantity(per_unit, 'uL/unit'),
                        'final_volume': quantity(total, 'uL')}}


def recipe(request, template):
    if not template:
        return issue('missing_evidence', '请先选定含配制公式的方法')
    try:
        formula = catalog(template['content']).get(request.get('calculation'))
    except C.SkillError as exc:
        return issue('invalid_formula', str(exc))
    if not formula or formula['kind'] != 'prepare':
        return issue('missing_evidence', '所选方法版本无对应配制公式')
    evidence = {'template_name': template['name'], 'template_version': template['version'],
                'template_hash': template['sha256'], 'formula_definition': formula}
    values, problem = read_inputs(request.get('inputs', {}), formula['inputs'])
    if problem:
        return {**evidence, **problem}
    results = {}
    for name, rule in formula['outputs'].items():
        try:
            amount = evaluate(syntax(rule['formula'], values), values)
        except ArithmeticError:
            amount = None
        if not finite(amount) or amount < 0:
            return {**evidence, **issue('invalid_result', f'{name} 的结果非有限或小于零')}
        values[name] = amount
        results[name] = quantity(amount, rule['unit'])
    return {**evidence, 'status': 'computed', 'outputs': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--project')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--template')
    selection.add_argument('--experiment')
    parser.add_argument('--template-version')
    args = parser.parse_args()
    try:
        payload = sys.stdin.buffer.read().decode('utf-8-sig') if args.input == '-' else Path(args.input).read_text(encoding='utf-8-sig')
        request = json.loads(payload)
        rule_type = request.get('rule_type', 'cell_seeding')
        if rule_type == 'cell_seeding':
            answer = seeding(request)
        elif rule_type == 'reagent_formula':
            import stage_templates as T
            import workflow as W
            project = C.Project(C.find_project_root(args.project))
            if args.experiment:
                snapshot = W.peek_state(project, C.safe_id(args.experiment)).get('template_snapshot')
                template = T.frozen(project, snapshot) if snapshot else None
            else:
                template = T.select(project, args.template, args.template_version)
            answer = recipe(request, template)
        else:
            raise C.SkillError('未知配制计算类型')
        C.ok(result=answer)
    except (C.SkillError, OSError, ValueError, AttributeError) as exc:
        C.die(str(exc), code='preparation_error')


if __name__ == '__main__':
    main()
