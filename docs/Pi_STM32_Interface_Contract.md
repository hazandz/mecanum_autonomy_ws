# Raspberry Pi–STM32 Interface Contract

**Contract version:** `0.2.1-draft`
**Protocol version:** `0x0001` — `PROPOSED_FOR_APPROVAL`
**Status:** Draft. The UART v1 rules below are normative within this draft, but
they are not `APPROVED`; motor enable remains prohibited until every applicable
`REQUIRED_DECISION`, `TBD_MEASURED`, manifest, approval, and evidence gate is
resolved.

## 1. Status and authoritative sources

This contract is derived from, and must not override:

1. `docs/MECANUM_NAV_DRL_Architecture.docx`
2. `docs/MECANUM_NAV_DRL_Project_Tree.txt`

When this document conflicts with either authoritative source, the authoritative source wins.

Any change to packet fields, protocol behavior, wheel configuration, safety boundary, or hardware ownership requires explicit approval and a contract version update.

### Status vocabulary

| Status | Meaning in this contract |
| --- | --- |
| `LOCKED` | An approved system or hardware fact that implementations must preserve. |
| `PROPOSED_FOR_APPROVAL` | Normative content of this draft that must be reviewed and explicitly approved before it is treated as approved protocol. |
| `REQUIRED_DECISION` | A design or governance choice intentionally not selected yet; it must be resolved before the dependent implementation or deployment step. |
| `TBD_MEASURED` | A real-robot value that must come from recorded measurement evidence and must not be guessed. |

## 2. Hardware boundary and locked wiring

### MCU and firmware

- MCU: STM32F411CEU6 Black Pill.
- Programming and debug: ST-Link V2.
- Firmware scheduler: FreeRTOS.
- CubeMX setting: `Debug = Serial Wire`, `Trace = Disabled`.
- This configuration preserves PA15, PB3, and PB4 for assigned functions.
- `imu.c/.h` are outside the active STM32 scope and must not be implemented. BNO055 belongs to Pi 5.

### Contract wheel names

The following mapping is locked:

| Contract wheel name | Physical label |
| --- | --- |
| FL | LF |
| FR | RF |
| RL | LB |
| RR | RB |

All firmware code, packet fields, telemetry, tests, and bridge code must use `FL`, `FR`, `RL`, `RR` as the logical wheel order. Physical labels are only wiring aliases.

### Motor drivers and motors

- Motor drivers: two TB6612 modules.
- Motors: four GA25-370 motors.
- TB6612 logic supply `VCC`: 3.3 V.
- Motor supply `VM`: LiPo 3S through the motor-power path.
- Both TB6612 modules use `STBY_SAFE`.
- `PB10` is an STM32 GPIO output named `MCU_MOTOR_ENABLE`.
- The `MCU_MOTOR_ENABLE` signal goes into the hardware gate; it is not a direct E-stop override.

### Full motor-driver pin mapping

| Contract wheel | Physical label | PWM | Direction input 1 | Direction input 2 |
| --- | --- | --- | --- | --- |
| FL | LF | `PWMB / PB1` | `BIN1 / PA4` | `BIN2 / PA5` |
| FR | RF | `PWMA / PB0` | `AIN1 / PA3` | `AIN2 / PA2` |
| RL | LB | `PWMA / PB4` | `AIN1 / PB13` | `AIN2 / PB12` |
| RR | RB | `PWMB / PB5` | `BIN1 / PB14` | `BIN2 / PB15` |

### Encoder mapping

| Contract wheel | Physical label | Timer | Pins |
| --- | --- | --- | --- |
| FL | LF | TIM2 | PA15, PB3 |
| FR | RF | TIM5 | PA0, PA1 |
| RL | LB | TIM1 | PA8, PA9 |
| RR | RB | TIM4 | PB6, PB7 |

### UART electrical connection

| Signal | Connection |
| --- | --- |
| Pi RX pin 10 | STM32 `PA11 / USART6_TX` |
| Pi TX pin 8 | STM32 `PA12 / USART6_RX` |
| Ground | Shared by Pi, STM32, and motor drivers |
| Signalling | 3.3 V TTL |

UART v1 framing, byte order, frame types, CRC, and buffer limits are
`PROPOSED_FOR_APPROVAL` in section 4. UART baud rate, flow control, command and
telemetry rates, timeout values, retry/recovery policy, and electrical
validation remain `REQUIRED_DECISION`.

### Pi-side devices outside STM32 telemetry

- BNO055 connects directly to Raspberry Pi 5 through I2C and Pi 3V3.
- LiDAR connects directly to Raspberry Pi through USB.
- Neither BNO055 nor LiDAR is carried in STM32 telemetry.

## 3. Ownership and data flow

```text
SafetySupervisor / FinalTwistPublisher
  -> /cmd_vel
  -> mecanum_base_bridge on Raspberry Pi
  -> command encoder and transport
  -> STM32 command receiver
  -> inverse kinematics
  -> FL, FR, RL, RR wheel PID
  -> PWM, direction, and motor-enable path
  -> GA25-370 motors

STM32 cumulative encoder telemetry: FL, FR, RL, RR
  -> mecanum_base_bridge on Raspberry Pi
  -> validation and forward kinematics
  -> /wheel/odometry_raw
  -> EKF
```

- `FinalTwistPublisher` is the only ROS publisher allowed on `/cmd_vel`.
- `mecanum_base_bridge` owns Pi–STM32 transport, telemetry validation, forward kinematics, and `/wheel/odometry_raw`.
- STM32 performs inverse kinematics from body twist to four wheel targets.
- STM32 does not publish ROS messages or TF.
- `mecanum_base_bridge` does not publish TF.
- EKF is the only publisher of `odom -> base_link`.
- `mecanum_base_bridge` must be implemented after protocol approval and before HIL.

## 4. UART protocol v1 — PROPOSED_FOR_APPROVAL

The following protocol is normative within contract version `0.2.1-draft`.
It is `PROPOSED_FOR_APPROVAL`, not approved for motor enable or deployment.

### 4.1 LOCKED command semantic

The COMMAND semantic is `[vx_mps, vy_mps, wz_radps]`, expressed in the
`base_link` body frame. STM32 converts the body twist into `FL`, `FR`, `RL`,
`RR` wheel targets through inverse kinematics.

| Field | Meaning | Unit |
| --- | --- | --- |
| `vx_mps` | Forward linear velocity in `base_link` | metres per second |
| `vy_mps` | Lateral linear velocity in `base_link` | metres per second |
| `wz_radps` | Yaw angular velocity about `base_link` z-axis | radians per second |

### 4.2 Frame format

- Payloads are binary. All multibyte integers and `float32` values are
  little-endian.
- The decoded raw frame starts with this 4-byte header:

| Offset | Field | Type | Size |
| --- | --- | --- | --- |
| 0 | `protocol_version` | `uint16_le` | 2 bytes |
| 2 | `message_type` | `uint8` | 1 byte |
| 3 | `payload_length_bytes` | `uint8` | 1 byte |

- The raw frame is `header + payload + crc16_le`.
- `crc16_le` is CRC-16/CCITT-FALSE calculated over the decoded raw header and
  payload only. CRC parameters are polynomial `0x1021`, initial value
  `0xFFFF`, no input/output reflection, and final XOR `0x0000`.
- The wire frame is `COBS(raw_frame) + 0x00`. The `0x00` delimiter is not part
  of the COBS input and is not covered by CRC.
- A receiver MUST reject a frame with COBS failure, CRC failure, unsupported
  `protocol_version`, unknown `message_type`, or a payload length different
  from the exact length for that message type. Rejected frames do not refresh
  the command watchdog.

| Message type | Direction | Value | Exact payload length |
| --- | --- | --- | --- |
| `COMMAND` | Pi → STM32 | `0x01` | 20 bytes |
| `TELEMETRY` | STM32 → Pi | `0x02` | 65 bytes |
| `CONFIG_REQUEST` / `CONFIG_STATUS` | Pi → STM32 / STM32 → Pi | `0x03` | 40 / 50 bytes |

There is no separate ACK frame. A `CONFIG_STATUS` is the only direct status
response; it is sent only after a CONFIG request. COMMAND acceptance or
rejection does not create a response frame.

### 4.3 COMMAND — Pi to STM32

The COMMAND payload is exactly 20 bytes.

| Offset | Field | Type | Purpose |
| --- | --- | --- | --- |
| 0 | `command_sequence` | `uint32_le` | Strictly increasing Pi command-stream sequence |
| 4 | `reset_epoch` | `uint32_le` | Must equal STM32's configured epoch |
| 8 | `vx_mps` | `float32_le` | Forward body velocity |
| 12 | `vy_mps` | `float32_le` | Lateral body velocity |
| 16 | `wz_radps` | `float32_le` | Yaw body velocity |

- Pi sends a periodic command stream. Every transmitted COMMAND MUST use a
  strictly greater `command_sequence`, even when the twist is unchanged.
- STM32 accepts COMMAND only after an accepted CONFIG session and only when
  `reset_epoch` equals the configured epoch.
- Duplicate, backward, wrong-epoch, malformed, non-finite, or otherwise
  semantically invalid COMMAND frames MUST be rejected. They MUST NOT update
  `last_accepted_command_sequence` and MUST NOT refresh the watchdog.
- Retransmission with the same sequence MUST NOT be used to maintain command
  validity or the watchdog.
- COMMAND has no direct ACK or other response frame.

### 4.4 TELEMETRY — STM32 to Pi

The TELEMETRY payload is exactly 65 bytes. Ticks use the locked logical order
`FL`, `FR`, `RL`, `RR`.

| Offset | Field | Type | Purpose |
| --- | --- | --- | --- |
| 0 | `telemetry_sequence` | `uint32_le` | Detect duplicate, backward, and missing telemetry |
| 4 | `mcu_boot_id` | `uint64_le` | Detect MCU reboot |
| 12 | `reset_epoch` | `uint32_le` | Identify configured runtime reset boundary |
| 16 | `mcu_monotonic_time_us` | `uint64_le` | Validate temporal progression on the MCU clock |
| 24 | `ticks_fl` | `int64_le` | Cumulative FL encoder ticks |
| 32 | `ticks_fr` | `int64_le` | Cumulative FR encoder ticks |
| 40 | `ticks_rl` | `int64_le` | Cumulative RL encoder ticks |
| 48 | `ticks_rr` | `int64_le` | Cumulative RR encoder ticks |
| 56 | `last_accepted_command_sequence` | `uint32_le` | Latest COMMAND accepted by STM32 |
| 60 | `mcu_fault_bits` | `uint32_le` | Firmware fault state mapped to `Heartbeat.msg` `FAULT_*` constants |
| 64 | `estop_aux_active` | `uint8` | Physical E-stop auxiliary-contact diagnostic state |

- Pi bridge MUST validate protocol version, telemetry sequence, `mcu_boot_id`,
  `reset_epoch`, and MCU monotonic time before calculating wheel deltas.
- Pi bridge MUST NOT calculate a wheel delta across a changed `mcu_boot_id` or
  `reset_epoch`, or across an unresolved counter discontinuity.
- `last_accepted_command_sequence` is asynchronous telemetry acknowledgement
  of accepted UART packet receipt only. It does not prove applied PWM, wheel
  speed, or achieved body velocity.
- STM32 MUST snapshot all four cumulative `int64` tick counters coherently
  before composing TELEMETRY.
- Fault telemetry MUST map only to existing `FAULT_*` constants in
  `Heartbeat.msg`; no new ROS fault constant may be invented here. `FAULT_IMU`
  is not emitted by active STM32 scope because BNO055 is Pi-side.
- `mcu_fault_bits` MUST use the exact numeric bit values of the existing
  `Heartbeat.msg` `FAULT_*` constants. Undefined or reserved bits MUST be
  zero.
- STM32 `mcu_fault_bits` MAY set only the following exact `Heartbeat.msg` bits:

| Constant | Numeric bit value |
| --- | --- |
| `FAULT_TRANSPORT` | 1 |
| `FAULT_ESTOP_ACTIVE` | 2 |
| `FAULT_MCU_COMMAND_TIMEOUT` | 256 |
| `FAULT_MCU_COMMAND_INVALID` | 512 |
| `FAULT_MCU_CONTROL_LOOP` | 1024 |
| `FAULT_MOTOR_DRIVER` | 2048 |
| `FAULT_ENCODER` | 4096 |

- All other `mcu_fault_bits` bits MUST be zero.
- STM32 `mcu_fault_bits` MUST NOT set: `FAULT_POLICY_INFERENCE`,
  `FAULT_POLICY_COMMAND_INVALID`, `FAULT_POLICY_CONTROL_LOOP`,
  `FAULT_POLICY_MODEL_CONTRACT`, or `FAULT_IMU`.
- STM32 MAY set `FAULT_TRANSPORT` only when firmware detects a local UART or
  transport fault. A transport loss detected only by Pi bridge MUST NOT be
  inferred to mean STM32 set `FAULT_TRANSPORT`.

| Firmware or transport condition | Required Heartbeat mapping |
| --- | --- |
| Locally detected STM32 UART/transport failure | `FAULT_TRANSPORT` |
| Physical E-stop auxiliary state active | `FAULT_ESTOP_ACTIVE` |
| Command watchdog timeout | `FAULT_MCU_COMMAND_TIMEOUT` |
| Invalid command packet | `FAULT_MCU_COMMAND_INVALID` |
| MCU control-loop failure | `FAULT_MCU_CONTROL_LOOP` |
| TB6612 or motor-driver failure | `FAULT_MOTOR_DRIVER` |
| Encoder failure | `FAULT_ENCODER` |

### 4.5 CONFIG handshake

CONFIG uses `message_type = 0x03`. Direction and exact payload length
distinguish request from status.

#### CONFIG_REQUEST — Pi to STM32

The CONFIG request payload is exactly 40 bytes.

| Offset | Field | Type | Purpose |
| --- | --- | --- | --- |
| 0 | `config_sequence` | `uint32_le` | Correlate request and status |
| 4 | `reset_epoch` | `uint32_le` | Pi's intended control-session epoch |
| 8 | `hardware_config_hash` | `uint8[32]` | Raw SHA-256 digest of the hardware manifest contract input |

Any CONFIG_REQUEST with a supported protocol version, exact payload length, and
`hardware_config_hash` equal to the local hash is semantically valid for every
`uint32` `reset_epoch`. STM32 MUST accept that epoch and set it as the
configured epoch, unless local configuration is invalid and the defined reject
reason represents that condition. A valid CONFIG request, including one that
repeats the configured epoch, MUST clear accepted command state, request motor
disable, and enter
`CONFIG_ACCEPTED_MOTOR_DISABLED`. It MUST then wait for a fresh valid COMMAND
for that configured epoch.

A malformed CONFIG request, incompatible protocol version, mismatched hardware
hash, or invalid local configuration MUST be rejected without changing the
accepted session state. No `uint32` `reset_epoch` value alone is an invalid
epoch, and an otherwise valid CONFIG request MUST NOT be rejected merely
because its epoch differs from the previous configured epoch.

For deterministic rejection behavior, STM32 MUST evaluate local configuration
validity before comparing `hardware_config_hash`. If local configuration is
invalid, STM32 MUST return `CONFIG_REJECTED` with
`REJECT_LOCAL_CONFIG_INVALID`, even when the request hash also differs from
the local hash. STM32 MUST compare the request hash and return
`REJECT_HASH_MISMATCH` only when local configuration is valid.

#### CONFIG_STATUS — STM32 to Pi

The CONFIG status payload is exactly 50 bytes.

| Offset | Field | Type | Purpose |
| --- | --- | --- | --- |
| 0 | `config_sequence` | `uint32_le` | Echo CONFIG request sequence |
| 4 | `reset_epoch` | `uint32_le` | Echo requested/configured epoch |
| 8 | `hardware_config_hash` | `uint8[32]` | Echo requested hash |
| 40 | `mcu_boot_id` | `uint64_le` | Bind the status to a running MCU instance |
| 48 | `config_status` | `uint8` | Accepted or rejected configuration status |
| 49 | `reject_reason` | `uint8` | Reject diagnostic when status is not accepted |

The following CONFIG status constants are `PROPOSED_FOR_APPROVAL` normative
values for golden-vector implementation and test:

| Constant | Value |
| --- | --- |
| `CONFIG_ACCEPTED` | `0x01` |
| `CONFIG_REJECTED` | `0x02` |

The following reject reasons are `PROPOSED_FOR_APPROVAL` normative values:

| Constant | Value |
| --- | --- |
| `REJECT_NONE` | `0x00` |
| `REJECT_HASH_MISMATCH` | `0x01` |
| `REJECT_LOCAL_CONFIG_INVALID` | `0x02` |

`REJECT_INVALID_EPOCH` does not exist. No reject reason may reject an
otherwise valid CONFIG_REQUEST solely because of its `uint32` `reset_epoch`
value.

COBS failure, CRC failure, malformed raw header, header/payload-length
mismatch, unsupported protocol version, or unknown message type MUST be
dropped safely and MUST NOT produce CONFIG_STATUS. CONFIG_STATUS is emitted
only for a CONFIG_REQUEST that decoded successfully, has a supported protocol
version, and has the exact 40-byte payload length. Such a request with a hash
mismatch MUST return `CONFIG_REJECTED` with `REJECT_HASH_MISMATCH`; one with
invalid local configuration MUST return `CONFIG_REJECTED` with
`REJECT_LOCAL_CONFIG_INVALID`.

Pi MUST treat the handshake as successful only when all of the following are
true:

1. CONFIG_STATUS echoes the transmitted `config_sequence`.
2. CONFIG_STATUS echoes the transmitted `reset_epoch`.
3. CONFIG_STATUS echoes the Pi-sent `hardware_config_hash` byte-for-byte.
4. `config_status` indicates accepted.
5. CONFIG_STATUS `mcu_boot_id` equals the most recent valid TELEMETRY
   `mcu_boot_id`.

STM32 does not have a reliable signal for Pi restart or physical UART
reconnect. Pi MUST stop its command stream after detecting its own restart or
reconnect and send a new valid CONFIG_REQUEST before sending COMMAND again.
Loss of valid COMMAND is handled by the STM32 command watchdog and results in
the contract-defined safe stop.

### 4.6 Frame and buffer limits

| Frame | Raw frame: header + payload + CRC | Maximum wire frame: COBS + delimiter |
| --- | --- | --- |
| COMMAND | 26 bytes | 28 bytes |
| TELEMETRY | 71 bytes | 73 bytes |
| CONFIG_REQUEST | 46 bytes | 48 bytes |
| CONFIG_STATUS | 56 bytes | 58 bytes |

- Raw-frame storage MUST be at least 96 bytes.
- The COBS receive buffer, including its delimiter capacity, MUST be at least
  98 bytes.
- Implementations MUST reject frames exceeding these limits safely; they must
  not truncate, partially parse, or refresh the watchdog from them.

## 5. Reset, reboot, and counter semantics — PROPOSED_FOR_APPROVAL

- `mcu_boot_id` MUST change after every MCU reboot. Its persistent flash-journal
  generation algorithm is `REQUIRED_DECISION`.
- STM32 enters `BOOT_OR_UNCONFIGURED` with motor disabled after reboot.
- A valid CONFIG request creates or resets the configured control session as
  specified in section 4.5. CONFIG does not by itself enable motor output.
- COMMAND with a nonmatching epoch MUST be rejected without changing
  `last_accepted_command_sequence` or refreshing the watchdog.
- Pi bridge invalidates cached telemetry sequence and counter state after a
  boot-ID or epoch change, and publishes no fabricated delta across it.
- Telemetry sequence initialization, counter-wrap recovery, MCU monotonic-time
  discontinuity handling, UART retry/recovery policy, command rate, telemetry
  rate, and watchdog timeout remain `REQUIRED_DECISION`.

## 6. Safety and power boundary

### Physical E-stop boundary

```text
E-stop NC
  -> hardware gate
  -> STBY_SAFE = LOW on both TB6612 modules

PB10 / MCU_MOTOR_ENABLE GPIO output
  -> input of the hardware gate
```

- Opening the NC E-stop path must cause the hardware gate to force `STBY_SAFE = LOW` for both TB6612 drivers.
- `MCU_MOTOR_ENABLE` is an STM32 GPIO output, but only an input to the hardware gate.
- `MCU_MOTOR_ENABLE` must not directly override, bypass, or defeat the physical E-stop.
- STM32 reads E-stop state only through an auxiliary contact for telemetry and diagnostics.
- The physical E-stop path remains independent of Linux, ROS 2, DDS, and Python.
- Only the physical E-stop is required to be latched and require manual reset.
- Latching and manual-reset behavior for non-E-stop faults are `REQUIRED_DECISION`.

### Power and ground boundary

```text
LiPo 3S -> fuse -> VM of both TB6612 modules
LiPo 3S -> XL4016 -> Raspberry Pi 5
STM32 -> regulated, verified power path: REQUIRED_DECISION
TB6612 VCC logic = 3.3 V
Common GND: Raspberry Pi, STM32, and motor drivers
```

- `VM` must never be connected to a TB6612 logic-supply pin.
- STM32 must use a regulated and verified power path: `REQUIRED_DECISION`.
- A TB6612 motor-driver output must not be used as STM32's primary power source.
- XL4016 output setting, current capability, fuse characteristics, wire gauge, connector ratings, decoupling, brownout behavior, and power-up sequencing are `TBD_MEASURED` or `REQUIRED_DECISION` as applicable.
- Hardware-gate propagation delay, driver-fault integration, and E-stop auxiliary-contact polarity are `REQUIRED_DECISION`.

## 7. Hardware configuration provenance

The authoritative source for real wheel configuration is
`artifacts/hardware/<hardware_profile_id>/hardware_manifest.yaml`. It is the
only hardware-configuration input to `hardware_config_hash`.

The approved manifest must define:

| Configuration | Required use |
| --- | --- |
| Logical wheel order `FL`, `FR`, `RL`, `RR` | Firmware, telemetry, bridge, and tests |
| Physical mapping and wheel signs | Firmware/bridge validation |
| Encoder CPR and gear ratio | Tick-scale calculation |
| Wheel radius or diameter, wheelbase, and track | Inverse and forward kinematics |
| Other hardware configuration | Safety and motor-enable validation |

The following are provisional hardware inputs only. They are not approved manifest values:

| Input | Provisional value |
| --- | --- |
| Wheel diameter | 97 mm |
| Wheelbase | 210 mm |
| Track | approximately 190 mm |
| Gear ratio | 21.3:1 |
| Hall encoder | AB, 11 pulse/channel |

No ticks-per-wheel-revolution value may be derived for the contract until encoder interpretation, quadrature mode, gear ratio, and physical measurements are verified.

### 7.1 PROPOSED_FOR_APPROVAL hash algorithm

1. A strict YAML parser reads the manifest and MUST reject malformed input,
   duplicate mapping keys, unsupported tags, non-JSON values, and other input
   that cannot be represented by RFC8785 JCS.
2. The complete parsed manifest mapping, including its `hash_contract` mapping,
   is serialized as RFC8785 JCS UTF-8. `approval.yaml` is excluded completely
   and is never parsed as hash input.
3. The digest input bytes are exactly:

   ```text
   UTF-8("mecanum_hardware_config_hash/v1") ||
   0x00 ||
   UTF-8(RFC8785_JCS(complete_manifest_mapping))
   ```

4. `hardware_config_hash` is the raw 32-byte SHA-256 digest of those bytes.
   CONFIG_REQUEST carries those 32 raw bytes, not hexadecimal text.

`0x00` is the domain-separator delimiter. Its exact presence and position MUST
match the hardware manifest contract, generator, firmware, and Pi bridge.

Firmware receives the digest as a generated read-only byte array; it MUST NOT
parse YAML. The Pi bridge uses generated wheel-geometry configuration produced
from the same manifest input and sends the same raw digest in CONFIG_REQUEST.
Firmware and bridge MUST compare equal raw 32-byte hashes before motor enable.

`approval.yaml` records evidence, approval status, and an approved hash for
governance only. It is not an input to the digest; a changed approval status
cannot silently alter geometry, pin mapping, telemetry order, or hash.

The generator implementation, generated-file format, reproducible build gate,
and release authorization mechanism are `REQUIRED_DECISION`. Until they are
resolved, absent, invalid, mismatched, or unapproved generated configuration
MUST keep motor output disabled.

## 8. REQUIRED_DECISION registry

The following must be selected and recorded before the dependent build,
firmware, bridge, or deployment work may claim approval:

| Area | Required decision |
| --- | --- |
| `mcu_boot_id` | Persistent flash-journal algorithm, endurance treatment, and boot-ID initialization behavior |
| UART operation | Baud rate, flow control, command/telemetry rates, retry and reconnect policy, and electrical validation bounds |
| Command safety | Watchdog timeout, command timeout/rate, zero-command interaction, and approved safe-stop/recovery policy |
| Counter/time recovery | Telemetry sequence initialization, counter-wrap recovery, and MCU monotonic-time discontinuity handling |
| Generated configuration | Generator implementation, generated-file format, reproducible build gate, and release authorization mechanism |
| Non-E-stop faults | Fault-latch and manual-reset behavior where it is not the physical E-stop |
| STM32 power/safety integration | Verified regulated STM32 power path, gate propagation delay, driver-fault integration, and E-stop auxiliary-contact polarity |

## 9. TBD_MEASURED registry

The following values remain `TBD_MEASURED` until evidence is recorded and approved:

| Measurement area | Required evidence |
| --- | --- |
| TB6612 | Current and temperature under representative motor loads |
| PWM | Frequency, duty envelope, ramp behavior, and motor response |
| Motion | Velocity, acceleration, jerk, and braking envelope in all holonomic directions and yaw |
| PID | Gains and control-loop timing |
| Encoders | Scale, signs, geometry, counter behavior, and wheel slip |
| UART | Latency, jitter, packet-loss behavior, and sustainable telemetry rate |
| Runtime safety | Command TTL, MCU watchdog timeout, and heartbeat timeout |
| End-to-end safety | Sensor-to-actuator latency and stopping distance |
| E-stop | Hardware-gate response and motor-disable proof under system faults |
| Power | Integrity, voltage droop, thermal behavior, and brownout recovery |

Every measurement record must identify method, equipment, repetitions, hardware/firmware version, raw-data path, checksum, reviewer, date, and status.

## 10. Verification matrix before HIL and deploy_real

| Area | Required evidence |
| --- | --- |
| UART | Framing, corruption recovery, packet loss, reconnect, sequence handling |
| Protocol | Version mismatch rejection, malformed packet handling, reset/reboot behavior |
| Encoders | `FL`/`FR`/`RL`/`RR` mapping, signs, cumulative counting, wrap, discontinuity handling |
| Kinematics | STM32 inverse kinematics and Pi forward kinematics against the approved hardware manifest |
| Motor control | PWM/direction behavior, PID response, safe startup state |
| Watchdog | Loss of valid command causes the approved safe action within measured bounds |
| E-stop | NC E-stop hardwire forces `STBY_SAFE = LOW` on both TB6612 modules; `MCU_MOTOR_ENABLE` cannot defeat it |
| Faults | Heartbeat `FAULT_*` mapping, diagnostics, and approved recovery behavior |
| TB6612 | Bench current and thermal evidence before loaded operation |
| Bridge | `/wheel/odometry_raw` correctness, no TF publication, reboot/reset/packet-loss tests |

HIL is permitted and required to create measurement evidence.

`deploy_real` and Gate 4 remain blocked until all measurements required by their safety and deployment contracts are recorded as `VALID`, the required protocol decisions are approved, and the applicable safety evidence is complete.
