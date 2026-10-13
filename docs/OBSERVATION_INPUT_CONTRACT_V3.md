# Observation Input Contract V3

**Document revision:** `1`
**Change class:** `L2_ARCHITECTURE_CONTRACT_AND_PUBLIC_TYPED_BOUNDARY`
**Status at source base `5497b7e1938242422594f8150b06a32fe221ee70`:** review-candidate snapshot; not active technical authority
**Manifest:** `docs/architecture/OBSERVATION_INPUT_CONTRACT_V3_SEMANTIC_MANIFEST.json`
**Semantic-manifest SHA-256:** `769f96b929393239bc293af68d2418512b171dc5abf8e5135d796875847d8d77`

This document defines an abstract, typed and fail-closed contract boundary for future Gate B inputs. The semantic-manifest digest identifies the canonical JCS bytes for the complete five-contract set; it is not a source-file digest. The source-file digest of this document identifies only these document bytes and is recorded separately by Git/evidence after candidate creation. No contract instance, source pin, runtime observation, or resolved profile is created here.

## 1. Authority, lifecycle, and scope

The highest authority remains `docs/MECANUM_NAV_DRL_Architecture.docx` (SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`). Active Observation V3 technical authority remains ACR revision 3 and Specification revision 5, including the global 16-root `ResolvedConfig.config_hash` projection, RFC 8785 JCS, the nested `observation.input_profile` location, full-config rejection, and the existing receipt v2/QoS6 pins. This revision-1 document is a proposed L2 successor. It becomes an integration-resident target-governance record only after independent audit PASS, separate exact-commit User authorization, fast-forward, and remote-ref verification. Even then, its technical semantics do not activate until a separate activation/change-control explicitly makes them effective. Until that separate activation, ACR revision 3 and Specification revision 5 remain the active technical authority.

This contract defines five abstract identities, all revision `v3`:

| Contract ID | Abstract boundary |
|---|---|
| `mecanum.observation.lidar-snapshot/v3` | Raw angular LiDAR snapshot before sectorization and its 72-sector observation result. |
| `mecanum.observation.local-reference/v3` | Navigation/global-path reference represented in `base_link` and its three observation features. |
| `mecanum.observation.measured-twist/v3` | Base-frame measured twist components `[vx, vy, wz]`. |
| `mecanum.observation.frame-tf-binding/v3` | Static target TF ownership binding plus separately verified runtime transform evidence. |
| `mecanum.observation.lifecycle-barrier/v3` | Exact lifecycle/config identity and receipt admission across action/reset barriers and cutoff. |

The single semantic-manifest SHA-256 above is the semantic digest for this versioned contract set. No per-contract digest, concrete profile source, or source-file pin is asserted. Any later source reference must separately carry an exact contract identity/revision, immutable Git commit and path, source-file SHA-256, and applicable semantic-manifest digest; source bytes and semantic-manifest bytes are different hash domains.

## 2. Shared snapshot identity and admission

Each of the LiDAR, LocalReference, measured-twist, and final-issued-receipt runtime inputs carries the same required identity values:

| Member | Abstract exact type/domain | Rule |
|---|---|---|
| `episode_generation` | Receipt-v2-compatible `uint64` value | Required; exact equality. |
| `reset_epoch` | Receipt-v2-compatible `uint32` value | Required; exact equality. |
| `runtime_generation` | Receipt-v2-compatible `uint32` value | Required; exact equality. |
| `config_hash` | Lowercase 64-hex SHA-256 string for the global resolved configuration | Required in each typed snapshot and the receipt ingress context; exact equality. |

The four-value identity is compared atomically and exactly across every typed input and the `FinalIssuedCommandReceipt` ingress context. Receipt v2 itself remains byte-identical and has no `config_hash` field; this contract does not add one or define a message wrapper. A future separately authorized ingress boundary must bind the unchanged receipt instance to the applicable global `config_hash`. Partial match, missing identity/binding, stale/unready input, inferred alias, default, coercion, unverified runtime provenance, or invalid receipt rejects the input set. The pure core produces no observation vector unless all required typed inputs are admitted. There is no repair, fallback, reuse, or partial-vector behavior.

The identity is a runtime ingress binding, not a new `ResolvedConfig` root or a runtime fact stored in static configuration. The snapshot's `config_hash` value refers to the already-resolved global configuration; it does not introduce a Gate-B-only hash.

## 3. Typed input semantics

The types below describe abstract typed values at the core boundary. They do not select ROS message types, package versions, source files, topics, publishers, transport details, or a serialization/wire format. Those require their own approved immutable source selection and, where semantics or a public runtime interface are introduced, the applicable change-control. All required values must be present and validated; the core does not fill missing values.

### 3.1 LiDAR snapshot

The source value represents a raw angular scan before sectorization. Its canonical target frame is exactly `lidar_frame`. `RPLiDAR_A1M8_1`, `base_scan`, `lidar_link`, legacy names, and namespaced variants are not aliases. The observation result contains exactly 72 finite sector values in Architecture-defined order and normalization; this contract does not select numeric range, invalid/no-return handling, or normalization parameters beyond that active Architecture boundary.

The raw angular sample representation and ROS message/driver/header source are not selected here. Range limits, geometry/extrinsic, cadence, latency, freshness, scan–twist skew, timeout, and buffer limits remain `PENDING_MEASUREMENT` or require later profile-specific source selection. `observations/lidar.py` V1 is structural algorithm provenance only, not a runtime snapshot or ingress contract.

### 3.2 LocalReference snapshot

The value derives from the navigation/global-path reference and is expressed in `base_link`. Its exact ordered feature shape is `distance`, `sin_bearing`, `cos_bearing`, corresponding to the three LocalReference entries in the 81D observation. Feature values are typed finite observation values after the authority-approved transform/normalization boundary; this contract invents no limits, normalization constants, freshness values, source provider, topic, or message type. `observations/goal_features.py` and simulated odometry are not runtime canonical sources. Provider, typed source, transform evidence, freshness, and provenance remain unselected.

### 3.3 Measured-twist snapshot

The value has exactly the base-frame components `vx`, `vy`, and `wz`, in that order, corresponding to the three measured-twist entries in the 81D observation. The target runtime owner is one EKF fused-odometry publisher; the EKF remains the sole owner of `odom -> base_link`. No operational publisher, topic, message type, package/config pin, covariance policy, validity limit, freshness policy, or source provenance is selected here. Those values/evidence remain pending as applicable. Simulated odometry is not runtime authority. An invalid or out-of-range value is rejected; clipping, zero-fill, and fallback are forbidden.

### 3.4 Frame/TF binding

The target edge ownership is exact: localization owns `map -> odom`; the EKF owns `odom -> base_link`; robot description/`robot_state_publisher` owns `base_link -> lidar_frame`. This ownership is a static target contract, not runtime evidence. No frame alias is inferred. Physical transforms, LiDAR extrinsic, alignment, publisher uniqueness, and transform freshness require separately pinned sources and measurement/runtime evidence; they remain unverified here.

### 3.5 Lifecycle/barrier and final-issued receipt

`SafetyLifecycle` is the sole owner of action/reset barriers. The lifecycle tuple is exactly `(episode_generation, reset_epoch, runtime_generation)` with the domains in §2. An eligible final-issued receipt must match that tuple and `config_hash` exactly, occur strictly after the applicable action and reset barriers, and be no later than the observation cutoff. Missing, ambiguous, invalidated, pre-barrier, post-cutoff, stale, or unverifiable input is non-ready/no-vector under the existing ACR8 status mapping; this contract creates no status vocabulary.

The final-issued receipt remains the established receipt v2 interface and QoS6 transport authority. The message and transport contract are not changed. A PPO action, decoder output, actuator acknowledgement, cached command, or synthetic zero is not a substitute for an eligible receipt. Barrier occurrences, timestamps, sequence values, receipt instances/payloads, and freshness results are runtime facts; they are not static profile/config-hash values. Receipt/QoS compatibility or live delivery is not demonstrated by this document.

## 4. Adapter/core and simulator boundary

A future separately authorized adapter is the only layer that may receive raw ROS/generated objects. Before creating typed snapshots it must verify message type, QoS, frame, freshness, provenance, lifecycle identity, and barrier ordering against separately selected sources and evidence. The pure core consumes only typed, already-validated values. It performs no ROS import, I/O, clock read, repository/source lookup, implicit transform, or fallback. Any failure to prove required admission yields no vector.

`sim_train` does not fabricate ROS odometry, TF, or time. It may provide typed internal simulator facts only through a separate boundary; those facts do not become a runtime canonical source. Ground truth must not leak into policy observation.

## 5. Static profile and global hash boundary

The five contract semantics are intended to be referenced by a future static `ObservationInputProfileV3` nested at `ResolvedConfig.observation.input_profile`. This document supplies no concrete immutable source references and does not instantiate or resolve that profile. There is no root `gate_b`, Gate-B-only hash, or partial profile/hash. The active ACR revision 3 / Specification revision 5 global hash policy and exhaustive 16-root projection remain unchanged.

Runtime lifecycle values, timestamps, samples, receipt instances/payloads, sequences, barrier occurrences/results, freshness results, raw ROS objects, and runtime observations are not valid static resolved-config members. If present as resolved-config input, they are rejected rather than silently filtered. A future compiler rejects the entire resolved config and emits neither a partial profile nor a partial hash if any required source/pin/evidence is missing or unverifiable, or if a required measurement remains `PENDING_MEASUREMENT`.

The following remain pending and are not replaced by values in this document: concrete source selection and immutable references for each required profile group; LiDAR range/geometry/extrinsic and timing; LocalReference provider/transform/freshness; measured-twist source/validity/covariance/freshness; TF alignment and publisher evidence; lifecycle/barrier policy source and receipt-after-barrier timeout; and profile-source composition. No source pin, contract ID beyond the five IDs above, per-contract digest, alias, default, topic, package version, timeout, geometry, measurement, or runtime evidence is fabricated.

## 6. Migration, acceptance evidence, and status

The L2 change, if separately activated, introduces abstract typed-boundary semantics that existing code/configuration is not presumed to satisfy. Future implementation requires its own exact code authorization. Before implementation readiness, independent acceptance evidence must establish the exact source/provenance bindings, structural rejection behavior, identity matching, no-vector failure behavior, profile/compiler interaction with the active global hash, and preservation of the 81D layout and simulator/runtime separation. ROS adapter/QoS evidence and runtime/HIL evidence are separate later layers; this candidate produces none.

At source base `5497b7e1938242422594f8150b06a32fe221ee70`, this document and its companion candidate records are review snapshots pending independent audit and separate exact-commit User authorization and integration. After those conditions and remote-ref verification, they are integration-resident L2 target-governance records. They do not activate the new semantics; ACR revision 3 and Specification revision 5 remain active technical authority until separate activation/change-control. This candidate does not resolve a profile, start/pass Gate B, close WP-04, alter WP-05, or grant code/runtime/HIL/hardware/deployment authorization.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
WP-05: OPEN
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```
