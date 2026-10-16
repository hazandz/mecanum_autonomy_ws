# WP-06 Command Safety Core — atomic L2 decision and implementation

## Classification and provenance

- Work package: `WP06_COMMAND_SAFETY_CORE_ATOMIC_L2`
- Classification: `L2_COMMAND_SAFETY_CORE_PURE_LOGIC_IMPLEMENTATION`
- Exact source base: `d0b1234f1c23961c5dd7c04a35c9ec39d6077629`
- Architecture authority SHA-256: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`
- Receipt v2 source SHA-256: `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`
- Receipt ROSIDL atomic decision SHA-256: `35247070a76d6c98bd538ec68f47f6b4a41458f3f4b136d066baccba4ab87388`
- Receipt ROSIDL atomic evidence SHA-256: `75d7c1d07d36cce2502e994468989572d948c90bee8580953dd5e6194fede045`
- Evidence level: `PURE_CORE_SOURCE_AND_OFFLINE_UNIT_TEST_ONLY`

## Decision

The candidate adds an immutable, standard-library-only Python core that evaluates internal command candidates against explicitly injected context, health, steady-time, and motion-limit values. Its output is `SafetyCommandDecision`, an unpublished decision value. Invalid, missing, stale, ambiguous, wrong-source, wrong-frame, wrong-epoch/generation, non-finite, or unhealthy inputs fail closed to zero. E-stop and critical fault return zero immediately without normal acceleration/jerk limiting. Normal commands are constrained by injected hard velocity, acceleration, and jerk limits; this candidate supplies no operating limit values.

This is offline pure logic implementation only. It is not a runtime `SafetySupervisor`, ROS node, command arbiter, transport, collision shield, or physical safety implementation. `collision_clear` is an injected boundary assertion; the core does not calculate collision geometry or TTC. Hardware E-stop remains an external boundary. A future `FinalTwistPublisher` alone may publish `/cmd_vel`; only after an actual local publish may a receipt v2 be created.

The core does not import ROS/generated messages, create a topic/publisher/subscriber, create a receipt, call `FinalIssuedCommandReceipt`, or implement `FinalTwistPublisher`. It creates no runtime profile, `ResolvedConfigV3`, `config_hash`, runtime evidence, Gate B transition, or runtime authorization. `MotionLimits` must be supplied by a future resolved profile; this candidate does not pin operating values.

After independent audit PASS for the exact candidate, separate User authorization for that exact commit, fast-forward integration, and remote-ref verification, the source disposition may be recorded as `WP06_COMMAND_SAFETY_CORE: IMPLEMENTED_OFFLINE_ONLY`. This decision itself does not change WP-04, WP-05, Gate A, Gate B, or runtime approval.

## Preserved state

`WP-04: BLOCKED_BY_CONTRACT`

`WP-05: OPEN`

`GATE_A_STRUCTURAL_PRIMITIVES: PASSED`

`GATE_B: NOT_STARTED`

`RUNTIME_APPROVED: NOT_APPROVED`
