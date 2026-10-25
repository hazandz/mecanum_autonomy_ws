# ACR — Step 7 research-grade runtime acceptance simplification (L2)

**Decision ID:** `STEP07_RESEARCH_GRADE_RUNTIME_ACCEPTANCE_SIMPLIFICATION_L2`
**Owner authorization:** `OWNER_APPROVED_STEP07_RESEARCH_GRADE_SIMPLIFICATION_L2_OFFLINE_IMPLEMENTATION`
**Authority:** Architecture SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`
**Scope:** Step 7, `sim_eval` / `NAV2_BASELINE` research-grade integrated runtime acceptance.

## Decision

Replace the active Run005 forensic acceptance model with one runner, one in-process ROS observer, one rosbag recorder, a pure A1–A10 evaluator, local bounded synchronization, and six direct evidence heads. This decision retains the frozen Architecture invariants for TF authority, Ground Truth isolation, Observation V3, command ownership, Safety, map identity, and global resolved-config hashing.

The owner-approved SIM_BASELINE values and A1–A10 semantics are defined by the implementing authorization prompt and the versioned `navigation.step07_acceptance` policy. That policy is part of the existing complete `ResolvedConfigV3` and its existing global `config_hash`; no independent digest is introduced.

## Retired from active acceptance

Retire the 53-member source-pin inventory and refresh/closure phases; `mecanum.step07-run005-temporal-coherence/v1`; native lifecycle reservation and ACK/RELEASE; retained-record and cross-process monotonic protocols; per-sample GID proof; sealed sidecars and terminal/collection handshakes; failure settlement; nested validators; manifest/hash hierarchies; historical replay and availability prerequisites; tracked source-guard mutation; detached runtime checkout; and the C++ forensic observer dependency. Historical source, guards, runtime records, and outcomes remain preserved and are not rewritten.

`RUN005_FORENSIC_CAMPAIGN = RETIRED_AS_ACTIVE_ACCEPTANCE_MODEL`
`HISTORICAL_RECORDS = PRESERVED`
`INVOCATION_021_ROOT_CAUSE = ROOT_CAUSE_UNRESOLVED`

## Evidence boundary

This ACR authorizes only the bounded offline implementation scope specified by the owner. It does not authorize runtime execution, campaign invocation, Gate B, HIL, hardware, integration, or deployment. Until separate runtime authorization and review, the status remains `IMPLEMENTED_OFFLINE_ONLY`, `RUNTIME_AUTHORIZATION = NOT_GRANTED`, `GATE_B = NOT_STARTED`, and `REAL_READY = NOT_CLAIMED`.

## Candidate evidence snapshot

Candidate branch: `step07-research-runtime-simplification`, based on `fdc0e299515bda2286832aabec635948629517b5`. Offline evidence: fresh five-package build completed; the selected RL test set reports 727 passed/2 deselected, excluding the graph-creating lifecycle test and stale pure-only observation-source scan; bringup reports 237 passed with one stale WP05 source-pin assertion excluded; Fuel bootstrap reports 13 passed; base bridge reports 121 passed; interfaces report 8 passed; Step-7 tooling reports 5 passed; focused A1–A10/core/observer tests report 21 passed. The legacy RL nested-suite aggregator was excluded because it invokes the stale source scan internally. An earlier broad RL invocation did execute the lifecycle unit test before its graph-creating behavior was identified; no simulator, Nav2 launch, or campaign runner was started. The full build/test command results and exclusions are documented in the delivery report; this snapshot does not certify runtime behavior.
