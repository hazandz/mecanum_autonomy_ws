# STM32 Firmware Architecture

## 1. Mục đích, phạm vi và authority

Tài liệu này mô tả kiến trúc **nội bộ** firmware cho STM32F411CEU6 Black Pill
trong hệ Mecanum. Nó chuyển các contract đã khóa thành ranh giới module,
state machine, nguyên tắc FreeRTOS và chiến lược kiểm thử trước khi viết
firmware C.

Authority theo thứ tự:

1. `docs/MECANUM_NAV_DRL_Architecture.docx` là kiến trúc hệ thống tối cao.
2. `docs/Pi_STM32_Interface_Contract.md` là contract Pi ↔ STM32.
3. `artifacts/hardware/<hardware_profile_id>/hardware_manifest.yaml` là
   nguồn cấu hình phần cứng duy nhất.
4. `artifacts/hardware/<hardware_profile_id>/approval.yaml` là evidence và
   approval độc lập; nó không là input của `hardware_config_hash`.

### Phạm vi

- MCU: STM32F411CEU6 Black Pill.
- Debug/programming: ST-Link V2.
- Scheduler: FreeRTOS.
- Nhận command body twist từ Pi bridge, điều khiển bốn motor, đọc encoder,
  và gửi telemetry cumulative tick về Pi.
- Thực hiện inverse kinematics, wheel PID, PWM/direction và software
  watchdog.

### Non-goals

- Không chạy ROS 2, DDS, TF, Nav2, DRL hoặc Gymnasium.
- Không publish topic, không publish `/wheel/odometry_raw`, không broadcast
  TF và không tính forward kinematics cho ROS.
- Không điều khiển BNO055 hoặc LiDAR. BNO055 thuộc Raspberry Pi 5 qua I2C;
  YDLIDAR thuộc Pi qua USB.
- Không tự parse YAML, tự phê duyệt hardware profile, hoặc tự thay đổi
  protocol/hardware contract.
- Không thay thế physical E-stop bằng firmware.

## 2. Ownership và data flow

```text
SafetySupervisor
  -> FinalTwistPublisher
  -> /cmd_vel
  -> mecanum_base_bridge
  -> UART command [vx_mps, vy_mps, wz_radps] in base_link
  -> STM32 protocol/config validation
  -> inverse kinematics FL, FR, RL, RR
  -> four-wheel PID
  -> PWM/direction and TB6612 motor path

STM32 cumulative ticks FL, FR, RL, RR
  -> UART telemetry
  -> mecanum_base_bridge
  -> forward kinematics
  -> /wheel/odometry_raw
  -> EKF
```

- Pi bridge owns UART transport on the Pi side, telemetry validation, forward
  kinematics and `/wheel/odometry_raw` publication.
- STM32 owns inverse kinematics and the low-level wheel control path.
- Wheel order is always `FL`, `FR`, `RL`, `RR`; physical aliases only exist in
  the hardware manifest.
- STM32 does not publish TF. EKF owns `odom -> base_link`.
- UART command semantic is `[vx_mps, vy_mps, wz_radps]` in the `base_link`
  body frame. STM32 does not know ROS command source, ROS runtime generation,
  or ROS source instance ID.
- Telemetry acknowledgement only confirms accepted UART command receipt. It
  does not prove applied PWM, wheel velocity, or achieved body velocity.

## 3. Firmware state machine

| State | Motor policy | Entry condition | Exit condition |
|---|---|---|---|
| `BOOT_OR_UNCONFIGURED` | Disabled | Power-on, MCU reboot, unresolved generated configuration | Valid CONFIG handshake |
| `CONFIG_ACCEPTED_MOTOR_DISABLED` | Disabled | Valid CONFIG request, including one with the same epoch | Fresh valid COMMAND for configured epoch |
| `COMMAND_ACTIVE` | Control allowed subject to safety | Valid new command sequence and watchdog healthy | Watchdog, config replacement, safety stop, or reboot |
| `SAFE_STOP` | Zero wheel target and driver-disable request; physical braking behavior is `TBD_MEASURED` | Watchdog expiry, software critical fault, or explicit safe-stop condition | Recovery policy is `REQUIRED_DECISION`; no automatic physical E-stop override |

### CONFIG handshake and reset epoch

- Every valid `CONFIG_REQUEST` clears accepted command state, requests motor
  disable and enters `CONFIG_ACCEPTED_MOTOR_DISABLED`, even if its
  `reset_epoch` equals the configured epoch.
- A valid CONFIG request may set any contract-valid `uint32 reset_epoch` as
  the configured epoch if protocol version and `hardware_config_hash` match.
- COMMAND is accepted only when its epoch equals the configured epoch.
- A command with another epoch is rejected; it does not update
  `last_accepted_command_sequence` or refresh the watchdog.
- Command sequence must increase strictly within an epoch. Duplicate or
  backward sequence is dropped and does not refresh the watchdog.
- Pi starts a new control session by sending CONFIG. STM32 cannot infer a Pi
  restart or UART reconnect merely from an idle serial line.

## 4. Reboot, UART loss and recovery

```text
MCU reboot
  -> BOOT_OR_UNCONFIGURED

Pi restart or UART reconnect
  -> Pi stops command stream and sends valid CONFIG_REQUEST
  -> STM32 clears accepted command state
  -> CONFIG_ACCEPTED_MOTOR_DISABLED
```

- MCU reboot luôn vào `BOOT_OR_UNCONFIGURED` với motor disabled.
- STM32 không tự nhận biết Pi restart hoặc UART reconnect. Mất command hợp lệ
  được nhận biết bằng watchdog expiry và đưa control path vào `SAFE_STOP`.
- Pi restart hoặc reconnect phải ngừng command stream và gửi
  `CONFIG_REQUEST` mới trước khi phát command stream mới.
- Chỉ CONFIG hợp lệ mới clear accepted command state và tạo control session
  mới. CONFIG lỗi không thay đổi state session đang được chấp nhận.
- UART byte loss, malformed frames, CRC failure, incompatible protocol,
  unknown message type và invalid payload length không refresh watchdog.
- `mcu_boot_id` phải mới sau reboot. Thuật toán persistent generation của nó
  vẫn là `REQUIRED_DECISION`.
- Không suy diễn thêm recovery policy; behavior ngoài những rule contract đã
  khóa là `REQUIRED_DECISION`.

## 5. Kiến trúc module

`ControlSafetyTask` là owner duy nhất của firmware session state: configured
`hardware_config_hash` acceptance, configured `reset_epoch`, last accepted
command sequence, command eligibility, watchdog refresh/expiry và mọi
state-machine transition. `CommunicationTask` chỉ thực hiện transport
validation và chuyển candidate/result giữa UART với task owner này.

| Module | Dữ liệu nhận | Dữ liệu xuất | Trách nhiệm | Không được làm | Caller/task |
|---|---|---|---|---|---|
| `main` | Generated configuration, HAL/FreeRTOS startup result | Task creation và safe initial state | Initialize MCU, keep motor disabled at boot, create tasks | Parse YAML hoặc apply motion command | Reset/startup context; creates `StartupTask` |
| `safety_io` | E-stop auxiliary contact, driver-fault inputs, control permission request | Safety input snapshot và motor-disable request | Read diagnostics và present hardware safety state | Bypass E-stop gate hoặc issue PWM | `ControlSafetyTask`; telemetry reads a copied diagnostic snapshot |
| `communication` | UART RX byte stream, transport-valid ConfigRequest/CommandCandidate, outbound TX queue | Candidate queue và serialized CONFIG status/TELEMETRY frames | COBS framing, CRC, protocol version/message type/payload-length validation; own UART TX serialization, COBS encoding and ordered transmit | Accept CONFIG/COMMAND by hash, epoch or sequence; refresh watchdog; change session state; run PID, apply PWM, or emit COMMAND response frame | `CommunicationTask` only |
| `command_watchdog` | Accepted command event và steady MCU time | Watchdog healthy/expired state | Track valid fresh command arrival for configured session | Treat malformed/duplicate command as refresh | `ControlSafetyTask` |
| `encoder` | Timer encoder counters và overflow events | Cumulative `int64` ticks và coherent snapshot | Maintain cumulative FL/FR/RL/RR counters | Perform UART serialization hoặc change motor output | Encoder ISR writes; `ControlSafetyTask` and `TelemetryTask` request snapshots |
| `mecanum_kinematics` | Accepted body twist và generated geometry/sign config | Four wheel target velocities | Inverse kinematics in locked wheel order | Read pins, publish telemetry, hoặc choose safety state | `ControlSafetyTask` |
| `pid_controller` | Wheel targets, measured wheel motion, generated gains/limits | Per-wheel control effort | Closed-loop wheel control with bounded internal state | Enable motor hoặc override safety permission | `ControlSafetyTask` |
| `motor_control` | Selected per-wheel effort, direction và explicit permission from `ControlSafetyTask` | PWM/direction và MCU motor-enable request | Drive TB6612 control pins through approved path | Be called by another task, bypass E-stop, hoặc decide arbitration | `ControlSafetyTask` only |

`motor_control` is the only module that writes PWM/direction output registers.
It may be invoked only by `ControlSafetyTask`.

## 6. FreeRTOS architecture

### ISR and task responsibilities

| Context | Relative priority | Responsibility |
|---|---|---|
| UART RX ISR/DMA callback | Interrupt context | Copy/advance received bytes, notify `CommunicationTask`; no blocking parse or motor control |
| Encoder timer/overflow ISR | Interrupt context | Update counter extension state with bounded work |
| `StartupTask` | Startup-only | Initialize safe state, validate generated configuration presence, create/enable runtime tasks, then suspend or terminate |
| `ControlSafetyTask` | Highest among tasks | Own all session-state acceptance/transition decisions; consume validated candidates; refresh/expire watchdog; enqueue CONFIG status only after CONFIG_REQUEST; invoke kinematics, PID and motor control |
| `CommunicationTask` | Below ControlSafetyTask | Decode COBS/CRC and transport-validate frames; enqueue ConfigRequest/CommandCandidate; serialize/transmit CONFIG status and TELEMETRY from the outbound TX queue |
| `TelemetryTask` | Below ControlSafetyTask | Take coherent snapshots and enqueue telemetry requests; never transmit UART or change control state |

No numerical FreeRTOS priorities, control rate, telemetry rate or watchdog
timeout is set here. They remain `REQUIRED_DECISION` or `TBD_MEASURED`.

### Shared state and race rules

- UART ISR/DMA callback writes only a bounded RX stream/ring buffer and emits
  a task notification. It never calls kinematics, PID, PWM or blocking APIs.
- `CommunicationTask` performs only transport validation: COBS, CRC, protocol
  version, message type và payload length. It enqueues a
  `ConfigRequest`/`CommandCandidate` only after those checks pass.
- `ControlSafetyTask` performs all semantic validation: local hash acceptance,
  epoch and sequence checks, command eligibility, watchdog refresh/expiry and
  state-machine transition. It is the only task that can accept or reject a
  CONFIG/COMMAND candidate.
- CONFIG replacement and accepted-command reset are one transaction owned by
  `ControlSafetyTask`.
- After processing a CONFIG request, `ControlSafetyTask` enqueues exactly its
  CONFIG status to the outbound TX queue. COMMAND acceptance or rejection does
  not create a response frame.
- `TelemetryTask` only enqueues telemetry requests built from coherent copied
  snapshots. It never calls UART transmit directly.
- `CommunicationTask` is the only UART TX owner. No task or ISR calls UART
  transmit directly; `CommunicationTask` serializes, COBS-encodes and sends
  one outbound frame at a time in TX-queue order, preventing byte interleave.
- COMMAND outcome is observable only through asynchronous telemetry, including
  `last_accepted_command_sequence`, `mcu_fault_bits`, `estop_aux_active` and
  the other locked telemetry fields.
- Encoder ISRs own counter mutation. `encoder_snapshot()` copies all four
  `int64` values coherently under a short critical section, seqlock, or other
  approved synchronization mechanism.
- The critical section covers only copying shared counters; COBS, CRC,
  formatting and UART transmit occur outside it.
- `TelemetryTask` reads immutable/copy snapshots, never live mutable PID or
  command state.
- No ISR takes a mutex, waits on a queue, allocates memory, or calls motor
  control.
- No task other than `ControlSafetyTask` requests PWM, direction or motor
  enable through `motor_control`.

## 7. Safety invariants và configuration provenance

### Physical E-stop boundary

```text
E-stop NC
  -> hardware gate
  -> STBY_SAFE = LOW on both TB6612 modules

PB10 / MCU_MOTOR_ENABLE
  -> input of the hardware gate only
```

The NC E-stop hardware gate always wins over MCU software and PB10. Firmware
may request zero output or disable through `MCU_MOTOR_ENABLE`, but cannot
bypass the physical E-stop. STM32 reads E-stop only through its auxiliary
contact for telemetry and diagnostics.

1. `ControlSafetyTask` is the sole owner of session state, including hash/epoch
   acceptance, command sequence, command eligibility, watchdog and state
   transition.
2. `CommunicationTask` is the sole UART TX owner; only CONFIG status and
   TELEMETRY enter its ordered outbound TX queue.
3. Only `ControlSafetyTask` may request PWM/motor output via `motor_control`.
4. Physical E-stop does not depend on firmware, FreeRTOS, UART, Linux, ROS 2,
   DDS or Python.
5. UART/config failures, malformed frames, CRC failures, duplicate command
   sequence and backward command sequence do not refresh watchdog.
6. Every valid CONFIG clears accepted command state and holds motors disabled
   until a fresh valid command for the configured epoch arrives.
7. Telemetry uses one coherent snapshot of all four cumulative `int64` encoder
   ticks in order `FL`, `FR`, `RL`, `RR`.
8. Firmware must not enable motor with unresolved generated hardware
   configuration, an unapproved hardware profile, mismatched
   `hardware_config_hash`, or required hardware field still `TBD_MEASURED`.
9. Firmware does not parse `hardware_manifest.yaml` or `approval.yaml`.
   A future generator/build gate must supply a verified generated configuration
   and explicit release authorization; absent or invalid generated inputs mean
   motor disabled.
10. `approval.yaml` remains outside `hardware_config_hash`; approval changes
   must not silently alter geometry, pins, telemetry order or firmware hash.
11. `last_accepted_command_sequence` confirms valid packet acceptance only; it
   is not motor-motion evidence.
12. COMMAND acceptance or rejection creates no response frame; command result
    is reflected only in asynchronous locked telemetry fields.
13. No software action can raise `STBY_SAFE` while the physical NC E-stop path
    forces it LOW.

## 8. Test strategy trước firmware C

No test in this section is claimed PASS until evidence exists.

| Test level | Test group | Required checks |
|---|---|---|
| Unit | UART parser | COBS decode/resync, CRC-16/CCITT-FALSE, frame type/length/version rejection |
| Unit | Configuration state | CONFIG/hash/epoch validation, valid CONFIG clearing command state, status transitions |
| Unit | Command sequence | Strict increase, duplicate/backward rejection, wrong epoch and no watchdog refresh |
| Unit | Encoder | FL/FR/RL/RR order, cumulative extension, counter wrap và `int64` snapshot coherence |
| Unit | Kinematics and PID | Inverse kinematics, PID state/limit behavior và software fault-state transitions |
| Unit | Watchdog | Only accepted fresh command refreshes watchdog; timeout reaches `SAFE_STOP` |
| Integration | Reboot and UART loss | MCU reboot, Pi restart/reconnect handshake, packet loss và motor-disabled recovery |
| HIL | E-stop hardware gate | NC open forces both TB6612 `STBY_SAFE` LOW and PB10 cannot defeat it |
| HIL | Hardware evidence | Geometry, encoder scale/sign, UART timing, TB6612 current/thermal, power integrity and stopping/watchdog measurements |

Software mapping checks are not HIL evidence and do not justify setting
`approval_status: APPROVED`.

## 9. Open items

### REQUIRED_DECISION

- UART baud rate, flow control, DMA/ring-buffer design and reconnect retry
  policy.
- Final numeric protocol assignments where still marked proposal, including
  CONFIG status/reject codes.
- Persistent `mcu_boot_id` algorithm, flash-journal layout, endurance policy
  and counter-wrap maintenance.
- FreeRTOS numerical priorities, ISR priority compatibility, control period,
  telemetry period and watchdog timeout.
- Encoder snapshot synchronization primitive and memory-ordering rules.
- PID algorithm details, anti-windup behavior and non-E-stop fault recovery.
- STM32 regulated power path, driver-fault wiring and E-stop auxiliary-contact
  polarity.
- Generator/build-gate format for verified generated configuration and release
  authorization.

### TBD_MEASURED

- Wheel diameter/radius, wheelbase, track and final roller geometry evidence.
- Encoder counts per motor revolution, gear ratio, ticks per wheel revolution
  and counter behavior.
- Motor and encoder signs for all four logical wheels.
- PWM envelope, PID gains, wheel velocity/acceleration/jerk limits and braking
  behavior.
- UART latency, jitter, packet-loss rate and sustainable telemetry rate.
- Watchdog/command TTL, end-to-end latency and stopping envelope.
- TB6612 current/thermal behavior, power integrity, brownout behavior and
  physical E-stop gate response time.

Until these items are resolved through approved manifest, approval evidence,
generator verification and applicable HIL evidence, firmware remains
motor-disabled by design.
