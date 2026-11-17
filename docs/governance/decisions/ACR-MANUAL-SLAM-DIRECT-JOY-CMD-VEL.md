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

- MANUAL_SLAM target candidate ceiling: `2000 tick/s`; this is an offline
  requested target limit, not a validated operating speed.
- Five mapper levels: `800, 1100, 1400, 1700, 2000 tick/s` (40%, 55%, 70%,
  85%, 100% of that candidate ceiling), starting at 800 tick/s.
- The PID4 evidence record used a `1400 tick/s` target ceiling. Extending the
  mapper, firmware profile and PID4 target guard to 2000 changes only accepted
  target range; Kp/Ki, per-wheel/direction feedforward, integral cap, PWM cap,
  and direction/stall/synchronization guard thresholds are unchanged. The
  2000 tick/s candidate is not validated by the PID4 evidence.
- Encoder scale for mapper, wheel odometry, and the MANUAL_SLAM firmware profile:
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
- Android Gamepad ROS `Joy.buttons` indices for A/B/X/Y/L1/R1 are not confirmed
  by raw button-array captures. The mapper uses explicit `joy_button_*_index`
  parameters; `-1` means unconfigured and ignores that physical button while
  preserving analog-stick operation. Test mappings use shuffled synthetic
  indices and are not hardware-layout evidence.
- `UartBridgeNode`, `BridgeSession`, session identity/lifecycle checks, UART
  protocol and command validation remain in use; command-watchdog expiry is explicitly disabled for the validated MANUAL_SLAM bench profile. No Joy callback
  may access the session directly.
- The hardware launch keeps `/safety_lifecycle` disarmed. The separately
  approved terminal-2 mapping launch may configure/activate SLAM Toolbox and
  `/safety_lifecycle`, wait for fresh `/scan`, `/bno055/imu`, Joy and a healthy MCU heartbeat,
  require a fresh neutral Joy sample, call the existing safety rearm service,
  verify lifecycle motion permission, then call the mapper enable service.
  It never fabricates Joy, publishes a movement command, or rearms during
  terminal-1 hardware launch. Service/dependency timeout or rejection aborts
  the mapping launch without a ready claim. After startup it monitors fresh
  sensor/Joy/heartbeat and lifecycle readiness, including periodic verification
  that `/slam_toolbox` remains active; dependency or lifecycle loss requests mapper
  software disarm and ends the mapping launch. Shutdown also requests disarm
  best-effort; this is not a physical E-stop or main-switch substitute.

### Terminal-2 mapping orchestration scope

This Owner-approved implementation candidate adds a second, MANUAL_SLAM-only
launch for async SLAM mapping. It is not included in AI/Nav2 launches and does
not change their lifecycle, safety, or command ownership. The orchestration
uses the existing safety lifecycle/rearm and mapper enable/disarm contracts.
Terminal-2 readiness gates are software checks; they do not establish ROS graph
exclusivity, physical E-stop protection, UART correctness on the robot, or
real-robot readiness. The terminal-1 hardware launch remains separate.
- E-stop auxiliary remains `UNKNOWN` when firmware cannot read a validated
  input. The Owner's main switch has not been verified to disconnect both motor
  drivers and is not treated as an E-stop.

### MANUAL_SLAM bench auxiliary E-stop scope

The Owner confirms no auxiliary E-stop circuit is installed on this bench and
accepts the main power switch as the available manual interruption method for
this bench trial only. Firmware telemetry remains `UNKNOWN`; it is never
rewritten to `INACTIVE` and no hardware state is fabricated. The bridge may be
explicitly configured with `manual_slam_bench_unmonitored_estop=true` only in
the MANUAL_SLAM bench launch: this suppresses unhealthy status caused solely
by the absent auxiliary input. A reported `ACTIVE`, any MCU fault, stale
telemetry, UART/session loss, or motor fault remains unhealthy/stopping. In
the validated MANUAL_SLAM bench firmware profile, command-watchdog expiry is
disabled, so loss of commands or connection silence alone does not stop the
active target. UART/transport failure, explicit zero/disarm, and PID4 motor
fault handling remain separate stopping paths. No IWDG/WWDG hardware watchdog
refresh or shutdown path is configured in this firmware source; do not infer
one from the command watchdog. Invalid/non-bench profile builds enable command
watchdog expiry. Other modes retain their own strict E-stop and watchdog
policies. The main switch's ability to
disconnect both drivers is unverified; this exception is not an equivalent
physical E-stop and does not establish robot readiness.
- The MANUAL_SLAM firmware candidate enables the PID4 experimental numerical
  profile only when built from a manifest whose geometry, 937.2 encoder scale,
  wheel order and Owner-reported signs validate. MCU output is disabled at boot;
  movement requires a matching session CONFIG and an accepted nonzero command.
  Zero command and transport/session failure disable output. Invalid profile,
  encoder snapshot, control interval/target/PWM, and PWM peripheral-start errors
  remain fatal and follow their existing SAFE_STOP/fault paths. Launch does not
  configure or rearm the MCU.
- PID4's 20 ms control cadence, 1 s ramp, per-wheel/direction feedforward,
  integral/effort caps and maximum-dt guard remain in use. For this explicitly
  selected MANUAL_SLAM bench profile only, wrong-direction, stall and
  comparable-wheel synchronization results are nonfatal tracking diagnostics:
  they do not set `MECANUM_FAULT_MOTOR_DRIVER` or put the session in SAFE_STOP.
  Firmware reports them separately as diagnostic bit `16384`; the bridge keeps
  that bit and warning detail, and treats it as nonfatal only when the explicit
  MANUAL_SLAM bench parameter is set. The heartbeat can therefore remain
  healthy while warning that wheel response is not enforced; `healthy` means
  telemetry/session and fatal-fault checks passed, not that wheel tracking was
  measured as correct. Other/default bridge configurations treat this bit as
  unhealthy. The
  one-shot 10 s arm delay, fixed 5 s autorun, 6 s test-run timeout and 1 s
  stop-hold are omitted for continuous session-owned manual commands; the 1 s
  full-scale ramp becomes a slew limit of the larger current/requested
  magnitude per second. The 150 tick/s synchronization warning is kept
  internally but is not published as telemetry. No exact ELF/flash image or
  hardware behavior is verified by this candidate.
- The MANUAL_SLAM tracking exception means a jammed or wrongly rotating wheel,
  or a wheel-speed synchronization error, will not by itself stop output. PWM
  peripheral failure, invalid configuration/encoder/control data, transport
  and session faults remain fatal. This is a deliberate bench-only reduction
  in automatic stopping coverage, not a safety or readiness claim.
- At 2000 tick/s, the unchanged feedforward equations `u0 + kv × target`
  produce effort demands of approximately 476/496/487/485 permille forward
  and 486/487/502/491 permille reverse (FL/FR/RL/RR), above the unchanged
  400-permille output cap. The PID runtime therefore clamps effort at that
  target. This source calculation indicates likely PWM saturation; it does
  not establish achievable wheel speed or explain the reported motor noise.

## Verification boundary

Offline tests/build validate source behavior only. They do not prove ROS graph
exclusivity, Pi driver compatibility, UART/session runtime, firmware/manifest
hash agreement on the installed MCU, watchdog response on hardware, sensor
mounting, E-stop behavior, mapping quality, or robot readiness. No hardware,
serial, HIL, SLAM runtime, flash, or rearm operation is authorized here.
