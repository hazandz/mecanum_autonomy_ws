# STM32 TELEMETRY v1 — Decision Record (DRAFT)

**Status:** `PENDING_USER_APPROVAL`
**Scope:** Decision draft only. This record does not authorize firmware, UART, motor, or hardware changes and does not replace the Pi–STM32 interface contract.

## Authority and purpose

This draft is derived from:

1. `docs/MECANUM_NAV_DRL_Architecture.docx`
2. `docs/MECANUM_NAV_DRL_Project_Tree.txt`
3. `docs/Pi_STM32_Interface_Contract.md`
4. `docs/Pi_STM32_UART_v1_Golden_Vectors.md`
5. `docs/STM32_Firmware_Architecture.md`

The proposed decisions below require user approval. Any decision that changes the Pi–STM32 protocol contract must also be reflected in that contract before implementation.

## Decision objective

> TELEMETRY v1 đầy đủ chỉ được phát sau CONFIG session hợp lệ; không có pre-config telemetry v1.

`CONFIG_STATUS` remains the protocol response to a valid `CONFIG_REQUEST`. After it is accepted, the first valid TELEMETRY can carry the real `mcu_boot_id` and configured `reset_epoch`, allowing the Pi to complete the contract-defined handshake check without inventing an unknown epoch sentinel.

## D-02 / D-08 compatibility constraint

The former D-08 proposal, USART6 TX-only on PA11, and D-02 cannot both be approved: a CONFIG session requires STM32 reception of `CONFIG_REQUEST` on PA12, while TX-only removes that RX capability. D-08 below therefore replaces the former TX-only proposal. It limits UART scope to CONFIG receive and telemetry/config-status transmit; it does not create a COMMAND receive path.

## Proposed decisions

| ID | Decision | Proposed value or approach | Reason | Remaining risk | Status |
|---|---|---|---|---|---|
| D-01 | `mcu_boot_id` | Use an append-only, power-loss-tolerant flash journal to allocate a new `uint64` boot ID on every MCU reboot. Include integrity checking and explicit exhaustion handling. | STM32F411 has no hardware RNG; a persistent allocator provides a value that changes across reboot for the protocol handshake. | Flash wear, brownout recovery, journal layout, reserved flash region, and exhaustion policy still need detailed design and tests. | `PENDING_USER_APPROVAL` |
| D-02 | TELEMETRY session gate | Do not emit complete TELEMETRY v1 before a valid CONFIG session. A valid CONFIG clears command state, returns `CONFIG_STATUS`, and enters the configured/motor-disabled state; only then may periodic TELEMETRY start. | `reset_epoch` is meaningful only as the configured session epoch. The contract defines no `0 = unknown` sentinel. | Exact startup ordering, including when the Pi obtains the first valid TELEMETRY needed to verify `mcu_boot_id`, must be tested against the handshake implementation. | `PENDING_USER_APPROVAL` |
| D-03 | MCU monotonic time | Use TIM11 configured as a 1 MHz free-running counter and extend it in firmware to a monotonic `uint64` microsecond value. | TIM1, TIM2, TIM4, and TIM5 are encoder counters; TIM3 is motor PWM; TIM10 is the current HAL timebase. TIM11 is the proposed unused timer resource. | TIM11 is 16-bit and shares an interrupt vector with TIM1 trigger/commutation; overflow correctness, clock configuration, NVIC ownership, and wrap tests are required. | `PENDING_USER_APPROVAL` |
| D-04 | Encoder telemetry snapshot | Maintain cumulative `int64` counts in wheel order FL, FR, RL, RR and expose one coherent four-wheel snapshot for TELEMETRY serialization. | TELEMETRY v1 requires four `int64` cumulative ticks; the current diagnostic positions are `int32` and are not yet a contract-ready coherent snapshot. | Atomicity/critical-section design, 16-bit and 32-bit timer wrap extension, sample coherency, and host/HIL wrap tests remain required. | `PENDING_USER_APPROVAL` |
| D-05 | Fault aggregation | Introduce a single fault aggregator before firmware may report `FAULT_NONE = 0`; it must only use the existing allowed STM32 `Heartbeat.msg` bit values. | A zero mask must mean that all approved STM32 fault inputs are represented and currently inactive, not that the implementation has omitted them. | Fault source coverage, latching/clearing rules, and mapping for local UART, watchdog, control-loop, driver, encoder, and E-stop conditions remain unresolved. No new ROS fault constant is proposed. | `PENDING_USER_APPROVAL` |
| D-06 | E-stop auxiliary telemetry | Keep `estop_aux_active` pending until the auxiliary contact input, electrical polarity, pull configuration, debounce, and fault interpretation are specified and tested. | The physical NC E-stop hardware gate remains independent of firmware; telemetry must not fabricate its auxiliary status. | Pin and circuit evidence are absent; no complete TELEMETRY v1 may claim a trustworthy E-stop auxiliary value until this is resolved. | `PENDING_USER_APPROVAL` |
| D-07 | No accepted command semantics | Keep the representation of “no accepted command yet” pending. Do not invent a sentinel for `last_accepted_command_sequence`; no complete TELEMETRY v1 is emitted until this semantic is specified. | TELEMETRY v1 has a required sequence field but the contract does not define a sentinel or pre-command meaning. | The decision may require a contract clarification or versioned contract change before implementation. | `PENDING_USER_APPROVAL` |
| D-08 | USART6 CONFIG_RX + TELEMETRY_TX, no COMMAND receive path | Retain USART6 PA11 as TX and PA12 as RX. After approval, PA11 may transmit only `CONFIG_STATUS` and periodic TELEMETRY; PA12 may receive and parse only `CONFIG_REQUEST`. COMMAND is not received, parsed, or dispatched. DMA RX, RX interrupt, motor-control paths, and PWM/PID are outside this scope. | D-02 requires a CONFIG session, so the STM32 must retain an RX capability for `CONFIG_REQUEST`. Explicitly excluding COMMAND preserves the telemetry/config-only safety boundary. | This requires explicit CubeMX/pinout approval, physical crossed TX/RX and 3.3 V TTL evidence, and a bounded, non-DMA/non-interrupt receive design before runtime work. It does not authorize any UART runtime before the dependent decisions are approved. | `PENDING_USER_APPROVAL` |
| D-09 | UART line settings | Use USART6 at 115200 baud, 8 data bits, no parity, 1 stop bit, and no hardware flow control. | This is the currently generated CubeMX configuration and is a straightforward initial setting for the proposed UART v1 codec. | The interface contract still marks baud/rate and electrical transport evidence as decisions; link margin, cable/noise behavior, and Pi configuration require verification. D-02 and the replacement D-08 must both be approved before any UART runtime. | `PENDING_USER_APPROVAL` |
| D-10 | Telemetry rate and TX fault/recovery policy | Leave the periodic rate, TX timeout/error handling, queue/buffer ownership, and recovery behavior as explicit pending decisions. | No safe numerical rate or recovery policy has been measured or approved, and none should be guessed from simulation. | Without these definitions, firmware cannot have a complete periodic-TX behavior or a valid test plan for congestion and transport faults. | `PENDING_USER_APPROVAL` |

## Proposed handshake ordering

This is a design sequence only. It does not authorize UART runtime or any motor behavior.

1. STM32 starts in the safe baseline with motor disabled.
2. Pi opens the transport.
3. Only after separate approval, Pi sends `CONFIG_REQUEST`.
4. STM32 validates CONFIG and creates or accepts the required session semantics.
5. STM32 returns `CONFIG_STATUS` on PA11.
6. Only after CONFIG is accepted does STM32 begin periodic TELEMETRY v1.
7. Pi treats the session as valid only when `CONFIG_STATUS` and TELEMETRY agree on every field required by the interface contract, including the echoed configuration data, `reset_epoch`, `hardware_config_hash`, and `mcu_boot_id` relationship.

COMMAND is absent from every step: STM32 does not receive, parse, dispatch, acknowledge, or act on COMMAND in this scope.

## Not permitted before approval

The following remain prohibited before the relevant decisions are approved and their required contract updates, if any, are complete:

- UART TX runtime.
- CONFIG RX or TX runtime.
- COMMAND RX or TX runtime.
- Motor enable.
- PWM or PID implementation/use.
- Any change to `approval.yaml`.

The current hardware approval remains DRAFT with motor enable disallowed. This document does not change that boundary.

## User approval checklist

### D-01 — Flash-journal `mcu_boot_id`

- [ ] APPROVED
- [ ] DEFERRED

### D-02 — TELEMETRY only after CONFIG accepted

- [ ] APPROVED
- [ ] DEFERRED

### D-03 — TIM11 1 MHz extended to `uint64` microseconds

- [ ] APPROVED
- [ ] DEFERRED

### D-04 — Coherent `int64` encoder snapshot

- [ ] APPROVED
- [ ] DEFERRED

### D-05 — Fault aggregator before `FAULT_NONE = 0`

- [ ] APPROVED
- [ ] DEFERRED

### D-06 — E-stop auxiliary input and polarity

- [ ] APPROVED
- [ ] DEFERRED

### D-07 — No-accepted-command telemetry semantics

- [ ] APPROVED
- [ ] DEFERRED

### D-08 — USART6 CONFIG_RX + TELEMETRY_TX, no COMMAND receive path

- [ ] APPROVED
- [ ] DEFERRED

### D-09 — 115200 8N1 without flow control

- [ ] APPROVED
- [ ] DEFERRED

### D-10 — Telemetry rate and TX fault/recovery policy

- [ ] APPROVED
- [ ] DEFERRED
