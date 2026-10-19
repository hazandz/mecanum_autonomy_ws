# Step-7 Run005 — installed package-prefix closure correction

Classification: `L1_HISTORICAL_PACKAGE_PREFIX_CLOSURE_CORRECTION`. Exact base and required sole parent: `b7105ccb651da6d0dcb916d7544481f7beacaae1`. Integration base: `f7f98c683d59cf4c62e462da9f37d4ffb2455c80`. Architecture SHA-256: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.

## Historical disposition

Run004 remains the immutable pre-acquire failure `STEP07_NAV2_BASELINE_RUN004_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED`. Its sole root cause is `PACKAGE_PREFIX_CLOSURE_MISSING_ROBOT_URDF_FINAL_DESCRIPTION`. This is a package-prefix preflight defect only, not a Pydantic, Fuel, Nav2, Gate B, safety, TF, or robot-runtime failure. Run004 is not retried and its guard, evidence, manifest, decision, runtime artifacts, and runtime worktree are unchanged.

## Run005 correction

The Run005 runner requires exactly these package prefixes: `ros_gz_sim`, `ros_gz_bridge`, `mecanum_base_bridge`, `mecanum_nav_bringup`, `ROBOT_URDF_final_description`, `robot_localization`, `step07_nav2_baseline_runtime_observer`, and `mecanum_nav_rl`. It verifies before installed-byte comparisons that every package used by the installed-file equality checks belongs to the collected prefix set. Regression coverage exercises the complete mocked host-preflight path and rejects a missing prefix.

The contract test’s final Run005 scope invariant now requires exact `RUN005_PATHS` for both dirty and committed candidate states; it no longer treats worktree dirtiness as a Phase-A/Phase-B selector. Its existing Run005 source-pin entry was refreshed to SHA-256 `50e826ba266c8177ec73c450c0a8a3ea77ae33184d98b0c534c4f08f1d6f409b`, size `40187`. The source-pin inventory remains 21 unique current-worktree pins, distinct from the 13-path delivery scope.

The canonical runtime interpreter remains `/home/hazan/step07_runtime_python312_pydantic_2_10_6/bin/python` with Python 3.12 and Pydantic 2.10.6. Fuel lowercase-path, map/world, TF ownership, Gate-B observer, safety/final-command, capacity, and retry contracts remain unchanged.

## Scope and offline evidence

The exact Run005 corrective scope is 13 paths from `b7105ccb651da6d0dcb916d7544481f7beacaae1`. Historical Run001–Run004 pins are checked using exact Git blobs at their historical commits, with SHA-256 and byte-size verification and no worktree fallback. Historical scope counts remain root campaign 23, lifecycle/QoS 14, acceptance-matrix 9, Run002 13, Run003 14, Run004 original 17, and Run004 corrective 11.

Phase-A results: focused Run005 scope/historical-pin tests 46 passed; full Step-7 tools 182 passed; bringup 239 passed; RL 707 passed; six-package external colcon build PASS; observer/interface tests PASS; installed source equality 6/6; eight required package prefixes and ROSIDL imports PASS; six Python files compiled; JSON/YAML/XML and duplicate-key checks PASS; Run005 pins 21/21; exact 13-path and historical checks PASS. Build/install/log and bytecode cache were outside the worktree.

Evidence SHA-256 `5a7c70bb5c9a21300d23ab0d2318223fcb1909ff6326b0b6540aba4863baedae`. Guard manifest SHA-256 `b51c528653b9b6b58118f020e05c6d2148ae419fc8acb89563cd268dc2542986`. Guard SHA-256 `14820301519f35bef273627ca0cd95372413389284df6c824a5f2d37ed3dcf5e`.

Run005 remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`, retry disabled. Runtime evidence is `NOT_CREATED`; `GATE_B=NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. No runtime was executed and no integration is claimed. Evidence ceiling: `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.
