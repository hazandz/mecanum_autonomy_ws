# S3 D3 — Bootstrap Create-Outcome Ownership Design

**Status: DRAFT — OPTION A IMPLEMENTED OFFLINE ONLY — RUNTIME NOT APPROVED**

## Purpose

This design records who can record the limited Candidate A
`create process exit-success` convention without parsing logs and without adding
a runtime command path. The S3.3.40 implementation is offline-testable only;
it creates no execution authority or run artifact.

## Historical pre-S3.3.40 ownership evidence

```text
historical pre-S3.3.40 launch ownership:
supervisor
  └─ ros2 launch typed_scene_observer.launch.py
       └─ TimerAction(3.0) → ros_gz_sim create

S3.3.40 offline-only target ownership:
supervisor → one directly owned ros_gz_sim create child
     while dedicated launch provides only world + /robot_description bootstrap
```

| Layer | Local evidence | What it owns / exposes | Limitation |
| --- | --- | --- | --- |
| Historical dedicated launch | Before S3.3.40, [typed_scene_observer.launch.py](../ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py) put `Node(package='ros_gz_sim', executable='create')` inside `TimerAction(3.0)`. | The launch owned the create child action. | This is historical only; S3.3.40 removed that Node and TimerAction. |
| ROS launch runtime | `/opt/ros/jazzy/lib/python3.12/site-packages/launch/events/process/process_exited.py` defines `ProcessExited.returncode`; `on_process_exit.py` can handle it for a target action. | The launch framework can observe a child process return code. | No current dedicated launch event handler emits a machine-readable supervisor handoff; adding one conflicts with the static launch allowlist and is not approved here. |
| S3.3.40 supervisor contract | [run_typed_scene_observer.py](../artifacts/simulation/contact_producer_evidence/tools/run_typed_scene_observer.py) has an injected, offline-only direct-create phase. Its execution branch remains blocked. | It validates the exact allowlisted create plan and records opaque process metadata from an injected child handle. | It has not launched a child, acquired a guard, or authorized runtime. |
| Installed `ros_gz_sim create` | Binary strings show `set_XML_from_topic`, Gazebo `Node::Request` errors, and `Entity creation successful/failed`; installed package version is `1.0.22`. | A direct child can be observed for OS-level completion and return code without parsing output. | Installed source does not specify exact `main()` return-code semantics or prove Scene insertion. |

### Audit answer

Before S3.3.40, the launch-owned `TimerAction → Node(create)` architecture
gave the supervisor **no locally evidenced typed/stable child-exit handoff**. It
therefore could not parse stdout/stderr or logs as a substitute. S3.3.40 removes
that architecture and implements an offline-only direct-child contract; the
outer `ros2 launch` exit code remains unsuitable as a create outcome.

## Options

| Option | Design | Evidence status | Result |
| --- | --- | --- | --- |
| **A — supervisor-owned create** | A future bootstrap launch retains only locked world startup and the narrowly approved `robot_state_publisher` description provider. After it has been launched, the supervisor directly starts exactly one direct allowlisted `/opt/ros/jazzy/lib/ros_gz_sim/create` child with the existing locked arguments, retains its process handle, and reads its OS exit status. | Direct child ownership and OS exit status are standard process semantics; no log parsing is needed. The semantic meaning of exit `0` remains only the user-approved operational convention. | **Selected and implemented offline only by S3.3.40; runtime approval remains absent.** |
| **B — launch-owned create with machine-readable handoff** | Keep create inside launch and expose its `ProcessExited.returncode` through an exact supervisor-consumable handoff. | Launch API can observe child exit, but no current launch contains such a handoff and no local approved typed mechanism was found that exports it without event handler/opaque logic or log parsing. | **UNAVAILABLE — no locally confirmed handoff.** |

Option B must not be assumed from `ProcessExited` alone: an event exists only
inside the launch runtime and the current static checker deliberately rejects
event handlers, opaque functions, and output-based handoff.

## Recommended Option A contract

```text
dedicated bootstrap launch:
  locked world + robot_state_publisher(/robot_description only)

supervisor:
  owns one ros_gz_sim create child
  → records argv, PID/process identity, start/end steady timestamps, exit code
  → does not inspect stdout/stderr to derive success
  → applies only user-approved post_create_delay_ms after exit-success convention
  → permits exactly one helper / exactly one RequestRaw
```

The direct create child retains the existing literals:

```text
-topic /robot_description
-name ROBOT_URDF_final
-allow_renaming false
-x 0 -y 0 -z 0.1 -Y 0
```

This remains bootstrap-only: exactly one initial spawn, no bridge, no
`/cmd_vel`, no pose/reset/pause/step/delete/world-control, no second spawn, and
no retry. The create exit-success convention is not a Scene/entity receipt,
reset receipt, settled-state proof, or atomic-insertion proof. Candidate A
negative hierarchy results remain `*_NOT_OBSERVED_AFTER_DELAY`, never `*_ABSENT`.

## S3.3.40 implementation record — offline only

| Surface | Implemented offline-only change | Validation completed | Runtime boundary retained |
| --- | --- | --- | --- |
| Dedicated launch | Removed `TimerAction` and launch-owned `ros_gz_sim create`; retained only locked world/resource/Xacro/description-provider bootstrap. | AST checker requires one description-provider Node, zero create Nodes, zero `TimerAction`, and exact no-bridge graph. | The launch was not run. |
| Supervisor | Added the pure `create_phase()` contract plus a separate future-only `RuntimeCreateAdapter`: exact allowlisted executable/argv, `subprocess.Popen(..., shell=False, start_new_session=True)`, process-group ownership, SIGINT-group interface, process identity, steady timestamps, exit code, delay gate, timeout grace, and immediate pre-spawn SHA-256 recomputation. | Offline fake/mocked tests cover one invocation, success, nonzero exit, timeout, interruption, missing exit code, spawn error, literal mismatch, plan SHA mismatch, changed SHA after plan creation, invalid path/file/hash, exact Popen arguments, separate session/group, SIGINT target, timeout grace, `--execute` fail-closed, no retry, and no stream parsing. | Adapter source exists only for later hash binding; no subprocess was created, guard acquired, helper called, or `RequestRaw` run. |
| Artifact / replacement guard | No artifact or new guard was created. | Existing guards remain untouched. | A future replacement packet/guard must bind ownership mode/version, argv, create executable hash, delay, launch/helper/world hashes, and one-request rule. |


## S3.3.43 runtime-adapter implementation record — offline only

`RuntimeCreateAdapter` is distinct from `create_phase()`. It accepts only the
exact `/opt/ros/jazzy/lib/ros_gz_sim/create` path and locked argv, invokes
`subprocess.Popen` with `shell=False`, `start_new_session=True`, and discarded
streams, then verifies the created process group equals the child PID. Its
`RuntimeCreateProcess` exposes only `pid`, `wait(timeout_ms)`, and
`send_sigint_group()`; the latter calls SIGINT only for that owned group.

The adapter has no helper, Scene request, bridge, command/control, retry, or
force-kill method. The CLI never instantiates it: `--execute` exits
`NO_EXECUTION_AUTHORITY` before `Popen`, guard activity, or runtime I/O. This
source is hash-bindable in a future replacement packet/guard, but does not
itself authorize execution.

## Terminal contract

| Status | Condition | Prohibited claim |
| --- | --- | --- |
| `SCENE_CREATE_OUTCOME_UNCONFIRMED` | Direct create child cannot start, does not exit under the approved convention, exits nonzero, is interrupted, or its exit code cannot be recorded. | Entity/Scene absence or spawn failure cause. |
| `SCENE_BOOTSTRAP_UNCONFIRMED` | Any required ownership, create-outcome, or delay precondition is missing/fails. | Permission to send `RequestRaw`. |
| `SCENE_BOOTSTRAP_READY_FOR_ONE_REQUEST` | Direct create process exit-success convention is recorded and the user-approved delay completes. | Scene receipt, reset receipt, or settled state. |
| `SCENE_*_NOT_OBSERVED_AFTER_DELAY` | Candidate A one-request response lacks a required exact hierarchy member. | Actual absence. |
| `SHUTDOWN_INCOMPLETE` | Future only: a timed-out create child remains alive after its future user-approved SIGINT grace period. | Spawn receipt, cleanup success, helper permission, or retry permission. |

No status authorizes a second Scene request, retry, or additional spawn.

## Remaining user decisions and blockers

The following S3.3.40 decisions are recorded for offline implementation only:

| Decision | Recorded value |
| --- | --- |
| Ownership mode | `SUPERVISOR_OWNED_CREATE_V1` |
| Create timeout | `create_timeout_ms=90000` |
| Post-create operational delay | `post_create_delay_ms=2000` |
| Exit-zero meaning | Candidate-A operational convention only; not a Scene/entity, reset, or settled-state receipt. |
| Cardinality / shutdown | One create, one Scene `RequestRaw`, no retry, capacity `1`, SIGINT-only; `create_shutdown_grace_ms=5000`. |

The S3.3.41 pre-spawn integrity gate is implemented offline: it requires the
exact `/opt/ros/jazzy/lib/ros_gz_sim/create` path to be a regular file, a
lowercase full SHA-256 in the plan, and an equal fresh SHA-256 immediately
before any injected spawn. Any mismatch produces
`SCENE_CREATE_OUTCOME_UNCONFIRMED` and `SCENE_BOOTSTRAP_UNCONFIRMED` with zero
create invocations, no delay, and no helper.

The S3.3.42 timeout/shutdown contract is implemented offline: a timeout sends
only injected `SIGINT` to the direct child process group, waits exactly
`create_shutdown_grace_ms=5000`, and returns either the retained
`SCENE_CREATE_OUTCOME_UNCONFIRMED` / `SCENE_BOOTSTRAP_UNCONFIRMED` outcome after
clean exit or outer `SHUTDOWN_INCOMPLETE` if the child remains alive. Neither
path permits helper execution, `RequestRaw`, retry, or another run.

Runtime still requires a new user-approved replacement execution packet and a
new capacity-one guard. The existing implementation does not authorize either.

`preflight_wait_ms=90000`, `request_timeout_ms=5000`, polling `10 ms`, capacity
`1`, and SIGINT-only shutdown remain locked literals, not decisions reopened by
this packet.

## Non-claims

This design does not prove a Scene entity, raw contact endpoint, collision,
ContactLatch, filter policy, reward, termination, Gym/training, TF authority,
reset/settle receipt, or hardware readiness. It does not add a bridge, command
path, control API, or ROS observer endpoint.

## Conclusion

**IMPLEMENTED_OFFLINE_ONLY — RUNTIME_NOT_APPROVED**
