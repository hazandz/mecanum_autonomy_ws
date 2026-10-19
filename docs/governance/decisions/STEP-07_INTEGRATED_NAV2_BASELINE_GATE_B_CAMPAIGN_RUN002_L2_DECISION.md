# Step-7 NAV2_BASELINE Run002 — pre-acquire failure evidence correction

Classification: `L2_RUNTIME_EVIDENCE_CAPACITY_ONE_TERMINAL_OUTCOME_AUDITABILITY_CORRECTION`.

## Immutable authority and history

This candidate is based on `5a44cd9910e9b6d6058d8d2d9252a86f7cf9dcd8`; its integration base remains `f7f98c683d59cf4c62e462da9f37d4ffb2455c80`. Architecture SHA-256 is `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`. Run001 is immutable and remains `STEP07_RUN001_OFFICIAL_RUNNER_INVOKED_PREACQUIRE_FAILURE_NO_RETRY`. Its source did not persist a run record before guard acquisition, so no raw failure literal is asserted or fabricated.

## Run002 correction

Run002 is a separate capacity-one campaign (`STEP07_NAV2_BASELINE_RUN_002`, partition `mecanum_step7_nav2_run002_f7f98c6`). Its seed remains pending, acquisition count zero, `runtime_authorization=NOT_GRANTED`, and retry disabled. After source/guard identity and detached runtime worktree validation, any build or host-preflight failure is captured before guard acquisition in canonical `run_record.json` and `preflight_failure.json`, with exception class/message/traceback, five process call counts, pending guard state before/after, and terminal `STEP07_NAV2_BASELINE_RUN002_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED`. A manifest and sums cover the emitted payload. This path creates no lock, does not mutate the guard, starts no runtime process and does not perform teardown.

If preflight succeeds, the separate Run002 runner retains the one-shot campaign contract: acquire only after authorization and all preflight, separate bootstrap/composite process groups, and finalize only after ordered teardown. This candidate grants no Run002 authorization and runs no campaign.

Evidence ceiling: `OFFLINE_PREACQUIRE_FAILURE_EVIDENCE_MECHANISM_ONLY`; runtime evidence `NOT_CREATED`; `GATE_B=NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`.


## Historical source-pin reference correction — 13-path scope

Run001 source pins are verified against Git blobs at exact review commit `5a44cd9910e9b6d6058d8d2d9252a86f7cf9dcd8` using `git show`; missing commit/blob and SHA-256 or size mismatch fail closed. The Run001 guard, runner, validator, evidence, authorization, and historical outcome remain unchanged. Run002 source pins continue to verify current candidate worktree bytes. The Step-7 scope contract now records the immutable chain 23 root-campaign paths → 14 lifecycle/QoS paths → 9 acceptance-matrix paths → this exact 13-path Run002 corrective.
