# Changelog

All notable changes to `mecanum_nav_rl_interfaces` are documented in this file.

## [2.5.0] - Unreleased

### Added

- Added `FinalIssuedCommandReceipt.msg` to ROSIDL generation. Its canonical
  schema source SHA-256 remains
  `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`.

### Scope

- This additive generated interface declaration is not a node or runtime
  implementation. It does not create a publisher on
  `/mecanum/final_issued_command`, establish runtime QoS, or provide receipt
  runtime evidence.

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
