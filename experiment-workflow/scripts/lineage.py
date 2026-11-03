"""Rebuildable sample-to-experiment dependency lookup; does not rewrite scientific history."""
import json
import _common as C


def descendants(p, sample_ids):
    samples = {f['id']: f for _, f, _ in C.iter_samples(p)}
    affected = set(sample_ids)
    while True:
        more = {sid for sid, f in samples.items() if
                set(((f.get('produced_by') or {}).get('inputs') or []) + (f.get('sources') or []) +
                    ([f['parent']] if f.get('parent') else [])) & affected}
        if more.issubset(affected): break
        affected |= more
    return affected


def affected_work(p, sample_ids):
    samples = {f['id']: f for _, f, _ in C.iter_samples(p)}
    affected = descendants(p, sample_ids)
    rows = []
    for path in p.experiments.glob('*/.experiment-workflow/workflow.json'):
        state = json.loads(path.read_text(encoding='utf-8'))
        used = {sid for sid in affected if state['experiment'] in samples.get(sid, {}).get('experiments', [])}
        used |= set(state.get('stage_progress', {})) & affected
        if used: rows.append({'experiment': state['experiment'], 'samples': sorted(used)})
    return rows


def notices(p, state):
    changed = False
    known = {x.get('id') for x in state.get('review_links', [])}
    for path in (p.state / 'review-notices').glob('*.json'):
        notice = json.loads(path.read_text(encoding='utf-8'))
        for scope in notice['affected']:
            if scope['experiment'] != state['experiment'] or notice['id'] in known: continue
            state['review_links'].append({'id': notice['id'], 'samples': scope['samples'], 'reason': notice['reason']})
            for sid in scope['samples']:
                for progress in state.get('stage_progress', {}).get(sid, {}).values(): progress['needs_review'] = True
            changed = True
    return changed
