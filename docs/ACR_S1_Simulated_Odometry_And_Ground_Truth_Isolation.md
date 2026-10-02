# ACR S1 Simulated Odometry And Ground Truth Isolation

Status: APPROVED

Authority: This record updates and is referenced by `MECANUM_NAV_DRL_Architecture.docx`. It does not change the Raspberry Pi–STM32 contract, real-robot hardware contract, ROS public interfaces, or any runtime implementation.

## Context

The legacy Gazebo model publishes `/ground_truth/odom` from Gazebo model state and `/odom` from `MecanumDrive`. `VelocityControl` is the intended model-motion actuator of that legacy simulation. `MecanumDrive` also turns wheel joints and publishes its legacy odometry path, but that path can diverge from model motion under wheel spin, contact, or slip.

The legacy environment passes ground-truth odometry into its policy observation and is not the contract for new implementation. The authoritative architecture requires noisy simulated odometry for `sim_train`, while ground truth is restricted to oracle and evaluation responsibilities.

## Decision

`sim_train` SHALL use this internal pipeline:

```text
Hidden Gazebo ground truth
  -> SimulatedOdometryEmulator
  -> noisy pose and measured-twist snapshot
  -> SnapshotSynchronizer
  -> ObservationEncoder
  -> PPO
```

The `SimulatedOdometryEmulator` is the only sensor-side `sim_train` component permitted to read hidden Gazebo ground truth for producing the pose and twist measurement presented to policy. `TrainingTaskOracle`, reset transaction/validation, reward, success/termination, and evaluator remain permitted to read ground truth for oracle purposes. No oracle component may pass raw ground truth, a ground-truth message, or an object reachable from ground truth into policy observation or policy runtime. The emulator MVP output is an internal typed snapshot; it SHALL NOT publish a public ROS `nav_msgs/msg/Odometry` topic and SHALL NOT publish TF.

The legacy `MecanumDrive` system continues to send `JointVelocityCmd` to the wheel joints and publish its legacy odometry path. It is therefore a legacy joint-actuation/odometry compatibility path, not merely wheel visualization. It is neither the intended model-motion actuator nor canonical policy odometry. Actuator reconciliation remains separate deferred work: this ACR neither disables nor legitimizes the current legacy actuator behavior.

`VelocityControl` remains the intended model-motion actuator of the legacy simulation pending the separately approved Gazebo actuator reconciliation work.

## Canonical Data Flow

| Data source | Permitted consumer | Prohibited consumer | Notes |
| --- | --- | --- | --- |
| `/ground_truth/odom` or Gazebo model/world pose | Sensor-side `SimulatedOdometryEmulator` for policy measurement only; `TrainingTaskOracle`; reset transaction/validation; reward; success/termination; evaluator for oracle purposes | PolicyNode; ObservationEncoder; policy runtime; raw policy sensor buffer | Ground truth is hidden from policy code and output; oracle components must not pass raw GT or a GT-reachable object into policy. |
| Internal noisy simulated pose/twist snapshot | SnapshotSynchronizer; ObservationEncoder; PPO policy | TrainingTaskOracle as its authoritative truth source | This is the only `sim_train` policy pose/twist input. |
| MecanumDrive `/odom` | Legacy joint-actuation/odometry compatibility path until reconciliation | Official policy odometry path | `MecanumDrive` still sends `JointVelocityCmd` to wheel joints; it is not the official noisy-odometry emulator input or output. |

Ground-truth consumers that calculate reward, success, termination, reset validation, or evaluator metrics SHALL keep those values out of the policy observation object and out of any object reachable by the policy runtime.

## Explicitly Forbidden Paths

The following are forbidden in `sim_train` policy execution:

- PolicyNode, ObservationEncoder, SnapshotSynchronizer, and policy runtime subscribing to `/ground_truth/odom`.
- Passing Gazebo world pose, model pose, a ground-truth message, or a raw ground-truth buffer/object to policy observation construction.
- Using `MecanumDrive` `/odom` as canonical policy odometry.
- Publishing a new TF edge or public ROS odometry topic as part of the MVP emulator.
- Reusing the legacy `mecanum_env.py` ground-truth observation path as the official environment contract.

## MVP Emulator Requirements

Each episode SHALL reset the emulator using the episode seed. The sampled parameter manifest SHALL be stored with the episode/run evidence so the result can be reproduced.

The MVP error model SHALL include:

- position bias and yaw bias sampled per episode;
- random-walk drift;
- velocity noise;
- a delay queue;
- dropout behavior.

Numerical distributions, bounds, update cadence, and domain-randomization schedule are simulation configuration decisions. They shall be explicit, seeded, and versioned; they are not measured real-robot values.

## Follow-on Profiles

The post-MVP target for `sim_eval` and `deploy_sim` is:

```text
wheel joint / encoder emulator
  -> simulated /wheel/odometry_raw equivalent
  -> EKF
  -> /odometry/filtered
```

The `deploy_real` target remains:

```text
STM32 cumulative encoder ticks
  -> /wheel/odometry_raw
  -> EKF
  -> /odometry/filtered
```

Only EKF is the `odom -> base_link` authority in integration and deployment profiles. The `sim_train` MVP creates no new TF authority; the profile-specific TF authority must be reconciled before adding a public simulator odometry/TF runtime.

## Rationale

The MVP separates the pose measurement presented to PPO from the true Gazebo state while retaining GT where a task oracle legitimately needs it. It works with the legacy `VelocityControl` actuator without promoting `MecanumDrive` joint-integrated odometry into an official source. The later encoder-emulator path aligns simulation evaluation with the real wheel-ticks-to-EKF pipeline.

## Consequences

- New official environment code must be built around an internal simulated-odometry boundary, not the legacy environment.
- A policy-ground-truth isolation test becomes a required contract test.
- Existing legacy `/odom` and TF remain non-canonical until Gazebo reconciliation; they must not silently become the new policy source.
- Public topic names, QoS, and any future sim-train TF authority require a separate Architecture Change Record before runtime deployment.

## Migration Status

No runtime migration has occurred. The existing legacy `mecanum_env.py` still leaks `/ground_truth/odom` into its observation path and remains outside the official contract. No `SimulatedOdometryEmulator`, policy runtime, simulator adapter, encoder emulator, EKF sim configuration, or isolation test implementation exists yet.

## Acceptance Criteria

- [ ] A unit test proves that policy observation accepts only the emulator output and never a ground-truth message/object.
- [ ] Graph/config tests prove PolicyNode and ObservationEncoder cannot subscribe to `/ground_truth/odom`.
- [ ] Reset clears emulator bias, drift, and delay queue according to the episode seed.
- [ ] Identical seed, sampled-parameter manifest, and input trace reproduce the same emulator output trace.
- [ ] `MecanumDrive` `/odom` is not declared as policy odometry in official runtime configuration.
- [ ] No runtime implementation, TF publisher, public odometry topic, or actuator change is implied or created by this ACR alone.

## Deferred Work

- Implement the internal emulator, sensor synchronization, reset transaction, and isolation tests.
- Decide and version the MVP noise distributions and domain-randomization configuration.
- Reconcile legacy `VelocityControl`, `MecanumDrive`, `/odom`, and TF ownership before modifying Gazebo runtime configuration.
- Implement the encoder emulator, simulated raw-wheel odometry, EKF sim path, and profile overlays for `sim_eval` and `deploy_sim`.
