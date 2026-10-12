# Local API

All responses are no-cache. The server is bound to 127.0.0.1 and accepts only localhost/127.0.0.1 Host headers with the selected port. No CORS capability is provided. This is a development server with synthetic identities.

| Route | Function |
|---|---|
| `GET /api/state` | State, global version, computed queue, catalog and session token |
| `POST /api/command` | Create/validate/arm/complete/measure/review/propose/cancel/advance |
| `GET /api/events` | Compact append-only event metadata |
| `GET /api/replay` | Recompute state and verify event/evidence hashes |
| `GET /api/export` | Full JSON state, event history and replay result |
| `GET /api/events.jsonl` | Complete event snapshots as JSONL |
| `GET /api/receipt.md?id=ir-…` | Version-specific Markdown receipt |
| `GET /api/evaluation` | Packaged fixed-fixture evaluation report |

Mutations use `Content-Type: application/json` and `X-Receipt-Token` from the state response. The browser Origin, if present, must match the local server. The token is a local CSRF control, not SSO. Actor values are `action-owner`, `metric-owner`, or read-only `observer`.

```json
{
  "command": "review",
  "data": {
    "id": "oc-example",
    "receipt_id": "ir-example",
    "decision": "accept",
    "reason": "Checked metric definitions, observed counts, guardrail and limitations."
  },
  "actor": "metric-owner",
  "key": "unique-request-id",
  "expected_version": 12
}
```

`create` accepts the exact fields in `config/example-contract.json`. Other lifecycle commands take `id` and a nonempty `reason`; measure also requires `supersedes` (null for the first measurement); review requires the latest `receipt_id` plus `accept`/`dispute`; propose requires the latest `receipt_id` and one of `regression_fixture`, `skill_amendment`, `new_experiment`, `no_action`. Advance accepts integer `days` (1–90) and is action-owner-only.

200 means saved or idempotent replay. 400 means malformed input/illegal transition/role violation. 403 means local session/host/origin rejection. 404 means unknown resource. 409 means stale global version, reused idempotency key, or integrity verification failure. Refresh after a stale-version conflict; do not silently overwrite. The same key and identical payload may safely retry a lost response. Schema, integrity and policy errors require investigation rather than automatic retries.

At work, replace this synthetic authority model with the existing signed action events, verified principals, resource ACLs and approved gateway; preserve the command invariants.
