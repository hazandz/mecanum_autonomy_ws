# WP-04 Gate A — Implementation Packet (Draft)

**Status:** `DRAFT_FOR_FOCUSED_INDEPENDENT_AUDIT_AND_USER_DECISION`
**Work package:** `WP-04-POLICY-CORE-P0`
**Candidate branch:** `wp-04-gate-a-implementation-packet-c37a5bff`
**Exact integration base:** `c37a5bff9dd6cc32fc503cdd796b31720a58a616`
**Packet role:** defines a proposed, bounded implementation scope for review only. It does not authorize implementation or change any canonical source.

## 1. Purpose and decision boundary

This packet proposes the exact Gate A scope for a later, separately authorized
implementation work package. Its purpose is to let a focused independent
auditor and the Project Owner/User decide whether that exact scope is
acceptable. This candidate creates no source implementation, test, interface,
configuration, runtime, or physical evidence.

PEP-001 revision `0.5.0` is active at the stated integration base. It permits
preparation and independent audit of an exact Gate A implementation packet;
it does not make WP-04 implementation-eligible or grant code authorization.
WP-04 remains `BLOCKED_BY_CONTRACT`. A later implementation would require a
passing focused audit, separate explicit user approval, and explicit
`CODE_AUTHORIZATION` for the exact implementation scope. Runtime, ROS, HIL,
hardware, `deploy_sim`, and `deploy_real` authorization would remain separate
decisions.

## 2. Authority and immutable references

The following are the exact authority/provenance pins at the packet base.
Embedded contract/manifest hashes are distinguished from full-document hashes.

| Source | Role/status at base | Exact path and revision | SHA-256 / identity |
|---|---|---|---|
| Architecture | Highest architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx` | Full file `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860` |
| PEP-001 | Active sequencing and Gate A scope authority | `docs/governance/PROJECT_EXECUTION_PLAN.md`, rev. `0.5.0` | Full file `ffcf5cbbbd25d174ff2ed97dd7fe4297ccefe5eaaf0f95d00b69aba1a820807b` |
| Canonical Source Registry | Active source selection | `docs/governance/CANONICAL_SOURCE_REGISTRY.md` | Full file `75d63ea7500f1a0c442100bb3d9dd9291ed27358e6061e5ac1fcc25ac0afe879` |
| Progress Ledger | Append-only progress/status evidence | `docs/governance/PROJECT_PROGRESS_LEDGER.md` | Full file at base `4f827842d83d9594ce0c58e60dda054b5d9fe2fd66cc3ca057b56b66c6d8e1c3` |
| ACR | Current approved Gate A/Gate B scope authority, as selected by Registry and approval record | `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md`, rev. `8` | Full file `03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c` |
| Receipt Topic QoS Contract | Current approved design-contract authority; no runtime authorization | `docs/RECEIPT_TOPIC_QOS_CONTRACT.md`, rev. `6` | Full file `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`; transport ID `mecanum.final-issued-receipt-topic-qos/v2`; transport manifest `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620` |
| Bundle approval | Records current source/status selection after canonical integration | `docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md` | Full file `4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529` |
| Gate A PEP change control | Immutable provenance for PEP rev. `0.5.0` | `docs/governance/decisions/WP-04_GATE_A_SEMANTIC_BUNDLE_PEP_CHANGE_CONTROL.md` | Full file `4876a0ad5afbe355ce5f410b9e5dbb2ef669455deedf2e2b2c9ca864c7425bb2` |

### 2.1 Semantic-design provenance — not independent approval

PEP-001 pins the following immutable source bytes as semantic-design
provenance. These pins do not canonicalize, approve, promote, or independently
satisfy an architecture/approval gate:

| Source | PEP-recorded status | Immutable source and path | Full-document / embedded hash |
|---|---|---|---|
| S2 Snapshot Synchronization Temporal Contract rev. `2` | `DRAFT — PENDING_INDEPENDENT_ARCHITECTURE_REVIEW_AND_USER_APPROVAL` | `origin/docs-v3-observation-contract-import@d3ca85536e35b38f7f3dffcf1dfd1bc16983aae9`; `docs/architecture/proposals/v3-observation-contracts/ACR_S2_SNAPSHOT_SYNCHRONIZATION_TEMPORAL_CONTRACT.md` | Full document `e1468d0373922a1806e14da91e7cc0336bcc7d70c4cd3ec4fc749078d86b70ab`; contract ID `mecanum.snapshot-synchronization-temporal/v1`; embedded contract/manifest SHA `1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f` |
| Observation Input Contract V3 rev. `6` | `REVISED_DRAFT — PENDING_INDEPENDENT_ARCHITECTURE_REVIEW_AND_USER_APPROVAL` | `origin/docs-v3-observation-contract-import@d3ca85536e35b38f7f3dffcf1dfd1bc16983aae9`; `docs/architecture/proposals/v3-observation-contracts/OBSERVATION_INPUT_CONTRACT_V3_DESIGN.md` | Full document `200703949d6b326a30ee8e2f75cd2cd14054576e6772ddc6ae3ff670e48eb76c` |
| V3 Observation Boundary Specification rev. `7` | Supporting design provenance only; not the active Gate A/B authority | `origin/docs-v3-observation-contract-import@d3ca85536e35b38f7f3dffcf1dfd1bc16983aae9`; `docs/architecture/proposals/v3-observation-contracts/V3_OBSERVATION_BOUNDARY_SPECIFICATION.md` | Full document `47ba6c432cc53798e9f8a97f3c0a97aae586d24bef98113716a4493e57ad4eeb` |

For active Gate A/Gate B scope, the Registry selects ACR rev. `8`; ACR8 §4
carries forward that scope. The standalone V3 Boundary Specification rev. `7`
remains supporting provenance and is not represented as replacing ACR8.
The pre-integration `DRAFT` labels in the QoS6/ACR8 bytes remain historical
text; the exact bundled approval record and Registry determine their current
document-authority/status effect after canonical integration. They do not
alter technical semantics or provide runtime approval.

### 2.2 Receipt references allowed as structural provenance

Gate A may carry exact final-issued-receipt references as structural identity
only. It does not implement or integrate the receipt interface, DDS transport,
ROS topic, publisher, subscriber, bridge, or history.

| Reference | Canonical path / ID | Pin |
|---|---|---|
| Receipt interface schema rev. `2` | `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg`; ID `mecanum.final-issued-receipt/v2` | SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a` |
| Interface dependency-closure manifest v. `1` | `docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json` | SHA-256 `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73` |
| Receipt transport manifest v. `2` | `docs/RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST.json`; ID `mecanum.final-issued-receipt-topic-qos/v2` | SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620` |
| QoS design contract rev. `6` | `docs/RECEIPT_TOPIC_QOS_CONTRACT.md` | Full-document SHA as listed above |

The full QoS/ACR document hashes, receipt schema hash, dependency-closure
hash, S2 embedded contract/manifest hash, and QoS transport-manifest hash are
distinct and must not be substituted for one another.

## 3. Exact proposed Gate A implementation boundary

PEP-001 rev. `0.5.0` constrains the first deliverable within
`WP-04-POLICY-CORE-P0` to a non-integrated pure-Python primitive scope:

1. immutable `ObservationCutoffV3` core type with structural fail-closed
   validation;
2. immutable structural `ObservationInputContractV3` model shapes; and
3. exact S2 and final-issued-receipt ID/SHA structural references.

The candidate implementation must preserve PEP ownership: `SafetyLifecycle`
remains sole owner of action/reset barriers;
`RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)` remains the
sole operational creator of one observation cutoff per transition; the pure
V3 core primitive represents/validates structure only. The packet does not
authorize adding a ROS adapter, modifying an adapter, or creating operational
timestamps or barrier facts.

### 3.1 Proposed file map and baseline inventory

The following file map is a proposal for the later code work package, not an
authorization to create or modify these files now. It preserves existing
package ownership and keeps Gate A in the pure core:

| File | Baseline state at `c37a5bff` | Gate A disposition / responsibility |
|---|---|---|
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/types.py` | Exists | Existing core type foundation; read-only reference for the later implementation unless its exact packet separately authorizes a minimal change. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/exceptions.py` | Exists | Existing exception foundation; no broad exception redesign is authorized. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/snapshots.py` | Exists | Existing typed-snapshot layer. Gate A does not add sensor synchronization, receipt ingestion, or a snapshot assembler here. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/models.py` | Exists | Existing configuration model module; out of Gate A edit scope. No `ResolvedConfigV3`, compiler, loader, composition, profile, YAML, or config-hash change. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/v3_observation_contracts.py` | Absent | Proposed new pure-core module for immutable cutoff/structural contract types and fail-closed structural validation only. Exact API/field matrix remains subject to independent packet review; no new semantic contract may be invented. |
| `ros2_ws/src/mecanum_nav_rl/test/test_v3_observation_contract_primitives.py` | Absent | Proposed new offline unit-test file for the later implementation package. Tests are specified below but are not run here. |
| `RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)` source file | No matching implementation path identified in the tracked package tree at this base | PEP ownership reference only. Exact source path and any later adapter work are `PENDING`; no adapter file is proposed for Gate A edits. |

This proposed map deliberately places structural `ObservationInputContractV3`
shapes alongside pure core primitives rather than changing the existing
configuration compiler/models. If independent review finds that a different
placement is required by an existing authority, the file map must be corrected
and re-reviewed before implementation; it must not be silently expanded into
configuration work.

### 3.2 Responsibility boundaries

- **Pure core:** owns only immutable value/type shape and structural,
  fail-closed validation for the permitted Gate A models. It does not resolve
  profiles, synchronize sensors, choose a cutoff operationally, encode policy
  observations, or emit commands.
- **Typed snapshots/contracts:** existing typed snapshots remain inputs/data
  structures owned by their existing contract boundaries. Gate A does not
  construct a new synchronized snapshot, combine sensor/receipt streams, or
  hold raw Ground Truth references. The new input-contract model is a
  structural model, not a resolved configuration or runtime snapshot.
- **ROS/runtime adapter:** remains outside Gate A. The PEP names the future
  ownership boundary but does not pin a source file path at this baseline.
  No `rclpy`, ROS message, topic, publisher, subscriber, TF, DDS, lifecycle
  process, or runtime adapter code is part of this packet.

## 4. Required invariants and exclusions

The later implementation packet must preserve the approved Gate A scope in
PEP-001 and the applicable technical invariants in the exact approved ACR8
bytes. At minimum, its design and acceptance evidence must show:

- cutoff ordering is strictly after the applicable action/reset barriers;
- cutoff and barriers retain the same lifecycle identity, epoch/reset epoch,
  generation/runtime generation, and profile ROS-time domain;
- `SafetyLifecycle` owns the barriers and the PEP-named adapter owns the
  operational cutoff-creation point; core primitives do not fabricate them;
- structural failures are typed and fail closed; no invalid/missing/mismatched
  structure is converted to a ready policy input;
- `config_hash` remains opaque caller-supplied provenance. Gate A does not
  generate, calculate, validate, or promote a hash, and does not add it as a
  configuration field;
- exact S2 and receipt references are preserved without aliases, fallback,
  hash substitution, or reinterpretation; S2/OIC draft pins remain
  provenance-only and do not satisfy their own approval gate;
- policy input remains isolated from raw Ground Truth; no V1 observation,
  decoder, history, snapshot, wrapper, alias, or fallback is reused.

The following are outside Gate A and must not appear as implementation
deliverables:

- `ResolvedConfigV3`, configuration/compiler/validator/composition/loader,
  YAML, profile, or resolved-profile changes;
- ROS/ROSIDL, QoS, TF, DDS, sensor adapters, `/cmd_vel`, publishers,
  subscribers, runtime integration, or safety/final-publisher implementation;
- receipt bridge/history, S2 synchronizer/buffer, LiDAR sectorizer,
  LocalReference normalizer, V3 assembler/encoder, or construction of any
  policy vector including 81D;
- V1 reuse; Ground Truth in any policy/observation path;
- profile timing/freshness/buffer values, sensor ranges, measured-twist
  validity/covariance/provenance, or X3 extrinsic/range/frame decisions;
- any map, scenario, hardware profile, physical measurement, or WP-05
  artifact instance. WP-05 foundation activation establishes governance and
  hash/location rules only; it did not select or create such instances.

Any field, validation rule, status mapping, numeric value, or source path not
settled by PEP-001 and the current approved ACR/QoS authority must be marked
`PENDING` in a later exact packet. A DRAFT/REVISED_DRAFT provenance source
cannot be used to silently decide it.

## 5. Proposed acceptance criteria for a later implementation review

These are proposed review criteria only. No check is executed by this packet
work package.

1. **Scope and immutability:** the exact approved code diff introduces only
   the permitted immutable core types and structural validators; no existing
   config compiler/model/profile or runtime/interface file changes.
2. **Fail-closed structure:** valid documented structures are accepted;
   missing, wrong-type, malformed, identity-mismatched, or invalid-order
   inputs produce the approved typed non-ready/error outcome without fallback
   or fabricated facts. The exact field-to-error matrix is `PENDING` wherever
   not specified by approved authority.
3. **Barrier/cutoff ownership:** tests demonstrate the pure core validates
   caller-supplied facts only; it neither creates barriers nor operational
   cutoffs. Ordering and identity/time-domain constraints are covered without
   introducing runtime dependencies.
4. **Reference integrity:** exact IDs/hashes are retained as structural
   references and mismatches fail closed. Full-document hashes are never
   confused with embedded contract/schema/manifest hashes.
5. **Isolation:** static inspection confirms no ROS imports or calls, no
   Ground Truth types/references, no V1 observation path, no config/hash
   implementation, no receipt/sensor synchronization, and no vector encoder.
6. **Offline determinism:** unit tests use in-memory structural fixtures
   only; fixtures are not profile values, measured evidence, or canonical
   contract sources.
7. **Evidence boundary:** test/static results, if separately authorized and
   produced later, are labeled `IMPLEMENTED_OFFLINE_ONLY`; they do not imply
   ROS graph, runtime, simulation, HIL, hardware, or real-robot readiness.

### 5.1 Checks to propose for the later code package

- Static import/scope checks proving the new pure-core surface is independent
  of `rclpy`, ROSIDL-generated packages, Gazebo, Nav2, PPO libraries, and
  runtime adapters.
- Unit cases for immutability, structural type validation, exact reference
  matching, missing/malformed values, barrier/cutoff ordering and
  lifecycle/epoch/generation/time-domain mismatch; each failure must remain
  typed and fail closed according to the approved contract.
- Static diff and dependency review proving no forbidden files or behaviors
  were introduced.
- If a later exact packet authorizes a narrow consumer-side structural test,
  it must remain pure/offline and must not create a synchronizer, receipt
  ingress, assembler, encoder, or 81D vector. Any such broader integration
  test is outside Gate A and requires a separate packet.

No command, test, build, formatter, ROS, Gazebo, Nav2, PPO, HIL, hardware, or
runtime check is authorized or run in this documentation work package.

## 6. Dependencies, assumptions, and open items

| Item | State at packet base | Packet treatment |
|---|---|---|
| WP-02 | `CLOSED` | No change. |
| WP-03 | `CLOSED` | PEP dependency is satisfied at the stated integration base; no WP-03 status or dependency change is proposed. |
| WP-04 | `BLOCKED_BY_CONTRACT` | Remains blocked; packet preparation/audit is not a status transition. |
| WP-05 | Foundation activation corrected and active; WP-05 remains open | No WP-05 audit, edit, status change, map/scenario/hardware selection, or artifact creation. |
| S2 rev.2 / OIC rev.6 | Draft provenance-only | Exact bytes are pinned in PEP; neither is promoted or treated as independently approved. Any Gate A use beyond provenance is `PENDING` an authority decision. |
| ROS adapter path | `PENDING` | PEP names ownership/operation but no source path is pinned; excluded from Gate A. |
| OIC exact structural field/error matrix | `PENDING` where not specified by approved PEP/ACR/QoS | Must be resolved by authority/audit before implementation; do not infer it from draft provenance alone. |
| Profile-specific timing, freshness, sensor and measured-twist evidence | `PENDING` | No values selected; remains outside Gate A and relevant to later connected/profile-resolving scope. |
| Runtime/HIL/hardware/deployment | Not approved | Requires distinct future approval and gates; not addressed by this packet. |

No assumption in this packet upgrades an evidence state or waives a dependency.

## 7. Deliverables and authorization sequence

### 7.1 Deliverables for a later Gate A implementation package

If separately authorized, that package would need to provide:

1. the exact pure-core implementation diff, limited to the reviewed file map;
2. the exact offline unit tests and static checks specified by its approved
   packet;
3. source/diff hashes, command outputs, and a scope report sufficient for
   focused independent audit;
4. explicit evidence that prohibited config, interface, ROS/runtime, V1,
   Ground Truth, synchronization, assembly, encoding, and WP-05 artifacts
   were not changed or introduced.

None of these implementation deliverables is created here.

### 7.2 Decision gates

```text
packet candidate
→ focused independent audit of exact branch tip
→ explicit user decision on that exact packet
→ separate explicit CODE_AUTHORIZATION for an exact implementation work package
→ offline implementation and only the checks authorized by that package
→ independent review of resulting implementation evidence
```

This packet does not claim Gate A passed or WP-04 opened/closed. Gate B or
any connected/profile-resolving work requires a separate exact packet and
must satisfy the applicable ACR8 gates, profile-specific evidence, and
separate user/code authorization. Gate A does not imply Gate B eligibility.
Runtime, HIL, hardware, `deploy_sim`, and `deploy_real` remain unapproved.

## 8. Candidate status

```text
WP-02: CLOSED
WP-03: CLOSED
WP-04: BLOCKED_BY_CONTRACT
WP-05: OPEN; FOUNDATION_ACTIVATION_ACTIVE; NO CONCRETE ARTIFACT SELECTED
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```

This file is a documentation-only candidate for independent audit. It does
not modify PEP-001, the Registry, Ledger, canonical contracts, schema,
configuration, source code, WP status/dependency, or any authorization.
