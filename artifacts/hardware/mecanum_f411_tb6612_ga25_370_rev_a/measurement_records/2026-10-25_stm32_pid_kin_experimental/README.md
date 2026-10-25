# STM32 PID/KIN experimental HIL record

Record date: 2026-10-25. Hardware profile: `mecanum_f411_tb6612_ga25_370_rev_a`.

This directory preserves three Owner-supplied loaded-floor HIL raw logs byte-for-byte, along with the source commit pins and the experimental worktree status/diff at evidence capture. The experimental source worktree was dirty: use `source_provenance.json` and `experimental_worktree_status.txt` to distinguish committed PID4/KIN1/KIN2 source from local PID0/analyzer/launch modifications and untracked artifacts. Classification is `SOURCE_COMMIT_PINNED_WITH_DECLARED_DIRTY_WORKTREE_STATE`; this is not an exact-clean-commit firmware reproduction. No firmware ELF/flash image was supplied or pinned.

## Archived logs

| Log | Bytes | SHA-256 | RUN samples | Command |
|---|---:|---|---:|---|
| `kin2_floor_forward_vx020.bin` | 31680 | `ec2d371e1ff887e962d4dc4930c42c858ab645f2c56e32389a8602551977c9d3` | 124 | `vx=+0.2 m/s, vy=0, wz=0` |
| `kin2_floor_strafe_left_vy010.bin` | 31680 | `c363289aabdd98a244a3d0d0b5edef01cbb297b6175c29a314ec2a596a608199` | 124 | `vx=0, vy=+0.1 m/s, wz=0` |
| `kin2_floor_rotate_cw_wz050.bin` | 31680 | `cb79f85b05094baec151183e5c041f6ea4031e910b44d7249f60469354c32fca` | 124 | `vx=0, vy=0, wz=-0.5 rad/s` |

Each file is 240 slots × 132-byte `Pid4LabSample`. Offline parsing used little-endian fields matching the committed sample layout. Each has 124 RUN records, 20 ms control `dt`, and 40 ms log spacing. The first-to-last timestamp span is 4.920 s; 124 sample periods represent 4.960 s nominal sample coverage. Trailing zero slots are not RUN records. `sampled_log_encoder_delta_sum_not_authoritative` is retained only as a diagnostic: logs are 25 Hz while control runs at 50 Hz and must not replace the Owner GDB cumulative totals.

Per-wheel derived steady metrics in the evidence JSON use the last 30% (38 samples) of RUN records. Manual displacement/heading notes and cumulative totals are Owner-reported; they are not reconstructed from encoder logs.

## Owner-reported physical observations

- Forward: about 0.95 m, slight right drift, no meaningful yaw rotation.
- Strafe Left: about 0.43 m left, no meaningful forward/backward drift, very small heading change.
- Rotate CW: rotated in place, no meaningful center drift; angle not formally measured. No rotational geometry accuracy is claimed.

## Calibration and approval boundary

The campaign used experimental values: wheel diameter 0.097 m, wheelbase 0.216 m, track 0.190 m, `Lx=0.108 m`, `Ly=0.095 m`, `K=0.203 m`, CPR 937.2, max target 1400 cps, `Kp=0.084`, `Ki=1.05`. Track has physical measurement provenance from the experimental campaign but is not canonically approved; wheelbase is not formally closed; CPR is experimental/theoretical and not canonical truth. A prior manual one-wheel revolution observation was about 906 counts, so encoder scale closure remains required. PID/KIN HIL evidence does not approve the hardware manifest.

The hardware manifest remains `TBD_MEASURED`; approval remains `DRAFT`, `motor_enable_allowed=false`. This record does not prove UART runtime, watchdog, E-stop, Pi forward kinematics, `/wheel/odometry_raw`, or real-hardware EKF. It does not change WP12/WP07, Gate 3/4, `DEPLOY_REAL`, or any hardware approval state.

`sha256sums.txt` lists every committed file in this directory except itself, in stable lexical path order.
