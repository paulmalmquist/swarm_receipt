"""Synthetic measurement adapter and an explicitly unavailable work boundary."""
import random
from domain import digest, windows, plus, timestamp


class BigQueryReadAdapter:
    """Integrate the approved work gateway; never accept free-form SQL here."""
    def measure(self, contract, at, principal):
        raise NotImplementedError('REPLACE_AT_WORK: approved read gateway, identity, catalog and budget policy required')


class FixtureAdapter:
    version = 'fixture-v1'

    def measure(self, contract, at, principal):
        d = contract['inputs']
        w = windows(contract)
        scenario = d['scenario']
        estimate = 8 * 256
        denied = ('identity_forbidden' if principal != d['owner'] else
                  'policy_forbidden' if scenario == 'forbidden' else
                  'query_budget_exceeded' if scenario == 'budget' or estimate > d['max_bytes'] else None)
        base = dict(adapter_version=self.version, synthetic=True, config_hash=contract['config_hash'], window_hash=digest(w), query_template='synthetic-aggregate-v1', query_hash=digest({'template': 'synthetic-aggregate-v1', 'metrics': contract['metrics']}), parameter_hash=digest(w), source_snapshot='demo://snapshot/' + digest({'config': contract['config_hash'], 'at': at})[:16], job_ref='demo://job/' + digest({'contract': contract['id'], 'at': at})[:16], estimated_bytes=estimate, bytes_processed=0 if denied else estimate, fresh_as_of=at, available_at=at, complete=True, confounders=[], composition_shift=False, denial=denied, rows=[])
        if denied:
            return base
        rng = random.Random(d['seed'])
        metric = contract['metrics']['primary']
        ratio = metric['unit'] == 'ratio'
        before = (.22 if metric['direction'] == 'lower' else .62) if ratio else 40.
        control_before = before + (.01 if ratio else 2)
        trend = .006 if ratio else 1.0
        improvement = .09 if ratio else 10.
        improvement += rng.uniform(-.003, .003) if ratio else rng.uniform(-.2, .2)
        signed = -improvement if metric['direction'] == 'lower' else improvement
        if scenario == 'harmed':
            signed = -signed
        if scenario == 'no_change':
            signed = .002 if ratio else .2
        values = {
            'primary': [before, before + trend + signed, control_before, control_before + trend],
            'guardrail': [.03, .032 if scenario != 'guardrail' else .075, .04, .041],
        }
        count = 20 if scenario == 'low_count' else 1000 + d['seed'] % 7 * 100
        for kind in ('primary', 'guardrail'):
            m = contract['metrics'][kind]
            for (cohort, period), value in zip([('treatment', 'baseline'), ('treatment', 'observed'), ('control', 'baseline'), ('control', 'observed')], values[kind]):
                row = dict(metric=kind, cohort=cohort, period=period, count=count, value=round(value, 8), **{k: m[k] for k in ('id', 'version', 'unit', 'grain')})
                if m['unit'] == 'ratio':
                    row['numerator'] = round(value * count)
                    row['value'] = row['numerator'] / count
                row['observation_hash'] = digest(row)
                base['rows'].append(row)
        if scenario == 'stale':
            base['fresh_as_of'] = plus(at, -8)
        if scenario == 'missing':
            base['rows'].pop()
            base['complete'] = False
        if scenario == 'metric_drift':
            base['rows'][0]['version'] = 'unapproved-v99'
        if scenario == 'confounded':
            base['confounders'] = ['Concurrent staffing change during the observation window']
        if scenario == 'composition_shift':
            base['composition_shift'] = True
            base['confounders'] = ['Treatment product mix changed; aggregate comparison is incompatible']
        if scenario == 'late_data':
            base['available_at'] = plus(w['mature_at'], 3)
            if timestamp(at) < timestamp(base['available_at']):
                base['complete'] = False
                base['rows'] = []
        base['row_count'] = len(base['rows'])
        base['result_artifact_hash'] = digest(base['rows'])
        return base
