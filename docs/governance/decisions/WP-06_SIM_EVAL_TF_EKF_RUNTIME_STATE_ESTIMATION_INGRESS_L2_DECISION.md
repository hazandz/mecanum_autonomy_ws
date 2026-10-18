# WP06-6F TF/EKF runtime state-estimation ingress — L2 decision

## Classification and authority

- Work item: `WP06-6F_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_WITH_CLOCK`.
- Classification: `L2_PROFILE_SPECIFIC_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS`.
- Exact base: `8b73bcb0b026fe337c023f6a30205dbe89d31eb5`.
- Architecture authority: `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Evidence ceiling: `IMPLEMENTED_OFFLINE_CPP_GID_OBSERVER_AND_PENDING_RUN002_GUARD_ONLY`.

This is source, governance, offline-test and build work only. It creates no runtime evidence or authorization, resolved profile, `ResolvedConfigV3`, `config_hash`, endpoint pin, Gate B transition or runtime approval. `runtime_eligible: false`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`.

## Selected topology and locked contracts

The future runtime starts the existing WP06-6C bootstrap separately and once. That bootstrap remains the owner of the only `robot_state_publisher`, with `use_sim_time=true`, and the static `base_link -> lidar_frame` edge from the robot Xacro. The WP06-6F composite launch starts only existing WP06-6C wheel/IMU ingress, one dedicated `/clock` bridge, and one `robot_localization/ekf_node`; it does not start bootstrap or another robot-state publisher.

The clock bridge has one `GZ_TO_ROS` mapping: Gazebo `/clock` (`gz.msgs.Clock`) to ROS `/clock` (`rosgraph_msgs/msg/Clock`). It is independent of legacy `gazebo.launch.py`. No bridge is defined for `/odom`, `/ground_truth/odom`, `/tf`, `/tf_static`, `/cmd_vel`, or `/map`.

The EKF retains `use_sim_time: true`, `reset_on_time_jump: true`, `publish_tf: true`, `two_d_mode: true`, `world_frame: odom`, and inputs `/wheel/odometry_raw` and `/imu/data`. Wheel fusion remains linear velocity X/Y only; IMU fusion remains yaw and yaw angular velocity only. No absolute Gazebo pose or new covariance tuning is introduced. The EKF is the intended sole dynamic owner of `odom -> base_link`; the bootstrap RSP retains sole static ownership of `base_link -> lidar_frame` using translation `[-0.031765, 0, 0.140]` and identity rotation. `map -> odom` is outside scope.

## Run 001 historical disposition and observer correction

Run 001 is an immutable historical failure caused by the observer API mismatch: Python `rclpy` in the target Jazzy environment does not accept `create_subscription(..., with_info=True)`. This is an observer execution failure; it is not evidence of a TF or EKF runtime failure. No Run 001 guard, lock, record, manifest, raw evidence or artifact is changed, and Run 001 is not retried.

The replacement observer is a dedicated `ament_cmake` C++ executable using `rclcpp::MessageInfo` and underlying RMW publisher GID. It snapshots `/tf` graph endpoints and accepts dynamic edge ownership only when the exact GID maps uniquely to the configured EKF endpoint. An unmappable GID fails closed as `TF_EDGE_PUBLISHER_GID_UNMAPPABLE`; no node-name fallback or global `/tf` publisher count is used. It records canonical schema-versioned JSON atomically, including multi-sample `/clock`, filtered odometry, edge-specific TF, static TF with RELIABLE/TRANSIENT_LOCAL QoS, endpoint mappings, map-to-odom observation, per-condition verdicts, and literal reasons. Python is now only an offline canonical-JSON parser/validator; no Python `with_info=` use remains under `ros2_ws/src`.

Teardown accounting has one predicate: `leader_returncode == 0 AND live_member_pids == [] AND zombie_member_pids == [] AND outcome == STOPPED`. Any recorded aggregate inconsistent with that predicate is `INTERNAL_EVIDENCE_INCONSISTENCY`.

## Run 002 guard and future runtime boundary

Run 002 has a separate capacity-one guard seeded `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity `1`, acquisition count `0`, and `runtime_authorization: NOT_GRANTED`. It has not been acquired or authorized. The future runner must complete static identity/source-pin and host-capability/import checks before acquiring that guard, call bootstrap and composite at most once, invoke the C++ observer exactly once, save its JSON output via the observer's atomic write, and tear down composite before bootstrap. Any post-acquisition failure consumes the guard and ends without retry. No runtime was executed as part of this corrective candidate.

## Evidence ceiling

`IMPLEMENTED_OFFLINE_CPP_GID_OBSERVER_AND_PENDING_RUN002_GUARD_ONLY`. The Run 002 runtime remains unauthorized and unexecuted; independent audit and a separate exact-run Owner authorization are required before any runtime.

## Corrective continuation — dynamic TF subscriber QoS

The dynamic `/tf` observer subscription uses explicit `KEEP_LAST(100)`, `BEST_EFFORT`, `VOLATILE` QoS to match the standard dynamic TF publisher contract. `/tf_static` remains `KEEP_LAST(1)`, `RELIABLE`, `TRANSIENT_LOCAL`. Observer schema v3 records both actual subscription profiles, graph publisher endpoint snapshots for `/tf` and `/tf_static`, and static-edge publisher GID mapping. The offline validator rejects QoS mismatches and requires the static `base_link -> lidar_frame` MessageInfo GID to map uniquely to the exact root-namespace `robot_state_publisher` TFMessage endpoint; there is no node-name fallback.

Current source pins:
- `ros2_ws/src/wp06_6f_tf_ekf_runtime_observer/src/wp06_6f_tf_ekf_runtime_observer.cpp` — `1efd9d91479984d59726a63d8146302d1429841617393fdbe12ad27ce3a8b4ee`
- `ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_tf_ekf_runtime_observer.py` — `41c2c8cfa705ef05a80cfe5bad3cfffb8478e03694458b458bbd1f4a1bd1b585`

This is an offline source/test/build correction only. Run 001 remains the immutable observer API mismatch failure and is not a TF/EKF failure. Run 002 remains unauthorized and pending with capacity 1 and acquisition count 0. No runtime authorization, runtime evidence, integration, or Gate B transition is created.


## WP06-6F static TF publisher ownership correction — current review delta

The observer now snapshots publisher endpoints for both `/tf` and `/tf_static`. It takes the static edge GID from `rclcpp::MessageInfo` and accepts `base_link -> lidar_frame` ownership only when that GID maps exactly once to `node_name=robot_state_publisher`, `node_namespace=/`, and `topic_type=tf2_msgs/msg/TFMessage`. Unmappable, non-unique, and wrong-owner mappings have distinct fail-closed literals; matching transform values alone cannot pass the owner criterion. Observer schema v3 records the endpoint snapshots, mapping, separate owner acceptance, and the QoS actually used. Dynamic `/tf` remains KEEP_LAST(100)/BEST_EFFORT/VOLATILE; `/tf_static` remains KEEP_LAST(1)/RELIABLE/TRANSIENT_LOCAL.

This candidate changes only observer validation/diagnostics and its governance pins. Run 001 remains the immutable observer API mismatch failure; Run 002 remains PENDING, capacity 1, acquisition count 0, `runtime_authorization: NOT_GRANTED`. No ROS/Gazebo/runtime was run and no authorization was issued. Evidence ceiling remains offline source/test/build only; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`.


## WP06-6F Run 002 JSON-container failure and Run 003 offline correction

Run 002 is classified as a historical observer execution failure. The C++ observer initialized five JSON collection members with brace-init (`Json member_{Json::array()}`), producing nested arrays rather than empty arrays. Reading a TF row then failed at `edge.at("publisher_gid")` with `json.exception.type_error.304`. This does not establish a TF, EKF, clock, or robot-state-publisher runtime failure. Run 002 runtime evidence and external artifacts remain unchanged; no retry is performed.

The corrective source initializes all five collections as actual empty arrays and validates dynamic TF rows as objects before GID access. Regression coverage checks each empty collection, a valid TF object through GID extraction, and absence of nested-array rows in the collection document. The offline Python validator rejects malformed collection shape using structured `OBSERVER_COLLECTION_NOT_ARRAY` / `OBSERVER_COLLECTION_ROW_NOT_OBJECT` literals and does not leak `AttributeError`.

A distinct Run 003 runner, guard module, synthetic session test, pending capacity-one guard and guard manifest are introduced. Run 003 is `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization: NOT_GRANTED`. It has not been authorized or consumed. Run 002 guard, manifest, runtime record, lock and raw external evidence are preserved byte-for-byte. Evidence ceiling remains offline source/test/build only; `runtime_eligible: false`, runtime evidence `NOT_CREATED`, `RUNTIME_APPROVED: NOT_APPROVED`, `GATE_B: NOT_STARTED`.


### Run 003 corrective source-pin snapshot

- `artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_wp06_6f_tf_ekf_run003_session.py` — `8a09146e744fa1fdab22a7ec4f016fd5a57e3d392acb897957f433dde21d9cfb`
- `artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/test_wp06_6f_tf_ekf_run003_session.py` — `528df24c81370718cc516e79af91d5d2a931276ce557e7b7bc5c0381dae84ef5`
- `artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/wp06_6f_tf_ekf_run003_runtime_guard.py` — `4611b250c89269c5a186eedeb4ad7a5aecfc94e3952fe1307c759605e8d6348e`
- `docs/MECANUM_NAV_DRL_Architecture.docx` — `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`
- `docs/governance/evidence/WP-05_SIM_EVAL_NAV2_BASELINE_STATIC_PROFILE_MANIFEST.json` — `9cb0e74ba87db917f31b56fd87a12e9af200824211a8077de9eac96434e4c62e`
- `ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_bootstrap.launch.py` — `64a5f2f0e6435e56004fe050d8d5e70bfb06d33a98fdbf01a6599f129ae82ac0`
- `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo` — `7bbaa475578600d8e18e437fa83720483b90b4af2bf4212151257152429576a2`
- `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro` — `d80f46f3b5f273257072d800b9ba0b34c763128bfeefc32959363babf106cc0d`
- `ros2_ws/src/mecanum_base_bridge/config/bridge/sim_eval_wheel_imu_ingress.runtime.yaml` — `2dafb19da5daeeb91c451ae57055caa389a0353900525fb9a5861e1c670c6547`
- `ros2_ws/src/mecanum_base_bridge/launch/sim_eval_wheel_imu_ingress.launch.py` — `1612ce773eb0b7cb05e4d081eee441418dea32314c3685adcdcd96dd569069b8`
- `ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_clock.runtime.yaml` — `89220ef78125348776575b1a14fa1727c9cb098d9c46d84a74e27e5e8715f0b1`
- `ros2_ws/src/mecanum_nav_bringup/config/profiles/sim_eval_nav2_baseline.static.yaml` — `4b1953e9ff161f610ba6eaeb97dccc9a8a7eba90a1a73ddf4addbb7f6d418d93`
- `ros2_ws/src/mecanum_nav_bringup/config/state_estimation/ekf_sim.yaml` — `6aaacd93181eb3cbfc1bd25067ebdc441bad40998ccb486fea1c51f3ffe8a755`
- `ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_tf_ekf_state_estimation.launch.py` — `a5b69d8ba721d63b0417dc93f877b68446bd764f824b3f0fefd574bfa367746f`
- `ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_static_profile_contract.py` — `8830f9428e638bb7bb0f00eaa8f29c631dc5dcf68f8a0bc7bc1ccda8b808cb2e`
- `ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_tf_ekf_runtime_contract.py` — `29da105b2218795c74d52fbf88418ff1df43d25ced1c575aa413b09f06f4322d`
- `ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_tf_ekf_runtime_observer.py` — `163e02eb8db27a8e9f355c6f343d30a6291b37289f2bdc3e486bab85922d7c9e`
- `ros2_ws/src/mecanum_nav_bringup/package.xml` — `c9a39f14de0e98fbb4749fdafa11150029f66f88d08d698030ecea84f8040187`
- `ros2_ws/src/mecanum_nav_bringup/setup.py` — `197aedcc12800ad57bd772aeb27082422ccb6025f444ab4518220c28aa297a22`
- `ros2_ws/src/mecanum_nav_bringup/test/test_dependency_lock_schema.py` — `1509d369dcd0f2cbe925060da607dc708733a294d6827b4e1f502d07ad8cc3ed`
- `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_scan_endpoint_probe.py` — `774956f0956541f1bf9bf6286f2398ae2648bbdf8560c5775267fce3b4362fa3`
- `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_static_profile_contract.py` — `0521864d7646713d44c9e0d6cbae29d1f09b4faa4fb344a0ab6c61ddfd48493b`
- `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` — `de40be3038ab42c8277c38b4c99e0df0863e4c4c7e52a6bd2bb44e3883b29736`
- `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_observer.py` — `a06b0a1a911aad69044166474a9ce06dec749fcd08776dc4b1ae2ea4b95fe4ce`
- `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_state_estimation_launch.py` — `0b9fc862ad6911411254c25f707cbaf488891609d959097e864e65367131b022`
- `ros2_ws/src/wp06_6f_tf_ekf_runtime_observer/CMakeLists.txt` — `900691f0cee9eb5fa4fb8ec6940f3cafae316f4aa5a2ff7f254fa76da5b3aed6`
- `ros2_ws/src/wp06_6f_tf_ekf_runtime_observer/package.xml` — `775abee8afce31c94b17ce13f0d63f5bd19f06b199ee645e5c2992fa404a21b4`
- `ros2_ws/src/wp06_6f_tf_ekf_runtime_observer/src/wp06_6f_tf_ekf_runtime_observer.cpp` — `70c74e56988ce750aa9c808e929d68df06a04f7a6d8bfeb175c74e40c2b014b7`
- `ros2_ws/src/wp06_6f_tf_ekf_runtime_observer/test/test_wp06_6f_tf_ekf_runtime_observer.cpp` — `b850e4fb03351568cda0d3466c8e0915df6f088877b2a810a4e5433647c855f0`
