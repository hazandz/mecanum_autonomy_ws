# PID-3A loaded floor test

## Purpose

PID-3A is a fixed-gain FF + PI closed-loop validation on the floor. It runs only ALL_FORWARD at 500 counts/s for 5 seconds, then stops automatically. It is an experimental lab; it does not run ROS, UART, reverse, strafe, rotation, or chassis kinematics.

Controller constants: Kp = 0.084, Ki = 1.05, Kd = 0. PWM is limited to 400 permille (40%); the independent integral states are limited to ±80 permille. The validated PID-2A ALL_FORWARD feedforward coefficients are compiled into `pid3_lab.c`.

## First test: ALL_FORWARD, 500 cps, 5 seconds

Use a stable test setup and confirm battery and driver wiring. The first floor test needs a clear, level path, a reachable physical E-stop, and the operator outside the robot's path. Mark the starting center position, starting heading, and a straight reference line on the floor. Afterward, record `forward_distance_cm`, `lateral_drift_cm`, and `heading_error_deg` manually. STM32 wheel encoders do not provide those chassis pose measurements.

Conceptual debugger workflow:

1. Build/flash with ST-Link.
2. Start debugger.
3. Confirm PID3 IDLE and outputs zero.
4. CLEAR_LOG.
5. Set `arm_magic = PID3_ARM_MAGIC` (`0x50334131`).
6. Set `request = ARM_AUTORUN`.
7. Resume MCU.
8. Confirm/observe transition to ARMED_DELAY if possible; `arm_remaining_ms` starts at 10000.
9. Disconnect debugger WITHOUT RESET.
10. Unplug ST-Link cable.
11. Place robot on the clear floor.
12. Move away / keep physical E-stop reachable.
13. Wait for countdown.
14. Robot runs ALL_FORWARD at 500 cps for 5 seconds.
15. Robot stops automatically and holds safe outputs for 1 second before COMPLETE.
16. Keep STM32 powered. **DO NOT power off STM32, reset MCU, or reflash firmware after the floor run.**
17. Reconnect ST-Link.
18. Attach to the running target WITHOUT RESET and WITHOUT FLASH/download.
19. Suspend.
20. Confirm COMPLETE, `last_error == 0`, `fault_wheel_mask == 0`, and `log_overflow == 0`.
21. Dump `g_pid3_log[]` and the final `g_pid3` metadata to CSV.
22. Run `python3 firmware_STM32/Test/pid3_analyze.py <saved.csv>`.

A debug configuration that performs Reset-and-Halt loses the RAM log. Use attach without reset; no specific CubeIDE menu path is assumed here. Set `request = ABORT` while attached to stop during ARMED_DELAY, RUN, or STOP_HOLD. Physical E-stop remains the primary emergency stop.

## CSV export

Export only captured RUN samples, with this header (one row per `g_pid3_log` entry):

```text
timestamp_ms,state,target_cps,dt_ms,fl_measured_cps,fr_measured_cps,rl_measured_cps,rr_measured_cps,fl_error_cps,fr_error_cps,rl_error_cps,rr_error_cps,fl_u_ff_permille,fr_u_ff_permille,rl_u_ff_permille,rr_u_ff_permille,fl_u_i_permille,fr_u_i_permille,rl_u_i_permille,rr_u_i_permille,fl_u_output_permille,fr_u_output_permille,rl_u_output_permille,rr_u_output_permille,fl_encoder_delta,fr_encoder_delta,rl_encoder_delta,rr_encoder_delta,sync_spread_cps,sync_warning,total_delta_fl,total_delta_fr,total_delta_rl,total_delta_rr,log_overflow,final_state,last_error,fault_wheel_mask,completed_count
```

The final control metadata columns are copied from `g_pid3` after COMPLETE onto each CSV row. `total_delta_*` are final cumulative encoder counts from `g_pid3`, likewise repeated on each row. The analyzer reports firmware-level screening only. Total-count spread is diagnostic; manual chassis observations must be recorded separately.
