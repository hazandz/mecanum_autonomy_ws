#ifndef SLAM_BENCH_MOTOR_RUNTIME_H
#define SLAM_BENCH_MOTOR_RUNTIME_H

#include <stdbool.h>
#include <stdint.h>
#include "pid_controller.h"
#include "slam_pid4_guard.h"

typedef struct {
    float wheel_diameter_m, wheelbase_m, track_m, counts_per_revolution;
    float max_wheel_cps, max_pwm_permille;
    /* Output is permille: Kp is permille/(tick/s), Ki is permille/tick. */
    float kp, ki, integral_limit;
    /* PID4 coefficients, in wheel order FL/FR/RL/RR and per direction. */
    float forward_ff_u0[4], forward_ff_kv[4];
    float reverse_ff_u0[4], reverse_ff_kv[4];
    int8_t encoder_tick_sign[4];
    bool experimental_profile_enabled;
    /* Bench-only exception: tracking guards diagnose but do not SAFE_STOP. */
    bool manual_slam_bench_profile;
    bool tracking_guard_faults_nonfatal;
} slam_bench_motor_config_t;

typedef enum {
    SLAM_MOTOR_RUNTIME_FAULT_NONE = 0,
    SLAM_MOTOR_RUNTIME_FAULT_PROFILE,
    SLAM_MOTOR_RUNTIME_FAULT_ENCODER,
    SLAM_MOTOR_RUNTIME_FAULT_CONTROL,
    SLAM_MOTOR_RUNTIME_FAULT_DRIVER,
} slam_motor_runtime_fault_t;

/* Zero/invalid defaults are intentional; Owner must provide an approved bench profile. */
extern const slam_bench_motor_config_t slam_bench_motor_config;

/* Pure profile adapter; outputs controller values in permille and tick/s. */
bool slam_bench_motor_profile_pid_config_for_wheel(
    unsigned wheel_index, PidControllerConfig *config);

bool slam_bench_motor_runtime_init(void);
bool slam_bench_motor_runtime_profile_valid(void);
bool slam_bench_motor_runtime_set_body_command(float vx_mps, float vy_mps, float wz_radps);
void slam_bench_motor_runtime_stop(void);
/* Clear a latched controller fault only after an accepted new session CONFIG. */
bool slam_bench_motor_runtime_new_session(void);
slam_motor_runtime_fault_t slam_bench_motor_runtime_fault(void);
/* Last wrong-direction/stall/synchronization guard result; not an MCU fault bit. */
slam_pid4_fault_t slam_bench_motor_runtime_tracking_diagnostic(void);
/* Policy helper: only explicit MANUAL_SLAM bench config makes tracking nonfatal. */
bool slam_bench_motor_tracking_guard_fault_is_fatal(
    const slam_bench_motor_config_t *config, slam_pid4_fault_t fault);
bool slam_bench_motor_runtime_enabled(void);
bool slam_bench_motor_runtime_telemetry_allowed(void);
void slam_bench_motor_runtime_step(float dt_seconds);

#ifdef MECANUM_HOST_TEST
void slam_bench_motor_runtime_test_set_fault(slam_motor_runtime_fault_t fault);
void slam_bench_motor_runtime_test_set_tracking_diagnostic(slam_pid4_fault_t fault);
unsigned slam_bench_motor_runtime_test_step_calls(void);
#endif

#endif
