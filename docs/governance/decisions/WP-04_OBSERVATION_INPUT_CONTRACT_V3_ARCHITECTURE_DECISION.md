# WP-04 Observation Input Contract V3 Architecture Decision

**Work package:** `WP04-OBSERVATION-INPUT-CONTRACT-V3-ARCHITECTURE-CLOSURE`
**Change class:** `L2_ARCHITECTURE_CONTRACT_AND_PUBLIC_TYPED_BOUNDARY`
**Decision basis:** Owner-approved decisions in the work-package prompt
**Exact source base:** `5497b7e1938242422594f8150b06a32fe221ee70`
**Architecture:** `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`
**State at source base:** review-candidate snapshot; ACR revision 3 and Observation V3 Specification revision 5 remain active technical authority.

This decision records the Owner-approved abstract Gate B contract set. It does not infer authority from Git ancestry and is not active technical semantics at the source base. After independent audit PASS, separate exact-commit User authorization, fast-forward, and remote-ref verification, it becomes an integration-resident L2 target-governance record; a separate activation/change-control is still required before its technical semantics become active. Until then, ACR revision 3 and Specification revision 5 remain active.

## 1. Authority and unchanged pins

The frozen Architecture DOCX is highest authority. Active Observation V3 technical authority is ACR revision 3, activated at integration `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`, with active Specification revision 5 SHA-256 `4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`. The active global `ResolvedConfig.config_hash` covers the exhaustive 16-root Architecture envelope using RFC 8785 JCS; only output `config_hash` is excluded. `observation.input_profile` remains nested; no root `gate_b` or Gate-B-only hash exists.

Receipt v2 and QoS6 are established pins and are unchanged: receipt interface ID `mecanum.final-issued-receipt/v2`, schema revision 2, source path `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg`, SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`; dependency-closure v1 SHA-256 `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`; QoS6 transport ID `mecanum.final-issued-receipt-topic-qos/v2`, transport-manifest SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`, and QoS6 full-document SHA-256 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`. These are distinct pin domains. No receipt field or transport bytes change.

## 2. Owner-approved abstract contract set

The candidate defines the five revision-`v3` identities below, without selecting concrete source files or profile instances:

| Contract ID | Approved abstract semantics | Still outside this decision |
|---|---|---|
| `mecanum.observation.lidar-snapshot/v3` | Raw angular scan before sectorization; exact target `lidar_frame`, no inferred aliases; exactly 72 finite sector outputs. | ROS type/driver/header source, ranges, normalization parameters not fixed by active authority, geometry/extrinsic and all timing/freshness/skew/timeout/buffer measurements. |
| `mecanum.observation.local-reference/v3` | Navigation/global-path reference expressed in `base_link`; ordered outputs `distance`, `sin_bearing`, `cos_bearing`. | Provider, typed source, topic/type, transform evidence, freshness and provenance. Simulation goal source is not runtime authority. |
| `mecanum.observation.measured-twist/v3` | Base-frame components `[vx, vy, wz]`; target semantic owner is one EKF fused-odometry publisher. Invalid/out-of-range values fail closed without clipping, zero-fill or fallback. | Operational publisher/topic/type, covariance/validity/freshness policy, package/config/source pins and measurements. Simulated odometry is not runtime authority. |
| `mecanum.observation.frame-tf-binding/v3` | Target owners: localization `map -> odom`; EKF `odom -> base_link`; robot description/`robot_state_publisher` `base_link -> lidar_frame`; no inferred frame aliases. | Physical transform, extrinsic, alignment, publisher uniqueness and freshness evidence. |
| `mecanum.observation.lifecycle-barrier/v3` | `SafetyLifecycle` solely owns action/reset barriers. Exact tuple `(episode_generation, reset_epoch, runtime_generation)` and receipt-after-barrier/before-cutoff admission. | Immutable concrete policy/source pin, observed barrier occurrences, timestamps, sequences, timeout and runtime evidence. |

The canonical semantic payload is the complete JCS manifest at `docs/architecture/OBSERVATION_INPUT_CONTRACT_V3_SEMANTIC_MANIFEST.json`, SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`. The companion contract document source-file SHA-256 at this candidate content is `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`. The manifest source-file SHA-256 equals its semantic-manifest digest because the exact file bytes are the canonical JCS payload; the two labels retain distinct evidence roles. No per-contract digest is asserted.

Each runtime snapshot and the receipt ingress context must match exactly and atomically on `episode_generation`, `reset_epoch`, `runtime_generation`, and global `config_hash`. The receipt v2 message has no `config_hash` field; the unchanged receipt is associated with the resolved global hash outside that message by a future separately authorized ingress mechanism. No ROS wrapper/message shape is created by this decision. Missing, mismatched, stale, unready, aliased, defaulted, coerced, partial, invalid or unverifiable inputs fail closed and produce no 81D observation vector.

## 3. Typed boundary, evidence, and migration

The companion contract `docs/OBSERVATION_INPUT_CONTRACT_V3.md` defines abstract required typed values and the pure-core/adapter seam. The core receives only typed, already-validated snapshots. A separately authorized adapter must establish middleware type, QoS, frame, freshness, provenance, lifecycle and barrier validation before presenting them. No source file, concrete profile, topic, ROS interface type, package version or runtime publisher has been selected.

All four inputs and receipt must share the exact identity above. Receipt must be strictly after the applicable action/reset barriers and no later than observation cutoff. A failure yields non-ready/no-vector using existing authorized ACR8 mappings; no new status vocabulary is created. `sim_train` may use typed internal simulator facts only at a separate boundary, does not fabricate ROS odometry/TF/time, is not runtime canonical authority, and must not expose ground truth to policy observation.

This L2 boundary changes the future contract semantics and requires later compatibility/migration analysis before implementation. Existing code is not presumed conformant. Required future evidence includes exact source/profile pins, static contract rejection evidence, shared-identity and barrier admission evidence, global-hash/compiler compatibility, 81D preservation, and simulation/runtime isolation. ROS adapter/QoS integration and runtime/HIL/hardware evidence remain separate later gates. The present candidate creates no code, ROSIDL, adapter, compiler, tests, profile instance, runtime config, or evidence artifact.

## 4. Pending items and fail-closed behavior

The six concrete profile-reference groups remain unresolved: LiDAR snapshot source; LocalReference source; measured-twist source; frame/geometry source; lifecycle/reset/action-barrier policy source; concrete profile source. Required pins/evidence not yet approved remain pending. Applicable unmeasured LiDAR range/geometry/extrinsic, timing/cadence/latency/freshness/skew/timeout/buffer, LocalReference transform/freshness, measured-twist validity/covariance/freshness, TF alignment/publisher uniqueness, lifecycle receipt timeout, and other source-dependent values remain `PENDING_MEASUREMENT` where measurement is required.

No source pin, contract ID beyond the five approved IDs, per-contract digest, topic, alias, default, package version, geometry, timeout, measurement, runtime fact or resolved-profile value is invented. If any required future source, pin, evidence or measurement is missing/unverifiable, the compiler must reject the entire resolved configuration and emit no partial profile or hash. Runtime observations and raw ROS/receipt objects are invalid static config/hash inputs and must be rejected, not filtered.

## 5. Status and authorization boundary

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
WP-05: OPEN
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```

This decision does not resolve `ObservationInputProfileV3`, start or pass Gate B, close WP-04, change WP-05, or grant code, ROS/ROSIDL, runtime, HIL, hardware, or deployment authority.
