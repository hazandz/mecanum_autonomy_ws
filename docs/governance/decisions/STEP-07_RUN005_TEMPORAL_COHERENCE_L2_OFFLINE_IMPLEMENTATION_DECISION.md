# Run005 temporal coherence L2 — offline implementation decision

**Status:** `IMPLEMENTED_OFFLINE_ONLY_PENDING_INDEPENDENT_AUDIT`
**Approval ID:** `OWNER_APPROVED_RUN005_TEMPORAL_L2_OFFLINE_66849EE6`
**Approved design commit:** `66849ee6af092dce973075bcd438bd3d936fd2a3`
**Contract:** `mecanum.step07-run005-temporal-coherence/v1`
**Semantic SHA-256:** `57aa6b871fd3bcdc4ae6eb2b6f7a0dcb66b07b927516b7b0969d5e47e5c36e59`

This record distinguishes the Owner’s design approval and offline implementation authorization from runtime authorization. Production source and offline tests were authorized. `production_implementation_authorized` records that this offline packet was authorized and implemented; `runtime_authorized=false`. No official runner, campaign runtime, invocation, or integration was authorized or performed by this corrective.

## Lineage and scope

- Branch: `step07-integrated-nav2-gateb-campaign-f7f98c6`
- Implementation base and required sole parent: `66849ee6af092dce973075bcd438bd3d936fd2a3`
- Campaign integration base: `f7f98c683d59cf4c62e462da9f37d4ffb2455c80`
- Audited integration tip: `fdc0e299515bda2286832aabec635948629517b5`
- Phase A source/test paths: 26
- Phase A.5 exact scope after pin closure: 29
- Phase B exact changed-path scope: 33
- Authorized allowlist: 37 paths; authorization is not a claim that every allowed path changed.
- `SOURCE_FREEZE=TRUE` denotes offline source/test and source-pin closure only.

The exact current path sets and their phase/base are recorded in the Run005 guard and evidence. Historical source, runtime evidence, consumed guards, locks, and Invocation_014–021 artifacts are outside this change.

## Implemented contract

The Run005 config compiler binds `navigation.temporal_coherence_contract` to the approved semantic ID and digest, includes the binding in the existing global configuration hash, and leaves profiles that omit the policy unchanged. The regenerated Run005 resolved config has global `config_hash` `4fac960ff2298cefd1b261db314bfa8e802855f8cb6290b762594658982b7925`.

The Python collector implements the approved fixed-trigger timestamp and nonblocking exact-time TF state machine, request/result identity binding, immutable admitted path context, one pending observation snapshot, exact pinned correlation records, rollback/context invalidation, and final freshness/deadline/context checks after transform. It preserves transform exceptions and does not substitute a latest transform or mutate raw path input.

The C++ observer adds a private lifecycle ingress that validates the pinned endpoint and per-message publisher GID, uses Linux `CLOCK_MONOTONIC` for cross-process receive provenance, bounds queue/history/artifacts and references, atomically publishes admitted lifecycle records, and retains the exact acknowledged records used. Missing or contradictory provenance and required-data loss fail closed. No public ROS message or QoS contract was changed.

Runner and validator bind the temporal contract, ingress session, and native record references to the candidate bundle. Existing five-vector, navigation, QoS, safety, evidence-chain, and teardown acceptance remain in force. Source guard semantics remain pending/capacity one/acquisition zero/runtime authorization not granted; Gate B remains not started and runtime remains not approved.

## API and source-pin inventory

Local package/header fingerprints inspected for the implementation:

| Item | Version | SHA-256 | Bytes |
|---|---:|---|---:|
| `rclcpp` package.xml | 28.1.21 | `4402906749a1c8f95f624c28bd1ad9247b21826fba3a8d7cb532f0eb563a6040` | 2669 |
| `rmw` package.xml | 7.3.3 | `3b77f89b2ec4e12201bab5d7d0dd5b3f5738a0b19cb385659c51feaa288856bf` | 1479 |
| `rclcpp/message_info.hpp` | installed Jazzy header | `f6e33622fcd17a82ffb10a4d6639104ca2f2749f33a0f54068dc590ed5294a08` | 1628 |

The current source-pin inventory has 53 members: the prior 38 members plus 15 newly used config, temporal, lifecycle-ingress, packaging, and regression-test dependencies. Every entry records SHA-256 and exact byte size. The 53-member inventory is shared consistently by the guard, evidence, and manifest; those metadata files are excluded from self-referential pin cycles.

## Verification status

Offline verification completed: Step-7 tools 433 passed/2 skipped; full bringup 375 passed; full RL 740 passed; six-package external build passed; observer/ROSIDL 33 tests passed with zero failures; 18 changed Python files compiled; 22 installed/source artifacts, modules and resources matched byte-for-byte. Strict JSON/canonicality, semantic digest, YAML/XML/SDF parsing, 53/53 source-pin SHA-256/byte-size closure, exact Phase B scope (33 paths, separate 37-path authorization), guard/evidence/manifest coherence, ledger parent-byte-prefix and diff checks passed.

The two Step-7 skips are the Invocation_018 and Invocation_019 immutable-bundle checks; the test reports `external immutable invocation evidence root not configured`. They were not enabled because the task prohibits replaying historical bundle checksum/validator checks. No before/after historical inventory was captured in this execution, and no command wrote to historical evidence roots. Final metadata hashes are recorded in the candidate evidence/manifest after exact-byte serialization.

Evidence ceiling: `IMPLEMENTED_OFFLINE_ONLY_PENDING_INDEPENDENT_AUDIT`. Invocation_021 remains `ROOT_CAUSE_UNRESOLVED`; this implementation does not claim that its historical timeout cause was confirmed or repaired. Runtime, Gate-B, and real-robot readiness remain unapproved.
