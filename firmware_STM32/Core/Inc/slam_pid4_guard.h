#ifndef SLAM_PID4_GUARD_H
#define SLAM_PID4_GUARD_H

#include <stdbool.h>
#include <stdint.h>

#define SLAM_PID4_WHEEL_COUNT 4U
#define SLAM_PID4_SAMPLE_PERIOD_MS 20U
#define SLAM_PID4_MAX_CONTROL_DT_MS 100U
#define SLAM_PID4_RAMP_DURATION_MS 1000U
#define SLAM_PID4_DIRECTION_THRESHOLD_CPS 100.0f
#define SLAM_PID4_DIRECTION_FAULT_MS 200U
#define SLAM_PID4_STALL_OUTPUT_PERMILLE 120.0f
#define SLAM_PID4_STALL_GRACE_MS 400U
#define SLAM_PID4_STALL_FAULT_MS 500U
#define SLAM_PID4_SYNC_FAULT_CPS 300.0f
#define SLAM_PID4_SYNC_FAULT_MS 500U
#define SLAM_PID4_SYNC_TARGET_TOLERANCE_CPS 1.0f

typedef enum {
    SLAM_PID4_FAULT_NONE = 0,
    SLAM_PID4_FAULT_BAD_DT,
    SLAM_PID4_FAULT_INVALID_TARGET,
    SLAM_PID4_FAULT_WRONG_DIRECTION,
    SLAM_PID4_FAULT_STALL,
    SLAM_PID4_FAULT_SYNC,
    SLAM_PID4_FAULT_INVALID_PWM,
} slam_pid4_fault_t;

typedef enum {
    SLAM_PID4_COMMUTATE_COAST = 0,
    SLAM_PID4_COMMUTATE_SET_DIRECTION,
    SLAM_PID4_COMMUTATE_DRIVE,
} slam_pid4_commutation_t;

typedef struct {
    float ramped_target_cps[SLAM_PID4_WHEEL_COUNT];
    int8_t target_sign[SLAM_PID4_WHEEL_COUNT];
    int8_t direction_sign[SLAM_PID4_WHEEL_COUNT];
    uint32_t active_ms[SLAM_PID4_WHEEL_COUNT];
    uint32_t wrong_direction_ms[SLAM_PID4_WHEEL_COUNT];
    uint32_t stall_ms[SLAM_PID4_WHEEL_COUNT];
    uint32_t sync_active_ms;
    uint32_t sync_fault_ms;
    float sync_spread_cps;
    bool sync_warning;
} slam_pid4_guard_state_t;

void slam_pid4_guard_reset(slam_pid4_guard_state_t *state);
slam_pid4_fault_t slam_pid4_guard_ramp(
    slam_pid4_guard_state_t *state,
    const float requested_cps[SLAM_PID4_WHEEL_COUNT], uint32_t dt_ms);
slam_pid4_fault_t slam_pid4_guard_check(
    slam_pid4_guard_state_t *state,
    const float requested_cps[SLAM_PID4_WHEEL_COUNT],
    const float measured_cps[SLAM_PID4_WHEEL_COUNT],
    const float effort_permille[SLAM_PID4_WHEEL_COUNT], uint32_t dt_ms);
slam_pid4_commutation_t slam_pid4_guard_commutate(
    slam_pid4_guard_state_t *state, unsigned wheel_index, float target_cps);
bool slam_pid4_pwm_compare(uint32_t autoreload, float effort_permille,
                           uint32_t *compare);

#endif
