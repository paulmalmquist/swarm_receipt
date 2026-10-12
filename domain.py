"""Pure, deterministic domain rules for the synthetic Impact Receipt demo."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re

SCHEMA_VERSION = 1
RULE_VERSION = 'finite-cohort-delta-v1'
IDENTITIES = {
    'action-owner': 'Action owner · demo',
    'metric-owner': 'Metric owner · demo',
    'observer': 'Read-only observer · demo',
}
CATALOG = {
    'quality': {'label': 'Quality triage', 'primary': {'id': 'false_positive_rate', 'version': 'v3', 'unit': 'ratio', 'grain': 'inspection', 'direction': 'lower'}, 'guardrail': {'id': 'miss_rate', 'version': 'v2', 'unit': 'ratio', 'grain': 'inspection', 'direction': 'lower'}, 'threshold': .05, 'guardrail_limit': .01},
    'query': {'label': 'Query performance', 'primary': {'id': 'query_duration', 'version': 'v1', 'unit': 'seconds', 'grain': 'query', 'direction': 'lower'}, 'guardrail': {'id': 'query_error_rate', 'version': 'v1', 'unit': 'ratio', 'grain': 'query', 'direction': 'lower'}, 'threshold': 5., 'guardrail_limit': .01},
    'lineage': {'label': 'Evidence coverage', 'primary': {'id': 'evidence_coverage', 'version': 'v1', 'unit': 'ratio', 'grain': 'action', 'direction': 'higher'}, 'guardrail': {'id': 'stale_evidence_rate', 'version': 'v1', 'unit': 'ratio', 'grain': 'action', 'direction': 'lower'}, 'threshold': .05, 'guardrail_limit': .01},
}
SCENARIOS = ['improved', 'harmed', 'guardrail', 'no_change', 'confounded', 'stale', 'missing', 'low_count', 'metric_drift', 'composition_shift', 'late_data', 'budget', 'forbidden']


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def require(ok, code):
    if not ok:
        raise ValueError(code)


def timestamp(value):
    require(isinstance(value, str), 'timestamp_required')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('invalid_timestamp') from None
    require(parsed.tzinfo is not None, 'timezone_required')
    return parsed.astimezone(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def plus(value, days):
    return iso(timestamp(value) + timedelta(days=days))


def number(value, low, high, code):
    require(type(value) in (float, int) and math.isfinite(value) and low <= value <= high, code)


def text_field(value, name, limit=300):
    require(isinstance(value, str) and 0 < len(value.strip()) <= limit, 'invalid_' + name)


def contract_inputs(overrides=None):
    data = dict(title='Quality threshold adjustment', action_id='act-demo-001', decision_id='decision-demo-001', profile='quality', owner='action-owner', metric_owner='metric-owner', method='matched_comparison', threshold=.05, guardrail_limit=.01, baseline_days=14, start_day=7, end_day=21, lag_days=2, sla_days=3, min_count=100, freshness_hours=24, max_bytes=1000000, scenario='improved', seed=42, confounders=[], plan_ref='demo://plans/quality-threshold', config_ref='demo://config/threshold-v2', cohort_ref='demo://cohorts/matched-line', rationale='Measure a predeclared outcome after an authorized synthetic action.')
    data.update(overrides or {})
    return data


def validate_input(data):
    require(isinstance(data, dict), 'contract_object_required')
    require(set(data) == set(contract_inputs()), 'contract_fields_mismatch')
    for k in ('title', 'action_id', 'decision_id', 'plan_ref', 'config_ref', 'cohort_ref', 'rationale'):
        text_field(data[k], k, 1200 if k == 'rationale' else 300)
    for k in ('action_id', 'decision_id'):
        require(re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.:-]{2,119}', data[k]) is not None, 'invalid_' + k)
    for k in ('plan_ref', 'config_ref', 'cohort_ref'):
        require(data[k].startswith('demo://'), 'synthetic_reference_required')
    require(data['profile'] in CATALOG, 'unknown_metric_profile')
    require(data['owner'] == 'action-owner' and data['metric_owner'] == 'metric-owner', 'distinct_demo_owners_required')
    require(data['method'] in ('matched_comparison', 'before_after', 'associated_only'), 'unsupported_comparison')
    require(data['scenario'] in SCENARIOS, 'unknown_scenario')
    for k, low, high in [('baseline_days', 1, 90), ('start_day', 0, 89), ('end_day', 1, 90), ('lag_days', 0, 30), ('sla_days', 1, 30), ('min_count', 1, 100000), ('freshness_hours', 1, 168), ('max_bytes', 0, 10000000), ('seed', 0, 2147483647)]:
        require(type(data[k]) is int and low <= data[k] <= high, 'invalid_' + k)
    require(data['end_day'] > data['start_day'], 'illegal_observation_window')
    limit = 1 if CATALOG[data['profile']]['primary']['unit'] == 'ratio' else 10000
    number(data['threshold'], .000001, limit, 'invalid_threshold')
    number(data['guardrail_limit'], 0, 1, 'invalid_guardrail_limit')
    require(isinstance(data['confounders'], list) and len(data['confounders']) <= 20, 'invalid_confounders')
    for item in data['confounders']:
        text_field(item, 'confounder')
    return data


def make_contract(data, at, identifier):
    validate_input(data)
    timestamp(at)
    metric = deepcopy(CATALOG[data['profile']])
    for kind in ('primary', 'guardrail'):
        metric[kind].update(catalog_ref='demo://catalog/' + metric[kind]['id'], query_template='synthetic-aggregate-v1', dimensions=['matched_pair'], source_ref='demo://fixture/v1')
        metric[kind]['binding_hash'] = digest(metric[kind])
    return dict(id=identifier, schema_version=1, version=1, created_at=at, inputs=deepcopy(data), metrics=metric, config_hash=digest({'inputs': data, 'metrics': metric, 'rule': RULE_VERSION}), state='draft', action=None, measurements=[], cancellation=None, parent_id=None)


def windows(contract):
    if not contract['action']:
        return None
    at = contract['action']['completed_at']
    d = contract['inputs']
    return dict(baseline_start=plus(at, -d['baseline_days']), baseline_end=at, observation_start=plus(at, d['start_day']), observation_end=plus(at, d['end_day']), mature_at=plus(at, d['end_day'] + d['lag_days']), deadline=plus(at, d['end_day'] + d['lag_days'] + d['sla_days']))


def complete_action(contract, at):
    require(contract['state'] == 'armed', 'contract_must_be_armed')
    require(timestamp(at) >= timestamp(contract['armed_at']), 'action_precedes_contract')
    receipt = dict(id='ar-' + contract['id'], action_id=contract['inputs']['action_id'], decision_id=contract['inputs']['decision_id'], actor='synthetic-executor', authorization_ref='demo://authorizations/' + contract['id'], scope=contract['inputs']['profile'], config_ref=contract['inputs']['config_ref'], started_at=at, completed_at=at, synthetic=True)
    receipt['hash'] = digest(receipt)
    contract['action'] = receipt
    contract['state'] = 'observing'


def latest(contract):
    return contract['measurements'][-1] if contract['measurements'] else None


def review_state(measurement):
    reviews = measurement['reviews']
    if any(r['decision'] == 'dispute' for r in reviews):
        return 'disputed'
    if {r['actor'] for r in reviews if r['decision'] == 'accept'} == {'action-owner', 'metric-owner'}:
        return 'closed'
    return 'needs_review'


def lifecycle(contract, at):
    if contract['state'] == 'cancelled':
        return 'cancelled'
    measurement = latest(contract)
    if measurement:
        if measurement['analysis']['status'] == 'denied':
            return 'blocked'
        return review_state(measurement)
    if contract['state'] != 'observing':
        return contract['state']
    w = windows(contract)
    return 'ready' if timestamp(at) >= timestamp(w['mature_at']) else 'observing'


def analyze(contract, evidence, at):
    """Finite-cohort threshold comparison; no population inference or causal proof."""
    d = contract['inputs']
    reasons = []
    result = dict(rule_version=RULE_VERSION, status='inconclusive', attribution='none', causal_claim=False, primary=None, guardrail=None, reasons=reasons, config_hash=contract['config_hash'], interpretation='Synthetic finite-cohort comparison; thresholds are illustrative. No causal or population claim.')
    if evidence.get('denial'):
        result.update(status='denied')
        reasons.append(evidence['denial'])
        return result
    w = windows(contract)
    if not w or timestamp(at) < timestamp(w['mature_at']):
        reasons.append('window_not_mature')
        return result
    if evidence.get('confounders') or d['confounders']:
        reasons.append('unresolved_confounders')
    if d['method'] != 'matched_comparison':
        reasons.append('weak_comparison_design')
    if evidence.get('composition_shift'):
        reasons.append('cohort_composition_shift')
    if not evidence.get('complete'):
        reasons.append('incomplete_evidence')
    if evidence.get('config_hash') != contract['config_hash']:
        reasons.append('config_mismatch')
    if evidence.get('window_hash') != digest(w):
        reasons.append('window_mismatch')
    if timestamp(evidence['available_at']) > timestamp(at):
        reasons.append('late_arriving_evidence')
    age = (timestamp(at) - timestamp(evidence['fresh_as_of'])).total_seconds()
    if age < 0 or age > d['freshness_hours'] * 3600:
        reasons.append('stale_or_future_evidence')
    rows = evidence.get('rows', [])
    expected = {(k, c, p) for k in ('primary', 'guardrail') for c in ('treatment', 'control') for p in ('baseline', 'observed')}
    keys = [(r.get('metric'), r.get('cohort'), r.get('period')) for r in rows]
    if set(keys) != expected or len(keys) != len(expected):
        reasons.append('missing_or_duplicate_observations')
    for row in rows:
        metric = contract['metrics'].get(row.get('metric'), {})
        if any(row.get(k) != metric.get(k) for k in ('id', 'version', 'unit', 'grain')):
            reasons.append('metric_binding_mismatch')
        count = row.get('count')
        if type(count) is not int or count < d['min_count']:
            reasons.append('insufficient_sample')
        value = row.get('value')
        if type(value) not in (float, int) or not math.isfinite(value) or value < 0 or (row.get('unit') == 'ratio' and value > 1):
            reasons.append('invalid_numeric_observation')
        elif row.get('unit') == 'ratio' and type(count) is int and count > 0:
            numerator = row.get('numerator')
            if type(numerator) is not int or not 0 <= numerator <= count or abs(value - numerator / count) > 1e-12:
                reasons.append('invalid_rate_denominator')
    result['reasons'] = sorted(set(reasons))
    if reasons:
        result['attribution'] = 'associated_only' if 'weak_comparison_design' in reasons else 'none'
        return result
    lookup = {(r['metric'], r['cohort'], r['period']): r for r in rows}
    for kind in ('primary', 'guardrail'):
        tb = lookup[kind, 'treatment', 'baseline']['value']
        ta = lookup[kind, 'treatment', 'observed']['value']
        cb = lookup[kind, 'control', 'baseline']['value']
        ca = lookup[kind, 'control', 'observed']['value']
        raw = round(ta - tb, 10)
        adjusted = round(raw - (ca - cb), 10)
        result[kind] = dict(baseline=tb, observed=ta, control_baseline=cb, control_observed=ca, raw_delta=raw, adjusted_delta=adjusted, unit=contract['metrics'][kind]['unit'])
    result['attribution'] = 'matched_comparison'
    p = result['primary']
    benefit = -p['adjusted_delta'] if contract['metrics']['primary']['direction'] == 'lower' else p['adjusted_delta']
    p['benefit'] = benefit
    p['threshold'] = d['threshold']
    g = result['guardrail']
    g['limit'] = d['guardrail_limit']
    # An observed raw guardrail regression cannot be hidden by a worsening control.
    g['passed'] = max(g['raw_delta'], g['adjusted_delta']) <= d['guardrail_limit'] + 1e-12
    if not g['passed']:
        result['status'] = 'harmed'
        result['reasons'] = ['guardrail_regression']
    elif benefit <= -d['threshold'] + 1e-12:
        result['status'] = 'harmed'
        result['reasons'] = ['primary_regression']
    elif benefit >= d['threshold'] - 1e-12:
        result['status'] = 'improved'
        result['reasons'] = ['primary_threshold_met']
    else:
        result['status'] = 'no_change'
        result['reasons'] = ['below_materiality_threshold']
    return result


def mutation(state, command, data, actor):
    require(actor in IDENTITIES, 'unknown_identity')
    require(actor != 'observer', 'read_only_identity')
    require(isinstance(data, dict), 'data_object_required')
    s = deepcopy(state)
    at = s['clock']
    if command == 'create':
        require(actor == 'action-owner', 'action_owner_required')
        require(len(s['contracts']) < 200, 'demo_contract_limit')
        validate_input(data)
        require(not any(c['inputs']['action_id'] == data['action_id'] for c in s['contracts']), 'duplicate_action_id')
        c = make_contract(data, at, 'oc-' + digest({'data': data, 'at': at})[:12])
        s['contracts'].append(c)
        return s
    if command == 'advance':
        require(actor == 'action-owner', 'action_owner_required')
        require(set(data) == {'days'} and type(data['days']) is int and 1 <= data['days'] <= 90, 'invalid_clock_advance')
        s['clock'] = plus(at, data['days'])
        return s
    require('id' in data, 'id_required')
    c = next((x for x in s['contracts'] if x['id'] == data['id']), None)
    require(c is not None, 'contract_not_found')
    reason = data.get('reason')
    text_field(reason, 'reason', 1200)
    phase = lifecycle(c, at)
    if command in ('validate', 'arm', 'complete', 'cancel', 'measure'):
        require(actor == c['inputs']['owner'], 'action_owner_required')
    if command == 'validate':
        require(c['state'] == 'draft', 'draft_required')
        validate_input(c['inputs'])
        c['state'] = 'validated'
    elif command == 'arm':
        require(c['state'] == 'validated', 'validated_required')
        c['state'] = 'armed'
        c['armed_at'] = at
    elif command == 'complete':
        complete_action(c, at)
    elif command == 'cancel':
        require(phase not in ('closed', 'cancelled'), 'cannot_cancel_final_record')
        c['state'] = 'cancelled'
        c['cancellation'] = dict(actor=actor, reason=reason, at=at)
    elif command == 'measure':
        require(c['state'] == 'observing', 'completed_action_required')
        require(timestamp(at) >= timestamp(windows(c)['mature_at']), 'window_not_mature')
        from adapters import FixtureAdapter
        # Repeated measurement must explicitly refer to the receipt it supersedes.
        prior = latest(c)
        require(data.get('supersedes') == (prior['id'] if prior else None), 'supersession_mismatch')
        require(not prior or timestamp(at) > timestamp(prior['created_at']), 'advance_clock_before_remeasurement')
        evidence = FixtureAdapter().measure(c, at, actor)
        analysis = analyze(c, evidence, at)
        receipt = dict(id='ir-' + digest({'contract': c['id'], 'evidence': evidence, 'ordinal': len(c['measurements'])})[:12], ordinal=len(c['measurements']) + 1, created_at=at, contract_id=c['id'], config_hash=c['config_hash'], action_hash=c['action']['hash'], evidence=evidence, evidence_hash=digest(evidence), analysis=analysis, analysis_hash=digest(analysis), reviews=[], proposals=[], supersedes=prior['id'] if prior else None)
        receipt['receipt_hash'] = digest({k: v for k, v in receipt.items() if k not in ('reviews', 'proposals')})
        c['measurements'].append(receipt)
    elif command == 'review':
        require(phase in ('needs_review', 'disputed'), 'reviewable_receipt_required')
        m = latest(c)
        require(data.get('receipt_id') == m['id'], 'stale_receipt')
        require(actor in (c['inputs']['owner'], c['inputs']['metric_owner']), 'owner_required')
        require(not any(r['actor'] == actor for r in m['reviews']), 'review_already_recorded')
        require(data.get('decision') in ('accept', 'dispute'), 'invalid_review_decision')
        m['reviews'].append(dict(actor=actor, decision=data['decision'], reason=reason, at=at))
    elif command == 'propose':
        require(phase == 'closed', 'dual_review_required')
        m = latest(c)
        require(data.get('receipt_id') == m['id'], 'stale_receipt')
        require(not m['proposals'], 'proposal_already_exists')
        kind = data.get('kind')
        require(kind in ('regression_fixture', 'skill_amendment', 'new_experiment', 'no_action'), 'invalid_proposal_kind')
        m['proposals'].append(dict(id='lp-' + m['id'], kind=kind, text=reason, target_ref=c['inputs']['plan_ref'], source_receipt=m['id'], source_hash=m['receipt_hash'], state='proposed', actor=actor, created_at=at, expires_at=plus(at, 30), risk='Requires work-owner assessment; no automatic promotion'))
    else:
        raise ValueError('unknown_command')
    return s


def summary(state):
    rows = []
    eligible = []
    for c in state['contracts']:
        phase = lifecycle(c, state['clock'])
        w = windows(c)
        m = latest(c)
        deadline_elapsed = bool(w and timestamp(state['clock']) >= timestamp(w['deadline']))
        # Include post-completion cancellations in denominator; they cannot erase obligations.
        if deadline_elapsed:
            valid = [x for x in c['measurements'] if review_state(x) == 'closed' and x['analysis']['status'] != 'denied' and any(x['evidence'].get('rows', [])) and max(timestamp(r['at']) for r in x['reviews']) <= timestamp(w['deadline'])]
            eligible.append(bool(valid))
        ball = 'Action owner'
        if phase == 'observing':
            ball = 'Measurement window'
        elif phase == 'needs_review':
            reviewed = {r['actor'] for r in m['reviews']}
            ball = 'Metric owner' if 'action-owner' in reviewed else 'Action owner'
        elif phase in ('closed', 'cancelled'):
            ball = 'Closed'
        elif phase == 'disputed':
            ball = 'Action owner · remeasure'
        rows.append(dict(id=c['id'], phase=phase, status=m['analysis']['status'] if m else None, window=w, overdue=deadline_elapsed and phase != 'closed', ball=ball))
    return dict(rows=rows, closure=dict(numerator=sum(eligible), denominator=len(eligible), rate=sum(eligible) / len(eligible) if eligible else None, baseline=None, definition='Owner-reviewed, evidence-backed receipts closed by SLA / completed actions whose SLA has elapsed'), counts={k: sum(r['phase'] == k for r in rows) for k in ('ready', 'needs_review', 'closed', 'observing', 'blocked', 'disputed')}, query_bytes=sum(m['evidence']['bytes_processed'] for c in state['contracts'] for m in c['measurements']))


def receipt_markdown(contract, measurement):
    a = measurement['analysis']
    d = contract['inputs']
    lines = ['# Swarm Impact Receipt', '', '**SYNTHETIC DEMO — no production or causal claim.**', '', f"## {d['title']}", '', f"- Receipt: `{measurement['id']}`", f"- Action: `{d['action_id']}` · decision: `{d['decision_id']}`", f"- Contract: `{contract['id']}` · config: `{contract['config_hash']}`", f"- Status: **{a['status']}** · attribution: **{a['attribution']}**", f"- Review: **{review_state(measurement)}**", f"- Measured at: {measurement['created_at']}", f"- Supersedes: {measurement['supersedes'] or 'none'}", f"- Reasons: {', '.join(a['reasons'])}", f"- Plan: `{d['plan_ref']}` · config: `{d['config_ref']}`", '', '## Measurement', '', a['interpretation'], '', '`no_change` means below the configured finite-cohort materiality threshold; it is not statistical equivalence.', '']
    if a['primary']:
        lines += ['| Metric | Before | After | Control before | Control after | Adjusted delta |', '|---|---:|---:|---:|---:|---:|']
        for kind in ('primary', 'guardrail'):
            r = a[kind]
            lines.append(f"| {contract['metrics'][kind]['id']} | {r['baseline']:.5g} | {r['observed']:.5g} | {r['control_baseline']:.5g} | {r['control_observed']:.5g} | {r['adjusted_delta']:.5g} |")
    lines += ['', '## Provenance', '', f"- Evidence hash: `{measurement['evidence_hash']}`", f"- Receipt hash: `{measurement['receipt_hash']}`", f"- Rule: `{RULE_VERSION}`", f"- Source: `{measurement['evidence']['source_snapshot']}`", f"- Bytes processed: {measurement['evidence']['bytes_processed']} (synthetic units)", '', '## Owner decisions', '']
    lines += [f"- {r['actor']} · {r['decision']} · {r['at']}: {r['reason']}" for r in measurement['reviews']] or ['Pending.']
    lines += ['', '## Learning proposals', '']
    lines += [f"- {p['kind']} (proposed; expires {p['expires_at']}): {p['text']}" for p in measurement['proposals']] or ['None.']
    return '\n'.join(lines) + '\n'
