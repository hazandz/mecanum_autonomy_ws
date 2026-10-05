# V3 Observation Boundary Specification

**Revision:** `7`\
**Decision status:** `APPROVED_FOR_FOLLOW_ON_DESIGN_ONLY — OBSERVATION_INPUT_SEMANTICS; RECEIPT_BOUNDARY_CLOSED`\
**Runtime status:** `RUNTIME_NOT_APPROVED`\
**Decision owner:** Architecture lead, under the user's delegated project authority\
**Applies to:** the canonical V3 policy-observation path only

## 1. Purpose

This decision turns the frozen 81-element V3 observation schema into an
implementable boundary. It prevents the two errors found in the rejected
WP-04 candidate:

1. wiring a separate receipt/history path that never reaches the canonical
   observation vector; and
2. silently reusing the V1 PPO-decoder path as if it were a final-issued
   command path.

The future V3 path is profile-aware:

```text
validated profile ingress
  -> typed V3 snapshots
  -> V3 assembler and encoder
  -> immutable float32[81]
  -> policy consumer
```

The assembler is pure Python. ROS, TF lookup, QoS, queues, clocks, topic
subscriptions, command publication, simulation, and hardware remain outside
it.

## 2. Authorities and current-source findings

| Subject | Decision / finding |
| --- | --- |
| Observation shape | Fixed `float32[81]`: LiDAR `[0..71]`, local reference `[72..74]`, measured twist `[75..77]`, previous final-issued command `[78..80]`. |
| Component order | All velocity triplets are physical `[vx, vy, wz]`; `VelocityCommand` is `base_link`, m/s, m/s, rad/s. |
| Configuration | One immutable `ResolvedConfigV3` binds `schema_id = obs-v3-l72-g3-t3-c3-f32`, `config_hash`, frames, motion limits, topic contracts and owners to one assembler/session. |
| Present V1 code | `ObservationAssembler`, `RawLidarScan`, goal/twist extractors and `PreviousActionHistory` are V1-config- or simulation-bound. They are evidence of useful checks, not a canonical V3 implementation target. |
| Present V3 code | V3 models and compiler represent the schema, motion-limit policy, frame/TF and topic/QoS contract identifiers; no V3 assembler/encoder/consumer exists, and no complete resolved runtime profile has been demonstrated. |
| Hardware profile | The repository has an RPLiDAR A1M8 simulation sensor, not a YDLIDAR X3 driver, launch, URDF or measured profile. No simulation transform or limit may be copied to X3. |

Implementation does not automatically require an ACR only when it preserves the
already frozen 81D, final-command, safety and ground-truth-isolation semantics,
without changing a public topic, QoS, TF tree, action schema, reward contract
or safety boundary. The reset/`observation0` and public receipt decisions in
section 5 were approved together in ACR revision 6 and Receipt Topic QoS
Contract revision 4; that receipt boundary retains its approved status. The
semantic input-boundary design in Observation Input Contract V3 revision 6
is approved for follow-on design only. The complete profile-resolved contract
and composition, numerical profile values/evidence, and implementation remain
unapproved. This specification is not implementation authority and does not
change the frozen 81D, receipt/QoS, TF, or safety semantics.

## 3. Canonical V3 boundary

### 3.1 Session binding

`V3ObservationAssembler` shall be constructed with exactly one immutable
`ResolvedConfigV3` and one active lifecycle context. The session owns the
following immutable binding:

- `schema_id` and `config_hash` from the resolved config;
- current `reset_epoch` and `runtime_generation`;
- action and reset ROS-time barriers;
- an explicit, resolved observation timing policy;
- resolved goal-distance and LiDAR-sectorization policies;
- one resolved LiDAR extrinsic contract for `T_base_lidar`; and
- one immutable `ObservationCutoffV3` from the canonical
  `RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)` transaction,
  including transaction/lifecycle/schema/config identity, one profile ROS-time
  cut-off and the immutable SafetyLifecycle barriers.

The timing policy binds exact S2 contract
`mecanum.snapshot-synchronization-temporal/v1` / `1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f`. S2 and receipt
history must consume the same `ObservationCutoffV3`; neither derives a second
cut-off. `RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)` owns the
cut-off/transaction identity, while `SafetyLifecycle` still solely owns the
barrier values carried by it. The cut-off is valid only when it is strictly
after both barriers; otherwise the result is
`CUTOFF_BARRIER_ORDER_NON_READY` with no vector.

`SafetyLifecycle` is the **sole** creator and owner of the action/reset
ROS-time barriers for every runtime profile, including `sim_train`. The
assembler session, ingress, `SimulatedOdometryEmulator`, and
`SimTrainLocalReferenceBuilder` receive those barriers as immutable inputs and
may only test eligibility against them. They must never create, advance,
translate, substitute, or compare against a second barrier.

For `sim_train`, emulator/local-goal timestamps are profile ROS-time stamps,
not an independently-owned simulation clock. When `use_sim_time=true`, that is
the profile ROS clock in the same nanosecond unit and epoch as the supplied
SafetyLifecycle barriers. This rule preserves the internal/no-public-odometry
design: it does not require a synthetic odometry message, a public TF edge, or
a cross-process steady-clock comparison.

`config_hash` is a *session/run binding*, not a field required on each raw ROS
message. A final-issued receipt must carry the same hash because it crosses the
command/observation boundary. External raw scan, twist and localisation
messages instead carry their source identity, lifecycle identity and time
provenance. `sim_train` supplies the same semantics through its approved
internal typed snapshots; it does not manufacture ROS messages or TF merely to
fit this boundary.

### 3.2 Required typed inputs

The assembler shall accept only one complete candidate containing the four
inputs below. No input may be derived from PPO output or simulator ground
truth.

| Input | Required content | Validated producer boundary | Forbidden substitute |
| --- | --- | --- | --- |
| `LaserGeometrySnapshot` | immutable ranges, angle geometry, range minimum/maximum, exact header frame, ROS stamp, steady receive stamp, reset epoch, generation, source identity, validity, immutable `T_base_lidar`, and its profile/extrinsic provenance | ROS adapter validates `LaserScan`, expected topic/QoS/frame, captures the configured transform and records steady receipt time | fabricated 72 values, missing/default transform, V1 `RawLidarScan`, GT obstacle state |
| `NavigationLocalReference` (`sim_eval`, `deploy_sim`, `deploy_real`) | source/transform/reference ROS stamps, steady expiry, point expressed in `base_link`, distance, bearing, lifecycle/provenance | localisation adapter obtains its transform using the configured V3 localisation authority | simulator pose, map-frame point passed as local reference, a goal inferred from policy state |
| `SimTrainLocalReferenceSnapshot` (`sim_train`) | approved episode-goal contract identity, point in `base_link` semantics, profile ROS-time reference stamp from the emulator snapshot, source snapshot sequence, reset epoch, generation, source identity and validity | `SimTrainLocalReferenceBuilder` derives it only from episode-goal intent plus the noisy `SimulatedOdometryEmulator` typed snapshot; it consumes the SafetyLifecycle barriers | raw Ground Truth pose/world object/buffer, public odometry/TF surrogate, localisation-adapter or PPO-derived goal, independently-created/translated barrier |
| `EkfMeasuredTwistSnapshot` (`sim_eval`, `deploy_sim`, `deploy_real`) | physical body `vx, vy, wz`, units, `base_link`, odometry ROS stamp, steady receipt stamp, lifecycle, source identity and validity/fault provenance | configured EKF/state-estimation boundary, not a desired command | wheel-command estimate, PPO action, perfect simulator velocity |
| `SimTrainMeasuredTwistSnapshot` (`sim_train`) | physical body `vx, vy, wz`, units, `base_link` semantics, profile ROS-time stamp from the emulator snapshot, source snapshot sequence, lifecycle, source identity and validity provenance | `SimulatedOdometryEmulator` noisy typed snapshot; it consumes the SafetyLifecycle barriers | raw Ground Truth velocity/pose, public odometry/TF surrogate, wheel-command estimate, PPO action, independently-created/translated barrier |
| `FinalIssuedCommandReceipt` | physical final command, envelope provenance, local publication evidence and times described in section 5 | `FinalTwistPublisher`, after `SafetySupervisor` selected/limited the command | decoder output, Nav2/PPO candidate, safety candidate not issued for publication, actuator acknowledgement |

### 3.3 Separate timing and provenance rules

All inputs must belong to the active `reset_epoch` and
`runtime_generation`, have finite payloads, and match their declared
source/frame/unit policy. Their timing rules are deliberately different:

| Input group | Required timing and lifecycle rule |
| --- | --- |
| External input triple (`sim_eval`, `deploy_sim`, `deploy_real`) | S2 globally selects one `(scan, EKF motion, NavigationLocalReference)` triple, all at/before the shared `ObservationCutoffV3`, post-barrier and within individual steady receive ages. It requires both scan-motion and reference-motion skew limits, then ranks every eligible triple by latest coherence time, smaller worst skew, timestamps and stable arrival identities. |
| Internal input triple (`sim_train`) | S2 globally selects one `(scan, noisy emulator motion, SimTrainLocalReferenceSnapshot)` triple under the same shared cut-off and barriers. Local reference must identify the exact selected emulator snapshot contract/source/sequence; no internal barrier, fabricated ROS header, timestamp conversion or cross-process steady-time comparison is permitted. |
| `FinalIssuedCommandReceipt` | It matches lifecycle, schema/hash, source/mode and final-publisher provenance. Receipt history selects only against the **same** `ObservationCutoffV3` supplied to S2; it has no sensor-skew test and is not rejected merely because its command is older than a sensor. |

The exact numerical freshness and skew limits remain profile measurements. They
must be supplied through a resolved `ObservationTimingPolicyV3`; they must not
be hard-coded, guessed from YDLIDAR specifications, or copied from simulation.

On any failure, the result is a typed non-ready status holding **no vector**.
There is no zero-fill, reuse of the previous input, nearest-neighbour lookup,
silent frame alias, stale fallback or fabricated reward/policy step. The runtime
and safety lifecycle later decide the safe-stop response.

## 4. Feature construction

### 4.1 LiDAR features `[0..71]`

The V3 LiDAR core shall implement a dedicated `LidarSectorizerV3`; it must not
import or delegate to V1 `RawLidarScan` or its binner. Its resolved policy
defines the angular coverage, 72 bin boundaries, endpoint convention and
`range_min`/`range_max` for the active profile. The snapshot's immutable
`T_base_lidar` must match the session's resolved extrinsic contract. It has no
default value and, for YDLIDAR X3, remains `TBD_MEASURED` until physical
calibration is approved.

For each raw ray, it applies the architecture range rule in the sensor range
domain. It then transforms the ray endpoint through `T_base_lidar` to determine
the angular sector in `base_link`; the value retained for that sector remains
the sanitized sensor-ray range and is divided by the resolved profile
`range_max`. This avoids silently treating a rotated or offset sensor frame as
`base_link` while preserving the architecture's range-normalization rule:

| Raw range | V3 treatment |
| --- | --- |
| finite and in range | use its clipped physical value |
| greater than maximum or `+Inf` | use `range_max`; record no-return diagnostic ratio |
| `NaN`, `-Inf` or `<= 0` | use `range_max`; record invalid diagnostic ratio |
| finite below minimum | use `range_min`; record invalid diagnostic ratio |

No-return and invalid ratios are diagnostics/provenance only: the frozen vector
has exactly 72 LiDAR values and no spare feature positions. Missing sector
coverage or invalid scan geometry yields non-ready rather than a synthetic
value.

### 4.2 Local-reference features `[72..74]`

The only order is:

```text
[ clip(distance_m / goal_distance_scale_m, 0, 1), sin(bearing_rad), cos(bearing_rad) ]
```

`goal_distance_scale_m` is a resolved V3 policy value, not a literal in Python.
The reference point and bearing must already be in `base_link` semantics. For
the external navigation variant, the core checks the declared frame and
localisation source identity against the resolved V3 contract; a localisation
adapter owns ROS/TF lookup. For `sim_train`, it checks the internal-builder,
episode-goal, emulator-snapshot, lifecycle and profile-ROS-time provenance
instead. The policy/core never sees raw Ground Truth in either variant.

### 4.3 Measured-twist features `[75..77]`

The order is physical body twist `[vx, vy, wz]`. `sim_eval`, `deploy_sim` and
`deploy_real` use only the configured EKF snapshot. `sim_train` uses only the
noisy typed `SimulatedOdometryEmulator` snapshot; Ground Truth is not a
permitted substitute. Each component is divided by the corresponding resolved
`MotionLimitTargetPolicyV3` maximum:

```text
[ vx / max_vx_mps, vy / max_vy_mps, wz / max_wz_radps ]
```

Every maximum is positive and finite. The following is a **V3 policy decision**,
not an architecture fact: a non-finite component or an absolute physical value
above its maximum is invalid; V3 does **not** silently clip it. This rule, its
status code, and its maxima must be covered by the resolved config hash. Thus a
ready result is within `[-1, 1]` per axis while exposing a bad producer as a
typed failure.

### 4.4 Previous final-issued command `[78..80]`

The only source is the selected receipt in section 5. Its physical final
command uses the same per-axis `MotionLimitTargetPolicyV3` normalization and
the same `[vx, vy, wz]` order as measured twist. A PPO normalized action,
decoder result, Nav2 candidate, prior V1 history object or wrapper around one
is rejected by type and provenance checks.

## 5. Approved final-issued receipt interface, bridge and history

The public, cross-process receipt protocol is governed by the approved
`ACR_V3_OBSERVATION_BOUNDARY_CLOSURE` revision 6 and
`RECEIPT_TOPIC_QOS_CONTRACT` revision 4. They supersede earlier local-record
wording in this specification.

`FinalIssuedCommandReceipt.msg` contains the required
`std_msgs/Header header`, exact `base_link` frame, CommandEnvelope provenance,
`final_publisher_instance_id`, `final_publish_sequence`, decision/publication
code, schema/config identity, and planar final `geometry_msgs/Twist`. Its exact
receipt-interface pair is `mecanum.final-issued-receipt/v1` /
`90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e`.
Its exact topic-QoS pair is
`mecanum.final-issued-receipt-topic-qos/v1` /
`a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62`.

The receipt means only that `FinalTwistPublisher` locally issued the final
`/cmd_vel` command after safety arbitration. It is neither DDS-delivery proof
nor actuator acknowledgement; measured twist remains the actual-motion input.
Detailed limiter reasons remain in `SafetyState`/diagnostics and no safety
steady timestamp crosses this public boundary.

`V3ObservationIngress` may create an immutable pure-Python ingress projection
of this public message for the assembler. It must not reconstruct a receipt
from `SafetyState`, PPO/decoder output, Nav2 candidates, or a synthetic zero.
Its history admits only compatible active-lifecycle receipts and receives the
same immutable `ObservationCutoffV3` as S2. It follows the approved action/reset
barrier, coalesced-gap, late-join and cut-off selection rules, but does not
create a separate cut-off. A `SOURCE_SAFE_STOP` zero envelope is constructed by
`CommandArbiter` under `SafetySupervisor`; `FinalTwistPublisher` only issues
the final Twist and receipt.

### Reset closure for `observation0`

The approved reset sequence is: inhibit normal sources, issue the
architecture-required pre-reset zero, increment epoch and clear history, have
`SafetyLifecycle` create the reset barrier, then have `CommandArbiter` select a new-epoch post-barrier
`SOURCE_SAFE_STOP` zero envelope. `FinalTwistPublisher` issues the final zero
and receipt. The observation layer waits for that receipt and valid new-epoch
sensor/reference inputs before encoding `observation0`. The pure core never
manufactures this zero.

## 6. Responsibilities and non-delegation

| Boundary | Owns | Must not do |
| --- | --- | --- |
| `SafetyLifecycle` (all profiles) | create and own action/reset profile-ROS-time barriers; supply immutable barriers to ingress/snapshot producers | delegate or duplicate barrier ownership, create a per-simulator barrier, or compare a foreign time domain |
| `RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)` | create one `ObservationCutoffV3` per transition transaction and supply it unchanged to S2 and receipt history; ensure cut-off is strictly after both supplied barriers | own SafetyLifecycle barriers, create another cut-off in an input path, repair an invalid cut-off, or publish a new ROS protocol |
| External ROS adapter/lifecycle | ROS API, topic/QoS compatibility, TF lookup, source identity, raw message validity, steady receipt time and freshness transport evidence; consume SafetyLifecycle barriers | build a policy vector, use GT as an observation fallback, invent core normalization, or create/translate a barrier |
| `sim_train` internal boundary | `SimTrainLocalReferenceBuilder`, approved episode-goal intent, noisy emulator pose/twist snapshot provenance and Ground Truth isolation; consume SafetyLifecycle barriers in profile ROS time | publish synthetic odometry/TF, expose raw Ground Truth to the policy/core, claim a localisation-adapter path, or create/advance/translate a barrier |
| V3 pure core | typed invariants, frame/provenance/lifecycle/time compatibility, feature math, fixed ordering, finite `float32[81]`, typed non-ready results | read ROS, execute TF, publish, choose QoS, repair stale/faulty data |
| Safety/final publisher | arbitration, limiting, `/cmd_vel` ownership, final-issued receipt creation and final ordering | report actuator acknowledgement without one, let a candidate bypass the receipt contract |
| Policy consumer | consume only a ready immutable V3 vector | accept raw snapshots, call ROS, substitute a V1 or PPO command |

Exact X3 `header.frame_id` and the measured `T_base_lidar` must be bound to the
resolved profile's `frames_tf.lidar_frame` and extrinsic contract before runtime
approval. `lidar`, `lidar_frame` and `real_lidar` are not aliases and must
never be silently remapped in core code.

## 7. Gates before a future Codex work package

The following pure-Python work is architecturally outlined, but no work package
may be opened until `ObservationInputContractV3` and the required S2 timing
decisions are approved. It must then be implemented in one connected V3 path
and reviewed before integration:

1. create V3-only immutable snapshot, timing-policy, receipt/history and
   status types;
2. implement V3 sectorization, local-reference, measured-twist and
   final-command feature blocks, including `T_base_lidar` sector mapping;
3. implement `V3ObservationAssembler` and `V3ObservationEncoder`, producing
   precisely the 81 ordered `float32` values only from ready V3 inputs;
4. expose one V3 consumer seam; do not modify or delegate to the V1 assembler;
5. add pure-Python tests for vector order, per-axis normalization, invalid
   scan handling, `T_base_lidar` angle mapping, separate sensor/reference/
   receipt timing, single-owner barrier/time-domain mismatch, missing receipt, asynchronous
   zero selection, reset `observation0`, internal sim-train local-goal and
   measured-twist provenance/Ground-Truth rejection, type rejection and no
   decoder fallback.

The work package may inspect and modify only the ROS package's Python source
and pure-Python tests. It must not run tests, a build, ROS, Gazebo, PPO, Nav2,
drivers, serial I/O, hardware or a push without its separate authorization.

## 8. Remaining gates before runtime and YDLIDAR X3 use

This decision is sufficient for pure-core design, not for a real robot. Before
an X3 runtime profile can be approved, the project still needs a static
inventory and a measured profile for the exact driver/interface, frame,
mounting transform, range behaviour, invalid/no-return encoding, scan cadence,
transport jitter, QoS, freshness/skew values, serial settings and calibration.
Those are physical evidence tasks. They are deliberately not guessed here.

## 9. Acceptance verdict

`V3_RECEIPT_BOUNDARY: APPROVED_BY_USER`\
`OBSERVATION_INPUT_CONTRACT_V3: APPROVED_FOR_FOLLOW_ON_DESIGN_ONLY`\
`S2_SENSOR_TIMING: VALUES_UNRESOLVED`\
`CANONICAL_V3_IMPLEMENTATION: NOT_YET_IMPLEMENTED`\
`V3_OBSERVATION_IMPLEMENTATION: NOT_AUTHORIZED`\
`YDLIDAR_X3_RUNTIME_PROFILE: NOT_YET_MEASURED`\
`RUNTIME_NOT_APPROVED`
