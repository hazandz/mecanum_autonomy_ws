# S3 Post-Response Provenance Replacement-Run Packet

**Status:** `COMPLETED_REPLACEMENT_RUN — EVIDENCE_RETAINED`

## 1. Purpose and scope

This packet records the completed minimal replacement controlled measurement
that separated four local steady-clock events for each declared pose request:
call preparation, request dispatch, ROS response receipt, and the immediately
following capture barrier. The completed evidence is retained at
[`run-replacement-post-response-20260924T191000Z-03`](../artifacts/simulation/controlled_coordinate_reset_measurement/run-replacement-post-response-20260924T191000Z-03/).
It does not authorize a further pose request or any source change.

The intended evidence is limited to showing which recorded GT odometry
candidates were received after the ROS client had validated a successful
`SetEntityPose` response. It is **not** an atomic reset contract, a Gazebo
pose-application receipt, a settlement/freshness policy, or a coordinate-frame
decision.

## 2. Preserved evidence from the completed run

The existing run
[`run-controlled-20260924T180000Z-02`](../artifacts/simulation/controlled_coordinate_reset_measurement/run-controlled-20260924T180000Z-02/)
remains `VALID` for its declared operational scope, as reviewed in
[S3 Controlled Coordinate Evidence Review](S3_Controlled_Coordinate_Evidence_Review_DRAFT.md):

- The temporary bridge had exactly one service mapping and no topic bridge.
- `/world/world_demo/set_pose` was observed as
  `ros_gz_interfaces/srv/SetEntityPose` before and after capture.
- Exactly `P0 → P1 → P2` targeted only `ROBOT_URDF_final`; every retained
  response was `success=true`.
- The collector had no command publisher or action client; the frozen
  pre-existing `/cmd_vel` publisher allowlist did not change. There was no
  authorized world-control or hardware operation.
- GT traces contain observed pose candidates numerically near the requested
  x/y/yaw later in each capture interval. Their GT z values are `0`, whereas
  the request z values are `0.1`.

The latter is an `OBSERVED_CANDIDATE`, not identity mapping. This packet does
not change z, select a coordinate frame, or infer a pose-origin convention.

## 3. Provenance gap being addressed

The completed request records contain a pre-call
`barrier.captured_steady_ns` and a later post-probe barrier. They do **not**
contain either:

- `service_response_received_steady_ns`; or
- `post_response_barrier_steady_ns`.

Consequently, the existing analyzer's first GT row after the pre-call barrier
is only a candidate. It cannot demonstrate that the ROS client had received
the response, or that Gazebo had already reflected the pose in GT, before that
row arrived. The facts below must remain distinct:

| Fact | What the current run records | What it does not prove |
| --- | --- | --- |
| Request call | Pre-call barrier before `call_async` | Request dispatch or Gazebo application. |
| Service response success | `{"success": true}` payload | Local time the ROS client received the response. |
| First GT after pre-call barrier | A deterministic trace candidate | That the candidate follows ROS response receipt or application. |
| Later visible GT pose change | Observed trace sequence | A selected settle point, reset receipt, or coordinate mapping. |

## 4. Recorded per-probe steady-clock provenance

For every probe, the replacement collector recorded the following
monotonic/steady-clock values without converting them to ROS/simulation time:

| Field | Recorded capture point | Meaning and boundary |
| --- | --- | --- |
| `pre_call_steady_ns` | Immediately before `call_async(request)` | Last local event before the request API call. |
| `ros_request_dispatched_steady_ns` | Immediately after `call_async` returns the future | Local client-side dispatch boundary only; not a Gazebo receipt. |
| `ros_response_received_steady_ns` | Immediately when the future is first observed complete, before GT analysis | Local ROS-client response-receipt time. |
| `post_response_barrier_steady_ns` | Immediately after response validation confirms `success=true` | Starts classification of post-response GT candidates. |

The request/response record must preserve all four values, the complete request
payload, complete response payload, entity, and call order. A GT record is
classified `POST_RESPONSE_CANDIDATE` only if:

```text
gt.received_steady_ns > post_response_barrier_steady_ns
```

This comparison is valid because both operands are steady-clock values. The GT
ROS/simulation stamp remains separately retained and is never subtracted from a
steady timestamp.

`POST_RESPONSE_CANDIDATE` means only “received after this local response
barrier.” It still does not prove atomic reset, Gazebo pose application,
publication ordering inside Gazebo, TF authority, or an absolute receipt.

## 5. Replacement-run scope, fixed inputs, and guards

The user approved and completed one Gazebo simulation-only replacement run with
the following immutable boundaries. Its execution authority is consumed: all
three declared pose requests were sent in order, and this packet neither asks
for nor authorizes a rerun.

| Item | Required value |
| --- | --- |
| Target entity | `ROBOT_URDF_final` only |
| Pose order | Exactly `P0 → P1 → P2`; no retry or supplemental request |
| P0 | `x=-4.0`, `y=-3.0`, `z=0.1`, `yaw=0.0` |
| P1 | `x=-4.0`, `y=0.0`, `z=0.1`, `yaw=1.57079632679` |
| P2 | `x=-2.0`, `y=-3.0`, `z=0.1`, `yaw=-1.57079632679` |
| Bridge | One temporary, artifact-owned service bridge only: `/world/world_demo/set_pose@ros_gz_interfaces/srv/SetEntityPose@gz.msgs.Pose@gz.msgs.Boolean` |
| Shutdown | SIGINT only for Gazebo and bridge processes created by this run |

The completed run did not publish `/cmd_vel`, create a command publisher, run
teleop, Nav2, PPO, Gymnasium, reset/pause/step a world, spawn/delete an entity,
invoke world-control, or operate firmware or hardware.

| Guard | Classification | Explicit non-claim |
| --- | --- | --- |
| Warm-up `10 s` | `ADMINISTRATIVE_STOP_GUARD` | Not settling, freshness, or reset policy. |
| Post-response capture up to `10 s` | `ADMINISTRATIVE_STOP_GUARD` | Not a timeout SLA, velocity epsilon, settle threshold, or residual tolerance. |
| `topic_wait_seconds=90` | `PREFLIGHT_STOP_GUARD` | Not a freshness, reset, or measurement-acceptance policy. |

No settle threshold, velocity epsilon, timeout policy, freshness policy, or
residual tolerance is proposed or selected here.

## 6. Retained replacement artifacts

The completed replacement run created the non-overwriting directory linked in
Section 1 under `artifacts/simulation/controlled_coordinate_reset_measurement/`
and retains:

| Artifact | Recorded distinction |
| --- | --- |
| Request/response record | Four steady timestamps, request/response payloads, entity, call order, and service name/type. |
| GT trace | ROS/simulation stamp and steady receive time as separate fields, plus pose/twist. |
| Per-probe summary | `PRE_RESPONSE_CANDIDATE`, `POST_RESPONSE_CANDIDATE`, `OBSERVED_POSE_CHANGE`, and `NO_POST_RESPONSE_GT` classifications. |
| Aggregate report | Uses only `POST_RESPONSE_CANDIDATE` for a candidate request–GT relation; does not elevate it to mapping proof. |
| Graph/service snapshots and bridge lifecycle | Exact service type, frozen `/cmd_vel` allowlist, temporary bridge command/owner, and SIGINT shutdown evidence. |

`PRE_RESPONSE_CANDIDATE` is any retained GT candidate after dispatch but not
strictly after the post-response barrier. `OBSERVED_POSE_CHANGE` is a
descriptive change in the retained GT sequence, not a settle or receipt rule.

## 7. Execution safeguards and interpretation

| Condition | Required result | Further pose requests |
| --- | --- | --- |
| Exact service missing/type mismatch, graph change, or `/cmd_vel` allowlist change | Run `INVALID`; preserve evidence and shutdown | Stop; send none remaining. |
| Service error or response not received by the administrative guard | Run `INVALID`; preserve timestamps available | Stop; no retry. |
| Any required steady timestamp absent/non-monotonic in its local sequence | Run `INVALID` for mapping evidence | Stop; no extra request. |
| `success=true` but no GT after post-response barrier | Record `NO_POST_RESPONSE_GT`; do not infer relation | Continue only if no invalidation; never add a probe. |
| GT candidate after post-response barrier | Record `POST_RESPONSE_CANDIDATE` and any descriptive `OBSERVED_POSE_CHANGE` | Do not select a coordinate mapping automatically. |
| All declared probes complete | Report observational post-response candidates only | Shutdown; no fourth request. |

## 8. Completed execution record

- The user-approved Gazebo simulation-only replacement run completed with
  exactly `P0 → P1 → P2` against `ROBOT_URDF_final`; no retry, fourth request,
  or altered pose request is authorized by this completed packet.
- The retained records contain the four steady-clock fields and the
  post-response candidate rule for every probe.
- The evidence remains limited: it is not approval for atomic reset, Gazebo
  application receipt, coordinate mapping, TF authority, collision, task
  oracle, Gym, reward/termination, deployment, firmware, or hardware.

## Explicit non-claims

This packet does not alter raw evidence, reuse consumed request authority, or
approve implementation. Any future pose-control run would require separate
user approval before launch or service activity. Its `POST_RESPONSE_CANDIDATE`
records remain local receive-order evidence only, not Gazebo application or
reset receipts.
