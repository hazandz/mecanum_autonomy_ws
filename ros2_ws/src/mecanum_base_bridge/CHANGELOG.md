# Changelog — mecanum_base_bridge

## Unreleased

- U4 bổ sung session engine Pi thuần, generator hash RFC8785 cho manifest và
  kiểm thử offline; chưa có node ROS, telemetry runtime, HIL hoặc motor.
- Adds a bounded, single-owner pyserial byte transport with explicit port
  selection and caller-controlled reconnect attempts.
- Adds fake-backend offline transport tests to the package test runner.
- Records offline U2 scope only; no ROS/session, STM32, HIL, motor-enable, or
  deployment behavior is provided by this change.

## 0.3.0

- Adds an offline-only, profile-specific GZ-to-ROS wheel/IMU bridge and ingress launch.
- Runtime compatibility is not validated; `runtime_eligible: false`; no runtime evidence or approval is created.
- No Gazebo `/odom` or `/ground_truth/odom` mapping, TF bridge, EKF, Nav2, AMCL, or command publisher is launched by this package entry point; wheel-derived `/wheel/odometry_raw` remains the ingress output.


## 0.2.0

- Adds the L2 simulation-only `sim_eval` wheel/IMU ingress source and static source binding.
- This source is not a `deploy_real` implementation and does not imply runtime approval. The ROS–Gazebo bridge remains owned by WP06-6E and is not implemented here.
- Runtime graph, runtime evidence, Gate B transition and runtime authorization are not claimed.
