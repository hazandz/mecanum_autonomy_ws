# Step-7 Run005 attempt_002 — Fuel cache case-normalization correction

Classification: `L1_CANONICAL_FUEL_CACHE_PATH_CASE_NORMALIZATION_CORRECTION`. Exact base and required sole parent: `71ca32471f8e042a0048d319ca39cb9deff0c6f4`. Integration base: `f7f98c683d59cf4c62e462da9f37d4ffb2455c80`. Architecture SHA-256: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.

## Immutable attempt_001 disposition

Run005 attempt_001 was invoked once and is immutable. Its terminal outcome is `STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`; the root failure is `SIM_EVAL_FUEL_CACHE_MODEL_MISSING:OpenRobotics/Depot`, followed by `BOOTSTRAP_EXITED_BEFORE_READINESS`. The run record SHA-256 is `374565871f170fb2cbd7a9c089a2d0f47dd4e34d217357769259ef74f5409040`. This was the bootstrap's uppercase filesystem mapping disagreeing with the host preflight's canonical lowercase mapping. It is not a LiDAR, Nav2, Gate B, safety, TF, or robot failure. No retry or reinterpretation is permitted.

## Attempt_002 correction and scope

The SDF retains the exact case-sensitive Fuel URIs. Bootstrap cache lookup uses only the lowercase filesystem parents `fuel.gazebosim.org/openrobotics/models/depot` and `fuel.gazebosim.org/movai/models/tugbot`, matching Run005 host preflight. Uppercase owner/model parents reject. Exact URI set, one positive-integer version, required `model.config` and `model.sdf`, and root-contained path checks remain fail-closed. No host cache was changed and no Fuel download is included.

The bootstrap/host-preflight regression test requires both validators to resolve the same canonical lowercase paths and both to reject uppercase layout. Historical attempt_001 pins are read only from exact Git blobs at `71ca32471f8e042a0048d319ca39cb9deff0c6f4` and checked by SHA-256 and byte size with no checkout fallback. The active Run005 guard seed is for attempt_002 only: pending, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`. Attempt_002 requires its own exact candidate commit, independent audit, and new Owner authorization.

The current attempt_002 cumulative scope is exactly 13 paths (`RUN005_ATTEMPT_002_PATHS`), including the isolated-checkout runner correction, verified by exact set equality in dirty and committed states. Attempt_001 remains the immutable exact 13-path diff from `b7105ccb651da6d0dcb916d7544481f7beacaae1` to `71ca32471f8e042a0048d319ca39cb9deff0c6f4`. The runtime source-pin inventory remains 22 unique entries, independent from the 13 changed paths.

## Offline verification

- Isolated-checkout runner tests: 36 passed; focused bootstrap/scope tests: 29 passed.
- Full Step-7 tools suite: 185 passed.
- Full `mecanum_nav_bringup/test`: 239 passed.
- Full `mecanum_nav_rl/test`: 707 passed using the external install base.
- Six-package external colcon build: PASS.
- Observer and ROSIDL colcon tests: 25 passed, zero failures/errors.
- Python compilation, installed bootstrap launch byte equality, 22/22 source pins, canonical JSON/UTF-8/no-BOM/no-final-newline/duplicate-key, YAML/XML parsing, historical Git-blob checks, exact scope, and diff checks: PASS.

These are source/offline results only. No runtime was executed. Guard SHA-256 `ad5feb501244511edbe2fe9aded8e53d984453182aff0b3d14939e8a46dff181`; evidence SHA-256 `79ebedc1c3831760be2b8c5bc2c588588cd237e377d1ba0ff6ff759ff2ee1ed2`; guard-manifest SHA-256 `b95b01b7f98490ae9e157e471790d1d36cb835c8330f91c1ddfc2b1de09b4caa`. Run005 remains pending, capacity one, acquisition zero, and `runtime_authorization=NOT_GRANTED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling: `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.


## Corrective: isolated local runtime checkout

The attempt_002 runner creates the runtime checkout with a local `git clone --no-hardlinks --no-checkout` from the exact clean source checkout, checks out the exact review commit detached, and sets the destination `origin` to the official repository. Destination `.git` metadata is private, the checkout is clean and exact, and source repository metadata/ref/status are verified unchanged. Linked `git worktree` operations and network cloning are prohibited. Regression coverage uses a local Git fixture with read-only source metadata and verifies private metadata, no alternates, detached HEAD, clean status, official origin, and unchanged source metadata.

This corrective commit is based on `72d04391a9d6d83e3e18589212d566f17dc220d1`, the prior attempt_002 candidate. It does not alter attempt_001 or attempt_002 guard semantics, Fuel/map/TF/safety/Gate-B behavior, or retry policy. The exact cumulative attempt_002 scope is 13 paths; its current source-pin inventory remains 22 unique paths. A new exact candidate commit, independent audit, and Owner authorization remain prerequisites before any runtime invocation.

Current corrective record hashes: guard `4be7b4bd00324ba023c11a2717cdfcc91f8d9418ace98b47de40e2f181cc178f`; evidence `6f4ad54ecfd3b51a17c3a1251ef1322a63b4a9222fca1c47220dfa0bcdb8a24b`; guard manifest `22e1d9b6bc9d013a831b0ffbb06bddce8a18b05c1ab6092fac88a42a61761818`.


## Corrective: partition ownership and Nav2 pre-acquire closure

This L1 corrective is based on exact `87af41f45d721969f2767d36291252e3b14e3dcb`. It supersedes only current corrective scope and verification metadata; the prior attempt_002 13-path scope is preserved as historical. The direct corrective scope from that base is the exact 16-path set recorded in the current evidence JSON and manifest.

The child state-estimation launch now requires a non-empty caller-owned `gz_partition`, rejects missing/blank values with `SIM_EVAL_GZ_PARTITION_REQUIRED`, exports that exact value as `GZ_PARTITION`, and forwards it unchanged to wheel/IMU ingress. The WP06 partition literal is not a runtime routing condition. `use_sim_time=true` remains fail-closed. `mecanum_nav_bringup/package.xml` declares the four Step-7 Nav2 providers once, after the preserved WP05 common-root block and existing profile-specific dependencies. The runner checks seven Nav2 node package prefixes/executables and four plugin-provider prefixes before guard acquisition, then checks installed bytes for 15 runtime launch/config artifacts.

Run005 attempt_002 invocation_002 remains immutable: `COMPOSITE_EXITED_BEFORE_READINESS`, caused by `LEGACY_WP06_PARTITION_LOCK`; its consumed guard and evidence are untouched and it was not retried. Attempt_001 remains the separate immutable Fuel-case failure. This offline corrective did not run a runtime or official runner.

The current guard seed remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, and `runtime_authorization=NOT_GRANTED`; Gate B remains `NOT_STARTED`, `RUNTIME_APPROVED=NOT_APPROVED`. Current Run005 inventory is 34 unique SHA-256/size source pins, independent from the 16 changed paths. Evidence ceiling: `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.

Offline verification: focused tests 89 passed; Step-7 tools 205 passed; `mecanum_nav_bringup/test` 244 passed; `mecanum_nav_rl/test` 707 passed; six-package external colcon build PASS; observer 13 C++ cases PASS; ROSIDL 8 pytest cases PASS; installed source-byte closure 15/15 PASS; source pins 34/34 PASS.

Current record references: guard SHA-256 `1c8468d3df731719522e64d8b21370ce33543ff07f9c1835aa920bd5c8f0b520`; evidence SHA-256 `265807e5cc1da274dd0f08ffcdede4791838d6e334904c1dbfbf2b6d3341fe51`; guard-manifest SHA-256 `424104bafd0e164720499e6e5204a7de4d7916c87ac1d596db92ae6093c0bc87`.
