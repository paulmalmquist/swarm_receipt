#!/usr/bin/env python3
"""Portable CLI: demo, replay, export, or evaluate. See docs/API.md for commands."""
import argparse
import json
from pathlib import Path
import tempfile
from domain import contract_inputs, latest, receipt_markdown, digest
from storage import Store
from evaluate import evaluate


def demo(out):
    with tempfile.TemporaryDirectory() as directory:
        store=Store(Path(directory)/'demo.sqlite')
        def call(command,data,actor='action-owner'):
            version,_=store.read()
            store.change(dict(command=command,data=data,actor=actor,key='demo-'+str(version),expected_version=version))
        call('create',contract_inputs(dict(action_id='act-cli-demo',decision_id='decision-cli-demo',title='CLI end-to-end outcome')))
        cid=store.read()[1]['contracts'][-1]['id']
        for cmd in ('validate','arm','complete'):call(cmd,dict(id=cid,reason='Reproducible synthetic CLI demonstration'))
        call('advance',{'days':23})
        call('measure',dict(id=cid,supersedes=None,reason='Measurement window matured'))
        rid=latest(store.read()[1]['contracts'][-1])['id']
        for actor in ('action-owner','metric-owner'):call('review',dict(id=cid,receipt_id=rid,decision='accept',reason='Reviewed synthetic cohorts, guardrail, provenance and limits'),actor)
        call('propose',dict(id=cid,receipt_id=rid,kind='regression_fixture',reason='Retain this finite-cohort comparison as an explicit regression case'))
        contract=store.read()[1]['contracts'][-1];receipt=latest(contract)
        path=Path(out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(receipt_markdown(contract,receipt))
        return dict(passed=True,receipt_id=rid,status=receipt['analysis']['status'],reviewers=len(receipt['reviews']),proposals=len(receipt['proposals']),receipt_hash=receipt['receipt_hash'],replay=store.replay(),output=str(path))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['demo','eval','replay','export']);p.add_argument('--out',default='data/demo-receipt.md');p.add_argument('--db',default='data/receipts.sqlite');a=p.parse_args()
    if a.command=='demo':result=demo(a.out)
    elif a.command=='eval':result=evaluate()
    elif a.command=='replay':result=Store(a.db).replay()
    else:
        store=Store(a.db);version,state=store.read();result=dict(version=version,state=state,replay=store.replay(),events=store.events());Path(a.out).write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if a.command=='eval' and (result['errors'] or result['forbidden_positive']):raise SystemExit(1)


if __name__=='__main__':main()
