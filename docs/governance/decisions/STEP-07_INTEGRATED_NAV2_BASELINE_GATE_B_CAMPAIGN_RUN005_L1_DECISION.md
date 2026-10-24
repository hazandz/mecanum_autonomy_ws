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


### Quyết định corrective: guard mutation và process ownership

Corrective L1 trên base `53b7790c23c7d4969612259a8ee06be0353babd2`, vẫn Run005 attempt_002. Direct scope là exact 13 path; runtime source-pin inventory giữ 34 path duy nhất. Guard mutation exception chỉ được xóa lock khi strict runtime readback xác nhận đúng seed PENDING chưa acquire. Sau replacement hoặc unmask failure, strict readback CONSUMED đúng commit/authorization/count=1 đi vào post-acquire FAIL và terminal evidence. Readback không xác định giữ lock, ghi UNVERIFIED và không fallback sang source checkout.

Cả bốn component dùng cùng owned-spawn helper: SIGTERM được latch trong registration; child handle được ghi ledger trước PGID/snapshot. Teardown lấy ledger kể cả khi caller chưa nhận assignment. Chỉ signal process group đã xác minh; nếu không xác minh được, thử dừng chính child đã biết và ghi FAIL/unverified. Thứ tự composite trước bootstrap, acceptance, partition, QoS và capacity-one không đổi.

Phase A PASS: focused runner 142, guard 15, historical guard 19; full Step-7 tools 299, bringup 244, RL 707; build sáu package ngoài worktree; observer 13 và ROSIDL 8; py_compile sáu file; installed/source equality 15/15; source pins 34/34 sau reconciliation, JSON/YAML/XML và history/scope/diff checks. Không official runtime invocation trong corrective này.

Giữ lịch sử invocation_001–005, consumed guards/locks/evidence/runtime worktrees bất biến. Source seed còn PENDING, capacity 1, acquisition 0, runtime_authorization=NOT_GRANTED, không lock. Gate B NOT_STARTED; RUNTIME_APPROVED=NOT_APPROVED. Giới hạn: SIGKILL, mất điện hoặc filesystem không ghi được vẫn có thể ngăn terminal evidence. Evidence ceiling: SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT. Bước tiếp theo: independent audit exact corrective commit; runtime cần authorization riêng.


## Corrective L2 — composite lifecycle và Gate-B

Base/sole parent: `bb5fc04fe8e309c52e468f766893ef60625e6821`; cùng Run005 attempt_002. Owner đã phê duyệt escalation L2 vì thay đổi orchestration lifecycle, đồng bộ clock/binding/TF, lifetime hai observer và scan validity. Tên decision có hậu tố L1 được giữ theo exact allowlist; active decision này là L2. Architecture DOCX, profile sim_eval + NAV2_BASELINE, 16-root V3 config/hash, public topics/interfaces, TF owners, sole /cmd_vel publisher, receipt QoS và guard capacity-one không đổi.

SafetySupervisor và FinalTwistPublisher sử dụng use_sim_time đã được Jazzy Node khai báo và kiểm effective value phải boolean true. Policy lifecycle YAML không còn bị truyền như ROS parameter file: kiểm exact policy rồi tạo dictionary; Nav2 manager chỉ quản lý map_server, amcl, planner_server, controller_server, behavior_server, bt_navigator, bond_timeout=4.0. SafetyLifecycle là LifecycleNode riêng; handlers đăng ký trước node, configure sau process start rồi activate khi Inactive, mỗi handler một lần. Activation vẫn NON_READY. Runner đợi bảy ROS lifecycle Active id=3, clock/sensor freshness và TF thực trước đúng một rearm; không nhầm với custom PRIMARY_ACTIVE=2. Controller và BT navigator cùng dùng /odometry/filtered.

Gate-B tạo node use_sim_time=true, Buffer(node=self.node), đăng ký tf2_geometry_msgs trước transform. ROS time dùng cho goal/freshness/TF, steady time dùng cho timer/deadline; chưa clock/TF/identity thì chờ, future stamp bị reject. Exact FixtureBindingClaims giữ topic/type provenance khi đi qua validator pure-core; validator không được nới. Kiểm thử generated messages và in-memory TF gọi thật adapters → validator → assembler đã bắt và sửa import RawLidarScan cục bộ sai phạm vi. Action readiness bất đồng bộ; hai action mỗi loại gửi đúng một lần; requested_once/exit status lấy từ calls và results thực.

C++ observer thu 30 giây. Gate-B atomic-write một lần khi collection hoàn tất, giữ subscriptions sống tới runtime_observer.json cùng invocation parse đầy đủ và đúng config_hash. Peer chưa hoàn tất được chờ tới steady deadline 60 giây; sai hash/timeout/interruption không được PASS hoặc action retry. Giữ nguyên bốn lifecycle subscribers và raw graph/QoS acceptance. Scan +Inf là valid no-return với range metadata hợp lệ; NaN, -Inf, metadata sai, empty và stale scan vẫn fail closed/safe stop. Không nới command/odometry nonfinite checks, E-stop, limits hoặc collision ownership.

Phase A: focused behavioral 46 PASS; Step-7 tools 301 PASS; bringup 248 PASS; RL 715 PASS trong process riêng và external install-base. Thử gộp ba suite có 1 pure-import isolation failure do bringup import ROS; kết quả verification dùng ba suite cô lập, không lượt gộp. Build sáu package ngoài worktree PASS; observer 13 và ROSIDL 8 PASS; py_compile 13 file; installed/source 19/19 (15 runtime artifacts + 3 Python modules + package.xml). Parser C Jazzy kiểm AMCL/Nav2/EKF parameter files và parameter dictionaries. Không chạy campaign runtime hay official runner. SOURCE_FREEZE được chốt trước reconciliation này.

Direct scope là exact 23 path trong current_corrective_scope. Inventory là union 34 pin tại base với ba runtime source được Owner chỉ định: 37/37 SHA-256 + byte size, độc lập changed-path count. Historical pins luôn đọc exact Git blobs, không fallback worktree. Bảo toàn các scope lịch sử và guard mutation/process ownership tại base, WP06 và invocation_001–005; không sửa consumed guard, lock, runtime checkout hoặc external evidence lịch sử.

Source seed còn PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION, capacity=1, acquisition_count=0, runtime_authorization=NOT_GRANTED, không lock. Gate B NOT_STARTED; RUNTIME_APPROVED NOT_APPROVED. Evidence ceiling: SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT. Không tuyên bố ROS graph, Gazebo/Nav2 runtime PASS hay readiness cho robot thật. Giới hạn chứng cứ terminal trước đây (SIGKILL, mất điện, filesystem không ghi được) vẫn giữ nguyên. Bước tiếp theo: independent audit exact corrective commit; runtime chỉ sau authorization riêng của Owner.

Record hashes sau reconciliation:

- `artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json`: `2442328059cfea2143ea3660ad578bf8a69a535493459f7aec510a725c12e6aa`, 24103 bytes.

- `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json`: `1d206e32f5604ff425d30b3dbd8b2a377593a602d9e163e18a47065ce8995afe`, 38806 bytes.

- `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json`: `3c7ab3855df8fac785c21de85d1e3e522fffbb87aaf090b63a64fb81737f0b36`, 36217 bytes.


## L1 corrective: Run005 evidence-validator identity and verdict contract

Base: `c8e34ead42c9c3fa6d79bf73dc221a9cc599d42a`; direct corrective scope: exact 10-path set recorded in the current Run005 evidence JSON and guard manifest. This correction changes evidence validation only. It does not change runtime behavior, ROS topology, safety, authorization, guard state machine, source-pin inventory membership, or runtime policy.

The validator now accepts only run ID `STEP07_NAV2_BASELINE_RUN_005` and the exact Run005 PASS/FAIL terminal outcome strings. PASS requires every acceptance value to be true, an exactly empty `failure_reason_literals` list, and teardown marked completed, clean, ordered, and verified. A FAIL terminal record requires at least one failure literal. Run001 identity or stale Run001 terminal strings fail closed. `validate_run_directory()` is covered by a complete canonical synthetic Run005 bundle including manifest and checksums.

The active Run005 source-pin inventory remains 37 unique paths. Three existing entries were refreshed from current source bytes; no path was added. Historical Git-blob verification and prior historical scope records remain unchanged. Offline checks passed after pin refresh: Step-7 tools 306, bringup 249, RL 715, six-package external build, observer 13 and ROSIDL 8, Python compilation, and 15/15 installed/source runtime-artifact equality. No official runner or runtime was invoked.

Guard seed: `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`, no lock. Gate B remains `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling: `SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT`.

## Corrective L2 — IPv4 transport binding và graceful teardown

Base / sole parent: `f72ac2112e0d1545a72b6a9a12764664d508aaa8`; tiếp tục Run005 attempt_002. Corrective này xử lý hai root cause: Gazebo Transport phải bind vào đúng một IPv4 local hợp lệ trên interface của default route qua `GZ_IP`, và kết quả cuối chỉ được PASS nếu mọi owned process group thoát graceful ngay ở stop stage đầu tiên, không có SIGTERM/SIGKILL escalation.

Runner đọc structured IPv4 default-route, xác minh interface đang UP và địa chỉ local thuộc interface đó; loại route/IP thiếu hoặc mơ hồ, interface virtual/container, địa chỉ loopback/link-local và route/interface không khớp. Nó chạy bounded one-shot `gz topic` publish probe với `GZ_PARTITION` campaign chính xác và `GZ_IP` đã chọn. Probe không khởi chạy simulation. Cùng environment đã xác minh được truyền cho bootstrap, composite và hai observer. Interface/IP cùng kết quả probe đã sanitize được đưa vào pre-acquire evidence.

Teardown record phân biệt `clean`, `verified`, `ordered`, `graceful` và escalation history. Snapshot cuối sạch sau escalation vẫn là `graceful=false`; validator từ chối PASS nếu thiếu cờ graceful hoặc có escalation.

Run005 attempt_002 invocation_007 được ghi nhận là runtime failure bất biến: bootstrap READY, composite readiness timeout với multicast `Network is unreachable`; final teardown snapshot clean nhưng `lifecycle_manager` cần escalation nên teardown không graceful. Không diễn giải invocation này là PASS. Không sửa evidence, guard, lock hoặc runtime worktree lịch sử và không retry.

Sau khi bổ sung regression test guard trong allowlist và làm mới entry pin hiện hữu, Phase A được chạy lại: focused guard/contract 35 PASS; focused scope 4 PASS; full Step-7 tools 307 PASS; full bringup 250 PASS; full RL 715 PASS với external install base; external six-package build PASS; observer 13 và ROSIDL 8 PASS; `py_compile` PASS; installed/source artifacts 15/15 PASS. Source pin inventory giữ 37 unique entries, không đổi membership. Direct scope exact 13 paths từ base nêu trên.

Guard source vẫn `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`, không lock. Không có runtime trong corrective này; Gate B `NOT_STARTED`, `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling: `SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT`. Next action: independent audit exact corrective commit; runtime cần authorization riêng.

## L1 corrective — pure-Python default-route resolver

Base / sole parent: `e921b04e9ef8dc933a76966cf101613fab0f8062`. Đây vẫn là Run005 attempt_002; không tạo run hoặc thay đổi authorization. Invocation_009 là historical immutable pre-acquire failure với literal `GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:DEFAULT_ROUTE_EXIT_NONZERO`. Evidence chỉ xác nhận lệnh route bên ngoài trả nonzero; không suy đoán do cú pháp, quyền hay phiên bản.

Runner không còn gọi executable `ip` hoặc dùng netlink route dump. Resolver đọc `/proc/net/route`, chọn duy nhất default IPv4 route có metric thấp nhất, kiểm tra interface UP và physical qua sysfs, rồi dùng UDP `connect()` tới TEST-NET (không gửi packet) để lấy source IPv4. Source phải là địa chỉ usable, không loopback/link-local/multicast/unspecified/reserved và phải khớp địa chỉ trên interface bằng `SIOCGIFADDR`. Mọi lỗi fail-closed với `GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:<reason>`.

Probe `gz topic` publish bounded vẫn chạy trước guard với exact `GZ_PARTITION` và `GZ_IP` đã xác minh; bootstrap, composite và hai observer kế thừa cùng environment. Evidence chỉ lưu interface, IPv4 đã chọn, `PROC_NET_ROUTE_AND_UDP_CONNECT`, partition và kết quả probe đã sanitize; không lưu gateway hoặc raw network output.

Regression tests dùng route/sysfs/socket/command fakes; không gọi network thật. Offline evidence sau kiểm tra cuối được ghi trong Run005 evidence và append-only Ledger. Guard seed giữ PENDING, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`, không lock. Không chạy runtime; Gate B `NOT_STARTED`, `RUNTIME_APPROVED=NOT_APPROVED`.

## L1 corrective — Nav2 costmap integer dimensions and teardown escalation evidence

Exact source base / required parent: `a383f258b02a0f9a22b2dc72fb937dbcaba6973a`; branch `step07-integrated-nav2-gateb-campaign-f7f98c6`; actual direct diff is 11 paths; the authorized allowlist is 12 paths and additionally permits `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py`, which is unchanged. Invocation_010 remains immutable historical runtime FAIL. Its controller_server exited with `InvalidParameterTypeException`: local costmap `height` was YAML float `4.0` while Nav2 requires an integer; composite readiness then timed out. The saved evidence is `/tmp/step07_runtime_evidence/STEP07_NAV2_BASELINE_RUN_005_ATTEMPT_002_INVOCATION_010` and the runtime checkout is `/tmp/step07_nav2_run005_attempt_002_invocation_010`; neither was changed.

The runtime YAML changes only required-integer local costmap `width` and `height` scalars from `4.0` to integer `4`; global costmap has no width/height entries. The focused contract parses YAML and checks every existing global/local costmap dimension has exact Python integer type, while retaining historical scope assertions. The runner now records launcher log SIGTERM/SIGKILL escalation after SIGINT and reports `process_group_teardown_graceful=false` even when the final process snapshot is clean; regression coverage exercises that case. Other runtime acceptance semantics are unchanged.

Phase A source freeze was recorded after focused checks, Step-7 tools (311), bringup (252 in the pre-existing clean-scope run), RL (715), six-package external build, observer (13) / ROSIDL (8), `py_compile`, and installed/source byte equality (15/15) passed. A later full bringup rerun returned 247 passed / 5 failed because untracked colcon `log/` entries were included by existing exact-scope checks. These generated paths are outside the allowlist and were left untouched; the final exact-worktree-scope condition therefore does not pass. No commit or push was made. The corrective remains source/offline only; no runtime was invoked. Guard remains pending, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`; Gate B `NOT_STARTED`, `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling: `SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT`.


## Run005 attempt_002 — Gate-B collector lifecycle/order corrective (2026-10-23)

Invocation_014 remains immutable and failed with `STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`. Evidence recorded `NavigateToPose accepted=false/NO_RESULT`, one 81D vector, Gate-B sample timeout, C++ observer exit 2 after invalid ROS context, missing evidence chain, and `clean=false/graceful=false`. Its runtime checkout guard was consumed; source seed is a separate pending object.

This L1 evidence-collection corrective adds pre-goal action-server readiness, explicit READY artifacts for both ROS collectors and runner-owned evidence-chain collection, a config-bound trigger, collector settlement before composite/bootstrap teardown, and timestamp/correlation-bound structured chain failures. The C++ observer checks context before graph queries and persists fail-closed partial evidence. Five valid 81D samples remain mandatory. No safety/controller thresholds, map, Gazebo/TF/launch semantics, or public ROS interface changed.

Phase A `SOURCE_FREEZE=TRUE` is offline-only. Base/intended parent `a04ec4d317830e01a4613fc5251f2152b9e9946e`; direct scope 16; authorized paths 17. Pins remain 38 with eight existing hashes refreshed. Guard PENDING/capacity 1/acquisition 0/`runtime_authorization=NOT_GRANTED`, no lock; Gate B `NOT_STARTED`, `RUNTIME_APPROVED=NOT_APPROVED`. No runtime was run; independent audit remains required.


### Final scope-test closure (2026-10-23)

The bringup contract test now includes the current 16-path reconciled scope in its historical scope dispatch while retaining exact set equality. Full `mecanum_nav_bringup/test` passed 254/254. The existing pin for `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` was refreshed; source-pin membership remains 38. The source guard remains PENDING/capacity 1/acquisition 0/NOT_GRANTED with no lock. This test-only correction grants no runtime or Gate-B status.


## Corrective L1 — Invocation_015 QoS verdict và collector/action readiness

Base / intended parent: `7f5d16ffa4edca34672b5af82397df9bde186829` trên branch `step07-integrated-nav2-gateb-campaign-f7f98c6`. Exact direct scope: 16 paths; authorized allowlist: 17 paths (runtime-guard regression test được phép nhưng không đổi). Candidate: `STEP07_RUN005_ATTEMPT_002_COLLECTOR_VERDICT_LIFECYCLE_L1_CANDIDATE_PENDING_INDEPENDENT_AUDIT`.

Invocation_015 là runtime failure lịch sử bất biến. Run record `b9392c3eddd07a3b90c0d1383a61e99ba14f46a890f7c73219474fb749babe0c` ghi runner exit do `STEP07_NAV2_BASELINE_RUNTIME_OBSERVER_READINESS_TIMEOUT`; C++ observer đã ghi READY rồi exit 2 vì `QOS_METADATA_UNOBSERVABLE:receipt_qos_contract`. Gate-B không start, action-server readiness không được thử, NavigateToPose không attempt, không có năm vector 81D hoặc evidence chain. Teardown completed/verified/ordered nhưng clean/graceful là false. Source seed PENDING và runtime checkout guard CONSUMED là hai object khác nhau.

Corrective phân tách readiness khỏi verdict QoS; C++ chỉ ghi raw `PASS`/`FAIL`/`UNOBSERVABLE`, còn runner/validator resolve UNOBSERVABLE chỉ bằng source/install proof có SHA-256, byte size và pin hiện hành. Topic/type/reliability/durability/count mismatch vẫn FAIL. Sau composite readiness, runner chờ C++ READY, ghi kết quả action server PASS/FAIL/NOT_ATTEMPTED, rồi mới start Gate-B; goal chỉ trigger khi tất cả collector READY. Gate-B không-start và evidence-chain thiếu có stage failure canonical. Acceptance vẫn bắt buộc đúng năm vector 81D hợp lệ, goal hợp lệ, chain đủ Candidate → Safety decision/reason → final receipt → odometry và teardown clean/graceful. Safety/Nav2/map/Gazebo/TF/public interface không đổi.

Phase A/A.5 offline verification: focused 209; full Step-7 tools 321; bringup 254; RL 717; six-package external build PASS; observer 17 C++ cases; ROSIDL 8 cases; Python compile 7 files; installed/source equality 15 runtime artifacts + 3 Python modules; 38/38 source pins. Preservation inventory Invocation_014/015: 4,021 entries, SHA-256 `e936cdd3fa38a1aa4f6c25e9114fb01eadb2b1ab7d89e21f0775202244cecbb4`. No runner, live ROS/Gazebo, Nav2 runtime, HIL, hardware, Fuel provisioning or integration.

`SOURCE_FREEZE=TRUE` chỉ nghĩa source/offline candidate. Guard remains PENDING/capacity 1/acquisition 0/`runtime_authorization=NOT_GRANTED`, no source lock. `GATE_B=NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`; independent audit required.


## Corrective L1 — Invocation_016 QoS verdict and observer lifetime (2026-10-23)

Base / sole parent: `09014a320cd8dedb242c99d70cd24ffa0d8cd980` on `step07-integrated-nav2-gateb-campaign-f7f98c6`. Candidate: `STEP07_RUN005_ATTEMPT_002_LIFECYCLE_QOS_OBSERVER_LIFETIME_L1_CANDIDATE_PENDING_INDEPENDENT_AUDIT`. Actual direct changed-path set is 15 paths; the authorized set is 17 paths, with `step07_gate_b_evidence_validator.py` and `test_step07_run005_runtime_guard.py` unused.

Invocation_016 remains an immutable runtime failure. Its READY artifact records a live process, valid ROS context and created subscriptions. The READY PID belongs to the C++ child started by `ros2 run`; the runner compared it to the launcher PID and waited until `STEP07_NAV2_BASELINE_RUNTIME_OBSERVER_READINESS_TIMEOUT`. Settlement then stopped the observer, whose final raw graph had `lifecycle_endpoint_qos_contract=false` and receipt QoS `UNOBSERVABLE`. The graph had four of five expected lifecycle subscribers because Gate-B was never started; observed reliability/durability matched, while RMW history/depth metadata was `UNKNOWN/0`. Action-server readiness was not attempted, Gate-B was not started, vectors were zero, and no Gate-B evidence window formed.

The correction separates READY from final QoS verdict, validates the READY child PID within the runner-owned process group, and keeps the C++ observer alive until runner-controlled shutdown. Raw endpoint evidence retains endpoint identity/name, direction, type, GID, reliability, durability, history, depth, discovery snapshot time, status and reason. Runner/validator remain the only owners of final QoS resolution; UNOBSERVABLE requires exact pinned source/install proof with matching SHA-256, byte size and equality. Observable mismatch and invalid proof fail closed. The action-server result is recorded as PASS, FAIL, or NOT_ATTEMPTED with its blocking reason; Gate-B starts only after C++ readiness and action-server PASS. Gate-B non-start creates a canonical structured failure artifact. Five valid 81D samples, successful navigation and a complete timestamp/correlation-bound evidence chain remain mandatory.

Offline verification: Step-7 tools 325; bringup 255; RL 718 with external install; six-package external build PASS; observer 20 tests; ROSIDL 8 tests; `py_compile` 7 files; installed/source equality 18/18; source pins 38/38 with seven existing pins refreshed; historical Invocation_014/015/016 inventory 7,330 entries unchanged, SHA-256 `b3d09f92abd0f4d943e30656ee7f57c5a62f0cd04d6490ee0a6c5810bcec69a6`.

`SOURCE_FREEZE=TRUE` is offline-only. Source seed remains PENDING/capacity 1/acquisition 0/`runtime_authorization=NOT_GRANTED`, with no lock. `GATE_B=NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. No official runner or live ROS/Gazebo/Nav2, HIL, hardware, Fuel provisioning or integration was run. Independent audit is required.

Guard/evidence/manifest SHA-256: `a1cace23adbafa80e40bfd7a0965e85e0d58b9a16c1b536028b81ed018c3a42b` / `b0d684bf86f3dc4c98bf73fb6c009cce6c858a39f5ee6fbea6f2e84813848530` / `286f06372abaaf73317ed2ec45c6d3e415fd605dbf4176f13ce46403aef3795b`.


## 2026-10-23 — Run005 Invocation_017 corrective closure

Candidate branch `step07-integrated-nav2-gateb-campaign-f7f98c6`, base/intended sole parent `31555b8ff2472811994907791f0d9b8d7f56498f`. Corrective source/offline; historical Invocation_014–017 artifacts and runtime checkout/guard/lock were not modified.

Root cause handled in the source candidate: process-group roles are initialized before guard acquisition; launcher PID is distinct from child PID/PGID and ownership proof; readiness, raw QoS, QoS verdict and terminal outcome are separate; C++ collector stays alive until runner-controlled shutdown; QoS `UNOBSERVABLE` resolves only with valid source/install proof and mismatch/invalid proof fails closed; Gate-B is blocked if the C++ observer is not READY and a stage-failure artifact records the blocking reason.

`SOURCE_FREEZE=TRUE` is source/offline freeze. Phase A has 6 source/test paths; Phase A.5 keeps 38 pin members and refreshes 5 stale SHA-256/byte-size entries; Phase B actual scope is exactly 13 paths. Closure allowlist has 14 paths, with `test_step07_run005_runtime_guard.py` unchanged.

Phase A results: focused runner/validator 179 passed; bringup scope 6 and full bringup 256 passed; RL 718 passed with Python 3.12.3/Pydantic 2.10.6; six-package external build PASS; observer 20 and ROSIDL 8 passed; `py_compile` 5 files; Run005 equality harness 2 passed; parser/canonicality tests 25 passed; historical Git-blob checks 4 passed. Full Step-7 suite/final coherence are post-reconciliation checks, not runtime evidence.

Guard/evidence/manifest SHA-256: `030e8d66a44bc13eea2c40ef5643908aaa89ffe43a26edd64b853c1bac5a2016` (35051 bytes), `64a64924215adeab8272c6aac7e3b69b0a2845f157815050521bdeb620ded9a0` (58730 bytes), `0340916536b696dcb052d11ea79ab6b8cc246af77918bbce23b386f3febe1db3` (47920 bytes).

Guard seed remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. No runtime, integration, HIL, hardware or Fuel provisioning; no runtime PASS, Gate-B PASS or `REAL_READY` claim.


## 2026-10-23 — Invocation_018 failure-recording and collector teardown corrective closure

This offline corrective is based on `711c06d146e596b4ec74b8a3d546bcf71fcba5ef` and continues Run005 attempt_002; no new Run or invocation is created. Invocation_018 remains immutable and failed with `STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`. The source issues were unsafe concatenation when a failure field was `None` and a teardown branch that referenced `clean` before initialization.

The runner now records nullable failures safely, initializes teardown evidence fields before all branches, emits explicit fail-closed state when collector/action-server readiness or teardown cannot be proven, and does not treat collector exit code zero as acceptance. Gate-B remains blocked until collector and action-server readiness are established. Valid goal, full evidence chain, and exactly five valid 81D vectors remain required. Safety, Nav2, map, TF, Gazebo, launch, and public ROS interface contracts are unchanged.

Offline-only verification passed before metadata reconciliation: focused runner/validator 185; Step-7 334; bringup 256; RL 718; external six-package build; C++ observer 20; ROSIDL 8; py_compile; installed/source equality 18/18. The 38-pin membership is unchanged and two existing pins were refreshed. Exact direct delivery scope is 9 paths from `711c06d146e596b4ec74b8a3d546bcf71fcba5ef`; cumulative scope is 13 from `31555b8ff2472811994907791f0d9b8d7f56498f`.

Guard/evidence/manifest SHA-256: `847901e6316e36d52752e772741212236bc734a8b39a67144af7efc10cf2abd9` / `18f3987120ec7192b15440cc2f4351304f52a1d50e7d79398d62f0415c15d777` / `eb992557721c9badbb1a663d3c57508b0719c67a1c5ea89d8f05ae5fa3fb278d`. This record grants no runtime authorization and makes no Gate-B PASS, runtime PASS, or `REAL_READY` claim. Guard remains PENDING/capacity one/acquisition zero/NOT_GRANTED with no source lock; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`.


### Canonical JSON hash-chain correction (2026-10-23)

This append-only correction supersedes the previous metadata digest triplet after the guard was serialized with the Run005 canonical writer. Guard/evidence/manifest SHA-256: `ab863631b73bc6b2f7f004d380d785e9e108680789917fb91748cf930f935a3f` / `655551928c5a1a15ccb3d88f7adab22944c75dbe5596b0227dc0ebe1038a030e` / `795960653705336e22ee2e07cb850ff89aac7d622211182a8f0f382582601f77`. The guard semantic object was unchanged; seed, capacity, acquisition count, authorization scope, integration base, allowlist and historical fields were preserved.


## 2026-10-23 — Consolidated corrective L1 Invocation_019, OFFLINE

`supersedes`: phần metadata Invocation_019 chưa delivery trong candidate hiện hữu; không thay outcome hoặc artifact lịch sử. Base/sole-parent target `9a92b94b6f0d0d9a0f4ebdc8133ebecb34e6129f`, branch `step07-integrated-nav2-gateb-campaign-f7f98c6`.

Đóng lỗi stdout hợp nhất của action-server probe và Class C `SCOPE_CONTRACT_NOT_PHASE_AWARE`. Scope validation dùng diff từ base cố định, chọn đúng phase metadata và so sánh exact path set; reject thiếu governance path, path lạ/historical, untracked và phase mâu thuẫn. Contract JSON helper reject NaN/Infinity; fixture owned collector mô phỏng launcher/child cùng PGID. Readiness order giữ `cpp_initial_ready → action_server_ready → cpp_pre_gate_b_recheck → gate_b_start`; không đổi acceptance hoặc semantics runtime.

`SOURCE_FREEZE=TRUE` chỉ là offline source freeze. Phase A 3 paths; Phase A.5 6 paths; Phase B và final verification đúng 10 paths. Inventory 38/38 members không đổi; 3 pin thay đổi so với base, trong đó continuation này refresh 2 pin.

Phase A/A.5: Step-7 tools 342 PASS; bringup 277 PASS; RL 718 PASS với Python 3.12.3/Pydantic 2.10.6; six-package external build PASS; observer/ROSIDL colcon result 32 tests, 0 failures; py_compile 3; installed/source equality 15 artifacts + 3 modules; parsing JSON/YAML/XML và diff checks PASS. Các regression scope/JSON mới 21 PASS và readiness/preservation 15 PASS. Final post-reconciliation verification là điều kiện delivery riêng, không được suy thành runtime evidence.

Guard/evidence/manifest SHA-256: `18abe5ceae3f57779e2cefe854f6fcdd755778f83a07cf1a5bb3eb607f4398fc` / `221be36378ba26902f97b30c80a273b51f8c43b107995fac8470f6a6bc7b45a4` / `598ed75330969b8da0fd7828d39f265daa73ca45e7705976d3e0ca9ef2cc2907`.

| Pin đã đổi từ base | SHA-256 | Bytes |
|---|---|---:|
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py` | `4c47430805da4a8a2a4603615751c70293e355386d0722655ff605e7f7fe2966` | 151394 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py` | `f857d2dd3657c0396b91ad738d8bb57ac74a7f5a241628eabd8d1ffd07fee062` | 144126 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` | `83443026621379bbd36f82dd9fc67b3b2c195f5b4be38feadfe9cef99f42650d` | 107315 |

Exact changed paths:

- `artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json`
- `artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py`
- `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py`
- `docs/governance/CANONICAL_SOURCE_REGISTRY.md`
- `docs/governance/PROJECT_EXECUTION_PLAN.md`
- `docs/governance/PROJECT_PROGRESS_LEDGER.md`
- `docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md`
- `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json`
- `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json`
- `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py`

Historical evidence và runtime checkout 018/019 được đối chiếu inventory read-only; các target 014–017 đã vắng mặt khi bắt đầu, historical metadata Git được giữ. Không sửa evidence/guard/lock lịch sử. Guard seed PENDING, capacity 1, acquisition 0, runtime_authorization NOT_GRANTED, không source lock; Gate B NOT_STARTED, RUNTIME_APPROVED NOT_APPROVED. Không runtime, retry Invocation_019 hoặc integration. Evidence `IMPLEMENTED_OFFLINE_ONLY`; không có runtime approval từ record này.


## 2026-10-23 — Corrective L1 gộp F1–F5 trên commit 21eab358 (OFFLINE)

`supersedes`: metadata candidate hiện hành cho các finding F1–F5; không sửa outcome/artifact lịch sử. Branch `step07-integrated-nav2-gateb-campaign-f7f98c6`, base/sole-parent target `21eab3580be48de9f00585cba904445dae7ce62f`.

F1/F3: runner nhận collection artifact đúng schema/config/invocation khi Gate-B còn sống, yêu cầu C++ finalize một lần với PGID đã verified. C++ chụp graph/QoS và ghi peer artifact trước khi Gate-B destroy subscriptions. Runner thu terminal/exit codes, validate artifacts/acceptance, rồi teardown composite trước bootstrap. Regression fake liên component chạy chính block main mới; block cũ ở commit base tái tạo timeout. Không giảm endpoint requirements.

F2: generator pin SHA-256 và byte size từ exact UTF-8 bytes sau final serialization. Regression multibyte và final coherence kiểm cả hai. F4: collection là provisional handoff; terminal handshake/error ghi artifact riêng, bind collection/peer bằng hash và size. Navigation chain cũng ghi sidecar để không sửa raw artifacts đã finalized. Timeout, mismatch, exception/SIGTERM và action-result deadline phải fail closed có evidence.

F5: exact receipt/odometry được vector tham chiếu có thể nằm trước first-vector stamp khi vẫn fresh; giữ receipt/scan 500 ms và odometry 250 ms hiện hữu, timestamps/sequence/generation thật. Regression 10.00 s → 9.98 s PASS; stale/future/wrong identity/sequence/missing exact record FAIL. Không mở cửa sổ tùy ý hoặc fabricate metadata.

SOURCE_FREEZE=TRUE là offline freeze. Phase A 9 paths; A.5 12; Phase B actual 16; authorized allowlist 17 (runtime guard test không đổi). Source pins 38 membership giữ nguyên, 8 hash/size refreshed. Không có path source runtime mới.

Phase A/A.5 evidence: full Step-7 377 passed; bringup 289; RL 720; six-package external build PASS; observer/ROSIDL 33 tests, 0 failures; py_compile 7; installed/source equality 15 artifacts + 3 modules; JSON/YAML/XML/canonical/duplicate/nonfinite checks và diff checks PASS. Hai lỗi test implementation đã xử lý trước closure: thiếu import ở regression F5 và thiếu ngoặc initializer C++ test. Post-Phase-B verification là điều kiện delivery riêng, chưa ghi PASS trước khi chạy.

Guard/evidence/manifest SHA-256: `fc5b8de7d681e29f130490181705c1b0bf86da8eed939c26cea02de939b81c9c` / `a5a867a91383d95c7609d7da9e9161cfa0955b29d47637b8146a33f83519295d` / `95a6afedcceb7384e0ec1756d35f0061e962fcec33bc116c2a98a574a0c5489b`; exact evidence byte size `73921`.

Historical chỉ kiểm bytes hiện hữu: 5.119 entries tại evidence/runtime checkout 018/019; targets 014–017 ghi UNAVAILABLE, không tính preservation PASS. Guard source PENDING/capacity 1/acquisition 0/NOT_GRANTED, không lock; Gate B NOT_STARTED; RUNTIME_APPROVED NOT_APPROVED. Không runtime, retry, HIL/hardware, Fuel provisioning hoặc integration; public ROS/QoS/Safety/Nav2/map/TF/launch contracts không đổi. Evidence IMPLEMENTED_OFFLINE_ONLY.


## 2026-10-24 — Corrective L1 R1/R2 protocol and sealed verdict artifacts (OFFLINE)

Base/sole parent target: `71713d0a79b006580510169924732d6791c87858`; historical closure `21eab358..71713d0` is unchanged.

R1 was a protocol downgrade gap: the run record selected protocol 2.0 while the Gate-B document could enter the legacy path, and PASS did not require the complete handshake event chain. The validator now binds run record, collection, terminal, and handshake-failure protocol markers; rejects missing, unsupported, or contradictory protocol declarations; requires the four ordered events and `COMPLETE` for protocol-2 PASS; and validates stage-appropriate structured failure evidence. Legacy documents remain supported only when protocol markers are absent.

R2 was an incomplete integrity-coverage gap: a verdict artifact omitted from both manifest and `SHA256SUMS.txt` could escape the equality check. The validator now requires manifest schema/run identity/count, SHA-256 and exact byte size, exact checksum path/hash equality, sealed coverage for every verdict artifact actually read, all five required files for protocol-2 PASS, and safe in-root regular paths without symlinks or traversal. The manifest does not hash itself. Existing five-vector and acceptance requirements are unchanged.

Offline regressions exercise complete PASS via `validate_run_directory()`, protocol/event/terminal mutations, stage-specific failures, missing or unsealed artifacts, tampered bytes, symlink/path rejection, and fixed-base exact phase scopes. Phase A: Step-7 tools 408 passed/2 skipped, bringup 303 passed, RL 720 passed, validator 68 passed; source-pin drift encountered during source edits was closed in Phase A.5. Final post-Phase-B verification remains a separate required check. No runtime or authorization claim is made.


## 2026-10-24 — Run005 R3/R4 offline validator corrective

Historical delivery commit `dcc36a39f410651f5e7a142fa52eeda5daa50012` has base/sole parent `bbac7448be59cc4afa54902744f1d4cf14fdf66c`; `71713d0a79b006580510169924732d6791c87858` remains the correct R1/R2 parent. This R3/R4 lineage correction is superseded as current metadata by R5, whose base/sole parent is `dcc36a39f410651f5e7a142fa52eeda5daa50012`. R3 separates sealed runner stage-failure artifacts from Gate-B protocol-2 collections and requires snapshot evidence only after `CPP_SNAPSHOT_COMPLETE`. R4 validates any present `collector_handshake.failure.json` against the run record before early returns and rejects contradictory failure sidecars in COMPLETE/PASS bundles. Collection acceptance, exactly five 81D vectors, navigation chain, legacy evidence, and protocol markers remain fail-closed.

Phase A: focused runner/validator 266 passed, 2 skipped; bringup 316 passed after R3 lineage scope correction; RL 720 passed using Python 3.12.3 / Pydantic 2.10.6 and external install base /tmp/step07_audit21_corrective/install; `py_compile` 4 paths PASS. Pre-pin full Step-7 was 414 passed/2 skipped with only expected runner pin drift. Phase A.5 preserves 38/38 pin membership and refreshes 4 existing entries. Phase A source scope is 4 paths; A.5 is 7; final Phase B scope is 11; allowlist is 12 with runner test unchanged. Post-reconciliation verification is not preclaimed.

Guard/evidence/manifest SHA-256: `12b8a61a2a4320cb035aea50ee045bc0bd2860d7babaece3a72504e0784f95b5` / `d1e68ca5e1677504f3163c3cb53765ce8d8a544ddc27c20e93fdc954c35c333d` (81268 bytes) / `6aef5ef3cd5a6f93c806f64d841b1d708f3bb80cb4d8bc5a32327492f13d0121`. Guard remains PENDING, capacity 1, acquisition 0, runtime authorization NOT_GRANTED, Gate B NOT_STARTED, RUNTIME_APPROVED NOT_APPROVED. No runtime or integration was run.


### 2026-10-24 — R3/R4 allowlist/scope metadata correction

Final coherence detected that the actual 11-path Phase B scope had been copied into the allowlist field. Corrected the authorized allowlist to the exact 12 permitted paths, retaining the unchanged runner test as authorized-only. Actual changed-path set remains exactly 11; no additional source path was introduced. The R3 scope regression now checks actual scope separately from allowlist membership. This metadata correction refreshed source pins from the final four changed source/test files; post-correction test results are pending and not preclaimed.

Current metadata hashes: guard `30945fa6f806af2ab511b998980e0a9776d5db04c76c656a90b50708921a2469`, evidence `f9737b59162be1ad8dddf512cb226edef93fd97caed565d1fef0f9a6e761b761` (81454 bytes), manifest `57bc5f58427b40fb630972eb72ebbbef98ee97625a3023796273a8a8f77514f4`.


Final verification addendum (2026-10-24): after the allowlist correction, Step-7 tools 415 passed/2 skipped, bringup 316 passed, RL 720 passed, six-package external build 6 packages, observer/ROSIDL 33 tests with zero failures, py_compile 4 paths, 38/38 pins and final coherence PASS. No runtime/integration. Final guard/evidence/manifest SHA-256: `30945fa6f806af2ab511b998980e0a9776d5db04c76c656a90b50708921a2469` / `14adeff6614d7a90bb435f0b3b67fa72974019ffc742ed5162241f4776b17600` (81910 bytes) / `d3ccfa90434799667eced082553b35b68e90ae960a9cf9fdf4837019119e102c`.


## 2026-10-24 — Run005 R5 lineage metadata correction

Current candidate: branch `step07-integrated-nav2-gateb-campaign-f7f98c6`; base and required sole parent `dcc36a39f410651f5e7a142fa52eeda5daa50012`. Exact current Phase B scope and authorized allowlist are the same eight paths: `artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json, docs/governance/CANONICAL_SOURCE_REGISTRY.md, docs/governance/PROJECT_EXECUTION_PLAN.md, docs/governance/PROJECT_PROGRESS_LEDGER.md, docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md, docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json, docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json, ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py`. Phase A is the contract test only; Phase A.5 adds the guard, evidence and manifest for the existing-pin refresh. `SOURCE_FREEZE=TRUE` records offline source/test and pin closure only. Historical R3/R4 delivery is `dcc36a39f410651f5e7a142fa52eeda5daa50012` with base/sole parent `bbac7448be59cc4afa54902744f1d4cf14fdf66c`; its previously recorded `71713d0...` parent is superseded. R1/R2 retains historical parent `71713d0a79b006580510169924732d6791c87858`. Runtime behavior is unchanged; guard remains pending, capacity 1, acquisition 0, and runtime authorization NOT_GRANTED. No Gate-B PASS or runtime approval is claimed.


## 2026-10-24 — Invocation_020 offline corrective (current candidate)

Base and required sole parent: `d123c708bb3b0fd80c8096daa9836da50440db85`. Historical Invocation_020 remains `STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED` and its evidence/runtime checkout/consumed guard/lock were not changed. Forensic evidence does not resolve the timeout cause: `ROOT_CAUSE_UNRESOLVED`; no inference was made from `NO_RESULT` or QoS `UNOBSERVABLE`.

Confirmed offline source defects corrected: readiness exception settlement no longer emits a null or fifth readiness transition after four readiness stages pass; navigation chain `artifact_written` now means the actual sidecar was written and read back, and failure chains preserve the real stage/blocker and missing links. Gate-B diagnostic-only evidence now records bounded action, trigger, clock/TF, freshness/generation and blocker state. No timeout, TF, lifecycle, safety, QoS, navigation, or vector acceptance semantics changed.

Current phase: `PHASE_B`, `SOURCE_FREEZE=TRUE`. Exact scope from base `d123c708bb3b0fd80c8096daa9836da50440db85`: 14 paths; authorized allowlist: 17 paths. Phase A=7; Phase A.5=10; Phase B=14. Existing source-pin membership remains 38/38; 7 stale SHA-256/byte-size entries refreshed. Current final verification was not preclaimed in metadata.

Offline checks completed before reconciliation: focused behavior suites passed; Step-7 tools 417 passed/2 skipped with only expected dirty-runner source-pin drift; full bringup 342 passed; full RL 722 passed; six-package external build passed; 18 installed/source byte comparisons passed; Python 3.12.3/Pydantic 2.10.6; py_compile and diff whitespace passed. Full post-reconciliation verification remains required before delivery.


## 2026-10-24 — Run005 Invocation_021 failure-chain consistency corrective (OFFLINE)

Base/required sole parent: `dee7d5dec565e51252f6a851c5959f07b8b8b512`; branch `step07-integrated-nav2-gateb-campaign-f7f98c6`. Failure-chain root reason/stage/blocker, sealed sidecar identity/hash/size and later settlement wrapper context are bound separately. The validator checks a sealed FAILURE sidecar before canonical success-chain reconstruction; a valid missing-correlation bundle returns structured FAIL, while PASS still requires the full success chain and acceptance. End-to-end regressions exercise production chain failure, failure writer, settlement and `validate_run_directory()` with receipt/odometry gaps, sidecar-before/after-settlement, resealed context/hash mutations, and PASS contradiction.

Phase A source scope: 4 paths; Phase A.5: 7; Phase B exact changed scope: 11; authorized allowlist: 12. Existing 38 source-pin members retained; four SHA-256/byte-size entries refreshed. `SOURCE_FREEZE=TRUE` denotes offline source/test and pin closure only. Pre-reconciliation full Step-7: 426 passed, 2 skipped, with only expected stale runner pin; full bringup: 353 passed. Focused runner/validator: 278 passed, 2 skipped. Post-reconciliation full tools/bringup and final coherence are required and are not preclaimed. RL, six-package build, observer/ROSIDL, and installed/source equality are inherited from base: only tool scripts/tests and a bringup test changed; package runtime sources/dependencies/build inputs are unchanged.

Guard/evidence/manifest SHA-256: `5fc2fd8e1cae2714c74a8bf6020005f31fd49874adf6bede29065f89157109a4` / `fa156da3608ca839e7b23374594ba5f02c6e327af37923f2e9de9d84575c56ff` (91949 bytes) / `142e0228f7ac7a1628421523ad391cc290dc209e9828f7ff16b5b9112464a0e4`. Guard remains PENDING/capacity 1/acquisition 0/NOT_GRANTED; Gate B NOT_STARTED; RUNTIME_APPROVED NOT_APPROVED. Invocation_020 remains immutable FAIL; timeout remains `ROOT_CAUSE_UNRESOLVED`. No runtime, retry, integration or hardware action occurred.

`PLAN_UPDATE_PROPOSAL`: Run005 Invocation_021 failure-chain consistency; branch as above; base/parent dee7d5d; evidence IMPLEMENTED_OFFLINE_ONLY; Phase A and pin closure completed, post-reconciliation checks pending; next action is final offline verification and conditional single review delivery. Runtime approval remains separate.

## 2026-10-24 — Run005 observer acceptance persistence corrective (OFFLINE)

Base/required sole parent `50fd738de91283c2c879f58fa6286ce5e15fc4bf`; branch `step07-integrated-nav2-gateb-campaign-f7f98c6`. `validate_observer()` returned a completed acceptance map, but runner assignment occurred only after canonical navigation-chain and Gate-B validation; chain failure therefore persisted observer acceptance as false. Runner now derives `observer_acceptance` from the validated nonempty boolean map and stores it immediately after observer validation. If validation throws or is unavailable, initialized false remains. Chain failure still finalizes campaign FAIL and does not promote Gate-B or navigation acceptance. Validator comparison remains strict.

Production-flow regressions start with the same false acceptance as `main()`, use real observer validation and the production persistence helper, trigger receipt/odometry correlation failure, invoke production writer, settlement and final record generation, seal, then call `validate_run_directory()`. Both sidecar timing variants are covered, as are observer fail/exception, chain success followed by Gate-B validation failure, resealed acceptance drift, protocol-2 PASS and legacy behavior.

Phase A exact scope 4 paths; Phase A.5 7; Phase B 11; authorized allowlist 12 (validator production path unchanged). Existing source-pin inventory remains 38/38; four SHA-256/byte-size entries refreshed. Pre-reconciliation focused runner/validator 284 passed/2 skipped; scope 22 passed; Step-7 432 passed/2 skipped with only expected dirty-runner pin drift; bringup 364 passed; py_compile 4 paths. Post-reconciliation final tests/coherence are pending and not preclaimed. RL 722, six-package external build, installed/source equality 18/18, observer/ROSIDL remain inherited from base; no runtime package source/dependency changed.

Guard/evidence/manifest SHA-256 `e84a65455ee04be1fcfe68b821994a4ac7d9d778d3d4438555a06df85d185f13` / `8975846020e8ad19a0a4363d7457dc2971e344d7ea4ffad61f2abd032fffe695` (96747 bytes) / `b549835b46e1c234979a5935e1175086145822c9dc77ecf3b6480e140803cbf9`. Guard PENDING/capacity 1/acquisition 0/NOT_GRANTED; Gate B NOT_STARTED; RUNTIME_APPROVED NOT_APPROVED. Invocation_020 remains immutable FAIL; timeout remains `ROOT_CAUSE_UNRESOLVED`. No runtime, retry, integration or hardware action occurred.

`PLAN_UPDATE_PROPOSAL`: Run005 observer acceptance persistence L1; branch and base as above; evidence IMPLEMENTED_OFFLINE_ONLY; source/test and pin closure completed, post-reconciliation final checks pending; next action is final offline verification and conditional single review delivery. Runtime authorization remains separate.

## 2026-10-24 — Final verification result: observer acceptance persistence corrective

Post-reconciliation final verification completed against the exact 11-path Phase B scope from `50fd738de91283c2c879f58fa6286ce5e15fc4bf`. Step-7 tools: 433 passed, 2 skipped; full `mecanum_nav_bringup/test`: 364 passed. Focused runner/validator: 284 passed, 2 skipped; scope/lineage checks: 22 passed; Python 3.12.3 / Pydantic 2.10.6; four changed Python files passed `py_compile`. Canonical JSON, duplicate/non-finite rejection, 38/38 source pins (SHA-256 and byte size), exact scope (11 actual paths within the 12-path allowlist), guard/evidence/manifest linkage, Ledger parent-byte-prefix, and staged/unstaged diff checks passed. Four existing pin hash/size values were refreshed; membership stayed 38.

RL tests (722 passed), six-package external build, installed/source equality (18 comparisons), and observer/ROSIDL checks are inherited from the verified base; they were not rerun because package runtime source, dependencies, and build inputs did not change. No runtime or integration was run. Guard remains PENDING/capacity 1/acquisition 0/NOT_GRANTED; Gate B remains NOT_STARTED; RUNTIME_APPROVED remains NOT_APPROVED. Invocation_020 remains historical and unchanged; its timeout cause remains `ROOT_CAUSE_UNRESOLVED`.
