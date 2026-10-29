# ACR — Roadmap B Training Semantics and B1 Scope (L2)

**Decision ID:** `ROADMAP_B_TRAINING_SEMANTICS_AND_B1_SCOPE_L2`
**Status:** `OWNER_AUTHORIZED_L2_AMENDMENT_FOR_ROADMAP_B`
**Authority:** Lead Robotics Architect approval under Owner delegation dated 2026-10-27; Owner execution instruction dated 2026-10-29.
**Implementation scope:** `ROADMAP_B_B1_PURE_RL_TRANSITION_CONTRACTS` (offline pure core only).

## 1. Relationship to frozen Architecture

This ACR records approved Roadmap B amendments. These semantics are not
represented as pre-existing text in `MECANUM_NAV_DRL_Architecture.docx`, which
remains the highest architecture authority outside the explicit amendments
below. No Architecture DOCX bytes, public ROS interface, Safety limit, global
configuration hash algorithm, or current resolved configuration is changed.
The amendment does not authorize runtime, training, integration, HIL, or real
robot activity.

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
