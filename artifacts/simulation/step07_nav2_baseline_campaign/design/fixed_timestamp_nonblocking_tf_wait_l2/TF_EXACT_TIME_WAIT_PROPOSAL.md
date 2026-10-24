# FIXED_TIMESTAMP_NONBLOCKING_TF_WAIT — L2 design packet

**Status:** `DRAFT_L2_PENDING_INDEPENDENT_REVIEW_AND_OWNER_APPROVAL`
**Mode:** review-only packet and offline model; no production implementation or runtime.
**Packet base / required parent:** `674791655d43155accfe2b230f20994b76cbbc7b`
**Pinned production baseline:** `4e83ce6cffdd9910c288f90454ab747497d7a4a6`
**Branch:** `step07-integrated-nav2-gateb-campaign-f7f98c6`
**Invocation_021:** `ROOT_CAUSE_UNRESOLVED_FOR_INVOCATION_021` remains unchanged.

## 1. Scope and evidence boundary

This correction records decisions F1–F4 for a future Run005 collector change. It changes only these four packet files. No production source, ACR, profile, resolved config/config hash, guard, historical evidence, or runtime checkout is changed. The original Invocation_021 forensic report and harness remain outside the repository and untouched.

The model first imports the production baseline from the explicitly supplied `--repo-root`, checks the resolved module path and pinned SHA-256, then separately exercises `_Collector._tick()` and `_features_from_path()` using fake objects. A mismatch stops execution; there is no fallback source or overlay discovery. The proposed state model runs separately. Import and monotonic-clock monkeypatches are scoped to the baseline call and asserted restored.

The model covers temporal state transitions and LocalReference transform behavior only. `81D_acceptance`, QoS, evidence-chain acceptance, campaign acceptance, Nav2 runtime, and tf2 runtime are `NOT_EVALUATED`. No offline outcome confirms Invocation_021's root cause.

## 2. Authority consulted

- `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`, especially §45, **GlobalPath and LocalReference**.
- `AGENTS.md`: Architecture is highest authority; source and offline test evidence cannot silently replace or resolve an authority contract.
- `docs/governance/PROJECT_EXECUTION_PLAN.md`, `docs/governance/CANONICAL_SOURCE_REGISTRY.md`, and the latest relevant entries in `docs/governance/PROJECT_PROGRESS_LEDGER.md`.
- `docs/architecture/ARCH_CHANGE_RECORD_OBSERVATION_INPUT_PROFILE_V3.md`, `docs/OBSERVATION_V3_SPECIFICATION.md`, and `docs/OBSERVATION_INPUT_CONTRACT_V3.md` for identity, receipt/barrier, freshness, and profile/hash boundaries.

Architecture §45 defines the authoritative path fields: `goal_id`, `path_sequence`, `reset_epoch`, `runtime_generation`, `map_id`, `map_content_hash`, ROS path stamp, steady receipt/expiry, and immutable poses. These fields belong to a returned `GlobalPathSnapshot`; they are not prerequisites to a planner request. Their exact producer/API mapping into this Run005 collector, including how replacement/revision events and steady expiry are observed, remains unspecified. The model binds these values only after a matching successful planner result; it does not invent their production source.

## 3. F1 — cause-ordered contexts and Phase A

### Attempt context before planner

The current goal trigger is JSON and has no ROS header. At the first consumption of a valid trigger, read ROS time once. If positive, pin `t_A` and this attempt context exactly once:

- the goal intent/goal ID granted to the attempt;
- active lifecycle/config identity `(episode_generation, reset_epoch, runtime_generation, config_hash)`;
- map identity `(map_id, map_content_hash)`;
- barrier revision/event context.

This **AttemptContext deliberately has no** `path_sequence`, path stamp, path expiry, returned path, or `PathContext`. The system must not fabricate a path or infer one from the goal. If ROS time is zero/unstarted when the trigger is consumed, retain no `t_A`, send no action, and keep nonblocking until valid ROS time or the existing steady deadline. File mtime and wall time are never used.

Poll exact-time TF for the pinned positive `t_A`. False availability, including a future-extrapolation-like fake buffer result, does not establish permanent unserviceability; continue querying the same stamp until an existing invalidation, terminal failure, or steady campaign deadline. Never use latest TF, time zero, `now-minus-offset`, or move `t_A`. The steady deadline is checked even when ROS clock is zero or paused.

Before sending ComputePath, recheck active lifecycle/config identity, map identity, goal intent, and barrier revision/event against the pinned AttemptContext. Mismatch, rollback, or terminal failure ends this attempt. A later clock increase cannot restore READY. A query re-arm retains the same `t_A` and AttemptContext and cannot re-send the action. The attempt sends the planner action at most once.

The planner request keeps current production timestamp semantics: ROS time at request-send. `t_A` is the prerequisite lookup time, not the planner goal stamp. The model records both independently.

### Returned path binding after planner success

Only a planner result with status `SUCCEEDED`, the exact pending `request_id`, matching `goal_id`, matching lifecycle/config identity and map identity, and a still-active matching AttemptContext may create an eligible `PathContext`. A wrong-request callback, stale callback, old generation, mismatched map, or failed/pending result is rejected and creates no eligible path. Returned path fields are bound to that request/goal only after this check. Phase B cannot start without the accepted returned path and its full §45 identity.

## 4. F2 — single pending Phase B snapshot

Phase B requires the accepted returned path and a complete active path context. On first acquisition, pin one snapshot and:

- `t_vector`: ROS cutoff at acquisition;
- `t_odom`: exact odometry source stamp in that snapshot;
- `t_tf = t_odom`: exact transform query stamp;
- `t_commit`: ROS time read by the final supplier check after transform; provenance only.

Freshness is checked at acquisition and commit using existing authorized predicates. Every input must be at or before its applicable cutoff; the final-issued receipt must be after the action/reset barriers and no later than `t_vector`. Future or post-cutoff inputs are rejected. Do not change `t_vector`, `t_tf`, or pinned source stamps while waiting.

While a pending snapshot and its attempt/context remain valid, a second `capture_sample()` explicitly returns `REJECTED_PENDING_SNAPSHOT_EXISTS`. It cannot overwrite the first snapshot, cutoff, TF stamp, or correlation IDs. A different snapshot is accepted only after explicit commit or explicit invalidation/discard. New arrivals never replace pending members implicitly.

Measurement deduplication uses source measurement identity within lifecycle/path context—scan record, odometry record, receipt sequence, lifecycle sequence, goal/path sequence, epoch/generation, and map identity. It excludes model-generated `snapshot_id` and cutoff; changing those alone cannot make old measurements new. Correlation records remain immutable.

The transform request uses a deep copy of the path/pose. Raw poses and timestamps are not mutated. `can_transform=true` is followed by lookup/transform; a thrown exception is recorded with the original cause and cannot commit a LocalReference.

## 5. F3/F4 — rollback latch and final supplier check

All relevant model entry points—trigger consumption, Phase A polling/re-arm, planner-result admission, sample capture, and sample polling—read the same fake clock/context state and run the rollback/deadline guard. A rollback clears pending state, records a structured terminal failure, and latches the current attempt terminal. A subsequent capture, re-arm, result, or increased ROS time cannot restore it. A new attempt is outside this model and can only be created under a separately approved lifecycle/authorization contract.

For Phase B, the fake state supplier is read before lookup and **again after lookup/transform immediately before commit**. The final read supplies fresh ROS time, steady time, identity, AttemptContext, barrier revision, and PathContext. Commit repeats the overall steady-deadline check, freshness, cutoff ordering, exact context, and path identity checks using that final state. Therefore a lookup that advances ROS time beyond freshness, advances steady time to the deadline, or changes context/barrier/path cannot commit. The model does not reset the pinned input or timestamps after such a change.

If lookup throws, the supplier is still read after the failed transform. A rollback/deadline/context/freshness invalidation wins and discards/fails the pending attempt; otherwise the original lookup cause is retained as a structured wait outcome under the existing deadline policy. No timestamp fallback is used.

## 6. Regression coverage

`offline_model.py` uses named cases with expected outcomes asserted at each case. Coverage matrix is stored separately from behavioral case results; static declarations (including the source freshness values) are not counted as tests.

| Requirement | Behavioral case |
|---|---|
| Startup has no path; AttemptContext alone plus exact TF can send once; context change blocks the action | `startup_without_path_sends_planner_once`, `phase_a_attempt_context_change_before_action` |
| Bind path only after correct successful request result | `planner_success_correct_request_binds_path_after_result` |
| Wrong request, stale generation, and non-success result cannot bind path; only matching SUCCEEDED binds | `wrong_request_result_rejected`, `stale_generation_result_rejected`, `planner_non_success_result_does_not_bind_path`, `planner_success_correct_request_binds_path_after_result` |
| JSON trigger without header; zero ROS time waits while steady deadline runs | `json_trigger_no_header_clock_zero_steady_deadline` |
| Fixed `t_A`, late TF, send-time planner stamp, re-arm without action retry | `fixed_ta_late_tf_send_once` |
| Second capture rejected; first pending values preserved | `capture_second_snapshot_rejected_without_overwrite` |
| Rollback detected on a separate entry point, pending cleared, no recovery | `rollback_entrypoint_invalidates_and_latches_attempt` |
| Freshness recheck after transform | `lookup_advances_ros_past_freshness_final_check_rejects` |
| Steady deadline recheck after transform | `lookup_advances_steady_to_deadline_no_commit` |
| Context, barrier, and path changes during lookup fail final check | `lookup_context_change_context`, `lookup_context_change_barrier`, `lookup_context_change_path` |
| Barrier/path event advances through a change and remains invalidated after value-like return | `barrier_changed_then_values_return_revision_invalidates`, `path_sequence_changed_then_restored_payload_not_resurrected` |
| Future and post-cutoff inputs rejected | `phase_b_cutoff_rejects_future_and_post_cutoff_receipt` |
| Same measurements remain duplicate across new ID/cutoff | `same_measurements_new_snapshot_id_cutoff_duplicate` |
| `can_transform=true` plus lookup exception does not commit | `can_transform_true_lookup_exception_no_commit` |
| Transform request does not mutate raw path; callbacks proceed between returned polls | `transform_request_does_not_mutate_raw_path`, `callbacks_progress_between_nonblocking_polls` |

The production baseline runs separately with the pinned observer source methods and fake objects. Proposed outcomes are model evidence only. No case tests full 81D vector acceptance or campaign verdict.

## 7. Limits, mappings, and future authority work

No TF-age, skew, or path-expiry numeric bound is chosen or added. Existing source freshness constants in the model are declarations copied from the pinned baseline; they are not authority for TF age/skew/path expiry. Unresolved production mappings are:

1. Approved source/API that supplies the actual GlobalPathSnapshot fields to this collector, including path replacement events reflected by `path_sequence` and steady receipt/expiry.
2. Approved immutable source for applicable TF-age/future and reference/odometry skew predicates; this packet supplies no defaults.
3. Exact lifecycle/barrier event source and monotonic revision mapping at the collector boundary.
4. Whether later temporal-contract activation changes a contract/profile reference or global config hash. This packet does not alter ACR, profile, config hash, or public interface.
5. Versioned evidence/diagnostic schema if these state details are persisted later.

These mappings belong to a subsequent architecture-decision package. They are not guessed or implemented here.

## 8. Evidence status and PLAN_UPDATE_PROPOSAL

Model status is `PROPOSAL_ONLY_NOT_PRODUCTION`; it verifies only temporal state and LocalReference fake cases. `81D_acceptance`, QoS, evidence chain, campaign acceptance, Nav2 runtime, and tf2 runtime are `NOT_EVALUATED`. It cannot validate the real executor, TF cache, action transport, producer path semantics, or Invocation_021. Invocation_021 remains `ROOT_CAUSE_UNRESOLVED_FOR_INVOCATION_021`.

`PLAN_UPDATE_PROPOSAL`: Run005 fixed-time TF wait review packet corrective; branch `step07-integrated-nav2-gateb-campaign-f7f98c6`; packet base/required parent `674791655d43155accfe2b230f20994b76cbbc7b`; pinned production baseline `4e83ce6cffdd9910c288f90454ab747497d7a4a6`. Evidence is `IMPLEMENTED_OFFLINE_ONLY` for this four-file packet and fake model only. Next step: independent review and a subsequent architecture-decision package for the listed production field mappings; no production implementation or runtime is authorized by this packet.
