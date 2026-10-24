# PID-1A closed-loop speed lab

## Purpose

PID-1A is an experimental feedforward + PI closed-loop wheel-speed validation lab. It is not the production controller. It uses measured encoder counts/second and logs to RAM; there is no UART output in the controller loop.

## Default gains and profile

```text
Kp = 0.084
Ki = 1.05
PWM hard limit = 400 permille (40%)
Profile = 500 -> 1000 -> 1400 -> 1000 -> 500 cps
Plateau = 1500 ms
Zero gap = 400 ms
```

The selected direction applies a sign to the target; one run uses one wheel and one direction. `selected_wheel`: 0 FL, 1 FR, 2 RL, 3 RR. `direction`: 1 FORWARD, 2 REVERSE.

## Debugger workflow

1. Flash the experiment firmware and keep all wheels off the floor on a test stand.
2. Open the ST-Link debugger; confirm `g_pid1.state == PID1_STATE_IDLE` and safe zero output.
3. Set `g_pid1.selected_wheel = 0` and `g_pid1.direction = 1` for the first FL FORWARD run.
4. Set/confirm `g_pid1.plateau_ms = 1500`, `g_pid1.zero_gap_ms = 400`, `g_pid1.kp = 0.084`, `g_pid1.ki = 1.05`.
5. Set `g_pid1.request = PID1_REQUEST_CLEAR_LOG`, resume briefly, then suspend and confirm IDLE.
6. Set `g_pid1.request = PID1_REQUEST_RUN_PROFILE`, resume.
7. Watch state and wait for `PID1_STATE_COMPLETE`; use `PID1_REQUEST_ABORT` at any time to stop immediately.
8. Suspend and verify motor enable is low and `g_pid1.u_output == 0`.
9. Dump `g_pid1_log[0..g_pid1.log_count-1]` from RAM into CSV with the header below. Add the current `g_pid1.log_overflow` value and final `g_pid1.state` as `final_state` in every row. The analyzer requires final state `COMPLETE` (3) so an aborted/faulted run cannot pass.
10. Run `python3 firmware_STM32/Test/pid1_analyze.py path/to/pid1.csv`.

Keep a physical E-stop accessible during every bench test. PID-1 drives one wheel only, and firmware caps PWM at 40%. The analyzer is an initial screening tool; its PASS is not a runtime or safety approval.

## RAM CSV columns

```text
timestamp_ms,state,selected_wheel,direction,target_cps,measured_cps,error_cps,u_ff_permille,u_p_permille,u_i_permille,u_output_permille,encoder_delta,dt_ms,log_overflow
```

`target_cps` and `measured_cps` are signed in robot-forward coordinates. `error_cps` is calculated in the commanded direction's positive magnitude domain. `state` may be numeric; `RUN_PROFILE` is state 2 and `FAULT` is state 5.
