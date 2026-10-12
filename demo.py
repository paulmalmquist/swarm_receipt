"""Deterministic demo seeds. No company records, models or live systems."""
from domain import contract_inputs, make_contract, complete_action, plus, mutation

CLOCK = '2026-10-12T12:00:00Z'


def seed_state():
    state = dict(schema_version=1, clock=CLOCK, mode='synthetic-local', contracts=[])
    cases = [
        ('Quality triage threshold', 'quality', 'improved', 27, 'closed'),
        ('Query cache rollout', 'query', 'guardrail', 27, 'review'),
        ('Evidence linking skill', 'lineage', 'confounded', 27, 'review'),
        ('Inspection routing update', 'quality', 'no_change', 30, 'closed'),
        ('Batch query rewrite', 'query', 'improved', 24, 'ready'),
        ('Late inspection labels', 'quality', 'late_data', 24, 'review'),
        ('Catalog coverage pass', 'lineage', 'improved', 9, 'observing'),
        ('Source freshness check', 'lineage', 'stale', 27, 'ready'),
        ('Next threshold experiment', 'quality', 'improved', 0, 'draft'),
    ]
    for i, (title, profile, scenario, age, phase) in enumerate(cases):
        d = contract_inputs(dict(title=title, action_id=f'act-demo-{i+1:03}', decision_id=f'decision-demo-{i+1:03}', profile=profile, scenario=scenario, seed=42 + i, threshold=5. if profile == 'query' else .05))
        c = make_contract(d, plus(CLOCK, -age - 1), f'oc-demo-{i+1:03}')
        if phase != 'draft':
            c.update(state='armed', armed_at=plus(CLOCK, -age - 1))
            complete_action(c, plus(CLOCK, -age))
        state['contracts'].append(c)
        if phase in ('closed', 'review'):
            state['clock'] = plus(CLOCK, -age + 24)
            state = mutation(state, 'measure', dict(id=c['id'], reason='Seeded synthetic measurement', supersedes=None), 'action-owner')
            if phase == 'closed':
                receipt = state['contracts'][-1]['measurements'][-1]
                for actor in ('action-owner', 'metric-owner'):
                    state = mutation(state, 'review', dict(id=c['id'], receipt_id=receipt['id'], decision='accept', reason='Demo owner reviewed the finite-cohort evidence and its limits.'), actor)
        state['clock'] = CLOCK
    return state
