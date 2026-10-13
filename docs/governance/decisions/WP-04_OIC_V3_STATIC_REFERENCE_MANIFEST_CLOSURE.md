# WP-04 OIC V3 Static Reference Manifest Closure

**Work package:** `WP04-OIC-V3-STATIC-REFERENCE-MANIFEST-CLOSURE`
**Change class:** `L1_PROFILE_REFERENCE_AND_IMMUTABLE_PIN_CLOSURE`
**Source-base snapshot:** `2186cd061ee126611f7afaacbbd9e8e2319ecc91`
**Status at source base:** review candidate; pending independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification.
**Target post-integration status:** integrated L1 static-reference governance record only; not a resolved profile, runtime evidence, or `ResolvedConfig`/`config_hash` payload.

## 1. Authority and scope

The frozen Architecture remains highest authority. OIC V3 is active abstract technical authority at the source base: `docs/OBSERVATION_INPUT_CONTRACT_V3.md`, source-file SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; its canonical semantic manifest is `docs/architecture/OBSERVATION_INPUT_CONTRACT_V3_SEMANTIC_MANIFEST.json`, semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`. These hashes identify different evidence roles.

Receipt v2 and QoS6 remain established pins under the integrated bundle approval. This candidate records one static reference manifest with exactly seven reference groups: the five abstract OIC V3 contract identities, final-issued receipt interface v2, and final-issued receipt QoS6. It creates no concrete runtime publisher/topic/package/profile source selection, measurement evidence, resolved `ObservationInputProfileV3`, `ResolvedConfig`, or `config_hash`; it is not itself a `config_hash` payload.

## 2. Reference groups and pin semantics

The canonical JSON record is `docs/governance/evidence/WP-04_OBSERVATION_INPUT_PROFILE_V3_STATIC_REFERENCE_MANIFEST.json`. Its `references` array contains exactly these seven groups:

| Group | Established identity/pin | What remains unresolved |
|---|---|---|
| `lidar_snapshot_contract` | `mecanum.observation.lidar-snapshot/v3` plus OIC semantic-manifest digest | Concrete runtime source and profile binding; applicable measurements/evidence |
| `local_reference_contract` | `mecanum.observation.local-reference/v3` plus OIC semantic-manifest digest | Concrete navigation/global-path source and profile binding |
| `measured_twist_contract` | `mecanum.observation.measured-twist/v3` plus OIC semantic-manifest digest | Concrete EKF publisher/configuration source and profile binding; required validity/evidence |
| `frame_tf_binding_contract` | `mecanum.observation.frame-tf-binding/v3` plus OIC semantic-manifest digest | Profile-specific immutable source and runtime transform evidence |
| `lifecycle_barrier_contract` | `mecanum.observation.lifecycle-barrier/v3` plus OIC semantic-manifest digest | Immutable policy source and concrete runtime binding |
| `final_issued_receipt_interface_v2` | `mecanum.final-issued-receipt/v2`, schema revision 2, source-file SHA and dependency-closure v1 SHA | No receipt-v2 change; no claim of ROSIDL generation or runtime delivery |
| `final_issued_receipt_qos_v6` | `mecanum.final-issued-receipt-topic-qos/v2`, revision 6, transport-manifest v2 SHA and full QoS document SHA | No QoS change; no claim of live compatibility or runtime behavior |

For the first five groups, the OIC source-file SHA identifies the document bytes and the semantic-manifest SHA identifies the canonical abstract semantics. The receipt group hashes, dependency-closure hash, transport-manifest hash, full QoS document hash, and approval-record hash identify distinct byte sets; they are not interchangeable. The manifest pins the exact source-base Git commit and paths alongside those established digests. It invents no per-contract digest, source, alias, measurement, or default.

## 3. Fail-closed and evidence boundary

The manifest is static reference governance only. It is not a resolved profile, runtime profile, `ResolvedConfig`, `config_hash` input, publisher/topic/package/launch selection, measurement record, or authorization. If a required runtime source pin, measurement, or evidence is missing, the future compiler must not resolve `ObservationInputProfileV3`, must emit no `ResolvedConfig` or `config_hash`, and Navigation/Gate B bring-up must not proceed. `PENDING_MEASUREMENT` remains pending. Defaults, aliases, legacy files, and simulation sources cannot substitute for missing authority or evidence.

Runtime publisher identity, live topic/QoS compatibility, frames/TF observations, freshness, samples, lifecycle/barrier occurrences, receipt instances, and measurement results remain outside this static manifest. No runtime validation is claimed.

## 4. Lifecycle wording and status boundary

At source base `2186cd061ee126611f7afaacbbd9e8e2319ecc91`, this is a review-candidate snapshot awaiting independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification. After those conditions are satisfied for the exact candidate, it is an integrated L1 static-reference governance record only. That status does not make it a resolved profile or runtime evidence and does not change the active OIC semantics, start/pass Gate B, close WP-04, or grant code/runtime authorization.

No status or dependency transition is made: WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives remain `PASSED`; Gate B remains `NOT_STARTED`; WP-05 remains `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.
