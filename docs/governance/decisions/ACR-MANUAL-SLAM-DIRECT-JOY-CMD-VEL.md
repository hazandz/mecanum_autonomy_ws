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
  Zero command, transport/session failure or PID4 guard fault disables
  output. A guard fault moves the session to SAFE_STOP and requires a new
  accepted CONFIG before another command can be accepted. Launch does not
  configure or rearm the MCU.
- PID4's 20 ms control cadence, 1 s ramp, per-wheel/direction feedforward,
  integral/effort caps, maximum dt, wrong-direction, stall and comparable-wheel
  synchronization fault thresholds are carried into this manual runtime. The
  one-shot 10 s arm delay, fixed 5 s autorun, 6 s test-run timeout and 1 s
  stop-hold are omitted for continuous session-owned manual commands; the 1 s
  full-scale ramp becomes a slew limit of the larger current/requested
  magnitude per second. The 150 tick/s synchronization warning is kept
  internally but is not published as telemetry. No exact ELF/flash image or
  hardware behavior is verified by this candidate.

## Verification boundary

Offline tests/build validate source behavior only. They do not prove ROS graph
exclusivity, Pi driver compatibility, UART/session runtime, firmware/manifest
hash agreement on the installed MCU, watchdog response on hardware, sensor
mounting, E-stop behavior, mapping quality, or robot readiness. No hardware,
serial, HIL, SLAM runtime, flash, or rearm operation is authorized here.
