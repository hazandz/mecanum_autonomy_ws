# Observation V3 Specification

**Revision:** `2` (replacement candidate; prior review candidate `687469f…` is superseded provenance only)
**Status:** `CANDIDATE_ONLY_PENDING_FOCUSED_AUDIT_AND_CANONICAL_INTEGRATION`
**Work package:** `WP-04-GATE-B-EXACT-DATA-CONTRACT-COMPLETION-REFRESH`
**Candidate branch:** `wp-04-gate-b-exact-data-contract-completion-refresh-1e14644`
**Candidate base:** `origin/integration/implementation@1e14644a7d778a0c5ad32512430d775fd0e8ecd3`
**Runtime status:** `RUNTIME_NOT_APPROVED`

This replacement specification candidate carries forward the Owner decisions for Gate B and corrects the resolved-record scope. The prior review candidate `wp-04-gate-b-exact-data-contract-change-control-68174e@687469f4aa2f166566e31aa91c1b1d90648c3812` is superseded review provenance only; it was not integrated and is not active authority. This replacement remains inactive until focused independent audit, separate User authorization for its exact final commit, fast-forward to `integration/implementation`, and remote-ref verification. It does not pass Gate B, close WP-04, or authorize implementation or runtime.

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

The approved receipt v2 bytes remain unchanged. The Gate B binding is carried outside the ROS message by an immutable `ReceiptIngressBindingV3`. The binding decision below remains a selected candidate contract; the resolved record's public shape is a separate unresolved decision. `ResolvedConfigV3.gate_b` is a required compiler-owned slot, but this statement does not select the slot value's exact member set or type semantics.

The candidate record pins these values:

```text
receipt_interface_id                 = mecanum.final-issued-receipt/v2
receipt_interface_sha256             = 0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a
dependency_closure_manifest_sha256   = 0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73
qos_contract_id                      = mecanum.final-issued-receipt-topic-qos/v2
transport_manifest_sha256            = 338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620
observation_spec_revision            = 1
profile_id                           = required selected profile identity
lifecycle_identity                   = exact active SafetyLifecycle identity
expected_episode_generation          = 0..2^64-1
expected_reset_epoch                 = 0..2^32-1
expected_runtime_generation          = 0..2^32-1
```

These are the selected binding members, not fields in the receipt message. Every member is required, keyword-only, exact built-in `str` or `int`, with no default or coercion; subclasses and `bool` as an integer are rejected. Hash strings use lowercase 64-hex syntax and must exactly equal the applicable canonical pin or compiler-produced value. `observation_spec_revision >= 1`; `expected_episode_generation` is `0..2^64-1`; `expected_reset_epoch` and `expected_runtime_generation` are each `0..2^32-1`. Values compare exactly. The binding carries only the specification revision; its full-document SHA remains pinned externally by the Registry and decision record.

`resolved_config_hash` is not a binding member and is not added to `FinalIssuedCommandReceipt.msg`; its projection remains one of the two deferred blockers stated in §5. The exact public member set, types, and value semantics of `ResolvedGateBRecordV3`, including its resolved observation-input/profile composition, remain undecided. Observation Input Contract V3 revision 6 is `REVISED_DRAFT` provenance-only and is not field/default/schema authority for that record or for an `ObservationInputContractV3` implementation.

### Lifecycle tuple

Receipt eligibility requires exact compatibility with the active lifecycle and strict temporal ordering. The receipt must be strictly after both the action and reset barriers, and at or before the observation cutoff. A receipt before/equal to either barrier, after cutoff, or associated with a mismatching or invalidated lifecycle is not eligible.

The selected lifecycle tuple is `(episode_generation, reset_epoch, runtime_generation)` with atomic exact comparison. `ObservationCutoffV3.epoch == reset_epoch`; `ObservationCutoffV3.generation == runtime_generation`. `episode_generation` participates in the exact tuple comparison. `lifecycle_identity` is the exact string from active `SafetyLifecycle` context; the adapter verifies it against the configured ingress binding and does not infer it from a receipt. No partial match, reuse, alias, or fallback is allowed. Missing, ambiguous, or mismatching correspondence fails closed using the decision record's existing mapping; an ambiguous/unverifiable identity with no authorized mapping is `AUTHORITY_CHANGE_REQUIRED`.

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

This replacement candidate documents the decisions and unresolved shape/projection blockers; it does not itself satisfy the six ACR8 conditions, install/generate the ROSIDL interface, define runtime profiles, implement adapters, produce a resolved profile, or pass Gate B. The two independent blockers are `DECISION_DEFERRED_PENDING_EXACT_NON_CIRCULAR_CONFIG_HASH_PROJECTION` and `DECISION_DEFERRED_PENDING_EXACT_RESOLVED_OBSERVATION_INPUT_PROFILE_SHAPE`. Both must be resolved together in one consolidated resolved-config decision, audited, and integrated before any code-authorization candidate may be considered. Any later code work still requires a separate exact-scope packet, focused audit, and explicit `CODE_AUTHORIZATION`. ROSIDL, adapter/QoS integration, runtime, HIL, hardware, `deploy_sim`, and `deploy_real` remain outside this candidate.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
GATE_B_BOUNDARY_CLOSURE: ACTIVE_ON_INTEGRATION
CONFIG_HASH_PROJECTION: DECISION_DEFERRED_PENDING_EXACT_NON_CIRCULAR_CONFIG_HASH_PROJECTION
RESOLVED_INPUT_PROFILE_SHAPE: DECISION_DEFERRED_PENDING_EXACT_RESOLVED_OBSERVATION_INPUT_PROFILE_SHAPE
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```
