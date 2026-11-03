"""Host calendar action protocol. This module never calls a remote service itself."""
from __future__ import annotations
import argparse
import copy
import json
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path
import _common as C
import workflow as W

CAPABILITIES = {'create', 'read', 'find', 'update'}


def validate_config(cfg):
    if not isinstance(cfg, dict): return ['calendar 须为映射']
    errors = []
    if set(cfg) - {'provider', 'calendar_id', 'capabilities', 'timezone', 'status'}:
        errors.append('日历配置仅保存服务和能力，不接受凭据或未知字段')
    if cfg.get('status') == 'ready' and (not isinstance(cfg.get('provider'), str) or not cfg.get('provider') or
                                        not isinstance(cfg.get('calendar_id'), str) or not cfg.get('calendar_id') or
                                        not CAPABILITIES.issubset(set(cfg.get('capabilities') or []))):
        errors.append('日历连接缺少目标或 create/read/find/update 能力')
    try: tz(cfg.get('timezone', 'Asia/Shanghai'))
    except C.SkillError as exc: errors.append(str(exc))
    return errors


def tz(name):
    if name == 'Asia/Shanghai': return timezone(timedelta(hours=8))
    if name in ('UTC', 'Etc/UTC'): return timezone.utc
    try: return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise C.SkillError(f'时区不可用：{name}；请由宿主配置有效 IANA 时区') from exc


def binding(p):
    path = p.state / 'calendar.json'
    cfg = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else p.cfg.get('calendar') or {}
    cfg = dict(cfg)
    cfg.setdefault('timezone', p.cfg.get('timezone', 'Asia/Shanghai'))
    problems = validate_config(cfg)
    if problems: raise C.SkillError('；'.join(problems))
    return cfg


def onboarding(p):
    cfg = binding(p)
    return {'status': cfg.get('status', 'needs_setup'),
            'next_action': None if cfg.get('status') == 'ready' else 'choose_calendar_and_connect',
            'required_capabilities': sorted(CAPABILITIES),
            'guidance': '首次安装由宿主询问服务及目标，复用或安装对应插件/MCP，并完成用户登录；不得把未连接报告为成功'}


def configure(p, provider, calendar_id, capabilities, time_zone='Asia/Shanghai'):
    cfg = {'provider': provider, 'calendar_id': calendar_id, 'capabilities': list(capabilities),
           'timezone': time_zone, 'status': 'ready'}
    problems = validate_config(cfg)
    if problems: raise C.SkillError('；'.join(problems))
    C.atomic_write_text(p.state / 'calendar.json', C.json_text(cfg))
    return onboarding(p)


def schedule_value(schedule, time_zone):
    schedule = schedule or {}
    missing = [key for key in ('date', 'time', 'minutes') if schedule.get(key) is None or schedule.get(key) == '']
    if missing: return None, missing
    minutes = schedule['minutes']
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not math.isfinite(minutes) or minutes <= 0:
        raise C.SkillError('预计时长必须为正的有限分钟数')
    try:
        start = datetime.fromisoformat(f'{schedule["date"]}T{schedule["time"]}')
        if start.tzinfo is not None: raise ValueError('请使用本地日期时间并提供项目时区')
        start = start.replace(tzinfo=tz(time_zone))
    except (ValueError, TypeError) as exc: raise C.SkillError(f'排期日期或时间不合法：{exc}') from exc
    return {'start': start.isoformat(), 'end': (start + timedelta(minutes=minutes)).isoformat(),
            'timezone': time_zone}, []


def marker(followup_id): return 'experiment-workflow:' + followup_id


def event_body(eid, item):
    rows = [marker(item['id']), f'实验：{eid}', f'阶段：{item["stage"]}',
            '样品：' + '、'.join(item['samples']), '记录：' + item['record'], '后续内容：']
    rows.extend('- ' + text for text in item.get('remaining', []))
    rows.extend('- 待补：' + text for text in item.get('missing', []))
    return '\n'.join(rows)


def enqueue(state, eid, stage_id, title, samples, remaining, missing=()):
    # Stable stage identity; sample membership changes update the existing item.
    fid = C.sha256_text(f'{eid}:{stage_id}')[:24]
    old = state['followups'].get(fid, {})
    item = {**old, 'id': fid, 'stage': stage_id, 'title': title, 'samples': sorted(set(samples)),
            'remaining': list(remaining), 'missing': list(missing),
            'record': f'实验/{eid}/{C.RECORD_NAME}', 'completed': not remaining and not missing}
    revision = C.sha256_text(C.json_text({k: item[k] for k in ('samples', 'remaining', 'missing', 'completed')}))
    if revision != old.get('revision'):
        item.update(revision=revision, sync_status='pending', read_revision=None)
    state['followups'][fid] = item
    return item


def prepare(p, eid, fid, schedule=None):
    state = W.read_state(p, eid)
    item = state['followups'].get(fid)
    if not item: raise C.SkillError('未知日历待办')
    cfg = binding(p)
    if cfg.get('status') != 'ready':
        return {**onboarding(p), 'followup': item}
    bound = item.get('binding')
    current_binding = [cfg['provider'], cfg['calendar_id']]
    if bound and bound != current_binding:
        return {'status': 'needs_review', 'reason': '待办属于另一日历，须明确迁移后再同步'}
    if schedule:
        item['schedule'] = {**item.get('schedule', {}), **schedule}
    if item.get('inflight'):
        # Never dispatch an uncertain create twice: host must submit its receipt first.
        return {'status': 'awaiting_receipt', 'request': item['inflight']}
    if item.get('remote_id'):
        if item.get('sync_status') == 'synced': return {'status': 'synced', 'remote_id': item['remote_id']}
        if item.get('sync_status') == 'missing_remote': return {'status': 'needs_review', 'reason': '远端事项已删除，未自动重建'}
        op = 'update' if item.get('read_revision') == item['revision'] else 'read'
    else:
        if item.get('sync_status') == 'uncertain' or not item.get('lookup_complete'):
            op = 'find'
        else:
            op = 'create'
    times, missing = schedule_value(item.get('schedule'), cfg.get('timezone', 'Asia/Shanghai'))
    if not item.get('remote_id') and missing:
        item['sync_status'] = 'needs_schedule'
        W.save_state(p, eid, state, invalidate_archive=False)
        return {'status': 'needs_schedule', 'missing': missing, 'followup': fid}
    payload = {'marker': marker(fid)}
    if op in ('read', 'update'): payload['id'] = item['remote_id']
    if op in ('create', 'update'):
        subject = item.get('remote', {}).get('subject') or f'{eid} {item["title"]}'
        if item['completed'] and not subject.startswith('[已完成]'): subject = '[已完成] ' + subject
        if not item['completed'] and subject.startswith('[已完成] '): subject = subject[len('[已完成] '):]
        payload.update(subject=subject, body=event_body(eid, item))
        if op == 'create': payload.update(times)
        # Updating a description deliberately omits start/end, preserving manual scheduling.
    request = {'id': C.sha256_text(C.json_text([fid, item['revision'], op, payload])), 'operation': op, 'revision': item['revision'],
               'provider': cfg['provider'], 'calendar_id': cfg['calendar_id'], 'payload': payload}
    item.update(inflight=request, binding=current_binding, sync_status='inflight')
    W.save_state(p, eid, state, invalidate_archive=False)
    return {'status': 'dispatch', 'request': request}


def receipt(p, eid, fid, response):
    state = W.read_state(p, eid); item = state['followups'].get(fid)
    if not item: raise C.SkillError('未知待办')
    req = item.get('inflight')
    if not req:
        if response.get('request_id') == item.get('last_receipt'): return {'status': item['sync_status'], 'noop': True}
        raise C.SkillError('没有匹配的远端动作')
    if response.get('request_id') != req['id'] or not response.get('tool_call_id'):
        raise C.SkillError('收据须引用原请求及实际宿主工具调用')
    op = req['operation']
    if response.get('ok') is not True:
        item['sync_status'] = 'uncertain' if op == 'create' else 'pending'
        item['error'] = response.get('error') or '远端操作失败'
        if op == 'create': item['lookup_complete'] = False
    elif op == 'find':
        matches = response.get('matches')
        if not isinstance(matches, list) or response.get('lookup_complete') is not True:
            raise C.SkillError('查找收据须明确完整查询结果；不确定时不得重复创建')
        if len(matches) > 1: raise C.SkillError('远端匹配多条事项，须用户核对')
        if matches:
            event = matches[0]
            if not event.get('id') or marker(fid) not in event.get('body', ''):
                raise C.SkillError('远端匹配缺少稳定标识')
            item.update(remote_id=event['id'], remote=event)
        item.update(lookup_complete=True, sync_status='pending')
    elif op == 'read':
        event = response.get('event')
        if event is None and response.get('not_found') is True:
            item['sync_status'] = 'missing_remote'
        elif not isinstance(event, dict) or event.get('id') != item.get('remote_id'):
            raise C.SkillError('读取返回了错误事项')
        else: item.update(remote=event, read_revision=item['revision'], sync_status='pending')
    else:
        event = response.get('event') or {}
        if not event.get('id') or (op == 'update' and event['id'] != item.get('remote_id')):
            raise C.SkillError('写入收据缺少正确远端事项 ID')
        if marker(fid) not in event.get('body', ''): raise C.SkillError('写入回核缺少待办标识')
        if event.get('body') != req['payload']['body']: raise C.SkillError('远端正文未反映本次更新')
        if event.get('subject') != req['payload']['subject']: raise C.SkillError('远端标题未反映本次完成标识或更新')
        item.update(remote_id=event['id'], remote=event,
                    sync_status='synced' if req['revision'] == item['revision'] else 'pending', error=None)
    item.update(inflight=None, last_receipt=req['id'])
    item.setdefault('receipts', []).append({'request_id': req['id'], 'tool_call_id': response['tool_call_id'],
                                           'ok': response.get('ok'), 'at': C.ts_now()})
    W.save_state(p, eid, state, invalidate_archive=False)
    return {'status': item['sync_status'], 'remote_id': item.get('remote_id')}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--project', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('onboarding')
    conf = sub.add_parser('configure'); conf.add_argument('--file', required=True)
    for cmd in ('prepare', 'receipt'):
        arg = sub.add_parser(cmd); arg.add_argument('--experiment', required=True)
        arg.add_argument('--followup', required=True); arg.add_argument('--file', required=cmd == 'receipt')
    args = parser.parse_args()
    try:
        p = C.Project(args.project)
        with C.FileLock(p.state / 'workflow.lock'):
            W.recover_actions(p)
            data = json.loads(Path(args.file).read_text(encoding='utf-8')) if getattr(args, 'file', None) else None
            if args.command == 'onboarding': result = onboarding(p)
            elif args.command == 'configure': result = configure(p, **data)
            elif args.command == 'prepare': result = prepare(p, args.experiment, args.followup, data)
            else: result = receipt(p, args.experiment, args.followup, data)
            C.ok(result=result)
    except (C.SkillError, ValueError, OSError, KeyError, TypeError) as exc: C.die(str(exc), code='calendar_error')


if __name__ == '__main__': main()
