# WP12 STM32 PID/KIN experimental HIL evidence promotion

**Classification:** L2 evidence-only candidate
**Evidence level:** `EXPERIMENTAL_HIL_SUPPORTING_EVIDENCE`
**Candidate base:** `fdc0e299515bda2286832aabec635948629517b5` on `origin/integration/implementation`
**Evidence date:** 2026-10-25

## Decision record

This candidate archives owner-supplied raw logs and records supporting observations from an experimental STM32 PID and inverse-kinematics campaign on the physical mecanum robot. The reported pipeline was: body twist `[vx, vy, wz]` → STM32 inverse kinematics → four signed wheel CPS targets → FF + PI wheel control → PWM/direction → physical mecanum motion. Forward, Strafe Left, and Rotate CW each have supporting HIL evidence in the archived records.

The experimental sources are pinned to PID4 commit `231010db7de8a3f49f49a715da4339e129a48755`, KIN1 commit `cdfe81ed2d57cd18e94ee4b53c84a7c95679b321`, and KIN2 commit `515e4256f39340fa0de174e9bde01018dac81449`. The source worktree was dirty at capture. Its committed source provenance, three tracked modifications, untracked artifacts, raw logs, and tracked diff are recorded separately. The classification is `SOURCE_COMMIT_PINNED_WITH_DECLARED_DIRTY_WORKTREE_STATE`; this record does not claim that the HIL binary was built from an exact clean commit.

## Recorded motion evidence

- **Forward**, command `(+0.2, 0, 0)`: expected wheel target about `+615.093 cps` for all wheels. Owner GDB cumulative totals: FL 2765, FR 2757, RL 2776, RR 2786; spread 29 counts (about 1.05%). Owner-reported manual displacement was about 0.95 m, with slight right drift and no meaningful yaw. Raw log analysis reports 124 RUN samples, 40 ms logging interval, and 4.960 s nominal sample coverage. The final-30% measured speeds were FL 607.9, FR 625.0, RL 611.8, RR 617.1 cps; reported PWM saturation was 0 ms for each wheel.
- **Strafe Left**, command `(0, +0.1, 0)`: expected signs `[-,+,+,-]`, targets about `[-307.546,+307.546,+307.546,-307.546] cps`. Owner GDB totals: FL -1348, FR +1316, RL +1308, RR -1312. Manual observation: about 0.43 m left, no meaningful forward/backward drift, very small heading change. Parsed-log steady metrics and synchronization summaries are in the evidence JSON.
- **Rotate CW**, command `(0, 0, -0.5)`: expected signs `[+,-,+,-]`, targets about `[+312.159,-312.159,+312.159,-312.159] cps`. Owner GDB totals: FL +1373, FR -1384, RL +1380, RR -1380. Owner reported in-place rotation and no meaningful center drift. The yaw angle was not formally measured, so rotational geometry accuracy is not claimed.

The three raw logs are 31,680 bytes each (240 × 132-byte `Pid4LabSample`). Each contains 124 RUN samples at 40 ms log spacing; control `dt` is 20 ms. The recorded first-to-last timestamp span is 4.920 s; 124 nominal intervals cover 4.960 s. Decimated `encoder_delta` sums are diagnostic only and do not replace the authoritative GDB cumulative totals.

## Calibration and authority limits

Experimental constants included wheel diameter 0.097 m, wheelbase 0.216 m, track 0.190 m, `Lx=0.108 m`, `Ly=0.095 m`, `K=0.203 m`, CPR 937.2, max wheel target 1400 cps, `Kp=0.084`, and `Ki=1.05`. The 0.190 m track has physical measurement provenance from the experimental campaign but is not canonically approved. The 0.216 m wheelbase is not formally closed. CPR 937.2 remains experimental/theoretical; a prior manual one-wheel revolution observation was approximately 906 counts, so encoder-scale closure remains required.

The hardware manifest remains `TBD_MEASURED`; `approval.yaml` remains `DRAFT` with `motor_enable_allowed: false`. PID/KIN HIL evidence does not approve the hardware manifest. This is not production firmware validation. UART runtime, watchdog, physical E-stop, Pi forward kinematics, real `/wheel/odometry_raw`, and real-hardware EKF remain unproven by this campaign.

## Status boundary

```text
change_level: L2
evidence_level: EXPERIMENTAL_HIL_SUPPORTING_EVIDENCE
production_integration: NOT_PERFORMED
hardware_profile_approval: NOT_CHANGED
motor_enable_allowed: NOT_CHANGED
WP12_status_transition: NONE
WP07_status_transition: NONE
Gate3_status: NOT_CLAIMED
Gate4_status: NOT_CLAIMED
DEPLOY_REAL_ready: false
```

No authority, architecture, hardware manifest, approval, plan, registry, ledger, firmware, ROS, or runtime status is changed by this evidence-only record. Full source/raw provenance and parser-derived metrics are in `docs/governance/evidence/WP12_STM32_PID_KIN_EXPERIMENTAL_HIL_EVIDENCE.json` and the dated measurement directory under the hardware profile.
