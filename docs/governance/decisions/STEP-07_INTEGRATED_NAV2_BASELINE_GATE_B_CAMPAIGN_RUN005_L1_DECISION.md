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

## Corrective: output-parent preflight and pre-acquire evidence reliability

This L1 corrective is based on `c408ccd2a2f7b11787f725a24e818ffa038e3d36`. It supersedes only the active Run005 attempt_002 runner/output-preflight metadata. No new Run ID, attempt, runtime authorization, or runtime semantics are introduced.

Invocation_003 was invoked once and failed before guard acquisition. The observed pre-acquire exception was `PermissionError: [Errno 1] Operation not permitted` from the unused `socket.if_nameindex()` probe; the runner then failed to persist pre-acquire evidence with `OSError: [Errno 30] Read-only file system`. No evidence bundle was created; the pending source guard was not consumed, no lock was created, and bootstrap/composite/observers were not invoked. The runtime checkout had already been created. This outcome is recorded as `STEP07_NAV2_BASELINE_RUN005_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED`; invocation_003 was not retried.

The runner removes the network-interface probe and validates both absolute, absent output targets before clone/build/host checks/evidence/guard/processes. Each parent must already be a real, non-symlink directory; targets must be distinct and non-nested. An exclusive sentinel is created, written, fsynced, closed, and unlinked. Invalid targets fail with `RUNTIME_OUTPUT_PARENT_INVALID:<runtime_worktree|run_directory>`; inaccessible/read-only parents fail with `RUNTIME_OUTPUT_PARENT_NOT_WRITABLE:<runtime_worktree|run_directory>`. Such failure exits once with the stable literal and performs no secondary evidence write. Existing isolated-clone, package-prefix, partition, Fuel, runtime-Python, and installed-artifact checks remain unchanged.

The exact direct corrective scope is 11 paths from `c408ccd2a2f7b11787f725a24e818ffa038e3d36`; the prior 16-path partition/Nav2 corrective from `87af41f45d721969f2767d36291252e3b14e3dcb` remains historical. Run005 retains 34 unique current source pins, independent of changed-path count. Four existing pins were refreshed for the modified runner/test/contract paths; no pin was added.

Offline verification: focused runner/output tests 68 passed; full Step-7 tools 218 passed; bringup 244 passed; RL 707 passed; six-package external colcon build PASS; observer C++ 13 cases and ROSIDL 8 cases PASS; installed runtime artifacts 15/15; source pins 34/34. No ROS/Gazebo/runtime invocation occurred in this corrective.

The guard seed remains pending, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling: `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.

Current record hashes: guard `db5cfd94b9623c1497ba103444e931064c04cf76e7ebe455ba8a7f29a313752e`; evidence `39b220725d48f19f7b140da97868bc9c31ba5321c21dfa5c1be14572ca050813`; manifest `66bb591039054556824e0c032d552247d5319e8b5ec240bddea7960bf99bd17d`.


## Corrective: exact GZ_PARTITION process identity

Invocation_004 ran once and stopped before guard acquisition with `PREACQUIRE_FAILURE:RuntimeError:STALE_PARTITION_PROCESS_FOUND`. The run record shows runner count 1; bootstrap, composite, C++ observer, and Gate-B observer counts 0; `runtime_execution=false`; pending guard unchanged; no lock; and `teardown_applicable=false`. The evidence checksum verification passed. The runtime checkout was created and is preserved. This was a process-identity preflight result; no runtime campaign started and no retry occurred.

The stale-process scan now excludes runner ancestry, enumerates numeric `/proc` PID entries, and reads each candidate's NUL-delimited `environ`. A process matches only when one complete entry equals `GZ_PARTITION=mecanum_step7_nav2_run005_f7f98c6`. Disappeared or inaccessible candidate environments are ignored. Diagnostics contain numeric PIDs only and are ordered numerically. The scanner does not inspect command lines or infer partition ownership from arbitrary text.

The exact current direct corrective scope is 11 paths from `da82b2e5d65eedd80f42000283dccc42a5f6ed66`; the preceding output-parent correction remains the exact historical 11-path diff from `c408ccd2a2f7b11787f725a24e818ffa038e3d36`. Run005 retains exactly 34 unique source pins; three existing source/test pins were refreshed by SHA-256 and byte size. The source guard remains pending with capacity 1, acquisition count 0, and `runtime_authorization=NOT_GRANTED`. Gate B remains `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling remains `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.


## Corrective record: exact partition process identity — final offline reconciliation

This entry records the finalized current candidate state after the source/test stabilization and existing-pin refresh. The exact direct diff from `da82b2e5d65eedd80f42000283dccc42a5f6ed66` remains 11 paths. The scanner reads only numeric PID `environ` data for matching; ancestry exclusion uses process stat metadata. A match requires an exact NUL-delimited environment entry; inaccessible/disappeared environments do not block preflight.

Verification: focused Run005 runner/guard 82 passed; full Step-7 tools 223 passed; `mecanum_nav_bringup/test` 244 passed; `mecanum_nav_rl/test` 707 passed; six-package external build PASS; observer CTest 1/1 (13 cases) and ROSIDL tests 25/25 passed; installed runtime source equality 15/15; `py_compile` PASS for four modified Python files. Current source-pin inventory is 34/34 unique SHA-256/size entries. Invocation_004 remains the immutable checksum-verified pre-acquire failure recorded above; this corrective ran no official runner/runtime and did not consume the guard.

Current record hashes: guard `e71580a8c3ffb0feb7740f8aa194ad2206ce18f9e60cfc9fb4b5ad1c600da36a`; evidence `fe28092b4589cf85b270fdc6e8696197687626aa32ca33f85e3360f36db462e6`; manifest `a012aae26afbc5af4c025f7d70d3ef6a562b34c4659c361cccdf86622f9c5f93`. Corrected pin: `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py` SHA-256 `b5532869ebbf6f3cbdf7c657c89dd291d005671ae1d41c76e25224b2b9bc370d`, size `12201`; contract test SHA-256 `e88f0fc6be4a8c9bd22e7f855fc160c656b530870529d753ae788f8b55206982`, size `47558`.

### Step-7 Run005 attempt_002 host-transport preflight and terminal-record reliability corrective

This L1 corrective is based on `99d5c29c1c302260a8971e19e46f93d778a52f86` and has an exact 11-path direct scope. Before guard acquisition, the runner checks the campaign partition through `socket.if_nameindex()`, binds and closes a UDP loopback socket without sending data, and runs `gz topic -l` with the exact `GZ_PARTITION`. This is a transport capability probe only; it does not start a Gazebo simulation. Failures use `GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:<reason>` and are recorded as pre-acquire evidence with no guard acquisition, lock, or campaign process.

After guard acquisition, SIGTERM is converted to `RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM` and enters the existing exception/teardown path. Teardown remains composite then bootstrap; final run record, artifact manifest, and checksums are written after teardown. The prior signal handler is restored. SIGKILL cannot be caught, so a durable terminal record cannot be guaranteed after SIGKILL.

Invocation_005 is immutable. The saved artifact at `/tmp/step07_runtime_evidence/STEP07_NAV2_BASELINE_RUN_005_ATTEMPT_002_INVOCATION_005/run_record.json` has SHA-256 `5ffa675f8ec846d09a6c7e70ebaa3689eb7566f03398db565c4bd53874b360da` and exists; its terminal outcome is `STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`, `pre_teardown_failure` is `RuntimeError:BOOTSTRAP_READINESS_TIMEOUT`, and it records bootstrap 1, composite 0, observers 0, guard acquired/consumed, and teardown completed but not clean. The saved bootstrap log contains `getifaddrs: Operation not permitted` and `Error creating socket: Operation not permitted`. The saved manifest SHA-256 is `79db29fa7f96247ad393d41411e2ddd986dee1738624b0caded6178afe7eec65` and lists 5 artifacts. Therefore the claim that external termination prevented the final run record is contradicted by the preserved record; no such claim is made here. Historical attempt evidence was read only and not modified.

The current Run005 seed remains PENDING, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`; Gate B remains `NOT_STARTED` and `RUNTIME_APPROVED=NOT_APPROVED`. Run005 retains exactly 34 unique current-worktree source pins, independently of the 11 changed paths. The source/offline checks do not establish runtime readiness or Gate-B PASS.


## L1 corrective: terminal verdict and ROS discovery preflight

This corrective is based on `87ee34b1a945ecc12b525fe9f4711a368c0bdbc3` with an exact 11-path direct scope. Terminal PASS requires all acceptance values true, no failure literals, and completed, ordered, clean, verified teardown. SIGTERM after acquisition is a failure routed through best-effort composite-before-bootstrap teardown and terminal evidence finalization. Snapshot/stop uncertainty is never reported clean; filesystem/checksum errors remain distinct from verdict failure. The prior signal handler is restored. A durable record cannot be guaranteed after SIGKILL, power loss, or an unwritable filesystem.

Before guard acquisition, after ROS and overlay sourcing, the runner checks CLI support and runs bounded `ros2 topic list --no-daemon --spin-time 3`; an empty graph is valid for this capability probe. Permission/socket errors, timeout, nonzero status, or network-error output fail closed and produce pre-acquire evidence without guard acquisition. The exact-partition `gz topic -l` check remains. These probes do not establish runtime graph acceptance.

Invocation_005 is immutable and reported from its stored evidence: the run record exists, records `BOOTSTRAP_READINESS_TIMEOUT` after acquisition, bootstrap count 1, composite/observer counts 0, and teardown completed but not clean/order-correct. Bootstrap logs contain `getifaddrs: Operation not permitted` and `Error creating socket: Operation not permitted`. The stored record does not support a claim that external termination prevented finalization.

Phase A offline verification passed: focused Run005 116, scope 2, Step-7 tools 257, bringup 244, nav_rl 707, six-package external build, observer/ROSIDL, `py_compile`, installed-source equality 15/15, 34/34 source pins and parsing/history/scope checks. No runtime was run; guard remains pending/unconsumed. Evidence ceiling: `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.


## L1 corrective decision: SIGTERM boundary and guard acquisition

The corrective base is `bee34dd2d689fe585ae12000058b2f2903196659`. A SIGTERM before guard acquisition is a pre-acquire failure and must not claim consumption. The handler is installed before pre-acquire work; SIGTERM is blocked only across the guard mutation/handoff, with the acquired state marked before pending delivery is unblocked. Any SIGTERM after acquisition is a FAIL. During teardown and finalization the handler latches interruption without throwing, continues best-effort composite-before-bootstrap teardown, and synchronizes the terminal FAIL record, manifest, and checksums before restoring the prior handler when the evidence filesystem remains writable. PASS requires all acceptance values, no failure literals, and completed, ordered, clean, verified teardown. Filesystem/checksum failures remain distinct from verdict failures. No durable evidence guarantee is made for SIGKILL, power loss, or unwritable storage.

No acceptance, host probe, map/Fuel, TF, safety, QoS, Gate-B, guard-capacity, or process-ownership contract changed. Historical Run005 invocation_001–005 artifacts remain immutable. This correction performed no runtime/official runner invocation; Gate B remains `NOT_STARTED` and `RUNTIME_APPROVED=NOT_APPROVED`.
