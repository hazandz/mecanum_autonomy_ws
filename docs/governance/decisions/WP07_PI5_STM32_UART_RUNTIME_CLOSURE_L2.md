# WP07 PI5–STM32 UART Runtime Closure — L2 Owner Decision

**Decision ID:** `WP07_PI5_STM32_UART_RUNTIME_CLOSURE_L2`
**Approval status:** `OWNER_APPROVED_WITH_AMENDMENT`
**Approval token:** `OWNER_APPROVED_WP07_PI5_STM32_UART_RUNTIME_CLOSURE_L2_REV_A_20261025`
**Mandatory amendment:** `A1 — NO_PRECONFIG_TELEMETRY`
**Classification:** L2
**Approved implementation step:** U2 only for candidate `WP07_U2_PI_SERIAL_TRANSPORT_OFFLINE`
**Decision record date:** 2026-10-25

This file records the Owner-approved design for this development lane. U1 is
`U1_L2_DECISION_APPROVED`. The U2 candidate has not been independently audited
at its exact commit SHA. This decision does not create canonical integration,
runtime authorization, HIL authorization, motor-enable permission, or a WP07
canonical status transition. `approval.yaml` is not changed.

## A1 — No telemetry before accepted configuration

STM32 MUST NOT emit UART v1 `TELEMETRY` before it has accepted a valid
`CONFIG_REQUEST`. The handshake is:

1. Pi opens the explicitly selected UART.
2. Pi sends `CONFIG_REQUEST`.
3. STM32 validates the request and returns `CONFIG_STATUS`.
4. Only after `CONFIG_ACCEPTED` may STM32 begin periodic `TELEMETRY`.
5. Pi requires the first valid telemetry to carry the `mcu_boot_id` and
   `reset_epoch` matching the accepted configuration before entering `ACTIVE`.
6. Only then may the Pi bridge begin a fresh `COMMAND` stream.

A valid `CONFIG_STATUS` provides the initial boot ID used for this handshake;
telemetry before CONFIG is not required. `CONFIG_STATUS` alone does not make
the bridge `ACTIVE` and does not permit COMMAND. Do not introduce a sentinel or
special `reset_epoch` value for the preconfiguration state. Every `uint32`
`reset_epoch` value remains valid under the contract.

## Approved protocol and transport design

- UART protocol version is `0x0001`; framing is COBS followed by `0x00`, with
  CRC-16/CCITT-FALSE and little-endian fields. Existing packet types, payload
  sizes, frame/buffer limits, status constants, and reject codes stay fixed.
- UART electrical settings are 115200 baud, 8N1, `xonxoff=false`,
  `rtscts=false`, and `dsrdtr=false`.
- Pi uses pyserial, `timeout=0`, `write_timeout=0.020 s`, and exclusive access
  on Linux. Unsupported required configuration is an error; it is not silently
  dropped.
- STM32 uses `HAL_UARTEx_ReceiveToIdle_IT`, an initial 128-byte HAL RX buffer,
  and a 512-byte RX ring. Do not select DMA without HIL evidence.
- `CommunicationTask` is the sole UART TX owner. ISR code only transfers bytes
  into bounded storage/notifies a task; it does not parse COBS/CRC or decide
  session state.
- `ControlSafetyTask` owns CONFIG/COMMAND acceptance, watchdog and state, with
  an initial 5 ms check cycle. `TelemetryTask` snapshots/enqueues only.
  Communication TX scheduling is initially bounded at 10 ms.
- Initial COMMAND and post-CONFIG TELEMETRY rates are each 50 Hz.
  `/cmd_vel` freshness is 100 ms; STM32 command watchdog and valid-telemetry
  timeout are each 200 ms. CONFIG_STATUS timeout is 500 ms, with at most three
  attempts per handshake. Reconnect interval is 1 s. ROS heartbeat is 10 Hz.
- These are initial values for HIL verification, not measured motion or braking
  limits. The bridge MUST NOT synthesize zero commands when `/cmd_vel` is stale;
  it stops the COMMAND stream.
- COMMAND sequence begins at 1; sequence 0 is rejected.
  `last_accepted_command_sequence=0` means `NO_COMMAND_ACCEPTED_YET`.
  Watchdog expiry does not erase accepted-sequence history; boot/new CONFIG
  resets that history to zero. Malformed, CRC-failed, duplicate, backward,
  wrong-epoch, and non-finite commands do not refresh the watchdog.
- COMMAND acceptance confirms packet receipt only; it does not prove motor
  output. `SafetyLifecycle` retains lifecycle/reset identity ownership; the
  bridge does not self-rearm. Reconnect clears caches/baselines, starts a new
  handshake, and waits for a fresh command; old commands are never resumed.
- Encoder telemetry uses cumulative `int64` FL/FR/RL/RR counters from a
  coherent snapshot. Pi owns forward kinematics and `/wheel/odometry_raw`.
  Never compute deltas across boot, epoch, discontinuity, or invalid telemetry.
  ROS timestamps use Pi receive time; MCU time progression is checked without
  introducing a clock-synchronization system.
- The bridge emits no TF; EKF is the sole `odom → base_link` publisher.
  Heartbeat keeps existing messages/constants, distinguishing MCU-reported
  faults from Pi-observed transport loss. Do not invent MCU
  `FAULT_TRANSPORT`. BNO055 and LiDAR remain Pi-side and outside STM32
  telemetry.

## Owner-confirmed geometry and configuration

- Wheel diameter 0.097 m; radius 0.0485 m.
- Wheelbase 0.216 m; track 0.190 m; `Lx + Ly = 0.203 m`.
- `counts_per_wheel_revolution = 937.2`.
- Historical hand measurement 906 is inaccurate; do not require a new CPR
  measurement unless new contradictory evidence appears. Do not multiply 937.2
  by quadrature or gear ratio again.
- The hardware manifest remains the configuration source. `approval.yaml` is
  outside the hash. Preserve the existing SHA-256, domain separator, and
  RFC8785 JCS rules.
- Valid communication configuration and motor-enable permission are separate
  conditions. `motor_enable_allowed` remains false.

## Boot identity and implementation boundaries

- The proposed boot journal uses one dedicated flash sector: sector 7 at
  `0x08060000–0x0807FFFF`, with 32-bit cells and a non-wrapping counter.
  Interrupted writes, readback verification, exhausted space, and journal
  errors fail closed.
- Sector 7 MUST be reserved from the application linker region before the
  journal can be called production-ready. U2 does not implement the journal.
- Do not create a persistent-storage framework or guess hardware pins or
  polarity without evidence.
- HIL needs separate authorization. U7 requires a clean branch from the latest
  integration, the final required source transfer, impact tests, independent
  audit, Owner approval, and a separate integration task.
- Do not change `approval.yaml`, execute Gate 3/Gate 4, or run `deploy_real`.

## Candidate and status boundary

U2 is limited to the offline Pi serial transport, package metadata, tests,
documentation, this decision record, and its single evidence JSON. It does not
implement ROS endpoints, CONFIG/session state, telemetry validation, command
sequencing/cache, heartbeat, odometry, or STM32 firmware. Known sequence and
watchdog implementation gaps remain U4 work; U2 tests cannot be reported as
full L2 PASS.

U3, U4, U5, U6, and U7 remain future separately scoped work. PEP/WP07
canonical status is unchanged. No audit or approval is implied by this record.

The U2 package metadata remains at its existing development version `0.3.0`;
the transport change is recorded under `Unreleased`. The earlier prompt-level
metadata bump request was withdrawn by a later coordinator disposition. It is
not attributed to this Owner decision. Production release versioning is
reconciled at U7.
