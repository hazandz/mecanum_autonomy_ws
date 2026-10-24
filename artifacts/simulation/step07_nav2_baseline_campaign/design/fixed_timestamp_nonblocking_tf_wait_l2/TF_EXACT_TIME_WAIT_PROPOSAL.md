# FIXED_TIMESTAMP_NONBLOCKING_TF_WAIT — L2 design packet

**Status:** `DRAFT_L2_PENDING_INDEPENDENT_REVIEW_AND_OWNER_APPROVAL`
**Mode:** review-only design and offline validation; no production implementation or runtime.
**Source base / required parent for this packet:** `ae620c57f396f593a39aafb589f4f69b3daf37c2`
**Production baseline source commit:** `4e83ce6cffdd9910c288f90454ab747497d7a4a6`
**Branch:** `step07-integrated-nav2-gateb-campaign-f7f98c6`
**Invocation_021:** `ROOT_CAUSE_UNRESOLVED_FOR_INVOCATION_021` remains unchanged.

## 1. Scope and evidence boundary

This packet records the supplied architecture decisions for two separate TF operations in the Run005 Gate-B collector. It changes no production source, profile, config hash, guard, ACR, or runtime evidence. The original forensic report and harness under `/home/hazan/step07_forensic_reports/invocation_021/fixed_timestamp_nonblocking_tf_wait_20261024/` were read and left untouched; no raw historical evidence was copied.

The baseline model imports exactly `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py` from the pinned source checkout and verifies its SHA-256 (`39b9c08d01770c8ca12d1264297c69e5943a8b90640daa98ffeeaf9b2b28c28f`) before calling `_Collector._tick()` and `_features_from_path()` with fake objects. Import origin and hash are asserted. The proposed model is a separate deterministic Python state machine. Monkeypatches of import and monotonic time are scoped to a context manager and verified restored. It starts no ROS graph, node, action server, process, Gazebo, Nav2, campaign, or runtime evidence.

The model tests temporal state and LocalReference construction only. It does **not** evaluate 81D vector acceptance, QoS, evidence-chain acceptance, Gate-B/campaign acceptance, Nav2 runtime, or tf2 runtime buffer behavior. Offline cases do not confirm Invocation_021's cause.

## 2. Authority consulted

- `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`, including §45 `GlobalPath và LocalReference`: `GlobalPathSnapshot` has `goal_id`, `path_sequence`, `reset_epoch`, `runtime_generation`, `map_id`, `map_content_hash`, ROS path stamp, steady receipt/expiry, and immutable poses. `LocalReference` binds source-path stamp, transform/reference ROS stamps, steady expiry, and a `base_link` point; the observation builder checks reference/odometry skew within the selected `max_reference_snapshot_skew_ns`.
- `AGENTS.md`: Architecture is highest authority; offline evidence is not runtime evidence; unresolved conflict with a locked contract must not be silently decided.
- `docs/governance/PROJECT_EXECUTION_PLAN.md`: plan/governance cannot change frozen architecture; architecture-sensitive changes require a separately approved ACR/change-control.
- `docs/governance/CANONICAL_SOURCE_REGISTRY.md`: registry is source-selection/governance evidence, not authority to resolve an unselected profile value.
- Latest relevant `docs/governance/PROJECT_PROGRESS_LEDGER.md` entries: Invocation_021 remains historical and `ROOT_CAUSE_UNRESOLVED`; this packet does not replace that status.
- `docs/architecture/ARCH_CHANGE_RECORD_OBSERVATION_INPUT_PROFILE_V3.md`, `docs/OBSERVATION_V3_SPECIFICATION.md`, and `docs/OBSERVATION_INPUT_CONTRACT_V3.md`: exact lifecycle/config identity, lifecycle-owned barriers, receipt ordering, no future/post-cutoff or synthetic input, and unresolved profile-specific timing references.

### Section 45 authority vs remaining mapping

The fields `goal_id`, `path_sequence`, `reset_epoch`, `runtime_generation`, `map_id`, `map_content_hash`, ROS path stamp, steady receipt/expiry, and immutable poses already have architectural authority. The design therefore requires them in the active path context and binds them to the pending sample. The exact producer-side record/version that supplies each field to this collector, how a path replacement event is surfaced, and how steady expiry is enforced at this boundary remain unselected mappings. The implementation must map the authoritative fields; it must not invent substitute IDs or an expiry duration.

Architecture requires reference/odometry skew and configured TF-age/future rules, but this packet's consulted authority does not identify a concrete selected Run005 bound for those predicates. No TF-age, skew, path-expiry, or wait limit is added here. That unresolved source selection belongs to a subsequent architecture-decision package.

## 3. Executed decisions and recommended temporal contract

The following behavior is the design captured by the provided decisions. It is not production authorization.

### Phase A — JSON trigger prerequisite and planner request

1. The current trigger is JSON and has no ROS header. On the first consumption of a valid trigger, read ROS time once. If it is positive, pin `t_A` to that ROS-clock value and pin the attempt context (active lifecycle/config identity, trigger goal ID, and active path context). File mtime and wall time are never read. If ROS time is zero/unstarted, do not pin `t_A` and do not send an action; keep waiting nonblockingly under the existing steady deadline.
2. Evaluate the existing steady campaign deadline on every tick, including when ROS time is zero or paused. No new or extended campaign deadline is introduced.
3. Poll exact-time `map -> base_link` availability at the same `t_A` and against the same pinned context. A false availability result, including a future-extrapolation-like interval in the fake model, does not prove the query can never be served. Continue nonblocking polls until an existing invalidation/terminal predicate or the existing steady deadline ends the attempt. Do not switch to latest, time zero, `now - offset`, or a new timestamp.
4. Before sending ComputePath, compare the live identity and context with the pinned values. Any mismatch ends this attempt. A ROS-time rollback or terminal failure is terminal for this attempt; a later clock increase cannot restore READY. A paused clock does not stop the steady deadline.
5. Query re-arm changes only poll scheduling. It preserves `t_A` and attempt context and cannot send a second action. At most one action request is sent for this attempt.
6. Keep the planner request timestamp at the production behavior already in use: ROS time at request-send. `t_A` is only the TF prerequisite timestamp; it is **not** the planner goal stamp. The model records both values separately.
7. `can_transform=true` is not sufficient proof of a successful lookup. If the subsequent exact transform throws, retain the underlying cause as structured type/message, do not send/commit on that result, and remain subject to existing invalidation and steady-deadline policy. Do not silently choose another time.

### Phase B — sample acquisition, LocalReference transform, and commit

Each pending sample has four separate time values:

- `t_vector`: ROS cutoff read once at acquisition.
- `t_odom`: exact source stamp of the odometry record frozen into the sample.
- `t_tf`: exactly `t_odom`, used for the path-feature transform.
- `t_commit`: ROS time at the final validation/commit check; provenance only, never a replacement cutoff or data stamp.

At acquisition, require an active identity, barrier revision, and path context. Missing context rejects the sample. Pin one immutable snapshot: scan/odometry/lifecycle records, exact final-issued receipt and sequence, their source stamps/record IDs, action/reset barriers, lifecycle/config identity, path context, and immutable path poses. Check freshness with the existing selected source predicates at acquisition. Every input stamp must be at or before its applicable cutoff; the final-issued receipt must be strictly after applicable action/reset barriers and no later than `t_vector`. A future input or receipt after cutoff is rejected.

While TF is pending, keep exactly that snapshot. New arrivals may update live ingress but never replace pending members implicitly. Recheck the same exact transform at `t_tf`. At commit, check freshness again, exact active identity, authoritative barrier revision, exact path context, correlation links, and cutoff ordering. Any identity, barrier, or path-context change invalidates the pending sample. A revision/sequence/event must advance on change, so a state that later looks equal does not resurrect the old pending sample. A clock rollback invalidates the sample. Existing path steady expiry is honored; this design adds no duration.

If `can_transform` reports available but lookup throws, preserve its underlying exception type/message in structured diagnostics and do not commit. The retry/wait remains nonblocking and bounded only by existing invalidation and overall steady deadline. Never mutate raw path or pose: deep-copy the transform request and preserve raw source stamps/provenance.

The measurement deduplication key is built from source measurement identity and lifecycle/path context (scan record, odometry record, receipt sequence, lifecycle sequence, goal/path sequence, epoch/generation, and map identity). It excludes model-created `snapshot_id` and `t_vector`; changing those cannot make the same measurements appear new. Correlation records stay immutable and their timestamp ordering is preserved.

The model's commit record contains only temporal provenance and LocalReference output. It does not assemble a vector. Five valid 81D float32 samples, navigation success, QoS, evidence-chain integrity, and all existing acceptance remain requirements outside this model and are marked `NOT_EVALUATED`.

### Nonblocking state outline

```text
Phase A:
  JSON_VALID + ROS_TIME<=0 -> WAIT_CLOCK (no t_A, no action)
  first JSON_VALID + ROS_TIME>0 -> pin (t_A, attempt context) -> WAIT_EXACT_TF(t_A)
  poll false/lookup transient -> WAIT_EXACT_TF(t_A), steady deadline continues
  exact TF + active context still matches -> send ComputePath once at send-time ROS stamp
  rollback/context change/steady deadline/terminal failure -> terminal FAIL for attempt

Phase B:
  require active identity + barrier revision + path context
  acquire: t_vector=ROS now; pin records; t_tf=t_odom; validate cutoff/freshness
  poll callbacks and exact TF(t_tf) without blocking; never replace pending records
  final check: freshness + identity + revision + path + correlation + cutoff
  pass checks -> commit one LocalReference record at t_commit provenance
  mismatch/stale/future/rollback/lookup terminal/deadline -> discard/fail, no fallback
```

## 4. Offline model cases and requirement matrix

`offline_model.py` runs the pinned production baseline first/independently for the source methods, then executes proposed-model cases. The result JSON labels the two tracks separately and marks all out-of-model acceptance `NOT_EVALUATED`.

| Requirement | Model assertion/case |
|---|---|
| Trigger is JSON with no header; zero ROS clock does not pin/action; steady deadline still ends wait | `json_trigger_clock_invalid_steady_deadline` |
| TF arrives late at fixed `t_A`; planner request uses send-time stamp, distinct from `t_A` | `phase_a_late_tf_fixed_trigger_consumption_time` |
| Identity/context changes before action | `phase_a_identity_changed_before_action` |
| Rollback followed by increasing clock cannot restore attempt | `phase_a_rollback_terminal_no_resurrection` |
| False availability/target outside fake buffer is not declared permanently impossible; existing steady deadline ends attempt | `phase_a_target_outside_buffer_until_steady_deadline` |
| Query re-arm keeps `t_A`/context and sends one action only | `phase_a_rearm_one_action_preserve_ta` |
| Phase B rejects future input and receipt after `t_vector` | `phase_b_cutoff_rejects_future_and_post_cutoff_inputs` |
| Active barrier/path context is mandatory | `phase_b_missing_active_context_rejected` |
| Pending sample is not replaced by latest | `pending_snapshot_not_replaced_by_latest` |
| Duplicate measurements with new snapshot ID/cutoff remain duplicate | `same_measurements_different_snapshot_id_and_cutoff` |
| Acquisition freshness is rechecked at commit | `fresh_at_acquisition_stale_at_commit` |
| Barrier/path change then apparent return invalidates by revision/sequence | `barrier_and_path_change_then_return_invalidate` |
| `can_transform=true` followed by lookup exception never commits; cause is preserved | `can_transform_true_lookup_exception` |
| Raw path is immutable across transform request | `raw_path_immutability` |
| Callbacks proceed between nonblocking polls | `callbacks_progress_while_nonblocking_wait` |
| Production moving-now baseline and fixed-time proposed behavior are distinct | `phase_a_late_tf_fixed_trigger_consumption_time`, `phase_b_fixed_odom_transform_time` |

The model also checks existing source freshness values as a model input only; that does not select them as TF-age, skew, or path-expiry authority.

## 5. Identity, diagnostics, profile, and config hash

Active path context binds the Architecture §45 identity fields: `goal_id`, `path_sequence`, `reset_epoch`, `runtime_generation`, `map_id`, `map_content_hash`, ROS path stamp, steady receipt/expiry, and immutable poses. In addition it binds the current lifecycle/config identity and an authoritative barrier revision/event token. Any unselected source-to-field mapping is a prerequisite for a future implementation, not a reason to weaken the requirement.

Diagnostics should remain phase-specific and bounded: phase, source/target frame, fixed query stamp, attempt/snapshot identity, context/path sequence/map identity, pending-start and last-poll steady times, current availability, lookup exception type/message/cause, first/last blocker, saturating counters, freshness-at-acquisition/commit, and invalidation reason. Do not use one shared `tf.state` for both phases. Diagnostic details do not replace machine-readable context or acceptance.

This packet does not edit or resolve the static profile, config hash, or current ACR. Runtime timestamps and pending state remain runtime facts, not resolved-config members. The semantic choice of exact-time Phase A prerequisite and Phase B `t_tf=t_odom` must be taken to the subsequent architecture-decision package; any resulting contract version/profile/hash effect is decided there. No public ROS interface change is proposed.

## 6. Remaining decisions for the subsequent architecture package

The supplied decisions settle this packet's state-machine behavior. The following authority mappings remain missing and must be resolved before production implementation:

1. Which approved immutable Run005 source supplies the concrete TF age/future predicate required by Architecture, and how its result is evaluated without adding a local limit.
2. Which approved contract/profile source supplies the applicable reference/odometry skew predicate and freshness mapping at this collector boundary.
3. Which producer record/API maps Architecture §45 fields into active path context, including path replacement event/revision and steady expiry.
4. Whether the temporal binding changes require a new LocalReference contract reference/version and a resolved-profile/global `config_hash` change. The current profile/hash and ACR are not modified by this packet.
5. The exact bounded diagnostic schema/version and evidence-validator binding, if those diagnostics are persisted.

These are not implementation choices for this packet and no defaults are proposed.

## 7. Evidence limits and status

The proposed state machine is a fake-clock/fake-TF/fake-message model, not production code. The production comparison is limited to the two current source methods, called offline with fake objects from the pinned source file. It does not prove real tf2 cache/extrapolation behavior, executor scheduling, sensor cadence, QoS, action delivery, path producer semantics, full-vector correctness, evidence-chain acceptance, Gate-B acceptance, or any Invocation_021 root cause. No campaign, runtime, checksum, or historical validator was run.

The packet remains `DRAFT_L2_PENDING_INDEPENDENT_REVIEW_AND_OWNER_APPROVAL`. No runtime authorization or acceptance claim is made.

## 8. PLAN_UPDATE_PROPOSAL

Work item: Run005 fixed-timestamp nonblocking TF wait L2 design packet correction. Branch `step07-integrated-nav2-gateb-campaign-f7f98c6`; packet base/required parent `ae620c57f396f593a39aafb589f4f69b3daf37c2`; pinned production baseline `4e83ce6cffdd9910c288f90454ab747497d7a4a6`. Evidence status: `IMPLEMENTED_OFFLINE_ONLY` for the four-file design/model packet only; Invocation_021 remains `ROOT_CAUSE_UNRESOLVED_FOR_INVOCATION_021`. Next action: independent review and a subsequent architecture-decision package to resolve the source mappings in section 6 before any separately authorized production implementation. No runtime or new invocation is proposed.
