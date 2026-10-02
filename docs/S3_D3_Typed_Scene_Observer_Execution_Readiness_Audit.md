# S3 D3 Typed Scene Observer Execution Readiness Audit

## Scope

Read-only/offline execution-readiness audit for `S3.3.54_TYPED_SCENE_OBSERVER_FINAL_EXECUTION_RUN`. No guard state was written, no supervisor execution was invoked, and no Gazebo, ROS launch, create, helper runtime, Scene request, bridge, command, control, or hardware process ran.

## A. Guard and approval integrity

| Field | Observed value |
| --- | --- |
| Approval ID | `S3.3.54_TYPED_SCENE_OBSERVER_FINAL_EXECUTION_RUN` |
| Schema | `s3_d3_typed_scene_final_execution_guard/v1` |
| State | `authorized_not_consumed` |
| Capacity | `1` |
| `run_id` | `null` |
| `final_status` | `null` |
| `consumed_at_utc` | `null` |
| Actual packet SHA-256 | `f7e4403b67754ab7cbdc6496ecf2a04d6b97588b1a28a2b21be497d6b839d21f` |
| Guard packet SHA-256 | `f7e4403b67754ab7cbdc6496ecf2a04d6b97588b1a28a2b21be497d6b839d21f` |

The packet hash matches. The guard was read only.

## Locked context

| Input | Locked path or literal | SHA-256 / value |
| --- | --- | --- |
| Supervisor | `artifacts/simulation/contact_producer_evidence/tools/run_typed_scene_observer.py` | `a538ebb30c776bd3469df2d99ab25fa0c949f8d2d65c9b4bca5c7307d61d74f4` |
| Guard helper locked by record | `artifacts/simulation/contact_producer_evidence/tools/typed_scene_replacement_approval_guard.py` | `e117f205f81866a7ccac8f4a5942e2794aa73cea0ed1c3bf26aa0abcb55d47a1` |
| C++ helper | `artifacts/simulation/contact_producer_evidence/tools/typed_scene_observer.cpp` | `ff6cc497ce845e136469f8cc026c8d6076c129da39f53591072d3b62e6241424` |
| Dedicated launch source | `ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py` | `b6acf767471527f37c4e2d7c67cc46b693298cb4bf7028afb96be8d00c4f255d` |
| World source | `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` | `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` |
| Direct create executable | `/opt/ros/jazzy/lib/ros_gz_sim/create` | `549a91ca31d5b943457b1fa6ae25cc726867b6afa69d789e1afbd2af139fe02d` |
| World/entity/service | `world_demo`; `ROBOT_URDF_final`; `/world/world_demo/scene/info` | locked literals |
| Create argv | `-topic /robot_description -name ROBOT_URDF_final -allow_renaming false -x 0 -y 0 -z 0.1 -Y 0` | locked literal |
| Timing | helper `90000/5000/10 ms`; create `90000/2000/5000 ms` | locked literals |
| One-shot boundary | one create; one request; capacity one; retry forbidden; SIGINT only | locked literals |

## B. Source and import identity

The supervisor imported from:

```text
/home/hazan/mecanum_autonomy_ws/artifacts/simulation/contact_producer_evidence/tools/run_typed_scene_observer.py
```

Its imported approval helper was:

```text
/home/hazan/mecanum_autonomy_ws/artifacts/simulation/contact_producer_evidence/tools/typed_scene_final_run_guard.py
```

That actual imported helper SHA-256 is `dd8eb39fede436eef22c60fd362dc5f60f509af8896f8ff1d09d7e20dbea286c`. It is not the helper path or SHA locked in the S3.3.54 record, which locks `typed_scene_replacement_approval_guard.py` with SHA-256 `e117f205f81866a7ccac8f4a5942e2794aa73cea0ed1c3bf26aa0abcb55d47a1`.

All other locked filesystem paths above existed, were non-symlink regular files, and their SHA-256 values matched the guard. This import-identity mismatch is a drift, even though the guard helper's own current context function can hash its legacy `guard_helper_path`.

## C. Source versus installed-artifact drift

After sourcing `/opt/ros/jazzy/setup.bash` and `/home/hazan/mecanum_autonomy_ws/ros2_ws/install/setup.bash`, `ros2 pkg prefix ROBOT_URDF_final_description` returned:

```text
/home/hazan/mecanum_autonomy_ws/ros2_ws/install/ROBOT_URDF_final_description
```

The source locked by the guard is:

```text
/home/hazan/mecanum_autonomy_ws/ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py
```

The launch file that `ros2 launch` would require from install/share is absent:

```text
/home/hazan/mecanum_autonomy_ws/ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py
```

Therefore no installed-launch SHA-256 can be compared to the source-lock SHA. This is `FATAL_EXECUTION_DRIFT`: the runtime lookup route uses install/share, while the guard locks only a source launch that is not installed.

`ros_gz_sim`, `ros_gz_bridge`, and `ros_gz_interfaces` resolve to `/opt/ros/jazzy`; `ros2 pkg executables ros_gz_sim` lists `create`. The direct executable also exists at the locked absolute path. Availability of those packages does not repair the missing installed dedicated launch.

## D. Environment matrix

| Shell audit | `PKG_CONFIG_PATH` | Gazebo pkg-config result | OpenSSL result | Status |
| --- | --- | --- | --- | --- |
| Current shell | empty | `gz-transport13` and `gz-msgs10` unresolved | version `3.0.13`; flags `-lssl -lcrypto` | `BLOCKED` |
| `/opt/ros/jazzy/setup.bash` | empty | same unresolved packages | pass | `BLOCKED` |
| Jazzy plus workspace `install/setup.bash` | empty | same unresolved packages | pass | `BLOCKED` |

The top-level `.pc` files are installed as separate regular files:

```text
/opt/ros/jazzy/opt/gz_transport_vendor/lib/pkgconfig/gz-transport13.pc
/opt/ros/jazzy/opt/gz_msgs_vendor/lib/pkgconfig/gz-msgs10.pc
```

The required transitive `.pc` files are also separately installed:

```text
/opt/ros/jazzy/opt/gz_cmake_vendor/lib/pkgconfig/gz-cmake3.pc
/opt/ros/jazzy/opt/gz_utils_vendor/lib/pkgconfig/gz-utils2.pc
/opt/ros/jazzy/opt/gz_math_vendor/lib/pkgconfig/gz-math7.pc
```

No audited setup shell provides a `PKG_CONFIG_PATH` containing the top-level and transitive vendor directories. Therefore none is an environment that passes the supervisor's current `/usr/bin/pkg-config` prerequisite.

## E. Exact helper compile readiness

`RuntimeDependencyFactory.compile_helper()` invokes `/usr/bin/pkg-config --cflags --libs gz-transport13 gz-msgs10` before assembling the `/usr/bin/g++` argv. Because no audited setup shell passes that prerequisite, no exact helper compile was performed in this audit. This avoids claiming a compile readiness result without a passing environment.

The earlier offline reproduction recorded the exact prerequisite failure in `artifacts/simulation/contact_producer_evidence/repair_validation/S3_D3_Prepare_Compiler_Diagnostic_Report.md`.

## F. Static execution-path audit

The CLI compares `--guard-path` as a `Path` to an absolute expected path, so an execution command must pass the absolute guard path.

The actual source order is:

```text
prepare helper
→ build trusted context
→ acquire guard
→ launch bootstrap
→ one direct create phase
→ post-create delay inside create phase
→ helper once
→ persist artifact
→ SIGINT-only cleanup
→ consume guard
```

`prepare()` runs before acquisition. `compile_helper()` uses `shell=False`, `/usr/bin/pkg-config`, `/usr/bin/g++`, a temporary directory, and no helper execution. The current source returns `INVALID_PREPARE` for only listed caught exception classes; the main CLI maps ordinary returned `INVALID_PREPARE` to exit code zero because only `GUARD_CONSUMPTION_INCOMPLETE` and `SHUTDOWN_INCOMPLETE` map to nonzero. A `subprocess.CalledProcessError` from the pkg-config command is not in that catch list. Thus pre-acquisition failure reporting is not uniformly typed or reliably nonzero.

The dedicated source launch static checker passed. Its allowed source graph is resource path setup, Gazebo include, and a robot-description provider; it contains no bridge, `/cmd_vel`, pose/reset/world-control, raw-contact collector, or launch-owned create. The supervisor owns the only future create. Artifact creation begins in `RuntimeDependencyFactory._ensure_artifact_directory()` when bootstrap launch begins; a prepare failure has no durable run artifact.

## G. Runtime-only unknowns

The following remain `UNKNOWN_RUNTIME_ONLY`: Gazebo startup; installed package launch behavior after a repaired install artifact exists; robot spawn acceptance; Scene service advertisement; the exact Scene hierarchy `ROBOT_URDF_final → base_link → s3_d3_base_contact_sensor`; and all contact data. None is inferred from this audit.

## H. Gate summary

| Gate | Evidence | Status |
| --- | --- | --- |
| Guard structure and pending run fields | Read-only JSON record: authorized, capacity one, null run fields | `CONFIRMED` |
| Packet binding | Actual packet SHA equals guard SHA | `CONFIRMED` |
| Locked supervisor/C++ helper/source launch/world/create files | Existing non-symlink files and matching SHA-256 | `CONFIRMED` |
| Supervisor import identity | Supervisor imports `typed_scene_final_run_guard.py`; record locks a different helper path/SHA | `DRIFT` |
| Installed dedicated launch | Install/share omits `typed_scene_observer.launch.py` | `DRIFT` |
| ROS Gazebo packages and direct create executable | `ros_gz_*` prefixes and `ros_gz_sim create` are available | `CONFIRMED` |
| Current shell pkg-config | Gazebo packages unresolved | `BLOCKED` |
| Jazzy setup pkg-config | Gazebo packages unresolved | `BLOCKED` |
| Jazzy plus workspace setup pkg-config | Gazebo packages unresolved | `BLOCKED` |
| Exact helper compile | No audited environment passes required pkg-config prerequisite | `BLOCKED` |
| Runtime Gazebo/Scene/spawn evidence | Prohibited from this audit | `UNKNOWN_RUNTIME_ONLY` |

## Conclusion

`NOT_READY`

Blockers in execution order:

1. **Guard-helper import drift.** Evidence: the supervisor's actual import is `artifacts/simulation/contact_producer_evidence/tools/typed_scene_final_run_guard.py`, while the guard locks `typed_scene_replacement_approval_guard.py`. Smallest repair: explicitly bind the guard record to the helper that the supervisor actually imports, then revalidate the complete trusted context.
2. **Helper build environment unavailable.** Evidence: `PKG_CONFIG_PATH` is empty in all three audited shells, and `/usr/bin/pkg-config` cannot resolve `gz-transport13` or `gz-msgs10`. Smallest repair: establish a validated, version-matched pkg-config environment for the top-level and transitive Gazebo vendor `.pc` files in the isolated helper-build subprocess environment.
3. **Fatal installed-launch drift.** Evidence: `ros2 launch` resolves the package from `ros2_ws/install/ROBOT_URDF_final_description`, where `typed_scene_observer.launch.py` is absent. Smallest repair: make the dedicated launch an installed package artifact, then bind a guard to the installed launch identity rather than only its source identity.

No execution command is provided because the required gates are blocked or drifted.
