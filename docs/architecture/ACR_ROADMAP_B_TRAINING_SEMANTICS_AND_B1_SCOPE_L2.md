# ACR — Roadmap B Training Semantics and B1 Scope (L2)

**Decision ID:** `ROADMAP_B_TRAINING_SEMANTICS_AND_B1_SCOPE_L2`
**Status:** `OWNER_AUTHORIZED_L2_AMENDMENT_FOR_ROADMAP_B`
**Authority:** Lead Robotics Architect approval under Owner delegation dated 2026-10-27; Owner execution instruction dated 2026-10-29.
**Implementation scope:** B1 pure core and the separately scoped B2.1 configuration/interface candidate (offline only).

## 1. Relationship to frozen Architecture

This ACR records approved Roadmap B amendments. These semantics are not
represented as pre-existing text in `MECANUM_NAV_DRL_Architecture.docx`, which
remains the highest architecture authority outside the explicit amendments
below. No Architecture DOCX bytes, Safety limit, global configuration hash
algorithm, or current resolved configuration is changed by the B1 historical
scope. For B2, §5 is the explicit L2 exception approved by the Owner for two
new public ROS message interfaces; this ACR amendment is not text that was
already present in the frozen Architecture DOCX. The amendment does not
authorize runtime, training, integration, HIL, or real robot activity.

## 2. Roadmap B profile and collection semantics

1. Training targets `sim_train` / `LOCAL_TRAINING`. Benchmark simulation uses
   `NAV2_BASELINE` or `HYBRID_AI_LOCAL`. Policy observation remains
   `float32[81] = LiDAR72 + LocalReference3 + measured twist3 + previous
   final-issued command3`; action remains normalized `float32[3]` in
   `[vx, vy, wz]`, preserving `vy`.
2. Gate 1's Roadmap B simulation evidence is objective contract and
   fault-injection coverage plus a bounded soak of 30 successful transactional
   resets and 1,000 issued commands, including forward, reverse, lateral,
   rotational and diagonal motion. Any invalid transition, silent stale/GT
   fallback, or unexpected infrastructure failure fails the gate; injected
   expected faults must be rejected or safe-stopped correctly. Counts do not
   decrease after a failure. B1 supplies pure tests; B2 owns substrate/soak;
   B3 proves Gym correctness before the first optimizer update. B1 does not run
   the soak or claim Gate 1 pass.
3. Collection runs continuously at nominal 0.10 s ROS period and uses actual
   simulation `dt` for reward. A complete rollout and bootstrap/returns are
   followed by safety stop/near-zero, pause, PPO update/checkpoint/validation,
   fresh transactional reset, and the next segment. Dedicated safety and
   steady TTL/watchdog remain effective; nonzero commands do not persist
   through optimizer gaps. Timer, TTL and receipt runtime mechanics belong to
   B2/B3.
4. A segment cutoff is orchestration metadata, not an MDP terminal or Gym
   transition. The last valid transition retains its reward, flags and next
   observation; bootstrap uses the last valid pre-stop state, never the reset
   observation. An unfinished episode is `COLLECTION_CUTOFF`,
   `episode_complete=false`, with elapsed time, length, return-to-date and
   censored exposure. It is not labeled success, collision, timeout, or
   `is_success=false` as a task result. Reset clears command history, contact,
   stuck and settle state. Partial rollout is not retained across
   infrastructure failure and private SB3 buffers are not modified. B1 adds
   no Gym, trainer or SB3 wrapper.
5. Evaluation runs each task to true terminal or a preregistered evaluation
   horizon, independent of `n_steps`, training budget or checkpoint cadence.
   Baseline and all three Hybrid models use the same horizon. Infrastructure
   timeout is not task timeout. B1 tests pure data only.
6. Roadmap B baseline is holonomic NavFn + DWB at canonical base with
   `max_vx=0.25`, `max_vy=0.20`, `max_wz=0.80`, and
   `max_speed_xy=0.32015621187164245`, under the common hard Safety envelope.
   This replaces MPPI Omni only for this Roadmap B experiment. Hybrid uses
   Nav2 Planner + PPO and does not run DWB/FollowPath in parallel. No Step-7
   launch/YAML or final-test tuning changes are authorized here.
7. `LOCAL_TRAINING` uses `LOCAL_TASK_GOAL` and noisy emulator odometry; Hybrid
   uses `GLOBAL_PATH`, localized odometry and localization health. B2 must
   version and bind those semantics into the global config/schema
   compatibility and create a new hash with the existing algorithm. B1
   creates no resolved `sim_train` artifact or replacement hash.

## 3. B1 immutable pure-core contracts

1. Receipt-v2 selection binds publisher instance, session and global config
   identity in ingress context. Receipt-v2 has no config-hash field. Final
   publication ordering uses `final_publish_sequence`; the publish stamp is
   taken after successful sequential `/cmd_vel` publication. At cutoff `t_C`,
   select the greatest publication sequence whose stamp is at or before `t_C`.
   Commit requires the adjacent next sequence with
   `t_C < stamp <= evaluation_ros_now`. Equal-stamp publications are ordered
   by final sequence. The adjacent trailing receipt proves the cutoff boundary
   only; its payload is not observation input. Missing adjacency is pending;
   mismatch, rollback or conflicting duplicates reject. No sleep, clock read,
   retry, or receipt request occurs in pure core. Only two adjacent receipts
   are required. A stop after cutoff cannot rewrite that snapshot.
2. The issued action key matches POLICY source instance/sequence and lifecycle.
   The selected command may be a subsequent valid SAFE_STOP. Normalize the
   actual final physical payload by per-axis scale and reject out-of-envelope
   values; do not clamp or synthesize zero. No receipt means no reset commit or
   transition. Receipt is publication evidence, not actuator acknowledgement.
3. `LOCAL_TRAINING` reference is computed from task goal metadata and one exact
   `VALID` noisy odometry snapshot. For `p_ref_base = R(-yaw_hat) * (goal -
   noisy_pose)`, output `float32([clip(norm/10,0,1), sin(bearing),
   cos(bearing)])`; distance zero maps to `(0,0,1)`. It carries the same exact
   timestamp/sequence as the noisy snapshot, and exact scan/noisy-odometry
   skew is zero. DELAYED, DROPPED, future or stale samples reject. No raw GT
   message/reference reaches observation code. No public odometry or TF is
   added.
4. LOCAL_TRAINING goal success uses true oracle distance `<=0.15 m`, planar
   body speed `<=0.03 m/s`, angular speed `<=0.05 rad/s`, and all required
   health continuously for 1.0 s ROS. Final yaw is not required. Health covers
   simulator/clock, reset/scenario/world/session/lifecycle/barrier, Safety,
   scan, noisy odometry/reference/twist, hidden oracle pose/twist, contact and
   selected receipt. It does not require AMCL, Nav2 or Hybrid state. Maximum
   ROS age and receive steady age use equal per-input budgets: scan 500 ms;
   noisy odometry 250 ms; oracle 250 ms; lifecycle 500 ms; receipt 500 ms.
   Future stamps reject; clock domains are never subtracted from each other.
   Existing step and reset steady deadlines remain 2 s and 15 s. Noise,
   estimate proximity or noisy goal arrival cannot establish oracle success.
5. One transition is prepared completely before committing observation, reward
   terms, terminal flags/reason, info, command history, reward baseline and
   contact pulse consumption. Failure before commit leaves all committed
   state unchanged. `ContactLatch` is pure: active contact OR pending pulse is
   collision; true sets both, explicit healthy empty clears only active,
   silence changes nothing, reset clears and rejects old lifecycle facts, and
   successful commit consumes a pulse once without clearing sustained active
   contact. Abort preserves the pulse.
6. Reward-v3-baseline is retained:
   `r_progress=clip(2*delta_d,-1,1)`, `r_time=-0.10*dt_sim`,
   `r_clearance=-0.20*max(0,(0.30-clearance)/0.30)*dt_sim/0.10`,
   `r_smooth=clip(-0.005*dot(u-u_prev,u-u_prev)/max(dt_sim,1e-6),-1,0)`,
   terminal `+15 goal | -15 collision | -3 stuck | 0 otherwise`; total is the
   sum within `1e-6`. Commands are normalized final-issued payloads. `dt_sim`
   must be finite and positive. Infrastructure failures produce no transition
   or task penalty.
7. `STUCK` requires an actually covered 10 s ROS history, planar spread
   `<0.10 m`, and true goal-distance reduction `<0.10 m`; missing-health gaps,
   reset and rollback cannot bridge the window. Termination precedence is
   collision > goal > out-of-bounds > stuck > 120 s simulation horizon.
   Task terminals set `(terminated=true,truncated=false)`; horizon sets
   `(false,true)`. A terminal event wins a simultaneous limit. Out-of-bounds
   requires an explicitly bound valid-area authority. Collection cutoff and
   infrastructure errors are not task termination.
8. V3 action decoding takes explicit typed physical scales, preserves `vy`,
   and rejects non-finite/out-of-range actions. A compatibility entry for old
   pure callers may remain; B1's V3 path does not fall back to V1 config.
9. Observation0 requires an actual post-reset-barrier published zero
   SAFE_STOP receipt and a post-rearm authoritative lifecycle identity. A
   generation is never guessed by incrementing an old value.

## 4. Evidence and implementation boundary

B1 is pure/offline implementation plus targeted pure tests. It does not add
environment, trainer, runtime adapters/producers, ROS interfaces, launch or
configuration changes. It does not run Gate 1 soak, simulation, evaluation,
training, optimizer updates, Gate 3/4, HIL or hardware. B1 evidence can reach
`IMPLEMENTED_OFFLINE_ONLY_PENDING_INDEPENDENT_AUDIT` only after its authorized
implementation, required offline checks and candidate delivery. Independent
audit and integration remain separate decisions. B2 owns simulator/runtime
substrate and soak; B3 owns Gym/PPO smoke and dependency freeze; B4–B8 remain
independent downstream Roadmap B work.

## 5. B2.1 mode-specific configuration and interface amendments (L2)

Owner execution instruction dated 2026-10-29 authorizes this continuation
under this same Decision ID. It does not create a new Decision ID or alter the
frozen Architecture. The Owner identifies B1 as `CLOSED` and integrated at
base `bbd5a3c68e6745b5d143688266e044fa25093390`; this is an explicit Owner
status statement, not an inference from commit ancestry and not an independent
audit or Gate 1 claim. B2.1 is an offline source candidate. B2 remains open;
B2.2/B2.3, runtime, Gate 1, integration, HIL, training, and real-robot
validation are not authorized by this amendment.

### 5.1 Typed schema 3.1 and compatibility boundary (D1)

`sim_train` is paired only with `LOCAL_TRAINING`, `use_sim_time=true`,
`INTERNAL_SIMULATED_ODOMETRY`, and `NOT_APPLICABLE_LOCAL_TRAINING`. Its goal
source is `LOCAL_TASK_GOAL`; this mode does not require AMCL, Nav2, or
FollowPath. `base_link` and `lidar_frame` remain the sensor frames, with the
actual static extrinsic to be bound to a future robot/sensor asset. The mode
declares no `map -> odom` or `odom -> base_link` authority. Its scenario/world
identity is separate from an occupancy-map artifact.

The canonical root remains the existing sixteen architecture sections plus
schema/provenance metadata. There is no `backend` or `gui` root. Schema 3.0
inputs keep their serialization/API behavior; optional 3.1 fields are omitted
when absent. Legacy profiles receive no default training fields. Hashing
remains the existing SHA-256/JCS implementation and projection. The existing
`sim_eval` hash remains
`501a661b1ebde9b846325cc589927823e101375a6a189fcf84cac9ac8bf0aabe`.

The seven canonical structural fragment positions remain unchanged. The new
`LOCAL_TRAINING` frames and topic/QoS fragments are independent of `sim_eval`;
they do not rewrite the shared `frames.yaml` or `topics.yaml`. Unresolved
asset/scenario requirements remain input-layer values. Production resolution
must reject a missing binding, `UNRESOLVED`, or `TEST_ONLY` binding before
hashing and return no partial resolved object. Test fixtures are never
production resolved artifacts.

### 5.2 Simulation command, safety, timing, and stopping descriptor

These values describe the approved simulation profile only: `vx=0.25 m/s`,
`vy=0.20 m/s`, `wz=0.80 rad/s`, planar norm
`0.32015621187164245 m/s`; normal acceleration `0.50 m/s²` on x/y and
`1.00 rad/s²` angular; normal jerk `2.0 m/s³` on x/y and `4.0 rad/s³`
angular. Safety period is 20 ms; POLICY TTL is 200 ms; accepted final-command
and native actuator-watchdog limits are each 100 ms steady. These are distinct
from B1 receipt admission limits of 500 ms ROS and receive-steady age. Scan
age is 500 ms in both clocks; noisy odometry and oracle age are 250 ms in both
clocks; lifecycle age is 500 ms in both clocks; backend/contact receive age
while running is 200 ms steady.

The proposed bounded simulation stopping calculation uses body radius 0.35 m,
clearance 0.05 m, geometry reserve 0.02 m, 0.50 s ROS scan budget, 0.10 s
steady post-decision pipeline budget, 2.0 permitted ROS/steady advance
factor, 0.01 s ROS physics step and clock reserve, proposed braking
`0.50 m/s²`, and braking jerk `2.0 m/s³`. The specified equation gives
`T_r=0.72 s ROS`, `A_plus=hypot(0.50,0.50)`,
`T_cancel=A_plus/2`, `T_brake=V/0.50+0.50/2`, and
`D_total=0.9062243132582557 m`; the proposed cap is `D_stop_max=0.92 m`.
This replaces the prior 0.583 m proposal. These assumptions are not runtime
measurements; ordinary acceleration limits do not prove braking capability.
If later assets or runtime checks cannot meet them, POLICY remains closed and
no threshold is relaxed by inference. Distance is evaluated after transforming
the scan into `base_link`. The bounding circle and stopping envelope are a
limited L2 simulation simplification, not a complete robot protective system
or functional-safety proof.

### 5.3 Local training interfaces and receipt-carrier boundary (D2, D3, D4)

`LocalTrainingSafetyInput` is a public safety-only noisy-twist/admission
interface. It is not `nav_msgs/Odometry`; it has no pose, goal, or raw Ground
Truth. `/mecanum/local_training/safety_input` has one session-bound ingress
publisher and is consumed by local Safety and backend admission. Its stamp is
the source noisy-odometry stamp in `base_link`; valid twist is `[vx,vy,wz]`
in SI units and exactly three finite values. DELAYED/DROPPED carries an empty
array. Config hash uses 64 lowercase hexadecimal characters. Consumers capture
steady receive time locally. QoS is RELIABLE/VOLATILE/KEEP_LAST(10).
`POLICY_OPEN` requires a valid observation0 receipt proof; other admission
states carry no fabricated proof.

B2 backend admission treats the unchanged receipt-v2 payload as the atomic
actuator carrier; `/cmd_vel` remains published only by
`FinalTwistPublisher` and is captured by the backend. No second bridge or
actuator may consume `/cmd_vel` to move the simulated robot. The publication
key is bound ingress `(session_id, config_hash, final_publisher_instance_id,
final_publish_sequence)`. Receipt-v2 has no session/config fields; the
implementation does not claim otherwise. Admission also binds lifecycle,
frame, source identity, barrier, freshness, and POLICY transition UUID.

One POLICY issuance belongs to each pending step; source sequence equals
one-based step index. Waiting for a snapshot does not create another issuance.
The next issuance follows committed transition; abort/retry in the same
identity never rewinds sequence. Session ID is Run ID and source instance is a
nonzero boot nonce. B1 `policy_transition_identity()` remains the identity
function. Safety retains POLICY identity across timer ticks. SAFE_STOP has an
independent source instance/counter. Final publication sequence advances for
each actual publication. The publisher emits `/cmd_vel` first, samples its
stamp after publication, then emits the receipt. POLICY receipt uses the bound
step/UUID; SAFE_STOP uses step zero and empty transition UUID.

Correct next sequence is validated and applied once. Exact duplicate is
ignored without refreshing watchdog; same key with changed content is a fault;
older sequence is replay and does not refresh watchdog; a gap or reordering
zeros and closes the admission segment. Missing receipt reaches the separate
100 ms steady actuator watchdog. A late receipt does not reopen a faulted
segment. Startup anchor is only a matching post-barrier SAFE_STOP zero while
inhibited. Backend or final-publisher restart invalidates the session. A
watchdog zero never creates a receipt or observation. Receipt remains evidence
of publication, not actuator acknowledgement. B1 previous-command observation
continues to represent the actual final-issued command.

The native backend independently owns zero/watchdog state; backend status
cannot fabricate a receipt. During local-zero override, applied receipt is
invalid and all applied publication key/stamp/iteration fields are zero.
`SimulationContactState` reports state, coverage and a receipt key only; it
cannot establish achieved velocity.

### 5.4 Contact coverage contract (D5)

The future native backend reads contact sensor data after each Physics update
and covers every collision in a bound asset manifest. The manifest may track
at most 64 collisions; an oversized asset is rejected. Unsupported contact
engine, missing component, iteration gap, or ingress queue overflow (capacity
128) is unhealthy, never healthy-empty. Only the exact wheel-floor pair from
the manifest may be ignored, and only for finite valid normal within 15 degrees
of vertical and finite depth in `[0,0.005] m`. Chassis-floor is not filtered.
Known robot-external contact is contact. A wheel-floor report without valid
normal/depth is unhealthy/inhibited and creates no invented collision
penalty. A confirmed contact pulse is retained even alongside a health fault.

Contact clear needs three consecutive healthy covered samples at iterations
`k,k+1,k+2` spanning at least 20 ms ROS. Silence and paused heartbeat do not
clear contact or advance coverage. An iteration gap cannot heal from one empty
sample; reset is required. Complete coverage requires the observed collision
mask to cover the manifest-required mask and no missing physics iteration.
These are future runtime obligations, not B2.1 test evidence.

### 5.5 Reset, admission, and clock contract (D6)

Future Jazzy/Harmonic services are
`/world/b2_training_arena/control` (`ros_gz_interfaces/srv/ControlWorld`) and
`/world/b2_training_arena/set_pose` (`ros_gz_interfaces/srv/SetEntityPose`).
The entity is the exact model name `mecanum_b2`; cached numeric entity IDs are
not reused. Reset order is: new identity request; actual zero receipt and
near-zero; confirmed pause; pose request/ACK; emulator seed and buffer reset;
resume while inhibited; pose/twist/contact measurement; one explicit rearm;
authoritative lifecycle/barrier; fresh exact scan/odometry pair plus reset-zero
cutoff proof; observation0 commit. Service ACK alone does not prove achieved
pose/twist. `motion_permitted` is not a prerequisite to explicit rearm.
Episode reset does not use `reset.all` or reset the simulation clock.

Total reset deadline is 15 s steady; stop/standstill phase is at most 5 s
steady and braking target at most 2 s ROS; each service timeout is 1 s; pause
and resume confirmation each have 2 s, all inside the total deadline. Pose
limits are XY 0.01 m, yaw 0.02 rad, roll/pitch 0.05 rad, and Z 0.02 m.
Standstill uses oracle/backend measurement: 3-D linear norm at most 0.01 m/s,
3-D angular norm at most 0.02 rad/s, continuously for 0.20 s ROS and at least
21 100 Hz samples with no missing iteration. Noisy twist need not be zero.
Contact must clear and footprint clearance includes 0.05 m expansion.

Unintended clock stall at 200 ms steady causes zero; 1 s causes infrastructure
abort. Rollback invalidates and aborts the session without guessing a new
generation. Expected pause creates no zero-dt transition while steady watchdogs
continue. POLICY opens only after observation0 commit; matching selected zero
receipt after barrier; backend application of that receipt without local
override; continuous contact coverage to cutoff; no contact pulse; and all
current health valid with no reset, pause, or fault. Contact after cutoff does
not rewrite observation0 and blocks the next actuator step. Rearm alone never
reopens POLICY.

### 5.6 Noise, world, scenario, and collection descriptors (D7, D8)

The simulation-only nominal profile is `B2_NOISE_N0_V1`: per-episode position
bias sigma 0.005 m per axis and yaw bias 0.010 rad; per-input-tick position
drift 0.0001 m per axis and yaw drift 0.0001 rad; linear velocity noise
0.003 m/s per axis and yaw-rate noise 0.005 rad/s; 100 Hz input, nominal
0.01 s ROS tick, zero delay and zero dropout. The existing
`SimulatedOdometryEmulator` Gaussian zero-mean algorithm stays unchanged;
drift advances on input tick, not action. Negative `B2_NOISE_DELAY_V1` uses
30 samples (nominal 300 ms), and `B2_NOISE_DROP_V1` uses dropout probability
1.0. Delayed/dropped input yields no vector and no synthetic current stamp;
validation does not clamp noisy measurement. World seed is 20261029; soak
seeds are `2026102900+i`, `i=0..29`; fault seeds are `2026103000+case_index`.

Future world descriptor is `b2_training_arena`, entity `mecanum_b2`, 0.01 s
ROS physics step, target real-time factor 1, 8 m by 8 m interior, 1 m wall
height and 0.20 m thickness, obstacle at `(2.5,0)` sized `(0.2,1,1) m`, and
a 0.10 m, 1 kg contact probe. Spawn proposal `(0,0,0.10)` with zero yaw must
be validated by assets/measurement. Sensor descriptor is
`B2_GENERIC_2D_V1`: LiDAR 10 Hz, 500 beams, `-pi..pi`, range 0.10..8 m in
`lidar_frame`; Ground Truth is 100 Hz. Scan/noisy-odometry stamps pair exactly;
1 ns mismatch rejects. Buffers are bounded at 64; no nearest match,
interpolation, or stamp relabeling.

Future scenarios are: `B2_SOAK_V1` start `(0,0,0)`, goal `(2,2)`;
`B2_GOAL_SETTLE_V1` start/goal `(0,0)` with zero command; and
`B2_CONTACT_V1` start `(0,0,0)`, goal `(2,2)`, with contact probe. Oracle and
scenario reference is `GT_ODOM_2D`; policy reference remains B1 noisy emulator
odometry. World-to-task XY/yaw identity mapping must be declared and bound,
without a fabricated map/odom TF. Candidate bounds are not a valid-area
authority and no out-of-bounds terminal is introduced without one.

Collection interval is nominal 0.10 s ROS; reward uses actual `dt`. A future
bounded collection target is 30 successful resets and 1,000 issued POLICY
commands, including the approved forward, reverse, lateral, rotational,
diagonal, and mixed motion coverage. The first 10 episodes use 34 steps and
the remaining 20 use 33 steps. Collection cutoff is not success, collision,
timeout, or truncation: `episode_complete=false` and exposure is censored for
unfinished episodes. Evaluation runs to the task horizon and is independent
of rollout/training budget. Nav2 DWB is a Roadmap B comparison only and does
not run in `LOCAL_TRAINING`.

### 5.7 Package ownership and GUI option (D8)

B2.2 is expected to own the native simulation backend and a body-motion
surrogate using the approved robot/config geometry. B2.1 creates no package,
backend, actuator, Safety runtime, reset service, ingress/coordinator,
FinalTwistPublisher change, or GUI process. The backend ownership boundary
must remain distinct from `mecanum_nav_rl` pure configuration and from robot
assets under `ROBOT_URDF_final_description`.

Future launcher design has one `gui` argument defaulting to false and accepts
only exact `true` or `false`; invalid values fail before any process starts.
False is server-only. True starts the same server plus GUI-only process, using
one world, robot, and backend. GUI startup does not itself issue simulation
control requests. The launcher contract does not wire GUI actions to play,
pause, reset, set-pose, or rearm; this describes intended launcher behavior,
not a security boundary imposed on GUI capabilities. Proposed commands are
`gz sim --force-version 8 -s --headless-rendering <world>` and
`gz sim --force-version 8 -g --gui-config <installed-config>`, with identical
GZ partition/network/resource binding. Server retains Sensors/ogre2/headless
EGL and SceneBroadcaster in either mode; disabling the window does not disable
sensor rendering. Renderer, sensor, rate, timestamps, and dependencies are
not changed. The dedicated GUI config contains MinimalScene,
GzSceneManager, and InteractiveViewControl, and does not load WorldControl,
TransformControl, Spawn, or Teleop by default. `default_exit_action=CLOSE_GUI`
and `dialog_on_exit=false`; GUI is not a read-only security boundary.

GUI startup failure is explicit and prevents collection; there is no silent
fallback. GUI close/crash after opening is recorded separately; neither
process auto-restarts and GUI exit alone does not change motion permission. A
sensor/clock health fault still follows the existing fail-stop path. GUI
interaction is not an authorized launcher control path for play, pause, reset,
set pose, or rearm. Existing evidence records requested and actual GUI state
and command. GUI adds no V3 root or config hash field, and no
bit-identical trajectory/performance claim is made. GUI launch, assets,
packaging, and runtime tests are deferred to B2.2/B2.3.

### 5.8 B2.2 backend-control service amendment (L2)

The Owner-approved B2.2 corrective adds `mecanum_nav_rl_interfaces/srv/LocalTrainingBackendControl` at `/mecanum/local_training/backend_control` and advances the interface package from 2.6.0 to 2.7.0. The eight existing messages remain byte-stable; the live inventory is eight messages plus one service. The service uses RELIABLE/VOLATILE and carries control, binding, and proof facts only. It has no Twist, action, goal, or Ground Truth fields. Receipt-v2 remains the sole atomic actuator carrier.

The schema is version 1 with operations `BIND_SESSION`, `BIND_PENDING_STEP`, `CONFIRM_OBSERVATION0`, `INHIBIT`, `VERIFY_CONTACT_CAPABILITY`, and `BIND_RESET_CONTEXT`; probe actions are `NONE`, `START`, `QUERY`, and `ABORT`. The service source and generated tests pin its complete field order, types, bounds, constants, and reason codes. Common metadata is schema/session/config/asset identity, coordinator and backend identities, request sequence, and expected binding revision. Hashes are 64 lowercase hexadecimal characters. Operation-specific fields are required only by their operation; every unused field must be zero/empty. In particular, `INHIBIT` does not require fabricated lifecycle or proof data, and QUERY/ABORT reference the exact START request.

The bringup supervisor creates a nonzero coordinator-ingress identity in an immutable run descriptor and supplies that identity to the backend and future B2.3 coordinator. The backend does not trust the first request or receipt as an identity source. This is a consistency/provenance boundary in a trusted simulation environment, not caller authentication or a security boundary. Missing identity/binding keeps actuator admission inhibited without preventing passive scene inspection.

The backend service callback validates and copies requests into an ordered queue of capacity 8; simulation updates alone apply binding changes. A mutation must apply or fail within 1 s steady time. There is at most one pending binding mutation; QUERY, ABORT, and INHIBIT remain serviceable, and INHIBIT/reset/fault cancels pending operations that could open admission. A 128-entry response cache returns exact duplicate state without reapplying or refreshing actuator watchdog. Same-sequence changed content faults; old uncached sequence replays reject; sequence gaps fault. A new ordered request consumes its sequence even when BUSY or revision mismatch is cached. Retrying BUSY requires a new request sequence. Foreign session/backend requests cannot replace the active binding.

`BIND_SESSION` is startup-only while inhibited and cannot replace source instances. `BIND_RESET_CONTEXT` accepts only a strictly newer authoritative lifecycle/barrier while inhibited, with no probe or admission-opening mutation active. It clears current/pending step and observation0 eligibility, while preserving request replay protection, source ownership, and global final-publication watermark. It does not reset/rearm, advance a generation, or create observation0. A reset context needs a matching strictly post-barrier SAFE_STOP-zero anchor; late receipts cannot repair a faulted segment. Backend or final-publisher restart invalidates the session.

`BIND_PENDING_STEP` uses B1 `policy_transition_identity()` semantics and requires source sequence equal to step index; it creates no issuance or UUID. The backend retains current and one pending POLICY identity. Timer publications for current remain valid until the first matching pending receipt switches slots; afterward the old identity rejects. SAFE_STOP has its own source/counter and does not consume the pending step. Identity is never reassigned by arrival time, and counters never rewind. Action barrier is checked strictly for the receipt to which it applies.

`CONFIRM_OBSERVATION0` is a B2.3 confirmation after its actual B1 commit, not a backend-generated commit. The selected evidence is the session-bound, post-reset-barrier SAFE_STOP-zero publication at or before cutoff, with retained application history matching key/iteration/stamp and no local override. The adjacent key is selected+1 from the same publisher, strictly after cutoff, no later than ROS now, and fresh. It proves only the boundary: it needs neither zero payload nor actuator application and cannot replace the pre-cutoff command. Missing/evicted history rejects. Confirmation enables zero-only eligibility; it does not rearm or open POLICY. POLICY additionally needs the current step, healthy Safety/input/contact and verified capability, no pause/reset/fault/inhibit, and the actual Safety/FinalTwistPublisher receipt path.

### 5.9 Controlled contact-capability probe amendment (L2)

Contact capability remains unknown until a backend-controlled infrastructure probe completes; no caller boolean can assert it. The fixture is the installed `b2_contact_probe` model named uniquely `b2_capability_probe`, separate from the robot collision mask and without changing `B2_CONTACT_V1`. It is a 0.10 m cube of mass 1 kg with source-validated inertia and a contact sensor on its exact collision.

The planned world services are `/world/b2_training_arena/create` (`SpawnEntity`, `gz.msgs.EntityFactory` to `gz.msgs.Boolean`), `/set_pose` (`SetEntityPose`, `gz.msgs.Pose` to `gz.msgs.Boolean`), and `/remove` (`DeleteEntity`, `gz.msgs.Entity` to `gz.msgs.Boolean`). Support must be verified from the installed bridge/API before build; the presence of ROS service declarations alone is insufficient. START requires a separately authorized call while bound/inhibited, before observation0 or pending POLICY; `gui=true` neither plays the world nor starts the probe.

START spawns at world pose `(-2,0,0.07)`, yaw zero, and must prove ownership and exact registry geometry. Name conflict fails without deleting an existing entity. The backend requires at least three consecutive post-Physics samples of the exact fixture-floor pair spanning 20 ms ROS with finite valid normal/depth. It raises the fixture to z=0.20, checks achieved separation from measurement, then requires three covered-empty consecutive samples spanning 20 ms. It removes only the owned fixture and verifies absence from ECM before capability becomes VERIFIED. ACK alone is not achieved pose.

The proposed total deadline is 5 s steady from START receipt, including queueing and cleanup; reserve the final 1 s for cleanup and do not start an operation that would exceed the budget. START reaches APPLIED or an error within 1 s; APPLIED means probe started, not verified. Exact duplicate START cannot spawn twice. QUERY uses a new sequence and references START. ABORT/timeout does not retry. Cleanup failure keeps inhibit and records possible fixture residue. The proof binds session/backend/asset/registry/world/engine identity and fingerprint, exact entities, physics iterations, and simulation stamps. It is invalidated by identity change, restart, clock rollback, or fault; it may survive normal episode reset only while those identities remain unchanged and no invalidating fault occurs. Robot coverage is still checked independently each physics step. Fixture contact is not an RL collision penalty; real robot contact is not cleared to pass the probe. Teardown precedes reset/buffer clearing, fresh sensors, and any later observation0 transaction.

This probe establishes only a bounded contact-capability property. It does not demonstrate contact operation in Gazebo, moving robot collision behavior, actuator behavior, braking, GUI readiness, or functional safety.

## 6. Candidate evidence disposition

The above D1–D8 amendments are Owner-approved design contracts. Candidate
source, tests, and interface declarations are separate evidence. B2.1 can
reach `IMPLEMENTED_OFFLINE_ONLY_PENDING_INDEPENDENT_AUDIT` only after its exact
offline checks and delivery are verified. This document does not assert those
checks, independent audit, integration, Gate 1, runtime, training, functional
safety, HIL, or `REAL_READY`.

## 7. B2.1 packaging and interface-regression correction scope

The Owner's 2026-10-29 continuation authorizes a bounded offline correction
within the existing B2.1 L2 decision. The candidate allowlist expands only to
include `mecanum_nav_rl/setup.py` and the historical WP-06 ROSIDL regression
test. Training configuration assets must be installed at their declared V3
share paths; the six old V3 message declarations remain exact, with the two
B2 messages added to the exact live inventory at interface package version
2.6.0. Historical WP-06 allowlist, receipt hashes, and evidence assertions
remain unchanged.

The install-closure regression must compare an explicit source/destination
inventory with `setup.py`, reject missing, misplaced, or duplicate entries,
and compare every installed V3 asset byte-for-byte under a fresh external
install prefix. Offline builds may select only `mecanum_nav_rl_interfaces`
and `mecanum_nav_rl`, using existing underlay dependencies and temporary
build/install/log directories outside the repository. These build and test
permissions add no runtime authority and do not change D1-D8, GUI, safety,
noise, reset, interface, or hash semantics. This correction remains a source
candidate until required offline checks, delivery, and independent exact-commit
audit; it does not assert package build, test, audit, integration, Gate, or
runtime results in advance.

## 8. B2.2 simulation substrate — Owner-authorized offline implementation

Under the existing L2 Decision ID, B2.2 owns the native `mecanum_sim_backend`
package, B2-only robot/world assets, body-motion surrogate, receipt admission
and independent zero watchdog, simulation measurements/contact coverage,
trusted ports and reset adapters, launch/bridge/GUI process ownership, and
asset-bound scenarios plus resolved training configurations. The implementation
must preserve the existing B1 and B2.1 contracts, use the receipt-v2 payload as
the sole atomic actuator carrier, keep backend admission inhibited by default,
and never synthesize a command publisher, lifecycle transition, receipt, or
observation0 owned by B2.3.

The body-motion controller is a simulation surrogate, not a physical mecanum
drive or validated braking model. Commands preserve body `vx`, `vy`, and `wz`;
measurements come from post-physics pose and velocity, with world/body conversion
using measured orientation. Missing or invalid measurements fail closed. Contact
coverage is bound to the installed asset manifest and actual physics iterations;
an unverified sensor component, incomplete coverage, queue overflow, or
unclassifiable wheel-floor contact is unhealthy. Reset adapters return service
acknowledgments and measured facts, but do not rearm or open POLICY.

The B2.2 offline implementation scope includes native and exact Python tests,
fresh external builds of only the five named packages, static asset closure,
scenario/manifest/config generation from source assets, and install-byte checks.
These activities do not authorize ROS graph execution, Gazebo, launch, GUI
observation, motion, reset against a live world, training, evaluation, soak,
HIL, hardware, Gate acceptance, or real-robot claims. GUI acknowledgment in
offline tests may use injected fakes; production acknowledgment remains an
explicit Owner action after the separately authorized first observation.

B2.2 remains within the Owner-approved L2 scope. Independent exact-commit
audit is required before any next step. B2.3 and runtime are separate scopes;
B2 remains open. This ACR section records approved contract and scope, not test,
build, audit, integration, Gate, or runtime results.


### 5.10 ROSIDL service constant naming correction

The request declares `SCHEMA_VERSION=1`; the response declares
`RESPONSE_SCHEMA_VERSION=1`. Both request and response retain their
`schema_version` field. The distinct generated constant name avoids a C
enumerator collision in the installed ROSIDL output while preserving the
service fields, values, and wire data. This does not establish service runtime
behavior.
