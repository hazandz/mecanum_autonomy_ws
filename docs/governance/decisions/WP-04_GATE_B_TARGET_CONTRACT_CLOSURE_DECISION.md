# WP-04 Gate B target-contract closure decision

**Status:** `SOURCE_PARENT_REVIEW_SNAPSHOT; POST_INTEGRATION_TARGET_GOVERNANCE_RECORD_ONLY`
**Work package:** `WP04-GATE-B-TARGET-CONTRACT-CLOSURE-DECISION`
**Exact integration base:** `701bb0cc5ca17b71e083d3ce4fdebd2bf46fbcee`
**Architecture:** `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`
**Active observation authority at base:** ACR technical revision 3, SHA-256 `38cb74c0b09cd9c3ecbbac30c6520e0d01f7711adb788414a0a46489e844d9f8`; Observation V3 Specification technical revision 5, SHA-256 `4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`; both activated at integration `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`.
**Decision provenance:** Owner decisions supplied in this work-package request. No separate decision artifact or audit-report hash is asserted.

## 1. Purpose and authority boundary

This record captures target semantics for Gate B inputs and keeps them separate
from canonical source selection and immutable profile pins. The Architecture
DOCX remains highest authority. At the stated source parent, this record and
the companion ACR record revision 6 / Specification revision 8 were review
candidates awaiting audit and a separate User integration decision. After the
exact successor is audited, separately authorized, fast-forwarded, and its
remote ref verified, this record and those revisions are integration-resident
target-governance records only. They are not active technical semantics and do
not supersede ACR revision 3 or Specification revision 5. Git ancestry alone
is not audit, approval, or activation evidence.

The Owner-selected target semantics are:

1. The canonical LiDAR target/TF child frame is exactly `lidar_frame`. There is
   no implicit alias to `RPLiDAR_A1M8_1`, `base_scan`, or namespaced variants.
   The profile must still identify an approved exact sensor/frame contract;
   no observed runtime scan frame or transform is claimed.
2. Gate B LocalReference means the navigation/global-path reference expressed
   in `base_link`, consistent with Architecture §45. The simulation source
   `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/goal_features.py`
   is provenance/reference only and is not selected as the Gate B source.
3. Measured twist comes from one fused-odometry publisher owned by the EKF,
   consistent with Architecture §§11 and 41. The operational immutable
   publisher/config/source pin remains unselected. This decision does not add
   a topic alias or claim a runtime publisher has been verified.
4. TF target ownership is localization provider for `map -> odom`, EKF for
   `odom -> base_link`, and robot description via `robot_state_publisher` for
   `base_link -> lidar_frame`. Physical geometry/extrinsic remains
   `PENDING_MEASUREMENT`; no transform value is supplied.
5. Lifecycle/reset/action-barrier behavior preserves active ACR3/Specification
   epoch/generation compatibility, exact lifecycle matching, receipt-after-
   action-and-reset-barrier eligibility, cutoff ordering, and fail-closed
   handling. No new immutable policy source is selected. Runtime lifecycle
   values, timestamps, sequence values, and barrier occurrences are not static
   profile/config-hash values.
6. No resolved `ObservationInputProfileV3` exists by virtue of these decisions.
   A required source/pin/evidence/measurement that remains unresolved prevents
   the whole resolved configuration and global `config_hash`; no partial
   profile/hash or Gate B pass is permitted.

These decisions are consistent with Architecture §13 (profile-specific sensor
frames, exact frame validation, and no silent correction), §§20 and 45 (81D
observation and global-path LocalReference in `base_link`), §§11 and 41
(filtered odometry and EKF ownership), and §17 (epoch/generation/barrier
synchronization). `lidar_frame` is the selected semantic target frame; the
profile-specific raw sensor frame and any explicit transform/source relation
must be pinned rather than treated as an alias. This distinction preserves the
Architecture's profile-specific sensor input and frame-mismatch fail-fast rule.

## 2. Established canonical receipt and QoS pins

Receipt v2 and QoS6 are already selected by the integrated bundle approval and
Registry and remain established, not pending:

| Pin | Established identity and immutable evidence | Boundary |
|---|---|---|
| Receipt interface | `mecanum.final-issued-receipt/v2`, schema revision 2; `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg`; source commit `2e7a2980cb75f0567182ea694c04328d7d8643e0`; SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a` | Schema/source pin only; receipt instances and payload are runtime facts. |
| Dependency closure | Version 1; `docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json`; SHA-256 `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73` | Distinct from interface and transport-manifest hashes. |
| Receipt topic/QoS | `mecanum.final-issued-receipt-topic-qos/v2`; QoS revision 6; `docs/RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST.json`; source commit `2e7a2980cb75f0567182ea694c04328d7d8643e0`; manifest SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`; full QoS6 document SHA-256 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022` | Approved contract/manifest pins; not ROS/QoS runtime compatibility evidence. |

These exact values are carried forward from active Registry/approval authority.
This candidate neither changes nor reclassifies them, and it does not claim
ROSIDL generation, live endpoint compatibility, or runtime delivery evidence.

## 3. Source-selection and evidence inventory

The active ACR3 profile schema requires immutable references for the input
contracts and concrete profile source. Target semantics do not fill those
reference values. The following six groups remain
`PENDING_OWNER_SOURCE_SELECTION` until an applicable active authority selects a
single source and its exact identity/revision, Git commit, repository path,
source-file SHA-256, distinct contract digest, and provenance are verified:

| Group | Target decision now recorded | What remains unselected/unverified | Minimum closure evidence |
|---|---|---|---|
| LiDAR snapshot | Canonical target frame `lidar_frame`; no aliases | Canonical snapshot contract/source and exact relationship between its profile-specific sensor frame and target frame | Explicit Owner/authority source selection, then exact immutable reference and distinct contract/source digests; any required geometry/extrinsic measurement remains separate. |
| LocalReference | Navigation/global-path reference expressed in `base_link` | Canonical typed snapshot contract/source; simulation `goal_features.py` is not selected | Approved source selection plus immutable source and semantic-contract pins. |
| Measured twist | One fused-odometry publisher owned by EKF | Operational publisher/config/source pin and canonical typed snapshot contract; no new topic alias is selected | Approved immutable operational source/config pin and contract reference; required validity, covariance, freshness, and provenance values/evidence. |
| Frame/geometry | Localization → `map -> odom`; EKF → `odom -> base_link`; robot description/`robot_state_publisher` → `base_link -> lidar_frame` | Canonical profile frame/geometry contract source; physical transform/extrinsic | Approved immutable frame-source pin; required physical geometry/extrinsic as `PENDING_MEASUREMENT`. |
| Lifecycle/reset/action barrier | Preserve active exact lifecycle, epoch/generation, after-barrier and fail-closed semantics | Immutable lifecycle/reset/action-barrier policy source/reference | Approved immutable policy source and exact contract pin; runtime occurrence values remain outside static config. |
| Concrete profile source | No profile instance is selected | Concrete immutable source that composes all required selected references | Owner/authority selection and exact commit/path/source-file digest; profile remains unresolved until all required pins and evidence resolve. |

The presence of a file in the Registry-approved V3 input family is not itself
selection of a canonical Gate B contract reference. In particular,
`ros2_ws/src/mecanum_nav_rl/config/v3/frames.yaml` records architecture
intention/input, but does not alone establish the required profile contract
identity and digest. OIC revision 6, drafts, review candidates, and source-code
examples are provenance only and cannot supply missing fields, defaults, IDs,
digests, aliases, or measurements.

## 4. Measurement and fail-closed boundaries

All applicable but unmeasured physical LiDAR geometry/extrinsic and the active
Specification's timing, sensor-freshness, synchronization-skew, timeout,
buffer, and measured-twist values remain `PENDING_MEASUREMENT`. This candidate
chooses no numbers, topic/config pin, package version, source SHA, contract ID,
or default.

The active ACR3 global hash policy remains in force without change: RFC 8785
JCS UTF-8 over the fully resolved, validated, static Architecture
`ResolvedConfig`, with only output `config_hash` omitted. Runtime timestamps,
sensor samples, receipt instances/payloads/sequences, lifecycle values,
barrier occurrences, freshness results, and raw ROS objects are invalid
resolved-config inputs and must be rejected, not silently filtered. Any
required unresolved source, pin, evidence, or measurement rejects the entire
resolved config; the compiler emits neither a partial profile nor a partial
hash.

## 5. Review-snapshot and post-integration target status; authorization boundary

At source parent `701bb0cc5ca17b71e083d3ce4fdebd2bf46fbcee`, this record and the
ACR/specification successors were review candidates pending focused independent
audit PASS and separate User authorization for the exact candidate. After those
conditions plus fast-forward and remote-ref verification, the records are
integration-resident target-governance records, not active technical semantics.
At that same source-parent snapshot, this correction successor was still
awaiting its own exact-candidate audit, User authorization, integration, and
remote-ref verification; that is historical candidate state, not an indefinite
post-integration status. No new canonical source is selected here. Gate B
remains `NOT_STARTED`; WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural
primitives remain `PASSED`; WP-05 remains `OPEN`. No code, test, ROSIDL,
adapter, runtime, HIL, hardware, or deployment authorization is granted.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
WP-05: OPEN
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```
