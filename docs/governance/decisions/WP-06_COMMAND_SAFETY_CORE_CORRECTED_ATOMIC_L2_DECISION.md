# WP06 Command Safety Core — corrected atomic L2 decision

## Classification and lifecycle

Classification: `L2_COMMAND_SAFETY_CORE_CORRECTED_PURE_LOGIC_IMPLEMENTATION`.

This is a replacement candidate built directly from exact base
`d0b1234f1c23961c5dd7c04a35c9ec39d6077629`. It does not inherit, copy,
cherry-pick, or amend rejected candidate
`a3c9f7074f96a2d5632bb1cddd3ecffb18e1c58a`.

The pure Python core evaluates injected command and health values and returns
an unpublished `SafetyCommandDecision`. It is not a runtime `SafetySupervisor`,
ROS node, command arbiter, `FinalTwistPublisher`, or receipt producer. The
future `FinalTwistPublisher` remains the only component authorized by the
architecture to publish `/cmd_vel`; receipt v2 may be produced only after an
actual local publish in a later, separately authorized work package.

This decision becomes an integrated source/status record only after
independent audit PASS for the exact candidate, separate User authorization
for that exact commit, integration, and remote-ref verification. Until then it
is review-only. No integration or runtime status is asserted here.

## Corrections required by the prior audit

- **F-01 — integer widths:** `sequence` and `source_instance_id` are exact
  `uint64` values (`0..2^64-1`); `reset_epoch` and `runtime_generation` are
  exact `uint32` values (`0..2^32-1`). Separate validators enforce those
  ranges for candidate, context, and stored memory. Python booleans are not
  accepted as integers.
- **F-02 — emergency latch:** active E-stop or critical fault immediately
  selects zero, bypasses acceleration/jerk ramping, latches the emergency
  state and clears accepted-command identity. Clearing the input signal does
  not resume motion. Release requires explicit `manual_reset_authorized`, a
  completed reset, and an expected reset epoch different from the latched
  epoch. The release cycle remains zero and clears all command/sequence
  memory; a fresh command can only be evaluated on a later cycle. There is no
  automatic resume path.
- **F-03 — barriers:** reset-in-progress, reset-epoch change,
  runtime-generation change, source handover, and source-instance handover
  select zero and invalidate command identity/cache for the current cycle.
  Only a fresh command on a subsequent cycle can be considered.

Malformed, missing, stale, ambiguous, non-finite, wrong-frame, wrong-source,
or unhealthy inputs fail closed. TTL uses injected local steady time. Motion
limits are injected values and are not pinned as operational parameters.
`collision_clear` is an input boundary; no collision shield or TTC logic is
implemented. Hardware E-stop remains an external boundary, and this core only
handles injected software safety state.

## Evidence boundary and preserved status

Evidence level: `PURE_CORE_SOURCE_AND_OFFLINE_UNIT_TEST_ONLY`.

This candidate does not implement runtime collision/TTC integration, physical
E-stop integration, ROS interfaces or graph, `/cmd_vel` publisher, receipt
runtime, profile resolution, `ResolvedConfigV3`, `config_hash`, runtime
evidence, Gate B transition, or runtime authorization. `MotionLimits` must be
provided from a future resolved profile; this candidate does not choose or
pin them.

`RUNTIME_APPROVED: NOT_APPROVED` remains unchanged. WP-04, WP-05, Gate A, and
Gate B statuses remain unchanged. Evidence is limited to the source and
authorized offline unit tests; it is not runtime or hardware safety evidence.
