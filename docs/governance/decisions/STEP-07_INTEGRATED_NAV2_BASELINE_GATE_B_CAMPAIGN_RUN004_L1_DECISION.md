# Step-7 Run004 — Python 3.12 / Pydantic V2 environment closure

Classification: `L1_PYTHON_RUNTIME_ENVIRONMENT_CLOSURE`. This is a source/offline candidate based on `fdc0e299515bda2286832aabec635948629517b5`; integration base remains `f7f98c683d59cf4c62e462da9f37d4ffb2455c80`. Architecture SHA-256: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.

## Historical disposition

Run003 remains the immutable pre-acquire failure `STEP07_NAV2_BASELINE_RUN003_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED`. The cause recorded for this corrective is `PYDANTIC_V2_RUNTIME_ENVIRONMENT_CLOSURE_MISSING`: the Python 3.12 overlay lacked Pydantic V2. This is not a Fuel, Nav2, Gate B, safety, or robot-runtime failure. Run003 is not changed or retried. Run001–Run003 historical source pins are verified from exact Git blobs at their respective commits by SHA-256 and byte size, with no worktree fallback.

## Run004 dependency contract

The canonical interpreter is `/home/hazan/step07_runtime_python312_pydantic_2_10_6/bin/python` (Python 3.12) with exact requirement `pydantic==2.10.6`. The host provisioning helper creates a `--system-site-packages` virtual environment outside the repository and is Owner-invoked only. It is never called by the official runner. The runner does not install dependencies or access the network.

Before guard acquisition, Run004 validates the exact interpreter path and executable status, Python minor version, exact Pydantic version, `rclpy`, Gate-B observer import, and that the imported observer resolves inside the install overlay. These failures fail closed with `RUNTIME_PYTHON_ENVIRONMENT_INVALID:<reason>`. The exact interpreter is used for the probe, Gate-B observer process, and ROSIDL import check; the Gate-B observer does not fall back to bare `python3`.

## Guard, source pins and evidence ceiling

Run004 seed remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`, retry disabled. Run004 has 20 unique current-worktree SHA-256/size source pins, distinct from its exact 17 changed paths. No runtime evidence is created by this candidate. `GATE_B=NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`; runtime eligibility is false.

Offline results: Step-7 tools 138 passed; `mecanum_nav_rl/test` 707 passed; `mecanum_nav_bringup/test` 239 passed; six-package external colcon build PASS; observer and ROSIDL colcon tests 25 passed; py_compile 9 files PASS. The test dependency fingerprint is Python 3.12.3/Pydantic 2.10.6, with `pip freeze` SHA-256 `8fc5de359c1faf157acf11c35b740cd433abbe4d3a432158d88ff75e6677d26e`.

Evidence JSON SHA-256: `65365fa083db06098e3dfe63568a9ba1ff7f78eda596c9c3c2ab301e1a20a444`. Guard-manifest SHA-256: `7fd9eb0d27e45fa348233b0f7df7de8cf34ba0caa550c28c701c52e80f4a1c6d`.

Evidence: `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN004_L1_EVIDENCE.json`. Guard manifest: `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN004_GUARD_MANIFEST.json`.
