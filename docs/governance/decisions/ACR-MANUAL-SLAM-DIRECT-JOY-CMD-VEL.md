# ACR candidate: MANUAL_SLAM direct Joy command route

**Status:** `OWNER_APPROVED_FOR_THIS_IMPLEMENTATION_CANDIDATE; INDEPENDENT_AUDIT_PENDING`
**Date:** 2026-11-15
**Work branch:** `slam-real-manual-test`
**Implementation base:** `8bc495b005ae401bc9c7907fb0db4abc61eab7e4`

## Owner decision

The Owner explicitly approves a mode-specific exception for `MANUAL_SLAM`:

```text
Joy -> manual mapper -> /cmd_vel -> UartBridgeNode -> BridgeSession -> UART -> STM32
```

`MANUAL_SLAM` does not route Joy through `SafetySupervisor` or
`FinalTwistPublisher`. It must not launch either node or another normal
`/cmd_vel` publisher. Existing AI/Nav2 modes retain their current source,
supervisor, and sole-final-publisher contracts. The launch is a review candidate;
it does not establish graph-wide exclusive ownership because ROS discovery is
not a static ownership lock.

This is a scoped exception to Architecture sections 4.4, 31, 42, 43, and 49.
It does not amend the frozen Architecture document, grant runtime approval, or
claim functional safety. The exception applies only to the new
`MANUAL_SLAM` launch and Joy mapper configuration. Any integration or broader
mode change requires a separate review.

## Selected inputs

- Gearbox output target profile: experimental ceiling `1400 tick/s`.
- Five mapper levels: `280, 560, 840, 1120, 1400 tick/s`.
- Encoder scale for mapper, wheel odometry, and the disabled firmware profile:
  `937.2 tick/wheel revolution`. The approximately `906` count observation is
  retained as a separate unresolved observation and does not replace it.
- Motor-shaft/gearbox-output reduction: `21.3:1`.
- Wheel/gearbox-output ratio: `1.0` (Owner-confirmed direct coupling).
- The MANUAL_SLAM bench manifest records encoder tick signs `+1` for FL/FR/RL/RR
  with `OWNER_REPORTED` provenance from the Owner's manual forward rotation
  observation. The cited raw telemetry and FR reconnect result were unavailable
  in this checkout; this is not raw-file-verified measurement evidence and does
  not alter the canonical manifest.
- The `172 RPM` design target remains reference-only and is not the selected
  runtime ceiling.

## Required failure behavior

- Mapper starts disarmed. Explicit software enable requires a fresh neutral Joy
  sample before motion mapping is enabled. Invalid configuration, unexpected
  discovered `/cmd_vel` publisher, invalid/stale Joy, or Joy timeout disarms
  and emits zero while the mapper is alive.
- L1/R1 only change the selected tier on rising edges. No Joy button is
  assigned as a stop control because no unused physical button has been
  confirmed. The mapper's explicit disarm service is software-only.
- `UartBridgeNode`, `BridgeSession`, session identity/lifecycle checks, UART
  protocol, command freshness, and STM32 watchdog remain in use. No Joy callback
  may access the session directly.
- No lifecycle READY/rearm is emitted by the launch. Any later operator rearm
  is outside this offline candidate and requires a separate reviewed procedure.
- E-stop auxiliary remains `UNKNOWN` when firmware cannot read a validated
  input. The Owner's main switch has not been verified to disconnect both motor
  drivers and is not treated as an E-stop.
- Firmware motor runtime remains disarmed. PID4 numerical values and per-wheel,
  per-direction feedforward are represented from the pinned experimental
  source; this candidate does not reproduce PID4 timing and fault guards, and
  no exact ELF/flash image is pinned. Matching manifest hash and hardware
  profile review are also pending. No motor is enabled by this ACR or launch.

## Verification boundary

Offline tests/build validate source behavior only. They do not prove ROS graph
exclusivity, Pi driver compatibility, UART/session runtime, firmware/manifest
hash agreement on the installed MCU, watchdog response on hardware, sensor
mounting, E-stop behavior, mapping quality, or robot readiness. No hardware,
serial, HIL, SLAM runtime, flash, or rearm operation is authorized here.
