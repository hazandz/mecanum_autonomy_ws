# Step-7 Run004 — provisioning/runtime environment boundary correction

Classification: `L1_HOST_PROVISIONING_HELPER_ENVIRONMENT_DECOUPLING`. Corrective base and required sole parent: `cbf59ff938d8b96ec650859d9367bc6cb840f0c6`. Run004 original candidate base: `fdc0e299515bda2286832aabec635948629517b5`. Integration base: `f7f98c683d59cf4c62e462da9f37d4ffb2455c80`. Architecture SHA-256: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.

## Finding and fixed behavior

The prior host provisioning helper attempted to import `rclpy` before ROS Jazzy setup and the install overlay were sourced. That made provisioning depend on the caller shell. This corrective confines the helper to absolute outside-repository venv target validation, Python 3.12, exact `pydantic==2.10.6`, executable interpreter, and a valid non-secret package/version fingerprint. The helper records `rclpy_validation=DEFERRED_TO_SOURCED_RUNNER_PREFLIGHT`; absence of `rclpy` in the provisioning shell is not a helper failure.

The official Run004 runner remains the source of truth for ROS-dependent checks after `prepare_ros_environment()` sources ROS and the overlay: `rclpy`, Gate-B observer import, and observer module location within the installed overlay. Its `RUNTIME_PYTHON_ENVIRONMENT_INVALID:RCLPY_IMPORT_FAILED` pre-acquire failure remains fail-closed. Canonical interpreter, requirements pin, Gate-B semantics, guard behavior, historical source-pin policy, and retry policy are unchanged.

## Scope and evidence

The Run004 original candidate remains exactly 17 paths from `fdc0e299515bda2286832aabec635948629517b5` to `cbf59ff938d8b96ec650859d9367bc6cb840f0c6`. This corrective has exactly 11 paths from `cbf59ff938d8b96ec650859d9367bc6cb840f0c6`; its source/test Phase A scope is exactly four paths and its final scope adds the approved five remaining governance/guard paths plus the contract-test path as listed in evidence. The 20-entry Run004 current-worktree source-pin inventory is distinct from changed-path count. Run001–Run003 pins are checked against exact historical Git blobs; Run004 pins are checked against current candidate bytes.

Run004 guard remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`. Run001–Run003 historical artifacts remain unchanged. No runtime was executed; runtime evidence is `NOT_CREATED`; Gate B is `NOT_STARTED`; `RUNTIME_APPROVED` is `NOT_APPROVED`.

Offline verification: Step-7 tools 139 passed; bringup 239 passed; RL 707 passed; six-package external colcon build PASS; observer/ROSIDL tests PASS; py_compile and static parsing PASS; historical preservation, 20/20 source pins, exact scope chain, Ledger prefix, and diff checks PASS.

Evidence SHA-256: `e3b9eaab981f7bcb44192fcc1d61af53c79878f79103037a3857adc4389ff8ff`. Guard manifest SHA-256: `1369bac8fd60586a8e2231ff9f458cdc2820cfa599c32ab6e35df98533a0c376`. Guard SHA-256: `9704aad346fad36ae8a66054eac69b2ff882243c6dc9130cdc348b9dc4971abe`.
