# Mecanum Autonomy Workspace Instructions

## Authoritative sources

The only authoritative project documents are:

1. `docs/MECANUM_NAV_DRL_Architecture.docx`
2. `docs/MECANUM_NAV_DRL_Project_Tree.txt`

When existing code conflicts with these documents, the documents win.

Do not use V2.x documents, old drafts, prototype behavior, or generated build
artifacts as authority.

Before changing architecture-sensitive code, read both authoritative documents.

## Project status

The architecture is:

- `ARCHITECTURE_FROZEN`
- `IMPLEMENTATION_READY`
- `NOT_YET_REAL_ROBOT_VALIDATED`

Gate 3 and Gate 4 have not passed. Real-robot values marked `TBD_MEASURED`
must not be guessed or copied from simulation.

The current implementation stage is Phase 0 in progress. Core/config code
exists, but the v2.4.0 interface package, Pi-STM32 contract, base bridge,
bringup package, validators, tests, and safety runtime are incomplete.

## Architecture change restrictions

Do not change any of the following without explicit user approval:

- package ownership or dependency direction
- topic names, message types, publishers, or subscribers
- QoS profiles
- TF frames, TF edges, or TF authority
- custom message fields or constants
- observation, action, reward, or termination contracts
- command arbitration or SafetySupervisor behavior
- collision, stopping-distance, watchdog, or E-stop contracts
- Raspberry Pi–STM32 communication contract
- wheel order, signs, encoder, geometry, or hardware configuration contract
- map artifact identity or approval rules
- navigation modes or runtime profile matrix

If a requested change affects one of these contracts, stop and explain the
impact before editing. Ask for approval and require an Architecture Change
Record/version update when the official architecture requires one.

## Locked system contracts

- Main TF tree: `map -> odom -> base_link -> lidar_frame`.
- Ground truth is only for TrainingTaskOracle/evaluator. It must not enter
  policy observation or the primary TF tree.
- In `deploy_real`, `mecanum_base_bridge` creates `/wheel/odometry_raw` from
  STM32 telemetry.
- In simulation, a simulation adapter may create equivalent raw wheel
  odometry on `/wheel/odometry_raw`.
- Only EKF may publish the `odom -> base_link` TF edge.
- SLAM Toolbox owns `map -> odom` only in MAPPING.
- AMCL Omni owns `map -> odom` in NAV2_BASELINE and HYBRID_AI_LOCAL.
- Nav2 Planner Server runs in NAV2_BASELINE and HYBRID_AI_LOCAL.
- Nav2 Controller Server runs only in NAV2_BASELINE.
- In HYBRID_AI_LOCAL, Nav2 Planner Server creates the global path and PPO is
  the local controller. Nav2 Controller Server and FollowPath do not run.
- PPO is the local controller in LOCAL_TRAINING and HYBRID_AI_LOCAL.
- SafetySupervisor is the only final command selector and limiter.
- FinalTwistPublisher is the only publisher allowed on `/cmd_vel`.
- Physical E-stop must remain independent of Linux, ROS 2, DDS, and Python.
- Observation is 81 `float32` values: 72 angular LiDAR sectors, goal
  distance/sin/cos, measured vx/vy/wz, and previous issued vx/vy/wz.
- Action is normalized `float32` `[vx, vy, wz]` in `[-1, 1]`.
- Robot-real motion and stopping limits remain `TBD_MEASURED`.

## Package ownership

- `ROBOT_URDF_final_description`: robot description, Xacro/URDF, meshes,
  Gazebo model/world, and static geometry.
- `mecanum_nav_rl_interfaces`: Heartbeat, SafetyState, NavigationState, and
  CommandEnvelope.
- `mecanum_base_bridge`: Pi-STM32 transport, telemetry, real-robot wheel
  odometry, and final command transport; it does not publish TF.
- `mecanum_nav_rl`: pure core, DRL, Gym environment, hybrid navigation,
  simulation adapters, training, evaluation, deployment adapters, validators,
  and safety logic.
- `mecanum_nav_bringup`: system launch and EKF, SLAM, AMCL, Nav2, safety, and
  mode configuration.

Do not place DRL/training code in the robot-description package. Do not place
system bringup configuration in a component package.

## Working method

Before creating or editing a file:

1. Explain what the file is responsible for.
2. Explain what data it receives.
3. Explain what data it emits or returns.
4. Explain which node, process, launch file, or module runs with it.
5. Identify the authoritative architecture section and existing dependencies.
6. Ask before proceeding if the change touches a locked contract.

Work incrementally. Do not create all planned empty files at once. Create a
file only when beginning its module.

Prefer pure Python modules for domain logic. Pure core code must not import
`rclpy`, Gazebo, Gymnasium, or Stable-Baselines3.

Do not silently preserve prototype behavior when it conflicts with the
authoritative architecture. Report the conflict and migrate deliberately.

## Phase 0 Gazebo restriction

Do not conclude that the existing Gazebo VelocityControl and MecanumDrive
plugins sharing a configured `/cmd_vel` name is itself an error until their
actual plugin behavior, Gazebo transport topics, ROS bridge directions, and
runtime topic graph have been verified.

Do not modify the URDF, Gazebo plugin configuration, or related Gazebo launch
behavior during Phase 0. Record observations and defer any proposed change
until the relevant runtime behavior has been measured and the user has
approved the architecture-sensitive change.

## Safety and data rules

- Fail safe on missing, stale, invalid, wrong-frame, wrong-generation, or
  wrong-epoch runtime inputs.
- Infrastructure failures do not become fabricated RL transitions or task
  penalties.
- Do not use simulation limits as real-robot limits.
- Do not enable `deploy_real` before all required measurements, approved
  map/model artifacts, HIL evidence, and Gate 4 approval exist.
- Maps belong under `artifacts/maps/<map_id>` with canonical manifests and
  approval metadata, not as mutable copies inside ROS package source.
- Hardware geometry belongs in
  `artifacts/hardware/<hardware_profile_id>/hardware_manifest.yaml`.
- Generated bridge and firmware geometry must be verified using the same
  `hardware_config_hash`.

## Repository hygiene

- Preserve unrelated user changes in a dirty worktree.
- Do not edit generated `build/`, `install/`, `log/`, `__pycache__/`, model,
  checkpoint, dataset, or report output.
- Before editing, inspect `git status`.
- Use `rg` or `rg --files` for searches.
- Run focused tests first, then package tests, then workspace checks when the
  implementation stage permits.
- Never claim a package or gate has passed without corresponding test evidence.

## Current known gaps — update after each verified milestone

After each completed and tested milestone, update this section to reflect the
verified project state before relying on it for subsequent work.

- `mecanum_nav_rl_interfaces` has only Heartbeat and SafetyState and is still
  version 2.3.0.
- `mecanum_base_bridge` does not exist.
- `mecanum_nav_bringup` does not exist.
- Most `mecanum_nav_rl` runtime, navigation, environment, training,
  evaluation, deployment, safety, validator, and test directories are empty.
- Legacy `mecanum_env.py` and `train_ai.py` are in the robot-description
  package and do not define the official contract.
- Existing Nav2, odometry, collision, map, command, observation, reward,
  failure, and safety behavior must be reconciled with the official
  architecture before reuse.
