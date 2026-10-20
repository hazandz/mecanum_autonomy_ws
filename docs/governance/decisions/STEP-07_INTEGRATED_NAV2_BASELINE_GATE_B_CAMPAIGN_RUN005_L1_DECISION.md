# Step-7 Run005 attempt_002 — Fuel cache case-normalization correction

Classification: `L1_CANONICAL_FUEL_CACHE_PATH_CASE_NORMALIZATION_CORRECTION`. Exact base and required sole parent: `71ca32471f8e042a0048d319ca39cb9deff0c6f4`. Integration base: `f7f98c683d59cf4c62e462da9f37d4ffb2455c80`. Architecture SHA-256: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.

## Immutable attempt_001 disposition

Run005 attempt_001 was invoked once and is immutable. Its terminal outcome is `STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`; the root failure is `SIM_EVAL_FUEL_CACHE_MODEL_MISSING:OpenRobotics/Depot`, followed by `BOOTSTRAP_EXITED_BEFORE_READINESS`. The run record SHA-256 is `374565871f170fb2cbd7a9c089a2d0f47dd4e34d217357769259ef74f5409040`. This was the bootstrap's uppercase filesystem mapping disagreeing with the host preflight's canonical lowercase mapping. It is not a LiDAR, Nav2, Gate B, safety, TF, or robot failure. No retry or reinterpretation is permitted.

## Attempt_002 correction and scope

The SDF retains the exact case-sensitive Fuel URIs. Bootstrap cache lookup uses only the lowercase filesystem parents `fuel.gazebosim.org/openrobotics/models/depot` and `fuel.gazebosim.org/movai/models/tugbot`, matching Run005 host preflight. Uppercase owner/model parents reject. Exact URI set, one positive-integer version, required `model.config` and `model.sdf`, and root-contained path checks remain fail-closed. No host cache was changed and no Fuel download is included.

The bootstrap/host-preflight regression test requires both validators to resolve the same canonical lowercase paths and both to reject uppercase layout. Historical attempt_001 pins are read only from exact Git blobs at `71ca32471f8e042a0048d319ca39cb9deff0c6f4` and checked by SHA-256 and byte size with no checkout fallback. The active Run005 guard seed is for attempt_002 only: pending, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`. Attempt_002 requires its own exact candidate commit, independent audit, and new Owner authorization.

The direct attempt_002 corrective scope is exactly 12 paths (`RUN005_ATTEMPT_002_PATHS`), verified by exact set equality in dirty and committed states. Attempt_001 remains the immutable exact 13-path diff from `b7105ccb651da6d0dcb916d7544481f7beacaae1` to `71ca32471f8e042a0048d319ca39cb9deff0c6f4`. The runtime source-pin inventory remains 22 unique entries, independent from the 12 changed paths.

## Offline verification

- Focused bootstrap/Run005/scope suite: 72 passed.
- Full Step-7 tools suite: 184 passed.
- Full `mecanum_nav_bringup/test`: 239 passed.
- Full `mecanum_nav_rl/test`: 707 passed using the external install base.
- Six-package external colcon build: PASS.
- Observer and ROSIDL colcon tests: 25 passed, zero failures/errors.
- Python compilation, installed bootstrap launch byte equality, 22/22 source pins, canonical JSON/UTF-8/no-BOM/no-final-newline/duplicate-key, YAML/XML parsing, historical Git-blob checks, exact scope, and diff checks: PASS.

These are source/offline results only. No runtime was executed. Guard SHA-256 `ad5feb501244511edbe2fe9aded8e53d984453182aff0b3d14939e8a46dff181`; evidence SHA-256 `79ebedc1c3831760be2b8c5bc2c588588cd237e377d1ba0ff6ff759ff2ee1ed2`; guard-manifest SHA-256 `b95b01b7f98490ae9e157e471790d1d36cb835c8330f91c1ddfc2b1de09b4caa`. Run005 remains pending, capacity one, acquisition zero, and `runtime_authorization=NOT_GRANTED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling: `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.
