# ACR Draft — Run005 temporal coherence L2

**Status:** `DRAFT_L2_PENDING_INDEPENDENT_REVIEW_AND_OWNER_APPROVAL`

**active:** `false`

**production_implementation_authorized:** `false`

**runtime_authorized:** `false`

**Contract ID proposed:** `mecanum.step07-run005-temporal-coherence/v1`
**Draft source base:** `c6495dc0ebb036b298c9da04a32db6ede3eb9289`
**Architecture SHA-256:** `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`

This document records the supplied architecture decisions for independent review. It is not an active ACR, source selection, implementation authorization, runtime approval, or evidence of campaign behavior.

## 1. Scope and non-goals

This proposal applies only to the Run005 simulation `sim_eval` / `NAV2_BASELINE` collector. It does not apply to `deploy_real`, training, or a public ROS interface. Invocation_021 remains `ROOT_CAUSE_UNRESOLVED`. The offline model at base `c6495dc0ebb036b298c9da04a32db6ede3eb9289` is limited evidence for temporal state-machine examples; it is not runtime proof and does not establish the historical cause.

The proposal preserves the current five-vector 81D requirement, navigation-success requirement, QoS acceptance, Safety behavior, campaign steady deadline, and action cardinality of at most one planner request per attempt. It does not introduce an alternate TF lookup policy, latest-transform fallback, time-zero lookup, `now-minus-offset`, retry/replan, a public message, or a new Gate-B-only configuration hash.

## 2. Source facts and authority boundary

Architecture §45 defines `GlobalPathSnapshot` with `goal_id`, `path_sequence`, `reset_epoch`, `runtime_generation`, `map_id`, `map_content_hash`, ROS path stamp, steady receipt/expiry, and immutable poses. It defines LocalReference in `base_link`, with source path stamp, transform/reference ROS stamps, steady expiry, and the observation skew check against a same-epoch/generation `SensorSnapshot`. Architecture §45 supplies the data semantics; it does not activate the concrete Run005 adapter mapping proposed here.

The current Run005 observer source uses `_Collector._tick()` and `_features_from_path()`. The former currently polls TF and drives the ComputePathToPose / NavigateToPose flow; the latter transforms a selected path pose. The current source is evidence of implementation only. It is not by itself authority to activate the new timestamps or identity bindings in this proposal.

`SafetyLifecycleCore._set()` increments `sequence` for a state transition. Its ordinary monotonic `refresh()` updates `barrier_ros_time_ns` without incrementing `sequence`; a clock regression enters `_set()` and faults closed. The current `SafetyLifecycleState` message carries `episode_generation`, `reset_epoch`, `runtime_generation`, `sequence`, states, `barrier_stamp`, motion permission, and reason. It does not carry `source_instance_id`. The lifecycle node publishes that message on `/mecanum/safety_lifecycle_state`. Therefore publisher/source provenance is a required future ingress binding, not a field that this proposal claims is already present or verified. If that provenance cannot be proven from an independently approved binding, admission fails closed; no source is inferred from `header.stamp`, `barrier_stamp`, topic name alone, or a heartbeat.

The current simulation Safety YAML contains `freshness_ns.filtered_odometry_max_age: 250000000`; `SafetyPolicy.from_mapping()` validates positive integer freshness values, and `SafetySupervisorCore.evaluate()` applies that value to filtered odometry age. The value is a current source fact for filtered odometry. It is **not** current authority for LocalReference or TF freshness.

The Observation Input Contract V3 and its related specification require explicit source/provenance and exact lifecycle identity, reject missing or ambiguous correspondence, and state that concrete LocalReference provider, transform, freshness, and provenance remain unselected. This draft leaves those documents and the resolved profile unchanged. The proposed binding below needs independent review and Owner approval before it can become authority.

## 3. Normative proposal — Phase A prerequisite and planning

### 3.1 Attempt context and trigger time

The Run005 trigger is JSON and has no ROS header. On the first collector consumption of a valid trigger, select `t_A` as the current ROS clock value only if it is a positive integer nanosecond timestamp. File modification time and wall time are not substitutes. If ROS time is zero, unavailable, or invalid, do not pin `t_A`, do not send an action, and continue to obey the already-authorized steady campaign deadline.

At that same admission, pin an immutable `AttemptContext` containing only the Phase A identities:

- the goal intent issued to this attempt;
- the active lifecycle/config identity;
- map identity;
- barrier revision/event context.

Phase A does not require a path, `path_sequence`, path stamp, or path expiry before ComputePathToPose. A path is created only from the successful result of the planner request for this attempt.

### 3.2 Fixed exact-time TF polling

Pin `t_A` once. Poll exact-time TF for the same target timestamp without blocking the executor and without moving the query target. `can_transform` availability is only a readiness observation; a successful precheck does not replace the actual lookup and does not waive a lookup exception. An exception or a false availability result leaves the collector waiting only while the exact timestamp may still be served and the attempt context and steady deadline remain valid. A future extrapolation or transient false result alone does not prove that the timestamp can never be served.

Every poll verifies the active AttemptContext. A change or invalidation ends the attempt fail-closed. A ROS clock rollback latches terminal failure. Later clock growth does not resurrect the attempt. Re-arming the same exact TF query does not change `t_A` or context and must not send another action.

When exact-time TF is usable and the context is still valid, send ComputePathToPose once. Preserve the current planner-request timestamp semantics: its ROS stamp is the ROS time sampled at request send. `t_A` is a prerequisite timestamp, not a required timestamp for the planner goal. Planner action UUID and NavigateToPose action UUID are distinct identities and must not be assumed equal; the common binding is the goal intent within the invocation.

### 3.3 Returned path binding

Only after a ComputePathToPose result reports `SUCCEEDED` may the adapter create the returned-path context. Bind the result to the exact pending planner request/action goal, its goal intent, the pinned lifecycle/config identity, and map identity. A wrong-request, stale callback, non-success result, or prior generation result is rejected and cannot create an eligible path context.

`path_sequence` is an adapter admission counter that increments when a new returned path is accepted. It is not claimed to be a field supplied by a Nav2 message. The adapter records a steady receipt time at callback admission. Preserve an immutable copy of the returned path and its pose data.

For this single-goal campaign, path expiry cannot exceed the existing steady campaign deadline. Earlier invalidation applies at goal completion, lifecycle/config/map change, path replacement, cancel/preemption, or attempt failure. No new arithmetic TTL is selected, and this proposal authorizes no retry or replan.

## 4. Normative proposal — Phase B LocalReference sample

Phase B has separate timestamps and a pinned sample snapshot:

- `t_vector`: immutable ROS cutoff selected at sample acquisition;
- `t_tf`: exact ROS stamp of the pinned odometry record;
- `t_commit`: ROS time re-read after transform, used as commit provenance and final validation time.

The proposed simulation policy is `NEW_L2_POLICY_PROPOSAL`, not current authority or measured evidence:

1. Reference–odometry skew is exactly zero because `t_tf = t_odom` for the pinned odometry record.
2. LocalReference ROS age at final commit must satisfy `0 <= t_commit - t_tf <= filtered_odometry_max_age_ns` from the pinned simulation Safety source.
3. The current source value is `250000000 ns`, at `ros2_ws/src/mecanum_nav_rl/config/safety/sim_eval_nav2_baseline_safety.yaml`, key `freshness_ns.filtered_odometry_max_age`, interpreted by `SafetyPolicy.filtered_odometry_max_age_ns`. This use for LocalReference is proposed policy only. A missing or invalid selected source/value rejects the sample; there is no fallback.

This query-age bound does not prove freshness for every TF publisher. A sample still requires a successful exact-time lookup, compatible frames and timestamp, verified TF ownership, and all existing health/acceptance checks. No scan–odometry admission predicate changes. Independent freshness is not described as equivalent to exact synchronization. The simulation value must not be applied to a real robot.

At acquisition, pin the exact scan, odometry, lifecycle, receipt, path and identity records eligible under the existing cutoff/admission rules. No input later than the applicable cutoff is eligible. Do not substitute a newer receipt, scan, odometry record, lifecycle state, path, or “latest” snapshot while a sample is pending. Correlation records remain immutable and retain their original stamps and provenance.

At final commit, after the transform, re-read ROS time, steady time, active identity, barrier revision/event, and path context. Recheck the existing steady campaign deadline, proposed freshness bound, cutoff ordering, frame/identity match, and all existing admission checks. A clock rollback, deadline expiry, stale input, future/post-cutoff input, generation/epoch change, barrier event, or path invalidation rejects/discards the pending sample. Do not modify `t_vector`, `t_tf`, source record stamps, or provenance to make data eligible. Use a deep copy for transform requests; do not mutate the raw path/pose.

`can_transform == true` does not waive an exception from the subsequent exact lookup/transform. Such a failure cannot commit a sample; retain the original exception cause and follow the approved wait/invalidation/deadline behavior. No timestamp fallback is permitted.

The existing five valid 81D vectors and navigation success remain mandatory. This proposal does not weaken QoS, Safety, lifecycle barriers, or campaign acceptance.

## 5. Barrier revision and identity mapping

Use `SafetyLifecycleState.sequence` as the proposed barrier revision, atomically bound to `episode_generation`, `reset_epoch`, `runtime_generation`, and verified publisher/source provenance. This matches the current `SafetyLifecycleCore` distinction between `_set()` transitions (sequence increments) and ordinary `refresh()` updates (sequence unchanged). Do not use `header.stamp` or `barrier_stamp` as the revision because those times can change during heartbeat refresh.

Counter regression, a lifecycle tuple change, source/publisher identity change, or unverifiable correspondence invalidates the pending attempt/sample and fails closed. A change followed by a return to old field values remains invalidated because the event/revision advanced. No SafetyLifecycle source or message is changed by this proposal.

The current lifecycle message has no explicit publisher instance field. The implementation packet must identify an approved, immutable source/provenance mechanism before activation. It may not silently add an interface field, trust a topic name as sufficient provenance, or treat a missing binding as a match. If no existing approved mechanism can provide this proof, this mapping remains unresolved and blocks activation pending an Owner/architecture decision.

## 6. Contract, profile, and hash binding

Proposed contract identity: `mecanum.step07-run005-temporal-coherence/v1`. Before implementation activation, temporal semantics need an immutable source/version/digest selected explicitly by authority. This draft does not create that source pin or digest.

There is no Gate-B-only config hash and no seventeenth root in the resolved configuration. If an approved static contract/profile binding changes, the configuration compiler must validate the binding and recompute the existing global `config_hash`; the old hash cannot be reused for new semantics. Runtime timestamps, barrier events, snapshot contents, path instances, and freshness results remain runtime facts and do not become static config values.

No current ACR, profile, compiler, schema, resolved configuration, guard, or hash is changed here. Whether the new temporal contract identity/digest becomes part of an existing static profile projection, and what exact compiler/schema source implements that binding, remain decisions for the later implementation packet. The packet must reject missing/invalid bindings rather than select a default.

## 7. Current source facts versus future adapter behavior

| Area | Current source fact | Future behavior proposed here |
|---|---|---|
| Trigger / prerequisite | `_Collector._tick()` reads ROS time and trigger before planner request; JSON trigger has no message header. | Pin positive `t_A` on first valid-trigger consumption and exact-time poll without moving it. |
| Planner and path | `_request_path_once()` samples request-send ROS time; `_path_result()` accepts a successful map-frame path. | Bind only the matching successful result to the pinned attempt; assign adapter admission `path_sequence` and steady receipt time. |
| Lifecycle | `SafetyLifecycleCore._set()` advances `sequence`; monotonic `refresh()` does not. Lifecycle message exposes tuple and `sequence`, not source instance. | Bind sequence to tuple plus approved publisher/source provenance; fail closed when provenance cannot be established. |
| Odometry freshness | Safety config has a 250000000 ns filtered-odometry maximum age, consumed by `SafetyPolicy`. | Propose reusing this exact pinned value as the sim-only LocalReference age-at-commit bound; not active until approved. |
| LocalReference | `_features_from_path()` transforms a map-frame path pose to `base_link`; current Observation Input Contract leaves provider/transform/freshness source unselected. | Use pinned `t_tf=t_odom`, immutable inputs, exact lookup, and final commit recheck. |
| 81D/campaign verdict | Current campaign acceptance exists separately in runner/validator. | Preserve all current acceptance; this ACR does not prove it. |

Full source symbol/path fingerprints are in `STEP07_RUN005_TEMPORAL_COHERENCE_L2_SOURCE_MAPPING.json`.

## 8. Required evidence and acceptance tests after approval

An implementation packet, after separate approval, must add tests that exercise the production adapter and campaign contracts, not just the offline model:

1. JSON trigger with no ROS header; zero/unavailable ROS time does not pin `t_A` or send action, while the existing steady deadline continues.
2. Positive-time `t_A` is pinned once; TF polling stays at that exact time; late availability permits one planner request; re-arm never resends it.
3. Attempt identity changes before action; attempt is rejected and no action is sent.
4. Planner request uses send-time ROS stamp, distinct from prerequisite `t_A`.
5. Correct request `SUCCEEDED` binds path after result only; wrong request, stale callback/generation, canceled or non-success result does not bind it.
6. Path admission increments adapter `path_sequence`, captures steady receipt time, and path remains immutable; replacement/cancel/preemption/goal end/attempt failure invalidates the earlier context without retry/replan.
7. Barrier transition sequence increments; ordinary refresh does not; tuple/source mismatch, counter regression, event change-and-return, or unverified source provenance fails closed. `header.stamp` and `barrier_stamp` are not used as revision.
8. Phase B pins `t_vector`, exact odometry `t_tf`, receipt/scan/lifecycle/path and their original correlations; future or post-cutoff inputs reject. A second acquisition cannot replace a pending snapshot.
9. Recheck age and context at acquisition and after transform immediately before commit; stale, deadline, rollback, epoch/generation, barrier or path invalidation prevents commit.
10. `can_transform` true followed by lookup exception does not commit and preserves the original cause. Transform uses copied path/pose data without mutating source records.
11. Missing/invalid temporal source pin or invalid/missing 250000000 ns configured source rejects; there is no default/fallback. If selected contract/profile binding changes, compiler recomputes global `config_hash` and rejects reuse of an old hash.
12. Existing campaign-level acceptance remains unchanged: navigation success, exactly five valid 81D vectors, QoS/Safety acceptance, and complete sealed evidence remain independently required.

## 9. Expected dependency impact — not implementation authorization

Potential files/contracts for a separately approved implementation packet include:

- Run005 collector/orchestration and tests under `artifacts/simulation/step07_nav2_baseline_campaign/tools/`;
- `mecanum_nav_rl/observations/step07_gate_b_observer_node.py` and its tests for this Run005 simulation collector only;
- existing observation snapshot/synchronization types and validators if they own the selected typed mapping;
- the Run005 sim-eval static profile, resolved-config compiler/schema and validation tests only if the approved temporal contract is bound statically;
- lifecycle binding/ingress tests only if an already-authorized provenance mechanism exists;
- source-pin, validator, guard/evidence and governance files only if their current contract requires new immutable source references or changed hashes.

This list is impact analysis, not permission to edit any listed path. No public ROS interface, SafetyLifecycle source/message, QoS, map, TF ownership, Nav2 config, launch semantics, acceptance, current profile, resolved config, guard, pins, or governance is changed by this draft.

## 10. Activation gate and evidence limits

This proposal becomes eligible for implementation planning only after independent review and explicit Owner approval of the L2 temporal semantics and unresolved source/provenance/profile bindings. A separate implementation packet must then freeze the exact immutable sources, versions, digests, affected paths, compiler/hash behavior, and acceptance tests. Until then, `active=false`, `production_implementation_authorized=false`, and `runtime_authorized=false` remain in force.

The model at `c6495dc0ebb036b298c9da04a32db6ede3eb9289` is a fake-clock/fake-TF temporal state-machine model using the pinned production baseline separately. It does not test complete 81D acceptance, QoS, evidence-chain sealing, campaign verdict, Nav2 runtime, or tf2 runtime. `Invocation_021` remains `ROOT_CAUSE_UNRESOLVED`; neither the historical cause nor a runtime fix is established here.

**PLAN_UPDATE_PROPOSAL:** Run005 temporal-coherence L2 draft; branch `step07-integrated-nav2-gateb-campaign-f7f98c6`; base/required parent `c6495dc0ebb036b298c9da04a32db6ede3eb9289`. Evidence status: `DRAFT/PENDING_USER_APPROVAL`; model evidence remains limited and offline. Dependency: independent review and explicit Owner approval, plus resolution of lifecycle publisher provenance and immutable temporal contract/profile/compiler binding. Next action: review this draft and mapping; only then issue a separate implementation packet. No production implementation or runtime is authorized.
