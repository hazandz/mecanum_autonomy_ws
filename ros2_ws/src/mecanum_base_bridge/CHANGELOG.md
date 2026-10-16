# Changelog

## Unreleased

- Add a bounded, simulation-only wheel odometry emulator and IMU normalizer
  for `sim_eval`, plus the ROS ingress node and its source-binding contract.
- Wheel odometry is derived only from staging `JointState` wheel velocities;
  malformed intervals are barriers and never produce fabricated odometry.
- The node forces and verifies `use_sim_time: true` before creating endpoints.
- This source is not a Gazebo bridge implementation, runtime evidence,
  runtime approval, or deployment implementation. WP06-6E remains the sole
  owner of ROS–Gazebo bridge implementation.
