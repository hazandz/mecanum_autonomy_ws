# Observation V3 Specification

**Revision:** `1`
**Status:** `CANDIDATE_ONLY_PENDING_FOCUSED_AUDIT_AND_CANONICAL_INTEGRATION`
**Work package:** `WP-04-GATE-B-CONSOLIDATED-BOUNDARY-CLOSURE`
**Candidate base:** `origin/integration/implementation@50476170bb545483905308e5887990ab6220c566`
**Runtime status:** `RUNTIME_NOT_APPROVED`

This controlled specification candidate records the Owner decisions supplied for Gate B boundary closure. It is not active authority before focused independent audit, separate User authorization for the exact final commit, fast-forward to `integration/implementation`, and remote-ref verification. It does not pass Gate B, close WP-04, or authorize implementation or runtime.

## 1. Authority and exact pins

The governing architecture remains `docs/MECANUM_NAV_DRL_Architecture.docx`. Current approved Gate A/Gate B contract authority is ACR revision 8 and Receipt Topic QoS Contract revision 6, as selected by the Canonical Source Registry and the integrated bundled approval record. Their source files retain historical pre-integration `DRAFT` wording; that wording is superseded only for document authority/status by the approval record and Registry, not for technical content.

| Artifact | Exact identity | Canonical path | SHA-256 |
|---|---|---|---|
| ACR | revision 8 | `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md` | `03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c` |
| Receipt Topic QoS Contract | revision 6; `mecanum.final-issued-receipt-topic-qos/v2` | `docs/RECEIPT_TOPIC_QOS_CONTRACT.md` | Full document `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`; transport manifest `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620` |
| Receipt interface | `mecanum.final-issued-receipt/v2`, schema revision 2 | `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg` | `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a` |
| Dependency closure | version 1 | `docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json` | `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73` |
| Bundle approval record | QoS6/ACR8 approval | `docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md` | `4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529` |
| Gate A structural schema | active source selection, Gate A scope only | `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md` | `43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3` |
| Gate A error-carrier decision | accepted Gate A carrier only | `docs/governance/decisions/WP-04_GATE_A_ERROR_CARRIER_DECISION.md` | `72a2c94df548cb00557b1777e10d11b96b386329894edaf34e1d81c07ed4e94d` |

The receipt schema SHA, dependency-closure SHA, transport-manifest SHA, and full-document SHA values identify distinct byte sets and are not interchangeable. No `config_hash` is added to the receipt message. S2 revision 2, Observation Input Contract revision 6, and V3 Observation Boundary Specification revision 7 are provenance-only; none is promoted or used to add active fields.

## 2. Observation layout and ownership boundary

The policy observation remains exactly 81 `float32` values in the frozen order:

1. 72 LiDAR sectors;
2. 3 LocalReference features;
3. 3 measured-twist features `[vx, vy, wz]`;
4. 3 previous-final-issued-command features `[vx, vy, wz]`.

The 81D layout, feature ownership, frame/normalization rules, Ground Truth exclusion, and distinction among raw action, decoded candidate, and final-issued command are unchanged from Architecture and the approved contracts. This specification does not select numeric profile parameters. Ground Truth is excluded from policy input and its provenance path.

The pure-Python core accepts typed, already-validated values. A ROS adapter is responsible for middleware-facing message typing, QoS compatibility, frame validation, receive/freshness checks, source/provenance checks, and conversion into the typed ingress boundary. The core does not import ROS, inspect repositories/files, read clocks, perform I/O, or fabricate fallback values. No ROS adapter behavior is implemented or claimed by this document.

## 3. Gate B resolved record and receipt binding

The approved receipt v2 bytes remain unchanged. The Gate B binding is carried outside the ROS message by an immutable `ReceiptIngressBindingV3`, included in the resolved Gate B record owned and constructed only by the `ResolvedConfigV3` compiler. No caller-created or partially resolved record is accepted as a resolved Gate B record. There are no defaults, aliases, fallback, lookup, normalization, or unresolved tokens in a real resolved profile.

The candidate record pins these values:

```text
receipt_interface_id                 = mecanum.final-issued-receipt/v2
receipt_interface_sha256             = 0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a
dependency_closure_manifest_sha256   = 0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73
qos_contract_id                      = mecanum.final-issued-receipt-topic-qos/v2
transport_manifest_sha256            = 338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620
resolved_config_hash                 = compiler-produced hash of the exact resolved configuration
observation_spec_revision            = 1
```

These names describe the candidate record boundary, not fields in the receipt
message. Contract IDs, hashes, and `resolved_config_hash` are opaque exact
strings; `observation_spec_revision` is an integer revision. The expected
lifecycle facts are carried outside the message as exact identity/epoch/
generation values. Their public field names and exact cross-record comparison
mapping remain pending as stated below. The compiler, not an adapter or
caller, creates the resolved record after validating all pins.

`resolved_config_hash` is bound in the wrapper/config record and resolved configuration, never added to `FinalIssuedCommandReceipt.msg`. The exact public Python field names/types for `ReceiptIngressBindingV3`, the resolved Gate B record, and the binding of the specification's own final full-document SHA are `PENDING_OWNER_DECISION` until fixed by a focused implementation packet/change-control. The compiler must reject unresolved profile-dependent values rather than instantiate a real resolved profile from them.

### Lifecycle tuple

Receipt eligibility requires exact compatibility with the active lifecycle and strict temporal ordering. The receipt must be strictly after both the action and reset barriers, and at or before the observation cutoff. A receipt before/equal to either barrier, after cutoff, or associated with a mismatching or invalidated lifecycle is not eligible.

The receipt schema exposes `episode_generation`, `reset_epoch`, and `runtime_generation`; `ObservationCutoffV3` exposes `lifecycle_identity`, `epoch`, and `generation`. The exact comparison mapping for `lifecycle_identity` and the receipt's three generation/epoch members, including whether `episode_generation` is part of the Gate B compatibility tuple, is `PENDING_OWNER_DECISION`. Until that mapping is explicitly fixed, Gate B implementation is blocked; implementations must not guess, alias fields, or infer identity.

### Fail-closed state behavior

- Only a compatible, admitted receipt strictly after both barriers and not later than cutoff may satisfy the receipt input.
- A duplicate or non-monotonic sequence is rejected; a coalesced gap is classified only after an earlier accepted receipt from the same publisher instance, and is not by itself a missing latest-state receipt.
- Pre-barrier, stale, future, mismatched, missing, or invalidated inputs cannot be repaired using PPO action, decoder output, `SafetyState`, cached data, or synthetic zero.
- After reset, `observation0` requires the compatible new-epoch `SOURCE_SAFE_STOP` zero receipt with `CommandArbiter` provenance, admitted after the reset barrier.
- An action-bound timeout returns non-ready/no vector; no 81D vector is constructed.
- No state transition creates or advances barriers in this spec. `SafetyLifecycle` owns action/reset barriers; the assigned runtime adapter produces caller facts under its separate authority.

## 4. Pending measured/profile values

Unmeasured timing, receipt-after-barrier timeout, skew, buffer limits, sensor freshness, measured-twist validity/covariance/provenance, LiDAR timing, and X3 extrinsic/range/frame facts remain `PENDING_MEASUREMENT`. They must not be replaced by sample constants or values from provenance drafts. A compiler must reject these values in a real resolved profile until the applicable measured/approved evidence exists and is pinned. This specification does not assert any measurement, runtime profile, or successful resolution.

## 5. Gate B and implementation boundary

ACR8 requires all six Gate B conditions before a connected/profile-resolving implementation packet may be issued: (1) record approved ACR and update the controlled V3 specification; (2) bind approved QoS identity/manifest, delivery/coalescing/action-bound readiness and `TopicQosContractV3`; (3) define `ObservationInputContractV3` canonical source and compiler/composition validation with no unresolved resolved-config values; (4) add/register receipt message/topic and version/hash checks plus canonical QoS record; (5) define pure-Python typed-snapshot/receipt ingress seams; and (6) independently audit preservation of the 81D layout and process/safety isolation.

This candidate documents the boundary for those conditions but does not itself satisfy them, install/generate the ROSIDL interface, define runtime profiles, implement adapters, produce a resolved profile, or pass Gate B. Any code work requires a separate exact-scope implementation packet, focused audit, and explicit `CODE_AUTHORIZATION`. ROSIDL, adapter/QoS integration, runtime, HIL, hardware, `deploy_sim`, and `deploy_real` require their own staged authority/evidence and are not authorized here.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```
