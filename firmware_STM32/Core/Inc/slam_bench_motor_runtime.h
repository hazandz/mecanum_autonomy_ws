#ifndef SLAM_BENCH_MOTOR_RUNTIME_H
#define SLAM_BENCH_MOTOR_RUNTIME_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    float wheel_diameter_m, wheelbase_m, track_m, counts_per_revolution;
    float max_wheel_cps, max_pwm_effort;
    float kp, ki, integral_limit;
    float forward_ff_u0, forward_ff_kv, reverse_ff_u0, reverse_ff_kv;
    bool experimental_profile_enabled;
} slam_bench_motor_config_t;

/* Zero/invalid defaults are intentional; Owner must provide an approved bench profile. */
extern const slam_bench_motor_config_t slam_bench_motor_config;

bool slam_bench_motor_runtime_init(void);
bool slam_bench_motor_runtime_set_body_command(float vx_mps, float vy_mps, float wz_radps);
void slam_bench_motor_runtime_stop(void);
bool slam_bench_motor_runtime_enabled(void);
bool slam_bench_motor_runtime_telemetry_allowed(void);
void slam_bench_motor_runtime_step(float dt_seconds);

#endif
