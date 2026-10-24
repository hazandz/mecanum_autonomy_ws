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


## Corrective F1–F10 — Run005 temporal-coherence integration

`supersedes`: the preceding implementation section's current-candidate base, phase-scope counts, and verification summary. The approved L2 design origin and semantic contract remain unchanged.

- Corrective base and required sole parent: `9856f025bcc4d9c008664ba41fb0589303e005da`.
- Approval/design origin: `OWNER_APPROVED_RUN005_TEMPORAL_L2_OFFLINE_66849EE6` at `66849ee6af092dce973075bcd438bd3d936fd2a3`.
- Semantic contract: `mecanum.step07-run005-temporal-coherence/v1`; SHA-256 `57aa6b871fd3bcdc4ae6eb2b6f7a0dcb66b07b927516b7b0969d5e47e5c36e59`.
- Phase A source/test scope: 16 exact paths. Phase A.5 pin-closure scope: 19 exact paths. Phase B actual scope: 23 exact paths. The base-guard authorized allowlist has 37 unique paths; unused allowance is not included in actual scope.

F1/F2/F3 bind ordered per-sample references to unique retained native lifecycle records, use revision+canonical-request digest ACKs, release discarded pending reservations, and retain committed exact records through finalization. F4 stops acquisition after five samples while action/deadline progress continues. F5 protects exact retained copies through ring rollover and guards unsigned eviction arithmetic. F6 registers native ingress tests in CTest and verifies case discovery. F7 rejects nested duplicate/malformed/BOM/non-finite/oversize/symlink reference inputs and latches worker/write failures. F8 adds per-sample temporal and native provenance proof and validates resealed mutations against retained records. F9 checks the actual imported helpers and actual loader-resolved resource against pins and selected install prefixes before acquisition. F10 rejects explicit null contract binding, preserves omission semantics, and checks both compiler entry points' sealed config hash.

Offline verification before Phase B: Step-7 tools 443 passed/2 historical-root checks skipped; bringup 386 passed; RL 745 passed; six-package external build passed; CTest discovered one observer target with 31 GTest cases (all passed), and ROSIDL package tests passed (8 cases); `py_compile` passed for 12 changed Python files. Historical 018/019 preservation tests were skipped because evidence-root variables were unavailable; no historical bundle was replayed or modified. Full post-Phase-B verification is required and is not preclaimed in this entry.

`SOURCE_FREEZE=TRUE` means only source/test and existing-pin closure for offline verification. Guard remains pending/capacity 1/acquisition 0/`NOT_GRANTED`; Gate B `NOT_STARTED`; runtime approval `NOT_APPROVED`. Invocation_021 remains `ROOT_CAUSE_UNRESOLVED`. Evidence ceiling: `IMPLEMENTED_OFFLINE_ONLY_PENDING_INDEPENDENT_AUDIT`.


## Final offline verification addendum — Run005 F1–F10

`supersedes`: the appended F1–F10 section's statement that post-Phase-B verification was still pending. The 23-path exact scope, 37-path allowlist, 53 source-pin membership, and guard state are unchanged. Final offline suites passed: Step-7 443/2 skipped (historical roots unavailable), bringup 386, RL 745, six-package build, observer CTest 31 GTest cases, ROSIDL 8 tests, py_compile 12 Python files, installed/source equality, source pins, strict parsers, hash chain, exact scope, ledger prefix and diff checks. Evidence remains `IMPLEMENTED_OFFLINE_ONLY_PENDING_INDEPENDENT_AUDIT`; no runtime is authorized or claimed.
