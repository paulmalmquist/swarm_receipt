# swarm_receipt

**Swarm Impact Receipt** closes the measure → learn step of Paul OS: declare what an action should change, wait for evidence, measure the outcome, obtain owner review, and preserve the learning proposal.

A portable, synthetic local app. **Python 3.10+; no packages, API keys, models or cloud account required.**

## Run

```bash
git clone https://github.com/paulmalmquist/swarm_receipt.git
cd swarm_receipt
python3 server.py
```

Open **http://127.0.0.1:8766**. On Windows, `py -3 server.py` also works. Port 8766 avoids the Assumption Trial Ledger's default port.

The app starts with nine synthetic contracts across quality triage, query performance and evidence coverage. It creates `data/receipts.sqlite` and its companion content-addressed artifact directory on first run. Changes survive restarts. Stop the server before backing up the complete `data/` directory. To start a separate workspace, use `python3 server.py --db path/to/new.sqlite`.

## Try the complete workflow

1. Open **Query cache rollout**. Its primary metric improves, but the error-rate guardrail fails. The receipt is `harmed`.
2. Accept or dispute the evidence with a reason. Switch the top-right demo identity to **Metric owner** for the second review. These roles demonstrate the workflow; they are not authentication.
3. Open the already reviewed **Quality triage threshold** receipt and draft a regression fixture, next experiment, skill amendment, or no-action note.
4. Create a new contract as **Action owner**. Choose a metric, windows, threshold, guardrail, sample minimum, freshness and read budget. Validate, arm, and record **synthetic** action completion.
5. Advance the demo clock until evidence matures, measure, then review as both owners. Clock advancement affects every contract in this local demo and is not a real scheduler.
6. Inspect **Late inspection labels**, advance seven simulated days, and remeasure. The earlier inconclusive result remains in history.
7. Use **Evidence & audit** to verify replay or export the full JSON/JSONL packet. Individual receipts export to Markdown.

## Included

- Dark, responsive queue, contract builder, receipt comparison, timeline, learning proposals, and audit view.
- Frozen contract inputs, metric versions, action receipts and explicit measurement/SLA windows.
- Deterministic matched-cohort comparisons with primary thresholds and guardrails.
- Explicit inconclusive reasons for weak design, stale/missing/late evidence, low samples, composition shifts and metric incompatibility.
- Preflight identity, policy and byte-budget denials; two-owner review and disputes.
- Immutable evidence and analysis bodies, appended reviews, superseding measurements, draft-only learning proposals.
- SQLite transactions, idempotency keys, optimistic version checks, content hashes and deterministic command replay.
- 56 fixed evaluation cases (28 development / 28 held out), Python tests, JavaScript controller smoke test, CI and work handoff.

## Verification

```bash
python3 verify.py
```

This runs Python tests, the fixed evaluation set, and a full headless domain demo. If Node.js is installed, it also runs JavaScript syntax checks and a controller/render smoke test against the real local API. That smoke test **does not render a browser**. See `docs/VERIFICATION_REPORT.md` for actual results and gaps.

Optional commands:

```bash
python3 -m unittest discover -s tests -v
python3 evaluate.py
python3 cli.py demo --out data/demo-receipt.md
python3 server.py --replay
node tests/ui_smoke.cjs
```

Equivalent `make setup lint test demo eval verify` wrappers are included. No installation is needed for Python functionality.

## What a result means

`improved`, `harmed`, and `no_change` describe the **observed synthetic cohorts under the configured thresholds**. Adjusted change is treatment change minus control change. The app makes no causal claim, estimates no population confidence interval, and does not infer the benefits of inspection or manufacturing intervention. `no_change` means below the materiality threshold, not statistical equivalence. Before/after-only designs remain inconclusive. A raw guardrail breach cannot be hidden by a worsening control.

The headline closure metric shows its exact numerator and denominator. Both owners must accept an evidence-backed receipt by its SLA. Completed actions cancelled afterward remain in the denominator. Inconclusive receipts with some actual evidence can close after review; denied or entirely empty evidence cannot count as evidence-backed closure. The current-process baseline is **unknown**, not zero.

## Work integration

Read **[docs/WORK_HANDOFF.md](docs/WORK_HANDOFF.md)** first. This workspace has no production Paul OS, Swarm Court, Dreamcatcher, OpenMetadata or BigQuery interfaces. `BigQueryReadAdapter` is deliberately unavailable. Reuse the work environment's approved identity, catalog, query gateway, persistence, artifact and promotion components. This demo never executes real actions, changes skills, sends messages or calls a model.

The server binds to loopback only. Host/origin checks and session tokens protect the local workflow; selectable demo identities are not enterprise access control. Do not expose this Python development server as a shared app. Query budgets are synthetic byte units, not actual cloud charges. Local hashes detect inconsistency; they are not a tamper-proof audit service.

## Project map

| File | Responsibility |
|---|---|
| `domain.py` | Validation, state transitions, comparison, review, closure and Markdown |
| `adapters.py` | Deterministic evidence and unavailable work adapter |
| `storage.py` | SQLite events, immutable evidence, concurrency and replay |
| `server.py` | Loopback API and static UI |
| `web/` | No-build vanilla HTML/CSS/JS interface |
| `demo.py`, `cli.py` | Seed workspace and reproducible complete demo |
| `fixtures/`, `evaluate.py` | Frozen cases, labels, manifest and evaluation results |
| `tests/`, `verify.py` | Domain, persistence, HTTP and controller verification |
| `APP_SPEC.md`, `schemas/`, `docs/` | Implementation contracts, limits and transfer guidance |

No resume, company records, credentials or user runtime database are included.
