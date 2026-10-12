#!/usr/bin/env python3
"""Evaluate fixed labeled fixtures; do not tune thresholds on the held-out partition."""
import json
from pathlib import Path
from collections import Counter
from domain import analyze, digest

ROOT=Path(__file__).resolve().parent


def evaluate():
    cases=json.loads((ROOT/'fixtures/cases.json').read_text())
    manifest=json.loads((ROOT/'fixtures/manifest.json').read_text())
    if digest(cases)!=manifest['dataset_hash']:
        raise ValueError('fixture_manifest_hash_mismatch')
    partitions={p:dict(total=0,correct=0,status_confusion={},attribution_confusion={}) for p in ('development','held_out')}
    errors=[];forbidden_positive=0;predictions=[]
    for case in cases:
        a=analyze(case['contract'],case['evidence'],case['at']);part=partitions[case['partition']]
        part['total']+=1
        ok=a['status']==case['expected'] and a['attribution']==case['expected_attribution']
        part['correct']+=int(ok)
        for key,expected,actual in [('status_confusion',case['expected'],a['status']),('attribution_confusion',case['expected_attribution'],a['attribution'])]:
            row=part[key].setdefault(expected,{})
            row[actual]=row.get(actual,0)+1
        if not ok:errors.append(dict(id=case['id'],expected=case['expected'],actual=a['status'],attribution=a['attribution']))
        if case['group'] in ('confounded','invalid','forbidden') and (a['status'] in ('improved','harmed') or a['causal_claim']):forbidden_positive+=1
        predictions.append(dict(id=case['id'],partition=case['partition'],status=a['status'],attribution=a['attribution'],reasons=a['reasons']))
    report=dict(schema_version=1,total=len(cases),dataset_hash=digest(cases),**partitions,errors=errors,forbidden_positive=forbidden_positive,baseline={'current_process':None,'reason':'No work baseline available; measure prospectively in shadow mode.'},inconclusive=sum(p['status']=='inconclusive' for p in predictions),denied=sum(p['status']=='denied' for p in predictions),synthetic_query_bytes=sum(c['evidence']['bytes_processed'] for c in cases),reviewer_time=None,limits='Synthetic regression fixtures; no estimate of real-world performance, causality or statistical confidence.',predictions=predictions)
    return report


if __name__=='__main__':
    report=evaluate();(ROOT/'fixtures/evaluation-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='predictions'},indent=2))
    raise SystemExit(bool(report['errors'] or report['forbidden_positive']))
