# Changelog

All notable changes to `mecanum_nav_rl_interfaces` are documented in this file.

## [2.6.0] - Unreleased

### Added

- Added `LocalTrainingSafetyInput.msg` as a session-bound, safety-only noisy
  twist/admission contract; it contains no pose, task goal, or raw Ground Truth.
- Added `SimulationContactState.msg` as a backend status/contact-coverage
  contract. These declarations do not implement publishers, consumers,
  watchdogs, contact processing, or actuator behavior.

### Boundary

- Interface generation and offline declaration checks do not establish runtime
  behavior, Gate 1, training, or safety acceptance.

## [2.5.0] - Unreleased

### Added

- Added the existing `FinalIssuedCommandReceipt.msg` to ROSIDL generation at
  the build/interface layer. The schema source SHA-256 remains
  `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`.

### Scope

- This does not implement a runtime node or create
  `/mecanum/final_issued_command`, runtime QoS, or receipt runtime evidence.
- The historical `DRAFT` and “Not installed in a ROSIDL package” annotations
  are addressed only by the separate atomic L2 decision for ROSIDL generation
  status after its exact audit, User authorization, and integration conditions.
- The annotation “no implementation or runtime authorization” remains in
  effect for runtime producers/consumers and runtime behavior.

## [Unreleased] - 2.4.0

### Added

- Added `NavigationState.msg` for the navigation-state contract.
- Added `CommandEnvelope.msg` for source-tagged command arbitration.

### Changed

- Extended `SafetyState.msg` with `navigation_state_fresh`, `path_valid`,
  `motion_permitted`, and `navigation_state_age_ms`.
- Updated ROSIDL generation to include Heartbeat, SafetyState,
  NavigationState, and CommandEnvelope interfaces.

### Compatibility

- `SafetyState.msg` changed; packages that publish or subscribe to it must be
  rebuilt and reviewed against the 2.4.0 schema.
