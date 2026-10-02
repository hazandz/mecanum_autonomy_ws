# Changelog

All notable changes to `mecanum_nav_rl_interfaces` are documented in this file.

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
