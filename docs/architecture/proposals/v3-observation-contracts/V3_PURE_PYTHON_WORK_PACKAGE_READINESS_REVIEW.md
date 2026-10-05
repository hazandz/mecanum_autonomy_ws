# V3 Pure-Python Work Package Readiness Review

**Revision:** `3 — scope-closure user approved`\
**Date:** `2026-10-04`\
**Mode:** `ARCHITECTURE_READINESS_REVIEW` (static only)\
**Repository evidence:** `origin/integration/implementation@afa23732fb6a74beafceec21c2319a52f5f87b3f`\
**Architecture authority:** `MECANUM_NAV_DRL_Architecture(4).docx`, SHA-256 `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`\
**Governance authority:** `docs/governance/PROJECT_EXECUTION_PLAN.md` at the repository evidence ref\
**Scope-closure status:** `USER_APPROVED`\
**Runtime status:** `RUNTIME_NOT_APPROVED`

## 1. Purpose and current verdict

This document closes a design ambiguity in the first possible V3 pure-Python
scope. It does not authorize code and does not make a PEP change.

`V3_PURE_PYTHON_READINESS: NOT_READY_PENDING_GOVERNANCE_AND_SEMANTIC_APPROVAL`

The scope closure below passed independent architecture audit and is approved
by the user. It permits only the next semantic and governance decisions; it
does not authorize code.

No candidate implementation packet may use a new work-package ID until the PEP
maps that scope to one. `WP-05A`, `WP-05B`, and a repurposed `WP-06` are not
canonical identifiers in the current PEP.

## 2. Two gates still outside this review

### Semantic gate

The following documents are technically coherent but remain draft inputs, not
approved Architecture authority:

| Contract | Revision / exact binding | Intended use after approval |
| --- | --- | --- |
| S2 temporal contract | rev.2, `mecanum.snapshot-synchronization-temporal/v1` / `1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f` | post-barrier admission, global coherent triple, shared cut-off and typed non-ready rules |
| Observation Input Contract | rev.6 | profile variants and V3 input specification |
| V3 Observation Boundary | rev.7 | fixed 81D boundary, V3-only core, receipt projection |

The required user/Architecture decision is:

```text
APPROVED_FOR_FOLLOW_ON_DESIGN:
ACR_S2_SNAPSHOT_SYNCHRONIZATION_TEMPORAL_CONTRACT rev.2,
ObservationInputContractV3 rev.6, and
V3 Observation Boundary Specification rev.7.

Approval scope: semantic temporal and input-boundary contract only.
No profile timing values, code, build, test execution, ROS/runtime, HIL,
hardware, or deploy_real are authorized by this decision.

RUNTIME_NOT_APPROVED.
```

The text above is a required approval template, not a claim that it has already
been approved.

### PEP governance gate

At the evidence ref, the PEP defines:

| PEP ID | Scope | Initial status |
| --- | --- | --- |
| `WP-04-POLICY-CORE-P0` | Normalize LiDAR/`LocalReference` and bind previous command to final-issued receipt | `BLOCKED_BY_CONTRACT` |
| `WP-05-CANONICAL-ARTIFACT-FOUNDATION` | Map, scenario and hardware provenance/hash foundation | `BLOCKED_BY_CONTRACT` |
| `WP-06-BRINGUP-SAFETY-OFFLINE` | Bringup, command adapters, safety and final publisher offline implementation | `BLOCKED_BY_DEPENDENCY` |

Before any execution packet, PEP authority must either:

1. place the scope in section 4 under existing `WP-04` with narrowed
   deliverable and dependencies; or
2. revise the PEP under plan-change control and assign a new canonical ID.

This review does not make that choice.

## 3. Scope-closure decision — user approved

### 3.1 Chosen technical shape: model primitives only

The first potential implementation is **not compiler closure**. It is a
V3-only set of immutable contract primitives that can be constructed only as
structural in-memory test data until a later compiler/profile migration scope
is authorized.

It must not modify:

- `ResolvedConfigV3`;
- raw V3 profile inputs, YAML, loader, compiler, validator, composition or
  normal config hashing;
- `CommandSafetyContractV3`;
- any V1 observation, decoder, history or snapshot implementation;
- a public ROS message, topic, QoS, TF, sensor adapter, S2 buffer,
  assembler, encoder or runtime owner.

This removes the previous contradiction: no existing profile is invalidated by
a newly mandatory field, because the field is not attached to
`ResolvedConfigV3` in this first scope.

### 3.2 Static input-specification primitives

A future implementation may add a V3-only, non-integrated declarative model
for the *shape* of `ObservationInputContractV3`. It may define typed union
members and their structural invariants for:

- LiDAR geometry/range/sectorization descriptors and `T_base_lidar`
  provenance;
- `sim_train` internal versus external goal/twist source kinds;
- S2 contract ID/SHA reference;
- final-issued receipt interface/topic-QoS ID/SHA references.

It must not create a resolved profile, an operational provenance record, a
`deploy_sim`/`deploy_real` value, an X3 measurement or numerical timing
threshold. It must not claim that a configuration hash includes this model
until compiler closure explicitly integrates it.

### 3.3 `ObservationCutoffV3`: shared transaction primitive, not config

`ObservationCutoffV3` is a runtime transaction fact. Its proposed type owner
is a new V3-only core module:

```text
mecanum_nav_rl/core/v3_observation_contracts.py
```

This module owns immutable type shape and fail-closed validation only. It must
not select or synthesize a barrier, cut-off timestamp, lifecycle identity or
receipt. It must not import or extend legacy `core/snapshots.py`, V1
observation modules, ROS, DDS or configuration loading code.

Operational ownership remains separate:

| Concern | Owner |
| --- | --- |
| Action/reset barriers | `SafetyLifecycle` |
| Creation of exactly one cut-off after `wait_transition_snapshot(after=receipt)` | `RobotRuntimeAdapter` |
| Immutable type and validation | `core/v3_observation_contracts.py` |
| Consumption for coherent input selection | later S2/V3 core |
| Configuration hash calculation and resolved-profile membership | later compiler/config closure |

The primitive may carry an adapter-supplied active `config_hash` only as
transaction provenance. It neither calculates that hash nor becomes a
configuration value. Its validation requires a cut-off strictly after the
provided action and reset barrier timestamps in the same lifecycle identity;
failure is typed and fail-closed. Later S2 maps that failed condition to
`CUTOFF_BARRIER_ORDER_NON_READY`.

### 3.4 Deferred compiler/profile closure

A later, separate candidate scope may attach `observation_input` to
`ResolvedConfigV3`. That later scope must be atomic:

1. add the `ResolvedConfigV3` field and composition/hash ownership;
2. update raw-config loading, compiler and validator surfaces;
3. migrate every authoritative raw V3 profile that is eligible to resolve;
4. update all corresponding structural fixtures/tests in the same change;
5. reject any profile lacking approved provenance or required numerical
   evidence.

It must not introduce an optional V3 fallback or a hidden default merely to
keep old profiles compiling. `deploy_real` remains blocked until its separate
`MEASURED_REGISTRY` evidence exists. This deferred scope requires a fresh
readiness review; it is not part of the first primitive scope.

## 4. Static repository evidence

| Finding | Classification | Consequence |
| --- | --- | --- |
| `ResolvedConfigV3` has no `observation_input` field. `test_config_v3_schema.py` constructs it directly as a complete object. | `SOURCE_FACT` | Adding a mandatory field without migration would invalidate existing structural construction. |
| `config/v3_composition.py` derives fragment ownership from `ResolvedConfigV3`; the current runtime-profile fragment owns only `runtime` and `motion_limits`. | `SOURCE_FACT` | Compiler closure must update ownership and hash as part of one later atomic migration. |
| `config/v3_policy.py`, `v3_compiler.py`, and `v3_validators.py` currently reject `SIM_BASELINE` for `deploy_sim`. | `SOURCE_FACT` | This policy alignment belongs to later compiler closure, not the primitive scope. |
| Existing `observations/{assembly,encoder,synchronizer,previous_command}.py` are V1-bound. | `SOURCE_FACT` | No direct reuse, delegation, wrapping or modification is permitted. |
| Existing `core/` contains generic immutable types but also legacy snapshot/lifecycle modules. | `SOURCE_FACT` | The proposed V3 core module must be new and must have an explicit no-legacy-import boundary. |
| Interfaces contain `CommandEnvelope.msg` and `SafetyState.msg`, not a final-issued receipt message. | `SOURCE_FACT` | Public receipt interface and bridge are out of scope. |

## 5. Candidate primitive scope — not authorized

After both gates in section 2, the candidate’s source area may be limited to:

```text
ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/v3_observation_contracts.py
ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/v3_observation_input_models.py
ros2_ws/src/mecanum_nav_rl/test/test_v3_observation_contract_primitives.py
```

The exact eventual file list must be revalidated against the approved PEP
mapping before edits. No existing compiler/config/profile file is included.

### Required static-only outcome

1. Immutable, V3-only structural model classes that reject malformed values,
   invalid lifecycle identity and a cut-off at or before either barrier.
2. An `ObservationCutoffV3` constructed from caller-supplied transaction facts;
   the class generates neither barrier nor cut-off.
3. Structural source-kind/union validation with no raw Ground Truth fallback,
   no V1 imports and no public synthetic odometry/TF route.
4. Exact identifier/hash pair validation for S2 and final-issued receipt
   references, without ROS protocol implementation.
5. Unit tests with only clearly named, in-memory non-canonical fixture data.

### Fixture rule

All test data is structural, in-memory and non-canonical. It is not a profile,
provenance record, hardware measurement, `deploy_sim`/`deploy_real` value or
runtime evidence. A fixture must not be written to a profile fragment or made
eligible for `ResolvedConfigV3` deployment use.

## 6. Acceptance criteria for the future packet

| Area | Static proof required |
| --- | --- |
| Isolation | No ROS/Gazebo/Gymnasium/SB3 imports; no V1 observation/decoder/snapshot imports. |
| Ownership | The core primitive generates no barriers or cut-off timestamp; operational creation is attributed only to the future `RobotRuntimeAdapter` boundary. |
| Temporal invariant | Cut-off must be strictly later than both caller-supplied barriers and share the same lifecycle identity; invalid input fails closed. |
| Model boundary | No edit to `ResolvedConfigV3`, loader/compiler/validator/composition/hash, raw profile, YAML or `CommandSafetyContractV3`. |
| Structural bindings | S2 and receipt ID/SHA pairs must match their approved semantic contract values exactly. |
| Fixtures | Tests never create a deployment-resolvable profile or stand in for measurement/provenance. |

No test may run unless its eventual implementation packet separately permits
test execution.

## 7. Final status and next action

`SCOPE_CLOSURE_DECISION: USER_APPROVED`\
`V3_PURE_PYTHON_READINESS: NOT_READY_PENDING_GOVERNANCE_AND_SEMANTIC_APPROVAL`\
`SEMANTIC_APPROVAL: REQUIRED`\
`CANONICAL_WORK_PACKAGE_ID: UNRESOLVED`\
`CANDIDATE_PURE_PYTHON_SCOPE: NOT_AUTHORIZED_FOR_CODE`\
`RUNTIME_NOT_APPROVED`

The next safe action is the user's separate semantic approval (or rejection)
of the three documents in section 2. After semantic approval, PEP authority
must map the candidate scope before an implementation packet is drafted. No
source change is authorized by this review.
