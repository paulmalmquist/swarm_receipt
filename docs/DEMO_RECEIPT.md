# Swarm Impact Receipt

**SYNTHETIC DEMO — no production or causal claim.**

## CLI end-to-end outcome

- Receipt: `ir-3497eecce515`
- Action: `act-cli-demo` · decision: `decision-cli-demo`
- Contract: `oc-5cc01f93fa17` · config: `fccc05cc5ee4d7e929ef244f9c22bc30db6bca061cb991c6c85b903f4dfebc89`
- Status: **improved** · attribution: **matched_comparison**
- Review: **closed**
- Measured at: 2026-11-04T12:00:00Z
- Supersedes: none
- Reasons: primary_threshold_met
- Plan: `demo://plans/quality-threshold` · config: `demo://config/threshold-v2`

## Measurement

Synthetic finite-cohort comparison; thresholds are illustrative. No causal or population claim.

`no_change` means below the configured finite-cohort materiality threshold; it is not statistical equivalence.

| Metric | Before | After | Control before | Control after | Adjusted delta |
|---|---:|---:|---:|---:|---:|
| false_positive_rate | 0.22 | 0.135 | 0.23 | 0.236 | -0.091 |
| miss_rate | 0.03 | 0.032 | 0.04 | 0.041 | 0.001 |

## Provenance

- Evidence hash: `b74f2c851176a7ed048220920cf545e8d3fae77d26fe17feff645dfb111233eb`
- Receipt hash: `f7757179e81f8768a5ed68fa4143909e75d00464da0fda38b679b445b73cfb85`
- Rule: `finite-cohort-delta-v1`
- Source: `demo://snapshot/4a55423508c176ed`
- Bytes processed: 2048 (synthetic units)

## Owner decisions

- action-owner · accept · 2026-11-04T12:00:00Z: Reviewed synthetic cohorts, guardrail, provenance and limits
- metric-owner · accept · 2026-11-04T12:00:00Z: Reviewed synthetic cohorts, guardrail, provenance and limits

## Learning proposals

- regression_fixture (proposed; expires 2026-12-04T12:00:00Z): Retain this finite-cohort comparison as an explicit regression case
