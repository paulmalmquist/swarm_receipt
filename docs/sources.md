# Source-to-feature record

This implementation was grounded in the supplied October 11, 2026 Swarm Impact Receipt proposal and observation-loop research. The proposal's source claims were provided as design context; this build did not independently reverify podcast transcripts or current cloud documentation.

| Source in the supplied proposal | Evidence class | Implemented design |
|---|---|---|
| [Periodic Labs / Latent Space](https://www.latent.space/p/periodic) | Podcast guest claims about negative results and process lineage | Retain harmed, null and inconclusive outcomes alongside successes |
| [MLOps Community: production evaluations](https://home.mlops.community/public/videos/its-2026-and-were-still-talking-evals) | Guest perspective about business outcomes | Frozen metric/window contracts and explicit closure metric |
| [Dwarkesh: experimental feedback](https://www.dwarkesh.com/p/john-beren-charlie) | Researcher discussion | Optional evidence-linked next-experiment proposal, never automatic promotion |
| [Practical AI: enterprise deployment](https://practicalai.show/373/transcript) | Practitioner perspective about identity and controlled interfaces | Explicit identity/read-adapter boundaries and audit trail |
| Observation-loop research supplied by Paul | Architecture research | Preserve observe → decide → measure → learn lineage and process/version context |

The causal limits, deterministic rules, synthetic examples and acceptance tests are implementation choices, not claims established by the podcasts. The value hypothesis is that an owned measurement contract and reviewable evidence improve institutional learning; only a prospective work pilot can establish that.

Production BigQuery behavior is not implemented or assumed here. During integration, consult official documentation for query execution metadata, allow-listed read templates, byte caps and historical evidence availability. Do not treat the placeholder source/job URLs as real query receipts.
