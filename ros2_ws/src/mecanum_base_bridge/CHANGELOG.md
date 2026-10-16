# Changelog

## 0.2.0

- Adds the bounded `sim_eval` wheel-odometry emulator and `base_link` IMU ingress source, with offline validation and tests.
- This simulation-only ingress is not a `deploy_real` implementation and does not constitute runtime approval, runtime evidence, Gate B evidence, or a ROS–Gazebo bridge implementation. Candidate 6E remains the sole owner of that bridge implementation.
- The historical static ingress contract v1 remains unchanged; this package addition does not resolve its pending source-binding status.
