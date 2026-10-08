# WP-03 — Receipt Interface v2 Contract Proposal

**Status:** `DRAFT_FOR_INDEPENDENT_AUDIT_AND_USER_DECISION`
**Baseline:** `integration/implementation@9a4c0d233e8237f01a04880fe99e8a3114528f4`
**Proposed interface ID:** `mecanum.final-issued-receipt/v2`
**Proposed schema revision:** `2`
**Schema artifact:** `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_V2_DRAFT.msg`
**Schema SHA-256:** `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`
**Dependency-closure manifest:** `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST_V1.json`
**Dependency-closure manifest SHA-256:** `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`

This is a proposal for audit and user decision. The schema remains outside the ROSIDL package and is not implementation authority.

## 1. Authority and decision status

At the baseline, Receipt Topic QoS Contract revision 5 and ACR revision 7 are the current canonical documents, as recorded by the bundled approval record. They pin the receipt interface to `mecanum.final-issued-receipt/v1` and the historical SHA-256 `90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e`. The completed provenance search supplied by the user found no matching schema artifact. This proposal does not assign the v1 ID or hash to the v2 schema and does not claim compatibility with v1.

The source status for the D2 documents is `DRAFT — PENDING_USER_DECISION`. The Transition Provenance Decision Packet records D2-B, explicit `transition_id`, as `USER_SELECTED_FOR_CORE_ONLY_IMPLEMENTATION`. That is limited to core-only identity joining; it does not approve runtime receipt ownership, a public wire schema, UUID encoding, or profile boundary behavior.

All new wire-layout choices in this candidate—including `episode_generation:uint64`, `step_index:uint64`, flattened fields, `transition_id` bounded UUID text, and the UUID validation rule—are `PROPOSED_FOR_USER_DECISION`. They are not user-approved or canonical.

## 2. Source basis by scope

| Source | What it supports here | What it does not approve |
|---|---|---|
| QoS revision 5 §4 | The `CommandEnvelope`-mirrored fields and source constants; physical planar `final_command`; `final_publisher_instance_id:uint64`; `final_publish_sequence:uint64` and its sequence semantics; `CommandArbiter` safe-stop envelope ownership. | New `episode_generation`/`step_index` widths, UUID text, flattened wire layout, or the v2 identity. |
| `ros2_ws/src/mecanum_nav_rl_interfaces/msg/CommandEnvelope.msg` | Exact existing names, widths, and numeric source constants for `source`, `sequence`, `reset_epoch`, `runtime_generation`, `source_instance_id`, and `twist`. | Receipt-specific fields or any new identity encoding. |
| D2-B in `S3_Transition_Provenance_Decision_Packet_DRAFT.md` | User-selected explicit `transition_id` for core-only transition identity joining. | Public ROS wire representation, runtime token producer, receipt owner, or profile boundary. |
| D2 design and ownership drafts | Proposed receipt ownership/boundary, normalized representation, recovery, and future-evidence choices, with source status `DRAFT — PENDING_USER_DECISION`. | No unresolved D2 proposal is represented as an approved decision by this candidate. |
| This candidate's explicit wire choices | Proposed v2 layout and UUID rule, submitted for decision. | Canonical approval or implementation authorization. |

## 3. Proposed fields

The schema file contains the following exact proposal. The external closure manifest pins the referenced ROS message definitions by official repository, immutable commit, exact path, and file SHA-256.

| Field(s) | Proposed meaning / validation | Basis and status |
|---|---|---|
| `header` | `std_msgs/Header`; accepted frame is `base_link`; stamp uses the ROS-time domain and QoS action/reset-barrier comparison. | QoS rev.5 §§2, 6; dependency closure pinned separately. |
| `episode_generation`, `reset_epoch`, `runtime_generation` | Flattened lifecycle fields; `uint64`, `uint32`, `uint32`. | `reset_epoch` and `runtime_generation` mirror QoS §4 / `CommandEnvelope`; `episode_generation:uint64` and flattened layout are `PROPOSED_FOR_USER_DECISION`. |
| `step_index`, `transition_id` | Flattened transition fields; proposed `step_index` type is `uint64`, with no positive/minimum-value rule asserted here; proposed `transition_id` type is `string<=36`. Candidate UUID syntax is exactly 36 ASCII lowercase canonical characters, with hyphens at positions 9/14/19/24 and lowercase hex elsewhere; no UUID version/variant restriction. | D2-B supports only core-only explicit token joining. These candidate wire choices are `PROPOSED_FOR_USER_DECISION`; any `step_index` range/meaning remains `PENDING_USER_DECISION`. D2-B does not establish positive-step semantics. |
| `source` | `uint8`, with constants UNKNOWN=0, POLICY=1, NAV2=2, TELEOP=3, SAFE_STOP=4. UNKNOWN is non-ready. | QoS §4 and `CommandEnvelope.msg`. |
| `sequence`, `source_instance_id` | `uint64`; preserve `CommandEnvelope` names and semantics. | QoS §4 and `CommandEnvelope.msg`. |
| `final_publisher_instance_id` | `uint64`; identifies a `FinalTwistPublisher` process instance and changes on process restart. | QoS §4. |
| `final_publish_sequence` | `uint64`; begins at 1 per publisher instance, strictly increases per emitted receipt, and does not reset at `reset_epoch`. | QoS §4. |
| `final_command` | `geometry_msgs/Twist`; finite physical planar `base_link` velocity: `linear.x=vx`, `linear.y=vy`, `angular.z=wz`; other components exactly zero. | QoS §4. |

The UUID rule, public `/v2` identity and new field widths are choices proposed for user decision, not facts inherited from D2. No fields are added for normalized command, `config_hash`, profile, explicit boundary status, receipt owner, or transport-manifest data.

## 4. D2 draft items not represented in this schema

These omissions are not recorded as approved waivers. The applicable D2 drafts remain `DRAFT — PENDING_USER_DECISION`; the items below therefore remain pending unless the user separately decides them:

| D2 draft item | Treatment in v2 schema | Decision status |
|---|---|---|
| Normalized final command and exact conversion/provenance | Not a field. QoS §4 only requires the physical final command; D2 draft says normalized values require an exact conversion contract. | `PENDING_USER_DECISION`; no conversion is selected. |
| `receipt_id` versus command sequence identity | No standalone `receipt_id`; schema carries the QoS-defined `(final_publisher_instance_id, final_publish_sequence)` stream identity separately from transition identity. | Whether this fully satisfies any D2 core receipt-ID need remains `PENDING_USER_DECISION`. |
| `action_barrier_ros_ns` | No separate field; `header.stamp` remains the QoS receipt timestamp, and barrier ownership/comparison remains external under QoS §6. | Any additional D2 barrier representation remains `PENDING_USER_DECISION`. |
| `publish_or_handoff_status` | No status field; the candidate does not define a new profile or transport result encoding. | Status-field need and exact semantics remain `PENDING_USER_DECISION`. |
| `provenance_version`, safety/config hash, command-path identity | Not added; schema SHA and dependency-closure SHA are external pins. | Additional provenance fields remain `PENDING_USER_DECISION`. |
| Local steady receive-time diagnostic | Not included in the public receipt message. | The D2 design draft describes this as optional; inclusion and diagnostic ownership remain `PENDING_USER_DECISION`. |
| Receipt owner and successful profile boundary | Not encoded as message fields. QoS §2 identifies the logical publisher; detailed D2 ownership/boundary drafts remain pending. | D2 ownership and boundary dispositions remain `PENDING_USER_DECISION` except where QoS itself defines existing transport behavior. |
| Failure/recovery, reset clearing, post-issue abort, and runtime evidence | No new schema fields or behavior are introduced. | D2 proposals/evidence obligations remain pending; this proposal does not waive them. |

## 5. v1 and v2 identity disposition

The existing v1 ID/hash remain historical provenance. The proposed v2 ID is not a repointing of v1. If approved, the full QoS6/ACR8 bundle will expressly replace the operative pin while preserving v1 historical values. Schema SHA, dependency-closure SHA, transport-manifest SHA, and full-document hashes are separate identities and must not be substituted for one another.

## 6. Canonical dependency closure

The closure manifest pins these exact transitive message definitions:

| Dependency | Official repository | Immutable source commit | Exact path | SHA-256 |
|---|---|---|---|---|
| `std_msgs/msg/Header.msg` | `https://github.com/ros2/common_interfaces.git` | `a941f14bb318d8d904505ed935ccbb97f24a70a4` | `std_msgs/msg/Header.msg` | `d2cea14630e39ed0fa5b432ba9160a7c38855b9427d3344f99e83e83facb53c2` |
| `builtin_interfaces/msg/Time.msg` | `https://github.com/ros2/rcl_interfaces.git` | `7aa3caf43377ea6ad615bc1040832e2c7566bfbe` | `builtin_interfaces/msg/Time.msg` | `dc5a01ddde3aecffee21eb24974fe77cc969f873218a2b1811aa0ac8a456b8bd` |
| `geometry_msgs/msg/Twist.msg` | `https://github.com/ros2/common_interfaces.git` | `a941f14bb318d8d904505ed935ccbb97f24a70a4` | `geometry_msgs/msg/Twist.msg` | `ed471ef861f65af991b1f64d66ef941dd41dd4c0702f6222512b1a16c62d58b0` |
| `geometry_msgs/msg/Vector3.msg` | `https://github.com/ros2/common_interfaces.git` | `a941f14bb318d8d904505ed935ccbb97f24a70a4` | `geometry_msgs/msg/Vector3.msg` | `d8b9ea9aad1f424faf4d2b94dae1e1368af1e5d59de11aeed019399cff7f9e1d` |

The immutable commits were resolved from release tags `5.3.8` and `2.0.4`; the official source file hashes were checked against the installed ROS Jazzy message bytes. The manifest SHA-256 identifies the closure manifest bytes, not the `.msg`, transport manifest, or full contract documents.

### 6.1 Proposed canonical target paths

The Registry identifies the canonical interface directory family but does not specify the exact new message filename or manifest locations. The following paths are concrete proposals for user/governance decision; they are not canonicalized by this document:

| Artifact | Proposed canonical target path | Status and byte-identity condition |
|---|---|---|
| Receipt schema | `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg` | `PROPOSED_FOR_USER_DECISION`; on any later approved integration, bytes must match the proposal `.msg` SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`. |
| Dependency-closure manifest | `docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json` | `PROPOSED_FOR_USER_DECISION`; bytes must match the pinned closure-manifest SHA-256 `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`. |
| Standalone transport manifest JSON | `docs/RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST.json` | `PROPOSED_FOR_USER_DECISION`; bytes must match the pinned transport-manifest SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620` and remain byte-identical to the manifest embedded in QoS §4. |

The matching candidate artifacts remain at their proposal paths. Path selection alone does not approve or canonicalize these files.

## 7. Transport and companion pins

The proposed transport manifest is `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST_V2_DRAFT.json`, version `2`, ID `mecanum.final-issued-receipt-topic-qos/v2`. It includes the interface v2 ID, `.msg` SHA-256, and closure-manifest SHA-256. Its exact SHA-256 is `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`. QoS policy and transport behavior values are carried forward unchanged.

The schema SHA covers only `WP-03_RECEIPT_INTERFACE_V2_DRAFT.msg`; the closure manifest SHA `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73` covers only its JSON manifest; the transport-manifest SHA covers only the transport JSON; and QoS6/ACR8 full-document SHA values cover their respective complete Markdown bytes. These are distinct pins.

## 8. Effect

QoS5/ACR7 and their bundled approval record remain canonical authority until a new bundle is independently audited, approved by the user, and canonically integrated. These drafts do not amend canonical files, close WP-03, change WP-04 dependency/status, or grant implementation, code, ROS, runtime, HIL, hardware, or `deploy_real` authorization.

```text
WP-02: CLOSED
WP-03: BLOCKED_BY_CONTRACT
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```
