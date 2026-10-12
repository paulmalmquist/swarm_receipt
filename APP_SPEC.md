# Swarm Impact Receipt: implemented portable specification

## Lifecycle and authority
A contract is created as `draft`, validated, armed, then given an immutable synthetic action-completion receipt. Completion cannot predate arming. Measurement is permitted at `completion + end_day + lag_days`; review SLA is that maturity time plus `sla_days`. All arithmetic uses UTC and timezone-aware instants. Baseline is `[completion - baseline_days, completion)`; observation is `[completion + start_day, completion + end_day)`. No measurement is performed automatically when the clock moves.

Inputs cannot be edited after creation. Prototype contract changes require a new contract/action ID; in-place revision and retrospective redefinition are intentionally unavailable. A remeasurement uses the exact original contract and creates a child receipt with an explicit `supersedes` reference. Prior evidence and reviews remain untouched. A cancelled contract cannot be measured or reviewed. Completed-action cancellations do not remove its measurement obligation from the historical closure denominator.

Each measurement receives `improved`, `harmed`, `no_change`, `inconclusive`, or `denied`. Status is separate from attribution (`matched_comparison`, `associated_only`, `none`) and review (`needs_review`, `disputed`, `closed`). Action owner and metric owner are distinct demo identities. Both must accept the latest receipt for closure. Each has one immutable decision per receipt. Disputes require remeasurement, not overwriting reviews. Denied measurements cannot be reviewed or close. A learning proposal requires dual review, links one exact receipt, expires after 30 demo days and remains a draft. Superseded sources and expired proposals are displayed explicitly.

## Deterministic evaluation
The adapter supplies eight aggregates: primary and guardrail × treatment and matched control × baseline and observed. Ratio metrics retain integer numerators and denominators. Units, versions, grain, cohort/period completeness, counts, availability, freshness, confounders, composition and hashes tying evidence to windows/config are checked. Data gaps do not become zeros or passes.

`adjusted_delta = (treatment_after - treatment_before) - (control_after - control_before)`.

The primary benefit is adjusted delta for a higher-is-better metric and its negative for lower-is-better. `improved` requires benefit ≥ the frozen threshold. Primary regression ≤ negative threshold gives `harmed`. A guardrail violation gives `harmed` regardless of primary improvement; both raw and adjusted guardrail regression must stay within the limit. Everything within materiality limits is `no_change`. Boundary comparisons use a 1e-12 numeric tolerance. Weak comparison or any unresolved evidence defect returns `inconclusive` before numerical classification. Policy, identity and budget failures produce `denied` with zero rows/processed bytes.

This is a descriptive, finite-cohort rule. No confidence interval, randomization claim, treatment-effect estimate, population generalization or statistical equivalence is implemented. Matched comparison alone does not establish causality. The fixtures expose aggregate composition shifts as a flag; the demo does not discover Simpson's paradox from raw stratified records. Work adaptation requires explicit cohort construction, measurement uncertainty and domain-reviewed analysis methods.

## Storage and replay
SQLite WAL is schema version 1. Every successful command commits a full state snapshot in one transaction, with a unique idempotency key, request hash, previous-event hash and resulting-event hash. `BEGIN IMMEDIATE` serializes local writers; a global expected version rejects stale edits. A duplicate key with the same payload returns the original event version; another payload is a conflict.

Evidence JSON is stored under its SHA-256 name using atomic filesystem replacement before the event transaction commits. A crash before commit can leave an unreferenced artifact; it cannot produce a committed reference without a completed artifact write. Reads and replay fail closed on missing/corrupt evidence. Replay recomputes every command from the deterministic seed and compares canonical states, event chains and artifacts. Event snapshots include demo time and actual record time; actual timestamps are excluded from deterministic state hashes.

Receipt identity, evidence, numeric analysis and original hash remain immutable; reviews and proposals append separately. The receipt hash deliberately excludes those appended decisions. Historical seed records are labeled synthetic; their initial import is one seed event. Hashes are integrity checks, not cryptographic proof against a privileged local actor who can rewrite the whole chain.

## UI
- Outcome queue: search, domain/state/design filters, due windows, exact closure counts and next owner.
- Contract builder: thresholds, observation/baseline/maturation/review windows, minimum sample, freshness, budget, scenario and seed.
- Receipt: treatment/control comparison, guardrail, reasons, dual review, full evidence, prior versions and Markdown export.
- Timeline: per-contract histories with metric/grain versions; no incompatible pooling.
- Learning proposals: draft changes and source receipts with expiry/supersession labels.
- Audit: event list, deterministic replay, evaluation results, metric catalog and JSON/JSONL exports.

HTML uses semantic controls, visible labels, focus styles, dialog keyboard semantics, contrast-oriented colors, text status alongside colors, responsive layouts and reduced-motion support. Actual browser layout/accessibility testing remains unverified in this build; a Node controller/render smoke test exercises logic without a browser.

## Deliberate packaging simplifications
The portable API consolidates writes at `/api/command`; it does not pretend to implement the proposal's work REST/webhook paths. The CLI supports demo/eval/replay/export; lifecycle commands are available through the UI/API. On-demand measurements use short local transactions, not a distributed scheduler or lease service. The optional live BigQuery boundary is an unavailable adapter, not a simulated production integration. Numeric input validation in `domain.py` is authoritative; JSON schemas document transferable shapes and supplement, rather than replace, semantic checks.
