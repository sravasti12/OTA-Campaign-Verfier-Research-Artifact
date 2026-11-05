# Roadmap after Phase 11

Phases 1?10 are implemented. Phase 11 adds local release validation and portfolio
evidence; remote CI and live OIDC gates remain pending by user choice. No further
numbered implementation phases are planned; external identity-provider setup and network
deployment remain operator configuration, not validated deployment claims. It gives the portfolio
project a complete local simulation workflow from source evidence through
planning, fault investigation, retained results, and human review. Further phases
are optional improvements, not claims of completed capabilities. Implement one
phase at a time, with its own passing tests and review.

## Phase 8 — measurable quality and reproducibility

Industry problem: a convincing demonstration is insufficient without evidence
of what the verifier detects and where it fails.

Add a versioned scenario corpus with compatible intermediate states, rollback
traps, dependency cycles, concurrency limits, and explicitly infeasible cases.
Use independent small-state oracles and metamorphic checks to supplement the
existing deterministic tests. Extend the extraction evaluation with held-out
paraphrases and unsupported requirements; report per-constraint precision/recall,
evidence-span accuracy, faithfulness false acceptance, schema rejection, latency,
and provider/model configuration. Keep fixture regression scores separate from
optional live-model measurements. Freeze seeds and corpus versions, export
machine-readable reports, and add CI for supported Python versions and Windows
plus Linux. Establish measured baselines before choosing performance thresholds.

Done when a fresh checkout can reproduce offline reports, the deterministic core
is tested with model calls forbidden, and optional live evaluation is clearly
separated from synthetic fixture results. Implemented methodology and local verification are documented in [Phase 8](phase8.md).
The configured multi-platform CI matrix still needs its first remote execution.

## Phase 9 — explicit campaign policy selection

Industry problem: engineers need to compare candidate strategies without
mistaking a better result under different assumptions for approval of the
original proposal.

Introduce an explicit policy identity in a new analysis revision and evidence
schema. Compare baseline and guarded strategies under stated assumptions;
approval applies only to the selected, fully analyzed policy and evidence hash.
Add resource budgets or bounded outage requirements only with documented units
and deterministic semantics. Preserve both improvements and regressions in
comparison reports. Never silently replace failed baseline evidence with a
passing alternative or weaken rollback authorization.

Done when policy changes invalidate prior reviews, all required intermediate
checks remain active, and adversarial regression tests prevent cross-policy
approval or incomplete coverage from being accepted. Implemented rules and
verification are documented in [Phase 9](phase9.md). Resource/outage physics
were not expanded; all existing simulation assumptions remain explicit.

## Phase 10 — shared review and operational hardening, if needed

Industry problem: a local self-reported reviewer is insufficient for a shared
team review process.

Define the deployment scope first. Add authenticated reviewer identities,
permission roles, protected configuration, deliberate schema migrations,
SQLite backup/restore verification, retention controls, and immutable export
identifiers. For multiple hosts, select a suitable transactional database and
worker model rather than sharing a SQLite file over the network. Add deployment
and recovery documentation only for infrastructure actually exercised.

Done when unauthorized/stale decisions are rejected, migrations preserve prior
evidence, backups restore verified runs, and concurrent review behavior is
covered by integration tests. Implemented single-host controls and limits are
documented in [Phase 10](phase10.md). Live OIDC and network deployment are not
claimed as exercised. Shared mode remains optional for the local portfolio demo.

All phases remain simulation work. A richer simulator, more tests, or a recorded
approval does not establish behavior on real vehicles or regulatory certification.


## Phase 11 ? release validation and portfolio evidence

Local deliverables include reproducible demo bundles, restart/backup/restore
rehearsal, architecture documentation, genuine browser screenshots and recording,
and a release-oriented README. The user confirmed GitHub and OIDC are not
configured and requested setup documentation with those checks left pending.
See [Phase 11 evidence and release gates](phase11.md). No remote CI result or
live identity-provider result is claimed.
