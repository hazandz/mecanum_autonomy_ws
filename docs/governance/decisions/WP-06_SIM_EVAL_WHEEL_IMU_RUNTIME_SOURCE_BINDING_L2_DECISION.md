# WP06 sim_eval wheel/IMU runtime ingress — replacement candidate decision

## Classification and lifecycle

- Decision class: `L2_SIM_EVAL_WHEEL_IMU_RUNTIME_SOURCE_BINDING_IMPLEMENTATION_CORRECTION`.
- Candidate class: `SIM_EVAL_WHEEL_IMU_RUNTIME_INGRESS_ROSIDL_SEQUENCE_CORRECTED`.
- Exact source base: `43c94789f628b4211189fc391326e0b119cbb6d3`.
- Review branch: `wp06-sim-eval-wheel-imu-ingress-rosidl-sequence-fix-43c9478`.
- This is a fresh replacement constructed from the exact integration base. Rejected commits `38d52b19b8cacecbe49961f77df47eaacfd8c3c4` and `3f40b6dcf34e07f9f9df33889df2c9379163d3fd` are historical references only; neither is an ancestor or source of this candidate.
- Evidence level: `IMPLEMENTED_OFFLINE_BUILD_AND_TEST_ONLY`; this is not runtime evidence.
- Candidate lifecycle: review candidate only, pending independent audit and separate exact-candidate User authorization.

## Scope and preserved ownership

This candidate records the bounded sim_eval wheel/IMU ingress source: model-level IMU source, wheel encoder odometry core, IMU normalizer, one ROS ingress node, static binding, package registration, tests and governance records. The Wheel staging input is `/sim_eval/wheel_joint_states` (`sensor_msgs/msg/JointState`) and canonical output is `/wheel/odometry_raw` (`nav_msgs/msg/Odometry`). The IMU staging input is `/sim_eval/imu_raw` (`sensor_msgs/msg/Imu`) and canonical output is `/imu/data` (`sensor_msgs/msg/Imu`). The source publishes no TF. `/odom` and `/ground_truth/odom` are not accepted inputs.

The Gazebo IMU is attached to `base_link`, named `sim_eval_base_imu`, emits `/sim_eval/imu/raw` at the declared 50.0 Hz, and does not create a frame or TF. Wheel integration uses the approved logical wheel order, joint names, mecanum equations, geometry, covariance and a 0.20 s maximum accepted source gap. The package default is sim time, and the node applies `set_parameters_atomically(Parameter("use_sim_time", value=True))`, verifies both success and the effective value, and does so before creating any publisher or subscription.

WP06-6E remains the sole owner of ROS–Gazebo bridge implementation. No bridge implementation or bridge launch is included here. Runtime eligibility remains false pending WP06-6E and runtime evidence. Existing static ingress v1 and Step 5A profile closure are historical inputs and are not modified.

## Corrections

- **F-01 — invalid interval barrier retained.** Malformed, duplicate, or over-gap wheel samples clear only the interval timestamp and preserve the last trusted pose. The next valid sample establishes a baseline and produces no output; only the following valid adjacent sample can integrate. A backward timestamp resets pose and baseline. Kinematics and integration are computed in local values and state is committed only after finite-result validation.
- **F-02 — effective sim-time contract retained.** The node atomically sets `use_sim_time=true`, checks `result.successful`, checks the effective parameter is exactly `True`, and raises `RuntimeError` before endpoint creation if either check fails. Conditional `has_parameter`/`declare_parameter` logic is not used.
- **F-03 — ROSIDL numeric sequence acceptance corrected.** The wheel emulator accepts indexed `collections.abc.Sequence` inputs, including `array.array('d')`, while rejecting strings, bytes, bytearrays, generators/iterators, malformed lengths and invalid wheel values. It does not coerce inputs to a list before validation. Earlier tests used list fixtures and did not establish acceptance of the ROSIDL numeric sequence representation.

## Non-goals and retained statuses

This candidate does not create a TF publisher, bridge, runtime graph, launch execution, `/cmd_vel` publisher, runtime evidence, profile resolution, `ResolvedConfigV3`, `config_hash`, Gate B transition or runtime authorization. No Gazebo, ROS graph/node, launch, Nav2, AMCL, EKF runtime, Map Server, HIL, hardware or deployment execution is claimed. `RUNTIME_APPROVED: NOT_APPROVED`; WP-04/WP-05 and Gate A/Gate B statuses are unchanged. Future post-integration status wording may say `IMPLEMENTED_OFFLINE_ONLY` only after independent audit PASS, explicit User authorization, integration and remote-ref verification.
