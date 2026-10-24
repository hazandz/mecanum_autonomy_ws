# PID-2A four-wheel speed lab

## Purpose

PID-2A runs four independent feedforward + PI wheel-speed loops at the same time. It measures shared-drive operation and wheel synchronization on a stationary test stand. It does not implement chassis navigation, mecanum kinematics, ROS commands, strafe, rotation, or arbitrary wheel targets.

## Controller

```text
Kp = 0.084
Ki = 1.05
Integral clamp = +/-80 permille per wheel
PWM hard limit = 400 permille (40%)
Control period = 20 ms nominal; measured dt is used
Log rate = 25 Hz
```

The validated feedforward table is stored in `pid2_lab.c`, indexed by wheel and direction. Encoder speeds are signed in robot-forward coordinates; controller error is normalized into the selected direction.

## First runtime: ALL_FORWARD only

Run this first profile only in `PID2_MODE_ALL_FORWARD`:

```text
+500 -> +1000 -> +1400 -> +1000 -> +500 counts/s
1500 ms per plateau; 400 ms zero gap before and after
```

Before powering the motor driver, confirm a stable test stand, all four wheels fully off the ground, battery and driver wiring checked, and physical E-stop reachable. PID-2 controls all wheels simultaneously; do not use this test on the floor. This README does not direct an ALL_REVERSE run.

## STM32CubeIDE / ST-Link workflow

1. Refresh the CubeIDE project/source list so `Core/Src/pid2_lab.c` is included in the build, then build and flash the experiment firmware.
2. Open the ST-Link debugger and inspect `g_pid2`; verify `state == PID2_STATE_IDLE`, motor gate low, and all outputs zero.
3. Set `g_pid2.mode = PID2_MODE_ALL_FORWARD` (`1`), and confirm gains/profile values.
4. Set `g_pid2.request = PID2_REQUEST_CLEAR_LOG` (`3`), resume briefly, suspend, and verify IDLE.
5. Set `g_pid2.request = PID2_REQUEST_RUN_PROFILE` (`1`) and resume.
6. Wait for `PID2_STATE_COMPLETE` (`3`). To stop at any time, set `g_pid2.request = PID2_REQUEST_ABORT` (`2`); ABORT is checked first each cycle.
7. Suspend and verify the motor gate is low, all four `u_output` fields are zero, `fault_wheel_mask == 0`, and `log_overflow == 0`.
8. Export `g_pid2_log[0..g_pid2.log_count-1]` from RAM as CSV using the header below. Add current `g_pid2.log_overflow` and final `g_pid2.state` as columns `log_overflow` and `final_state` on every row.
9. Run `python3 firmware_STM32/Test/pid2_analyze.py path/to/pid2.csv`.

The analyzer requires five complete plateaus, all four wheels, no FAULT/overflow, final state COMPLETE, and per-wheel/synchronization criteria. Optional PID-1 integral comparison:

```bash
python3 firmware_STM32/Test/pid2_analyze.py pid2.csv --pid1-baseline pid1.csv
```

That optional output is only a possible shared-supply loading indication; this lab has no voltage sensor and does not measure voltage sag.

## CSV columns

```text
timestamp_ms,state,mode,target_cps,dt_ms,fl_measured_cps,fl_error_cps,fl_u_ff_permille,fl_u_i_permille,fl_u_output_permille,fl_encoder_delta,fr_measured_cps,fr_error_cps,fr_u_ff_permille,fr_u_i_permille,fr_u_output_permille,fr_encoder_delta,rl_measured_cps,rl_error_cps,rl_u_ff_permille,rl_u_i_permille,rl_u_output_permille,rl_encoder_delta,rr_measured_cps,rr_error_cps,rr_u_ff_permille,rr_u_i_permille,rr_u_output_permille,rr_encoder_delta,sync_spread_cps,sync_warning,log_overflow,final_state
```

`state`, `mode`, and `final_state` may be numeric. State `2` is RUN_PROFILE, `3` is COMPLETE, and `5` is FAULT. Mode `1` is ALL_FORWARD, `2` is ALL_REVERSE.
