# WP06-6F TF/EKF runtime state-estimation ingress — L2 decision

## Authority and bounded status

- Work item: `WP06-6F_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_WITH_CLOCK`.
- Classification: `L2_PROFILE_SPECIFIC_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS`.
- Integration base: `8b73bcb0b026fe337c023f6a30205dbe89d31eb5`.
- Architecture SHA-256: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Current evidence ceiling: `IMPLEMENTED_OFFLINE_CROSS_LANGUAGE_JSON_SEMANTIC_VALIDATION_RUN004_GUARD_PENDING`.

This corrective candidate changes the runtime evidence contract only at the observer JSON reader boundary. It accepts strict, valid JSON based on parsed semantics and the existing fail-closed schema validator. It does not claim cross-language canonical JSON bytes or JCS conformance. Raw observer JSON remains integrity-protected by SHA-256 in the runtime artifact manifest and checksum list. No C++ observer, TF/EKF/clock contract, bridge mapping, or sensor semantics are changed.

`runtime_eligible: false`; runtime evidence status is `NOT_CREATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. Run004 is a newly seeded capacity-one guard only and is not authorized or executed by this candidate.

## Locked topology and contracts

The existing WP06-6C bootstrap runs the sole `robot_state_publisher` with simulation time and owns static `base_link -> lidar_frame`. The WP06-6F composite starts only the existing wheel/IMU ingress, a dedicated Gazebo-to-ROS `/clock` bridge, and one `robot_localization/ekf_node`; it starts neither bootstrap nor a second RSP. The only new bridge mapping is `/clock` (`gz.msgs.Clock`) to `/clock` (`rosgraph_msgs/msg/Clock`), direction `GZ_TO_ROS`. No bridge route exists for `/odom`, `/ground_truth/odom`, `/tf`, `/tf_static`, `/cmd_vel`, or `/map`.

The EKF uses simulation time, `reset_on_time_jump: true`, `publish_tf: true`, `two_d_mode: true`, `world_frame: odom`, and only `/wheel/odometry_raw` plus `/imu/data`; wheel fusion is linear velocity X/Y and IMU fusion is yaw/yaw-rate. The EKF is the intended sole dynamic `odom -> base_link` owner; the bootstrap RSP is the intended sole static `base_link -> lidar_frame` owner. These are source/design constraints, not runtime findings from this candidate.

## Immutable runtime history

- Run001 remains a historical observer API failure (`rclpy` does not support the attempted `with_info=True` subscription API); it is not interpreted as a TF/EKF failure and was not retried.
- Run002 remains a historical nested-array observer execution failure (`json.exception.type_error.304`), with its guard consumed once; it does not establish TF/EKF/clock/RSP failure and was not retried.
- Run003 was executed once at review commit `3f2748dc2ef809610fe0f4ebb88aef5db24d9924`; its raw observer output is valid JSON and semantically contains observer results, but the Python reader rejected it because it compared raw C++ bytes to Python `json.dumps` output. The recorded failure is `RUN003_VALID_JSON_REJECTED_BY_CROSS_LANGUAGE_BYTE_CANONICALITY_CHECK` and `NOT_A_TF_EKF_CLOCK_OR_ROBOT_FAILURE`. Run003 guard was consumed; its raw evidence and records remain unchanged and the run was not retried.

## Corrective contract

`load_observer_json()` requires valid UTF-8, no BOM, duplicate-key rejection, rejection of non-standard constants, a top-level object, and complete `validate_observer_document()` semantic checks. It does not require raw bytes to equal Python serialization. Schema, topic/type, row shape, QoS, monotonic sample counts, TF GID ownership, static transform/owner, `map -> odom` absence, observer errors, and recomputed acceptance remain fail-closed. Any future cross-language canonical byte/signature requirement is a separate work item requiring full JCS, not `json.dumps` as a substitute.

Run004 guard seed is `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity `1`, acquisition count `0`, `runtime_authorization=NOT_GRANTED`. It is pending and unconsumed. No runtime authorization is granted.

## Current status

`RUN004_SEMANTIC_VALIDATION_GUARD_PENDING`. Evidence ceiling is `IMPLEMENTED_OFFLINE_CROSS_LANGUAGE_JSON_SEMANTIC_VALIDATION_RUN004_GUARD_PENDING`; runtime evidence remains `NOT_CREATED`; `runtime_eligible: false`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. This candidate is source/governance/offline-test/build evidence only and does not establish runtime behavior.
