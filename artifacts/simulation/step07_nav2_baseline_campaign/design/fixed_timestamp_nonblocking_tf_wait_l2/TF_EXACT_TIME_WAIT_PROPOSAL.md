# FIXED_TIMESTAMP_NONBLOCKING_TF_WAIT — L2 design packet

**Status:** `DRAFT_L2_PENDING_INDEPENDENT_REVIEW_AND_OWNER_APPROVAL`
**Mode:** review-only design and offline model; no production implementation or runtime.
**Source base / proposed sole parent:** `4e83ce6cffdd9910c288f90454ab747497d7a4a6`
**Branch:** `step07-integrated-nav2-gateb-campaign-f7f98c6`
**Invocation_021:** `ROOT_CAUSE_UNRESOLVED_FOR_INVOCATION_021` remains unchanged.

## 1. Scope and evidence boundary

This packet proposes an L2 temporal contract for two distinct TF operations in the Run005 Gate-B collector. It adds no production behavior, guard state, runtime evidence, or approval. The original report and harness under `/home/hazan/step07_forensic_reports/invocation_021/fixed_timestamp_nonblocking_tf_wait_20261024/` were read and left untouched. No historical evidence was copied into this packet.

The source baseline is the read-only production observer at the exact source base above. The model calls `_Collector._tick()` and `_features_from_path()` with fake clocks, messages, actions, and TF buffers for the baseline rows. Proposed rows are a pure Python state-machine model. They do not exercise a live ROS graph or prove tf2 runtime behavior. In particular, a mechanism reproduced offline does not confirm the cause of Invocation_021.

## 2. Authority consulted

- `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`: ROS time is used for sensor/TF time; steady time governs wait/deadline; exact TF ownership and fail-closed freshness/provenance apply; a 81-element float32 observation and existing navigation acceptance remain required.
- `AGENTS.md`: frozen architecture and evidence hierarchy; no inference from offline checks to runtime readiness.
- `docs/governance/PROJECT_EXECUTION_PLAN.md`: work-branch plans cannot change frozen contracts; architecture-sensitive semantics require approved ACR/change control.
- `docs/governance/CANONICAL_SOURCE_REGISTRY.md`: governance is not technical authority; Observation V3 references and profile values may remain unresolved.
- `docs/governance/PROJECT_PROGRESS_LEDGER.md`: latest Run005 entries continue to classify Invocation_021 timeout as unresolved and keep runtime approval separate.
- `docs/architecture/ARCH_CHANGE_RECORD_OBSERVATION_INPUT_PROFILE_V3.md`, `docs/OBSERVATION_V3_SPECIFICATION.md`, and `docs/OBSERVATION_INPUT_CONTRACT_V3.md`: exact identity tuple, lifecycle-owned barriers, receipt ordering, LocalReference in `base_link`, no synthetic/fallback inputs, and unresolved profile-specific timing values.

The contract sources do **not** select a concrete TF age/future bound, Run005 LocalReference timestamp policy, active-path expiry, or every applicable scan/odometry skew value. This packet does not invent those values.

## 3. Recommended temporal contract

Use one immutable query time per operation and poll without blocking. Do not let a timer tick move the query target. Keep Phase A and Phase B semantically separate.

### Phase A — trigger-to-planner prerequisite

1. Read the trigger through its existing validated ROS ingress. The query target `t_A` is the trigger message's ROS header stamp from the first valid trigger accepted by the collector. File mtime and wall clock are never inputs. If this trigger has no usable ROS stamp under its existing message contract, fail closed; do not substitute `now`.
2. Pin `(t_A, trigger identity, lifecycle/config identity, goal identity)` once. Poll the exact `map -> base_link` transform for `t_A` from the existing timer. The timer returns immediately after each poll so action and subscription callbacks can run.
3. `UNAVAILABLE` means only that the nonblocking exact-time query did not establish availability. It does not label missing connectivity versus past/future extrapolation. Preserve the original TF exception type/message when an actual lookup throws.
4. Distinguish potentially pending from unserviceable: while `t_A` remains inside the existing TF buffer and input/trigger remains valid, exact lookup may become available. If the buffer reports a provable past/future range exclusion, identity invalidation occurs, or the existing whole-run steady deadline expires, terminate this phase as failure. Do not add a per-phase wait budget or increase the campaign deadline. If the installed API cannot prove eviction, keep the bounded nonblocking poll until an existing validity/deadline predicate ends it; report `UNAVAILABLE`, not a guessed cause.
5. A query re-arm clears only the poll scheduling state. It retains `t_A` and the pinned identity. It cannot issue a second ComputePath goal. Replacing the trigger/goal or lifecycle identity invalidates the pending attempt; a new action requires the existing action/lifecycle contract to admit a new goal, not merely a TF re-arm.
6. After exact TF availability and a final identity check, send ComputePath at most once. Whether its goal header must also carry `t_A` is an Owner decision. **Recommendation:** bind the request to `t_A` so the prerequisite and request refer to the same ROS instant; this is a semantic change from a send-time stamp and must not be implemented before approval.

### Phase B — one observation sample after planner success

Use one policy only: **pin the odometry source time for the path-feature transform**, and keep the vector cutoff separate.

- `t_vector`: ROS cutoff captured once when an eligible observation snapshot is acquired. It is not recalculated during TF waiting and is the cutoff against which receipt admission is checked.
- `t_odom`: exact header stamp of the odometry record pinned in that snapshot.
- `t_tf`: exactly `t_odom`; perform the path-feature transform at this time. Do not use latest TF, `now`, or `now - constant`.
- `t_commit`: ROS time read at the final nonblocking commit check. Store it as commit provenance only; never use it to replace `t_vector`, `t_odom`, input stamps, receipt stamp, or TF query time.

At acquisition, freeze deep copies/references with immutable record identities for scan, odometry, active lifecycle/barrier, exact final-issued receipt, path/goal, and all correlation records. Every input must have matching `(episode_generation, reset_epoch, runtime_generation, config_hash)` and satisfy its existing frame, provenance, freshness, and barrier predicates. The receipt must be strictly after applicable action/reset barriers and no later than `t_vector`. Scan/odometry/path/lifecycle records must not be future relative to their applicable cutoff. The selected path must be the same active goal/path identity and version at acquisition and commit. Do not replace a pinned member with a newer arrival while waiting.

At each timer poll, first allow callbacks to progress, then recheck ROS clock monotonicity, identity, lifecycle/barrier revision, active path version, existing freshness predicates, and the same exact TF query. Before commit, repeat all those checks. A clock rollback, generation/epoch change, barrier event (even if values later look equal), active-path replacement, stale/future input, missing exact correlation record, or whole-run deadline invalidates the pending snapshot. Discard it; do not mutate its timestamps or provenance to make it eligible.

Only after the exact transform and final checks pass may the model assemble/commit one vector from the pinned members. `t_vector` stamps must be strictly increasing; measurement keys must be unique. Preserve exact receipt and odometry record IDs/sequences and source stamps in the evidence chain. A transformed request must use a deep copy of the selected path pose; the raw path and its headers remain immutable. Five valid 81D float32 vectors, planner/navigation success, and the existing evidence, observer, QoS, and teardown requirements remain necessary. A committed sample or TF availability alone never passes Gate B.

The same overall collector steady deadline remains the only wait bound. No synchronization wait blocks an executor callback. An unavailable exact TF at the deadline is a failure, not a substituted transform.

### State outline

```text
Phase A: IDLE -> PIN_TRIGGER(t_A, identity) -> WAIT_EXACT_TF(t_A)
        -> READY -> SEND_COMPUTE_PATH_ONCE
        Any invalid identity / provably unserviceable query / existing deadline -> FAIL

Phase B: NO_SNAPSHOT -> ACQUIRE_AND_FREEZE(t_vector, t_odom, records, path version)
        -> WAIT_EXACT_TF(t_tf=t_odom) -> RECHECK_ALL -> COMMIT_ONE_SAMPLE
        Identity/barrier/path/clock/freshness/correlation/deadline failure -> DISCARD/FAIL
```

## 4. Limits, path identity, and config hash

No new age, skew, path-expiry, TF-future, retry, wait, or deadline limit is selected here. Existing source freshness values may be used only where the Run005 contract already selects them; they are not TF-age bounds. A configured TF bound is required by architecture but the applicable immutable Run005 profile value is unresolved. That authority gap must be closed before implementation can claim the transform acceptable.

Path identity should bind the accepted goal identity plus the returned path's exact source record/version (or a stable content digest if the producer contract supplies one). Replan/replacement invalidates an in-flight sample. The producer's authoritative path version/expiry source is not selected; the packet does not invent a TTL. The transform request is a deep copy so writing target frame/query stamp cannot mutate the source path.

Keep global `config_hash` unchanged if the implementation only changes runtime algorithm under an already-selected, unchanged static contract; runtime timestamps, pending state, identity instances, and observations are excluded from the 16-root static projection. However, exact-time semantics change the meaning of LocalReference/TF temporal binding. Therefore **the recommended path is an explicit L2 ACR and temporal-contract version/digest update before implementation**. If static profile references or contract semantics in the resolved configuration change, resolve a new global config and recompute its existing global hash; do not reuse the old hash as if it named new semantics. No Gate-B-only hash is proposed. No public ROS message/interface change is needed by this design. Whether the contract version/reference is included in the resolved profile and whether the config hash consequently changes is an Owner decision.

## 5. Proposed future implementation dependencies (not authorized here)

A separately authorized implementation would likely need:

- `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py` and its tests for the two pinned-time state machines, deep-copy behavior, diagnostics, freshness-at-acquisition/commit, action-once, and invalidation;
- Run005 runner/tests only if `t_A`, chosen action stamp, or phase diagnostics must be bound into run-record/evidence orchestration;
- Run005 validator/tests only if a versioned evidence schema must validate the new phase-specific timestamps/diagnostics;
- the existing bringup contract test only for explicit lineage/scope coverage;
- an approved ACR/contract/semantic manifest and any selected immutable profile source, plus pins/guard/evidence/governance only under a later exact allowlist.

No collector C++, Gate-B public ROS interface, QoS/Safety/Nav2 configuration, map, TF ownership, launch behavior, or profile file is changed by this packet. The config-hash implementation itself is not proposed for modification. This list is dependency planning, not an edit authorization.

## 6. Offline model and requirements matrix

Run `offline_model.py` with the canonical Python and a sourced ROS Jazzy/external package environment. It runs a separately labelled production baseline (direct calls to the current production methods using fake objects) and a proposal-only model. Its generated JSON records each case. It creates no ROS graph, process, campaign, vector evidence, or runtime artifact.

| Requirement | Proposed behavior | Offline case(s) |
|---|---|---|
| Trigger before first TF; do not chase now | Pin trigger ROS stamp once; poll same target | `trigger_before_first_tf_and_target_evicted`, `phase_a_late_tf_within_existing_window` |
| Target evicted/unserviceable | No retarget; fail only on provable invalidity or existing deadline | `trigger_before_first_tf_and_target_evicted`, `tf_never_arrives` |
| Late TF but still eligible | Exact-time lookup can become available without moving target | `phase_a_late_tf_within_existing_window`, `phase_b_tf_arrives_after_selection_but_data_fresh` |
| No TF / only after expiry | No sample; existing deadline/freshness yields failure | `tf_never_arrives`, `tf_after_input_expiry`, `fresh_at_acquisition_stale_at_commit` |
| Future/past/connectivity errors | Fail closed; do not infer a subtype from false availability | `future`, `past`, `missing_connectivity`, `tf_future`, `tf_past`, `tf_missing_connectivity` |
| Zero/rollback/jump | No zero-time snapshot; rollback invalidates; jump rechecks freshness | `clock_zero`, `clock_rollback`, `clock_forward_stales_inputs` |
| Generation/epoch and barrier ABA | Exact identity plus monotonic barrier revision invalidates pending | `generation_epoch_change_during_wait`, `barrier_changed_then_values_returned` |
| Receipt newer than odometry | Preserve exact receipt and stamps; require receipt <= cutoff | `receipt_newer_than_odom_but_not_after_vector_cutoff` |
| Path replacement | Version change discards pending snapshot | `path_version_changes_while_waiting` |
| Action and callbacks | TF re-arm never sends another action; callback progresses between polls | `phase_a_query_rearm_does_not_retry_action`, `callbacks_progress_while_nonblocking_tf_wait`, `action_callback_during_tf_wait` |
| Immutable raw path | Transform a deep copy only | `path_pose_input_immutability`, `transform_request_does_not_mutate_raw_path` |
| Exact records, no mixing | Commit keeps captured receipt/odom IDs instead of latest | `receipt_odom_update_while_pending` |
| Sample and terminal acceptance | Strictly increasing unique stamps; five samples alone insufficient | `five_monotonic_samples_and_navigation_gating` |

## 7. Diagnostic proposal

Keep bounded, phase-specific diagnostics; never overload a shared `tf.state`:

- `phase_a`: fixed query stamp/frame pair, trigger/goal identity, pending-start and last-poll steady stamps, poll count, availability (`AVAILABLE|UNAVAILABLE|LOOKUP_EXCEPTION`), original exception type/message/cause, first/last blocker, request-sent-once flag, invalidation reason.
- `phase_b`: `snapshot_id`, path ID/version, exact scan/odom/receipt/lifecycle/correlation IDs and stamps, `t_vector`, `t_tf`, `t_odom`, `t_commit`, acquisition/commit freshness results, identity and barrier revision, pending-start/last-poll times, bounded counters, first/last blocker, original TF exception/cause, discard reason.
- Bound counters (saturating), keep first/last blocker and a small capped transition ring; diagnostic caps must not change acceptance. Exact cap is a proposed schema detail requiring review, not a timing threshold.

## 8. Open Owner decisions before any production change

1. Approve trigger header ROS stamp as `t_A`, and decide whether ComputePath request must use that same stamp or only the gate is pinned.
2. Approve `t_tf=t_odom` for Phase B LocalReference on Run005, or identify the already-authorized exact-time source that governs it.
3. Identify the immutable configured TF age/future bound and its source. Do not implement with a newly invented bound.
4. Identify the Run005 scan/odometry skew and freshness authority; do not conflate source freshness limits with TF bounds.
5. Select the authoritative active-path identity/version/expiry source and invalidation event.
6. Decide whether the temporal contract gets a new version/reference and whether the resolved static profile/hash changes; approve the ACR and source allowlist.
7. Approve bounded diagnostic fields/retention without making diagnostic counters part of acceptance.

## 9. Validation limits and status

The model uses fake time, fake TF intervals/connectivity, fake callbacks, and ROS message objects only. Production baseline calls are offline function calls, not a running node. Model outcomes establish behavior only for those constructed cases. They do not validate real buffer cache policy, executor scheduling, DDS, TF topology, navigation, action delivery, sensor cadence, profile authority, or Invocation_021's timeout predicate. No historical checksum/validator was rerun. The original forensic material remains outside this packet and untouched.

The packet is `DRAFT_L2_PENDING_INDEPENDENT_REVIEW_AND_OWNER_APPROVAL`; source implementation, config/contract activation, and runtime are not authorized by its creation. No Gate-B, `RUNTIME_APPROVED`, or `REAL_READY` claim is made.

## 10. PLAN_UPDATE_PROPOSAL

Work item: Run005 temporal-coherence L2 design packet. Branch `step07-integrated-nav2-gateb-campaign-f7f98c6`; source base and proposed sole parent `4e83ce6cffdd9910c288f90454ab747497d7a4a6`. Evidence status: `IMPLEMENTED_OFFLINE_ONLY` for this review packet and fake model only; Invocation_021 remains `ROOT_CAUSE_UNRESOLVED_FOR_INVOCATION_021`. Dependencies: Architecture/Observation V3 authority reviewed; concrete TF bounds, path identity/expiry, Phase A action-stamp semantics, and Phase B timestamp binding remain unresolved. Next action: independent L2 review and explicit Owner decisions on section 8; only then prepare a separately authorized implementation scope. No runtime or new invocation is proposed.
