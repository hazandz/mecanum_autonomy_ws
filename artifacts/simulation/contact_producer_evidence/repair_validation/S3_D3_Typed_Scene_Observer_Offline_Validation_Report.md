# S3 D3 — Typed Scene Observer Offline Validation Report

## Scope

This report records offline-only validation of the temporary helper
[`typed_scene_observer.cpp`](../tools/typed_scene_observer.cpp). No Gazebo,
ROS, `gz` CLI, bridge, transport service request, collector runtime, command,
control action, UART, or hardware process was started.

The helper remains outside production packages. Its future runtime path is not
authorized by this report and was not invoked.

## Local compiler and package evidence

| Item | Observed value |
| --- | --- |
| Compiler | `g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0` |
| Transport package | `gz-transport13 13.5.0` |
| Message package | `gz-msgs10 10.3.2` |
| Build output location | Temporary directory only: `/tmp/tmp.s8MqGu34L2/typed_scene_observer` |
| Workspace binary | None created or retained. |

The compile command that passed was:

```bash
task_pkg_dirs=$(find /opt/ros/jazzy/opt -path '*/lib/pkgconfig/*.pc' -printf '%h\n' | sort -u | paste -sd: -)
PKG_CONFIG_PATH="$task_pkg_dirs" g++ -std=c++17 -Wall -Wextra -Werror \
  artifacts/simulation/contact_producer_evidence/tools/typed_scene_observer.cpp \
  -o "$task_tmp_dir/typed_scene_observer" \
  $(PKG_CONFIG_PATH="$task_pkg_dirs" pkg-config --cflags --libs gz-transport13 gz-msgs10)
```

The compiler accepted the local `gz::transport::Node`, `gz::msgs::Empty`, and
`gz::msgs::Scene` headers and linked `gz-transport13` plus `gz-msgs10`. It also
compiled the sole future `Node::RequestRaw` call using type names obtained from
the generated protobuf messages. No request was executed.

## Offline self-test results

The following command exited `0`:

```bash
/tmp/tmp.s8MqGu34L2/typed_scene_observer --offline-self-test
```

| Fixture | Expected status | Result |
| --- | --- | --- |
| Exact model → link → sensor → contact/collision fixture | `SCENE_SENSOR_PRESENT_IDENTITY_ONLY` | PASS |
| Missing model | `SCENE_MODEL_ABSENT` | PASS |
| Missing link | `SCENE_LINK_ABSENT` | PASS |
| Missing sensor | `SCENE_SENSOR_ABSENT` | PASS |
| Duplicate exact model | `SCENE_RESPONSE_UNDECODABLE` | PASS |
| Duplicate exact link | `SCENE_RESPONSE_UNDECODABLE` | PASS |
| Duplicate exact sensor | `SCENE_RESPONSE_UNDECODABLE` | PASS |
| `has_contact() == false` | `SCENE_SENSOR_PRESENT_IDENTITY_ONLY` | PASS |
| Empty collision name | `SCENE_SENSOR_PRESENT_IDENTITY_ONLY` | PASS |
| Wrong collision name | `SCENE_SENSOR_PRESENT_IDENTITY_ONLY` | PASS |
| Missing same-link collision | `SCENE_SENSOR_PRESENT_IDENTITY_ONLY` | PASS |
| Duplicate same-link collision | `SCENE_RESPONSE_UNDECODABLE` | PASS |
| Corrupt raw protobuf bytes | `SCENE_RESPONSE_UNDECODABLE` | PASS |

All 13 fixtures passed. The positive maximum was
`SCENE_SENSOR_PRESENT_IDENTITY_ONLY`; the helper does not emit
`SCENE_SENSOR_PRESENT`.

## Static offline-mode safety checks

| Check | Result |
| --- | --- |
| `--offline-self-test` function contains `gz::transport::Node` construction | PASS: none |
| `--offline-self-test` function contains `RequestRaw` call | PASS: none |
| Whole source `node.RequestRaw(` count | PASS: exactly `1`, in `RuntimeOnce` only |
| `sensor->type()` string comparison count | PASS: `0` |
| String literal `"contact"` comparison count | PASS: `0` |
| Full `SCENE_SENSOR_PRESENT` emission from classifier | PASS: none; status is intentionally unreachable |

The classifier uses only the approval-packet semantics: exact identity
equality, `Sensor::has_contact()`, non-empty exact
`ContactSensor::collision_name()`, and exactly-one same-link
`Collision::name()`. It deliberately does not reinterpret a contact submessage
as a type enum because the installed generated schema has no such enum.

## Remaining approval gates

This offline repair and validation does not authorize runtime. Before any
future one-shot run, the user must still approve:

- a bounded preflight wait;
- a typed-request timeout;
- an approval-bound capacity-one guard tied to the authority packet and locked
  literals; and
- exactly one runtime execution under the boundaries in the [typed Scene
  observer approval packet](../../../../docs/S3_D3_Typed_Scene_Observer_Run_Approval_Packet_DRAFT.md).

No raw artifact, prior approval record/guard, robot/world source, firmware, or
production package file was modified by this validation.


## S3.3.28 artifact-contract completion

The helper now accepts the future runtime-only form:

```text
--runtime-once --timeout-ms <positive-integer> --output-dir <directory>
```

The runtime path is present in source only and was not invoked. It contains one
`Node::RequestRaw` call. After a successful response, it writes
`scene_response.pb` losslessly **before** parsing a separate in-memory copy.
It then emits deterministic `scene_summary.json` and separate operational
`request_metadata.json`. `scene_summary.json` has no timestamps, uses fixed
literal values and lexically ordered JSON keys, and includes a SHA-256 of the
raw response bytes.

If raw, summary, or metadata persistence fails, the outer status is
`INVALID_EVIDENCE_PERSISTENCE_FAILURE`; it is not remapped to a `SCENE_*`
status and must not retain a presence/absence claim.

### S3.3.28 compile and offline results

The following offline-only compile passed with `-Wall -Wextra -Werror`:

```bash
task_pkg_dirs=$(find /opt/ros/jazzy/opt -path '*/lib/pkgconfig/*.pc' -printf '%h\n' | sort -u | paste -sd: -)
PKG_CONFIG_PATH="$task_pkg_dirs" g++ -std=c++17 -Wall -Wextra -Werror \
  artifacts/simulation/contact_producer_evidence/tools/typed_scene_observer.cpp \
  -o "$task_tmp_dir/typed_scene_observer" \
  $(PKG_CONFIG_PATH="$task_pkg_dirs" pkg-config --cflags --libs gz-transport13 gz-msgs10) \
  $(pkg-config --cflags --libs openssl)
```

| Offline mode or check | Result |
| --- | --- |
| `--offline-self-test` — 13 hierarchy/protobuf fixtures | PASS: 13/13 |
| `--offline-artifact-self-test` — raw `.pb` round-trip parse | PASS |
| SHA-256 recalculated from persisted raw bytes | PASS |
| Deterministic summary from two identical fixtures | PASS: byte-identical JSON |
| Duplicate fixture | PASS: `SCENE_RESPONSE_UNDECODABLE`, no presence/absence claim |
| Corrupt fixture | PASS: `SCENE_RESPONSE_UNDECODABLE`, no presence/absence claim |
| Output path blocked by regular file | PASS: `INVALID_EVIDENCE_PERSISTENCE_FAILURE` / `RAW_RESPONSE_WRITE_FAILED` |
| Temporary offline artifact cleanup | PASS |
| Offline-mode source scan: `Node` construction / `RequestRaw` | PASS: neither in either offline function |
| Whole-source `node.RequestRaw(` count | PASS: exactly 1, runtime path only |
| `Sensor::type()` or literal `"contact"` comparison | PASS: 0 |
| Classifier emission of `SCENE_SENSOR_PRESENT` | PASS: unreachable |

No Gazebo, ROS, `gz` CLI, bridge, service request, collector runtime, command,
control action, or hardware process was run during S3.3.28.

### Remaining blockers before runtime

- Typed service-discovery behavior remains unobserved against a running Gazebo
  server.
- The user must select and approve both the bounded preflight wait and the
  typed-request timeout; no numeric literal was selected offline.
- A new approval-bound capacity-one guard and explicit approval for exactly one
  runtime run remain required.
- `SCENE_SENSOR_PRESENT` remains prohibited because installed `gz-msgs10` has
  no Contact sensor enum and this contract forbids a string comparison.


## S3.3.29 typed service-discovery preflight

The version-matched, compiled discovery API is:

```cpp
void gz::transport::Node::ServiceList(std::vector<std::string> &_services) const;
```

The future runtime path now requires this exact command shape:

```text
--runtime-once --preflight-wait-ms <positive-integer> --timeout-ms <positive-integer> --output-dir <directory>
```

It creates the output directory before constructing the Transport node or
writing metadata. It polls `ServiceList` until the steady-clock deadline and
requires exactly one equality match for `/world/world_demo/scene/info`. An
absent or duplicate service entry reaches the preflight deadline without a
`RequestRaw` call and writes `SCENE_SERVICE_UNAVAILABLE` metadata. A confirmed
service permits the sole `RequestRaw`; its timeout/failure writes
`SCENE_REQUEST_INCOMPLETE` metadata. Persistence errors remain the outer
`INVALID_EVIDENCE_PERSISTENCE_FAILURE` status.

| S3.3.29 offline validation | Result |
| --- | --- |
| Compile of `Node::ServiceList(std::vector<std::string> &) const` and full runtime path | PASS |
| Valid runtime argument shape | PASS |
| Missing/zero/non-numeric preflight wait | PASS: rejected |
| Exact one service list entry | PASS: accepted by pure helper logic |
| Empty service list | PASS: unavailable by pure helper logic |
| Duplicate exact service entries | PASS: rejected by pure helper logic |
| Service-unavailable metadata output directory creation | PASS |
| Request-incomplete metadata output directory creation | PASS |
| `--offline-self-test` and `--offline-artifact-self-test` | PASS |

Static source counts after S3.3.29:

| Item | Count / result |
| --- | --- |
| `gz::transport::Node` construction in offline modes | `0` |
| `RequestRaw` call in offline modes | `0` |
| `node.ServiceList(` call | `1`, runtime path only |
| `node.RequestRaw(` call | `1`, runtime path only |
| `Sensor::type()` comparison | `0` |
| Literal `"contact"` comparison | `0` |
| Reachable `SCENE_SENSOR_PRESENT` emission | `0` |

No Gazebo, ROS, `gz` CLI, bridge, request runtime, collector, command,
control action, UART, or hardware process was run. The remaining blockers are
only user selection/approval of the preflight wait and request timeout,
an approval-bound capacity-one guard, and approval for exactly one runtime run.


## S3.3.30 polling and metadata-provenance hardening

The runtime preflight now polls the compiled typed
`Node::ServiceList(std::vector<std::string> &) const` with a fixed **10 ms**
interval. This is an implementation detail to avoid busy-spin; it does not
select, cap, or alter the user-supplied `--preflight-wait-ms` or
`--timeout-ms`. The sleep target is the earlier of `now + 10 ms` and the
steady-clock deadline.

| Runtime branch | Preflight timestamps | Request timestamps | Metadata terminal status |
| --- | --- | --- | --- |
| Service unavailable at deadline | Present | `null` / `null` | `SCENE_SERVICE_UNAVAILABLE` |
| Request serialization failure before `RequestRaw` | Present | Present for serialization attempt | `SCENE_REQUEST_INCOMPLETE` with `REQUEST_SERIALIZATION_FAILED` |
| Request timeout/failure | Present | Present | `SCENE_REQUEST_INCOMPLETE` |
| Scene classification | Present | Present | `SCENE_CLASSIFICATION_COMPLETE` plus inner `SCENE_*` status |
| Any required evidence persistence failure | No presence/absence claim may be retained | No presence/absence claim may be retained | Outer `INVALID_EVIDENCE_PERSISTENCE_FAILURE` |

`scene_summary.json` remains timestamp-free and deterministic. Operational
steady-clock values are confined to `request_metadata.json` schema v2.

| S3.3.30 offline validation | Result |
| --- | --- |
| `-Wall -Wextra -Werror` compile, including `ServiceList`, fixed sleep, and runtime path | PASS |
| Existing 13 hierarchy/protobuf fixtures | PASS: 13/13 |
| Exact service present / absent / duplicate pure logic | PASS |
| Positive, zero, invalid preflight CLI values | PASS: only positive value accepted |
| Poll interval nonzero and next poll bounded by deadline | PASS: `10 ms` |
| Request serialization failure injection seam | PASS: failure returned without a Transport node/request |
| Service-unavailable metadata: request timestamps are `null` | PASS |
| Request-incomplete metadata: both timestamp groups present | PASS |
| Both offline modes free of `Node` / `RequestRaw` | PASS |

Static counts: exactly one `node.ServiceList(` and one `node.RequestRaw(`,
both in `RuntimeOnce`; neither offline mode constructs a node or invokes a
request. `Sensor::type()` and literal `"contact"` comparisons remain absent,
and `SCENE_SENSOR_PRESENT` remains unreachable.

No Gazebo, ROS, `gz` CLI, bridge, runtime service request, command/control,
UART, or hardware operation ran. Remaining blockers are only user approval of
the preflight wait and request timeout, an approval-bound capacity-one guard,
and approval for exactly one runtime run.
