# Controlled Coordinate Reset Measurement Artifact

This directory contains evidence for exactly one user-approved Gazebo
simulation-only controlled coordinate measurement. The collector is outside all
production packages. It creates subscriptions for `/clock`,
`/ground_truth/odom`, `/odom`, `/scan`, and `/tf`, and exactly one
`ros_gz_interfaces/srv/SetEntityPose` client.

Allowed target and call sequence: `ROBOT_URDF_final`, `P0 → P1 → P2` only.
The collector creates no publisher, including no `/cmd_vel` publisher; no
world-control, reset, pause, step, spawn, delete, teleop, Nav2, PPO/Gymnasium,
or hardware operation is implemented.

The resulting evidence is not a scenario, reset, TF, collision, task-oracle,
Gym, reward, termination, or runtime approval.
