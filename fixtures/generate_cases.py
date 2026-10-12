"""Freeze labeled synthetic cases before running the evaluator. No label inference."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from domain import contract_inputs, make_contract, complete_action, plus, windows, digest
from adapters import FixtureAdapter

AT='2026-10-12T12:00:00Z'
GROUPS=[('clean',12,'improved'),('harm',10,'harmed'),('null',10,'no_change'),('confounded',10,'inconclusive'),('invalid',8,'inconclusive'),('forbidden',6,'denied')]
cases=[]
for group,n,label in GROUPS:
    for i in range(n):
        profile=['quality','query','lineage'][i%3]
        scenario={'clean':'improved','harm':'harmed' if i%2 else 'guardrail','null':'no_change','confounded':['confounded','composition_shift','improved','improved','confounded'][i%5],'invalid':['missing','stale','low_count','metric_drift','improved','improved','improved','late_data'][i%8],'forbidden':['forbidden','budget','improved'][i%3]}.get(group)
        method='before_after' if group=='confounded' and i%5==2 else 'associated_only' if group=='confounded' and i%5==3 else 'matched_comparison'
        identity='observer' if group=='forbidden' and i%3==2 else 'action-owner'
        inp=contract_inputs(dict(title=f'{group} case {i+1}',action_id=f'act-{group}-{i}',decision_id=f'decision-{group}-{i}',profile=profile,scenario=scenario,seed=100+i*37,method=method,threshold=5. if profile=='query' else .05))
        c=make_contract(inp,plus(AT,-31),f'oc-{group}-{i}')
        c.update(state='armed',armed_at=plus(AT,-31));complete_action(c,plus(AT,-30))
        at=plus(windows(c)['mature_at'],1) if scenario=='late_data' else AT
        evidence=FixtureAdapter().measure(c,at,identity)
        fault=None
        if group=='invalid' and i in (4,5,6):
            fault={4:'unit',5:'grain',6:'duplicate'}[i]
            if fault=='duplicate':evidence['rows'].append(dict(evidence['rows'][0]))
            else:evidence['rows'][0][fault]='incompatible'
        rationale={'clean':'Adequate same-grain comparison exceeds predeclared threshold; guardrail passes.','harm':'Primary regression or guardrail breach overrides any positive metric movement.','null':'Finite-cohort movement is below the declared materiality threshold.','confounded':'Weak design, confounding or composition prevents an attributable outcome classification.','invalid':'Evidence is missing, stale, immature, low-count or semantically incompatible.','forbidden':'Identity, policy or budget denies measurement before rows are read.'}[group]
        cases.append(dict(id=f'{group}-{i+1:02}',partition='development' if i%2==0 else 'held_out',group=group,at=at,contract=c,evidence=evidence,expected=label,expected_attribution='associated_only' if method!='matched_comparison' else 'matched_comparison' if label in ('improved','harmed','no_change') else 'none',owner_decision='not_reviewable' if label=='denied' else 'accept_with_stated_limits',rationale=rationale,injected_fault=fault))
root=Path(__file__).resolve().parent
(root/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
(root/'manifest.json').write_text(json.dumps(dict(schema_version=1,total=56,development=28,held_out=28,dataset_hash=digest(cases),groups={g:n for g,n,_ in GROUPS},notes='Fixed labels authored independently of evaluator outputs; synthetic holdout partition is a regression check, not an independent statistical validation.'),indent=2)+'\n')
print('Wrote 56 fixed synthetic cases with 28 development / 28 held-out cases.')
