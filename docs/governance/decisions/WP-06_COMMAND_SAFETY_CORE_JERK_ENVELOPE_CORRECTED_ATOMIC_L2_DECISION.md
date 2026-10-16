# WP06 command safety core — jerk-envelope corrected atomic L2 candidate

## Classification and candidate lineage

Classification: `L2_COMMAND_SAFETY_CORE_JERK_ENVELOPE_CORRECTED_PURE_LOGIC_IMPLEMENTATION`.

This candidate is created independently from exact integration base
`d0b1234f1c23961c5dd7c04a35c9ec39d6077629`. It does not cherry-pick, rebase,
merge, copy, or amend either rejected candidate
`a3c9f7074f96a2d5632bb1cddd3ecffb18e1c58a` or
`89f064af2af1afbc86cf9e10eb43c974709ae1e0`.

The candidate retains the prior F-01/F-02/F-03 corrections and addresses
F-04 by intersecting, per axis, the hard-velocity-derived acceleration
interval, acceleration interval, and jerk interval centered on the previous
acceleration. If the intersection is empty, the result is `FAULT`, zero, and
command-cache invalidation with reason
`INFEASIBLE_HARD_VELOCITY_ACCELERATION_JERK_ENVELOPE`. There is no
post-limiter velocity clipping that could invalidate the checked acceleration
or jerk.

## Retained safety contract

- `reset_epoch` and `runtime_generation` are exact `uint32`; `sequence` and
  `source_instance_id` are exact `uint64`.
- E-stop and critical fault latch, bypass normal ramps to zero, and do not
  auto-resume. Release requires explicit manual-reset authorization, a
  completed reset, and a changed reset epoch; the release cycle is zero and
  clears command identity/cache.
- Reset, epoch/generation change, source handover, and source-instance
  handover each create a zero barrier and invalidate accepted command state;
  a fresh command is considered only on a later cycle.
- TTL uses local steady time. Wrong frame, malformed, non-finite, stale,
  ambiguous, or unhealthy inputs fail closed. Limits are injected and not
  selected or pinned here.

## Evidence and non-claims

Evidence level: `PURE_CORE_SOURCE_AND_OFFLINE_UNIT_TEST_ONLY`.

The output remains an unpublished `SafetyCommandDecision`, not a receipt and
not a claim that a command was published. This candidate does not create a
runtime SafetySupervisor, ROS node, `FinalTwistPublisher`, `/cmd_vel`
publisher, receipt runtime, collision/TTC integration, physical E-stop
integration, profile, `ResolvedConfigV3`, `config_hash`, runtime evidence, or
runtime authorization. It does not establish physical braking or runtime
safety. The future `FinalTwistPublisher` remains the sole `/cmd_vel` publisher
under the Architecture; receipt v2 may be produced only after actual local
publish in a later authorized work package. Hardware E-stop remains an
external boundary.

After independent audit PASS for the exact candidate, separate User
authorization for that exact commit, integration, and remote-ref verification,
the status may be recorded as `WP06_COMMAND_SAFETY_CORE:
IMPLEMENTED_OFFLINE_ONLY`. Until then this is a review candidate. No WP-04,
WP-05, Gate A, Gate B, or runtime approval status changes. `RUNTIME_APPROVED:
NOT_APPROVED` remains unchanged.
