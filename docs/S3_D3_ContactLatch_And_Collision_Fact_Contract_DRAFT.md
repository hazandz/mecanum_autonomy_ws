# S3 D3 — ContactLatch and Collision Fact Contract

**Status: DRAFT — APPROVED DISPOSITIONS FOR CANDIDATE RECONCILIATION; RUNTIME EVIDENCE PENDING**

## Scope and decision boundary

This is a core/runtime contract design for D3 only. It does not implement a contact producer, ContactLatch, collision evaluator, termination evaluator, ROS node, Gazebo plugin, bridge, Gymnasium environment, reward, command path, or hardware behavior. It does not approve any runtime behavior.

The authoritative architecture remains [MECANUM NAV DRL Architecture](MECANUM_NAV_DRL_Architecture.docx), schema 3.0. The episode design and termination-input decisions are recorded in [S3 Episode Reward Termination Design](S3_Episode_Reward_Termination_Design_DRAFT.md) and [S3 Termination Inputs and Limits Decision Packet](S3_Termination_Inputs_And_Limits_Decision_Packet_DRAFT.md). This document narrows only the missing D3 collision-fact contract.

## 1. Static-source audit: geometry is not a contact producer

| Audited source | Static evidence | What it establishes | What it does **not** establish |
| --- | --- | --- | --- |
| [gazebo.launch.py](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) and [tugbot_depot.sdf](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) | The selected SDF world is `world_demo`; its world systems include Physics, UserCommands, SceneBroadcaster, Imu, and Sensors. | A Gazebo world with physics and sensor systems is statically configured. | A collision event stream, a contact latch, event ordering, or reset clearing. |
| [tugbot_depot.sdf](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) | Static collision names include `ground_plane/link/collision` and `depot_collision/collision_link/{wall1..wall4, boxes1..boxes11, pilar1..pilar4, pallet_mover1..pallet_mover2, stairs, shelfs1..shelfs18}`. A Fuel `Depot` include is remote and not fully resolved in this source audit. | Candidate world collision names and static geometry references exist. | Stable runtime scoped names, which pairs contact at runtime, or a policy collision rule. |
| [ROBOT_URDF_final.xacro](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro) | Collision geometry exists for `base_link`, four wheel links, `IntelRealsense_D435_Multibody_1`, and `RPLiDAR_A1M8_1`. | Robot-side candidate collision links exist in static source. | That any link should be included or excluded by a training collision policy. |
| [ROBOT_URDF_final.gazebo](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo) | Configures VelocityControl, MecanumDrive, OdometryPublisher, JointStatePublisher, camera, and GPU LiDAR. The audited file contains no contact sensor or contact plugin. | Existing motion, odometry, camera, and LiDAR configuration. | A runtime contact producer or collision fact. |
| [ros_gz_bridge_gazebo.yaml](../ros2_ws/src/ROBOT_URDF_final_description/config/ros_gz_bridge_gazebo.yaml) | The audited bridge configuration contains `/clock` mapping only. | The listed clock bridge is statically configured. | A ROS contact topic, contact message conversion, or ContactLatch input. |

The `<contact/>` element under the ground-plane collision surface in `tugbot_depot.sdf` is a surface/contact property. It is **not** a contact sensor, a contact-event publisher, a bridge mapping, or a ContactLatch producer.

`mecanum_env.py` may contain legacy contact-related code, but it is non-authoritative and is not evidence of the official runtime contract. It is not adopted by this design.

### Static collision-name boundary

The names above are `OBSERVED_STATIC_SOURCE` only. They may be altered by SDF inclusion, Fuel resolution, model nesting, or Gazebo scoped-name rules. A future producer must demonstrate its emitted entity/link identity format before any filter can rely on these strings.

## 2. Strict collision-source boundary

A collision fact may originate only from a future, approved contact producer and ContactLatch that satisfy this contract. It is a hidden task/runtime fact and must never enter PPO observation, `ObservationAssembler`, `ObservationEncoder`, or a policy topic.

The following are explicitly not substitutes for a collision fact:

- LiDAR scan or any scan range;
- `/odom`, measured twist, or wheel velocity;
- hidden ground-truth pose or GT odometry;
- `SetEntityPose` request/response or other pose-control evidence;
- motor state, UART acceptance, actuator acknowledgement, or visible robot movement.

Missing, stale, mismatched, malformed, or unavailable collision provenance is not evidence of no collision. At a transition requiring the fact, it must lead to `STEP_ABORT` and `FAULT`, not a fabricated non-collision result.

## 3. Proposed immutable facts — design only

No source API is created by this document. The following names describe the minimum future immutable value contract.

| Proposed value | Required fields | Intended meaning | Not evidence of |
| --- | --- | --- | --- |
| `ContactCandidateSnapshot` | `EpisodeLifecycleIdentity`; `TransitionIdentity`; non-empty unique `event_id`; simulation timestamp; immutable involved entity/link identities; `filter_policy_id`, version, and hash; latch status; source provenance | Read-only candidate exposed to a transition evaluator during the active action interval. | A raw Gazebo message, a collision policy approval, a consumed event, or physical rollback. |
| `CollisionFact` | All candidate identity/provenance fields; explicit validity/latch outcome; the selected immutable collision classification | The validated hidden input that an eventual termination evaluator may consider. | A PPO observation field, a clearance metric, a contact-source runtime implementation, or an actuator acknowledgement. |

The lifecycle and transition identities must be the existing `EpisodeLifecycleIdentity` and `TransitionIdentity`; D3 must not create a parallel identity system. Simulation timestamp is in the simulation/ROS timestamp domain. It must not be directly subtracted from steady receive time or wall time.

The existing pure-core `ContactCandidateSnapshot` in `core/episode_lifecycle.py` is intentionally a **test-only** two-field value (`transition_identity`, `event_id`). It proves core consume-once mechanics only; it does not satisfy the proposed runtime provenance contract above.

## 4. Approved ContactLatch and lifecycle disposition

This candidate records the Project Owner/User-authorized D3 disposition and
preserves Architecture §§15–16 as the controlling authority. `EpisodeEvaluator`
owns `ContactLatch` and per-transition aggregation into `CollisionFact` as a
logical role assignment; this does not claim that a module or runtime producer
exists.

The Architecture §16 state machine remains exact:

- A valid non-empty contact observation for the current epoch sets
  `contact_active = True` and `collision_pulse_pending = True`.
- During normal contact-observation updates, only a valid explicit-empty
  observation for the current epoch may set `contact_active = False`; that
  observation does not clear `collision_pulse_pending`.
- Silence, a missing message, a delayed/stale message, or invalid provenance is
  not a no-contact observation and must not clear either latch state.
- At transition consumption, collision is
  `contact_active OR collision_pulse_pending`; consumption clears only
  `collision_pulse_pending`, leaving `contact_active` unchanged.
- `RESET_BEGIN(new_epoch)` remains the separate atomic lifecycle reset: switch
  epoch atomically, clear both latch states and latch timestamps, and reject old
  epoch messages. No normal empty observation or transition-consumption rule
  substitutes for this reset.

Valid latch state must not be discarded merely because its source event arrived
before the action barrier. The action barrier determines transition
consumption, not whether valid contact is latched. Invalid lifecycle,
transition, timestamp, time-domain, source, or filter provenance remains
fail-closed. Required invalid/unavailable evidence yields `STEP_ABORT`/`FAULT`,
not a fabricated no-collision fact. These decisions do not reinterpret or
weaken reset, lifecycle, failure, or transition behavior.

## 5. Approved simulation source and collision classification disposition

The simulation source boundary is the simulator's authoritative
physics-contact event stream. `SimulationContactIngress` is only a logical
producer role: it receives those events and creates typed contact candidates
with producer identity/sequence, lifecycle/transition identity, source
timestamp/time domain, entity/link identities, and filter-policy ID/version/hash.
It does not replace or bypass the existing Architecture contact path:
generated contact instrumentation → Gazebo `gz.msgs.Contacts` →
`ros_gz_bridge` → `/mecanum/contacts`
(`ros_gz_interfaces/msg/Contacts`) → `ContactLatch`.
No collision is inferred from LiDAR, odometry, pose, raw Ground Truth policy
input, or images. No static SDF collision-name or implementation/plugin/API
choice is made here.

| Contact class | Approved candidate classification |
| --- | --- |
| Wheel–ground support | Exclude. |
| Robot self-contact | Exclude. |
| LiDAR, camera, or other sensor-link contact with non-ground external world objects | Include. |
| Base/chassis contact with non-ground external world objects | Include. |
| Wall, box, shelf, pallet, stair, or other non-ground external world contact | Include. |
| Ground contact through a non-wheel robot link | Include. |

The filter must use emitted runtime entity/link identities; static SDF names
alone are not sufficient.

`deploy_real` has no approved contact producer. A hardware producer and its
evidence remain a separate future decision; missing events must never be read as
“no collision.”

## 6. Future evidence obligations — not evidence claimed

| Evidence item | Required coverage | Status |
| --- | --- | --- |
| Simulation contact and no-contact behavior | Valid contact, valid explicit-empty normal update, silence/missing/delayed/provenance-invalid behavior | `FUTURE_RUNTIME_EVIDENCE_REQUIRED` |
| Identity and ordering | Duplicate/conflicting identity, replay, out-of-order and simultaneous events; stable producer sequence | `FUTURE_RUNTIME_EVIDENCE_REQUIRED` |
| Lifecycle and timestamp | Lifecycle/transition binding, timestamp/time-domain provenance, action-interval alignment, pre-barrier latch preservation | `FUTURE_RUNTIME_EVIDENCE_REQUIRED` |
| Reset | `RESET_BEGIN(new_epoch)` atomic state clearing and old-epoch rejection | `FUTURE_RUNTIME_EVIDENCE_REQUIRED` |
| Provenance | Producer identity, entity/link identity, filter-policy ID/version/hash end to end | `FUTURE_RUNTIME_EVIDENCE_REQUIRED` |
| `deploy_real` | Hardware contact producer, source contract, and evidence | `PENDING_SEPARATE_USER/GOVERNANCE_DECISION` |

The source/role/classification and state-machine dispositions are approved for
this documentation candidate. They do not claim an approved runtime producer,
ContactLatch implementation, or completed evidence.

## 7. Termination integration boundary

The authoritative precedence remains:

```text
collision > goal_reached > out_of_bounds > stuck > episode_limit
```

A collision fact is only a candidate input to a future pure termination evaluator. It does not itself reset a simulator, publish zero, create a Gym transition, or establish any other termination fact. If a required collision fact is absent or its lifecycle, transition, filter, timestamp, or source provenance mismatches, the operation must be `STEP_ABORT`/`FAULT`; it must not be interpreted as “no collision.”

This document does not derive `out_of_bounds` from `candidate_task_bounds`, does not define clearance, and does not alter terminal precedence.

## 8. Future core test matrix

| Test | Expected contract result |
| --- | --- |
| Valid latched candidate for the active lifecycle/transition and approved filter identity | Candidate can be staged for evaluation; no consumption before commit. |
| Duplicate event or replayed event ID | Rejected fail-closed; no second consumption. |
| Stale or future transition token | Rejected; no candidate joins the active step. |
| Lifecycle or runtime-generation mismatch | Rejected; no cross-episode leakage. |
| Filter policy ID/version/hash mismatch | Rejected; classification is not silently reused. |
| Abort after staging | `STEP_ABORT`; event remains unconsumed until reset/fault handling clears it. |
| Successful atomic commit | Event is consumed exactly once. |
| Reset/new generation | Staged and consumed state from the old lifecycle is unavailable. |
| Multiple simultaneous contacts | Behavior follows the approved deterministic aggregation rule. |
| Source-isolation scan | Core values import no ROS, Gazebo, TF, Gymnasium, SB3, policy observation module, or raw GT type. |

## Conclusion and handoff

**RUNTIME_EVIDENCE_PENDING.** No audited runtime contact sensor, plugin, bridge,
producer, or ContactLatch implementation is claimed. The user-authorized
source, classification, role, and Architecture-aligned latch dispositions are
recorded for this candidate; their runtime evidence remains outstanding.
A future implementation packet, runtime evidence plan, and authorization are
separate gates. This document does not authorize reward/termination
implementation, Gym integration, command publishing, hardware operation, or
`deploy_real`.

## 9. Decision provenance and candidate status

Source decision packet: `WP-03_USER_DECISION_RESOLUTION_PROPOSAL.md`; branch `wp-03-decision-packet-baseline-2e7a2980`; commit `473d1cc6265dc14230fa47a89546b14a9de2a6eb`; SHA-256 `3559f21a07520f10ac1dceb0c2e6f888597a0215a63a5b8b91fce10d340e583c`.
Independent audit verdict supplied with the authorization: `READINESS_FOR_USER_REVIEW: APPROVABLE` (audit report SHA was not provided).

The dispositions are recorded in candidate branch
`wp-03-decision-contract-reconciliation-2e7a2980`, based on integration
`2e7a2980cb75f0567182ea694c04328d7d8643e0`. This D3 document remains a draft
candidate until independent audit and canonical integration.
