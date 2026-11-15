#include "slam_bench_motor_runtime.h"

/* PID4 evidence profile, retained disabled pending runtime/firmware validation. */
const slam_bench_motor_config_t slam_bench_motor_config = {
    .wheel_diameter_m = 0.097f,
    .wheelbase_m = 0.216f,
    .track_m = 0.190f,
    .counts_per_revolution = 937.2f,
    .max_wheel_cps = 1400.0f,
    .max_pwm_permille = 400.0f,
    .kp = 0.084f,
    .ki = 1.05f,
    .integral_limit = 80.0f,
    .forward_ff_u0 = {40.330665f, 32.415574f, 61.698998f, 37.521999f},
    .forward_ff_kv = {0.217819026f, 0.231811480f, 0.212679580f, 0.223981830f},
    .reverse_ff_u0 = {36.253577f, 34.233335f, 54.760209f, 32.707200f},
    .reverse_ff_kv = {0.225076821f, 0.226312521f, 0.223609266f, 0.229221684f},
    /* Owner approval remains false: the experimental profile is never armed. */
    .experimental_profile_enabled = false,
};

bool slam_bench_motor_profile_pid_config_for_wheel(
    unsigned wheel_index, PidControllerConfig *config)
{
    if (config == 0 || wheel_index >= 4U) {
        return false;
    }
    *config = (PidControllerConfig){
        .kp = slam_bench_motor_config.kp,
        .ki = slam_bench_motor_config.ki,
        .integral_limit = slam_bench_motor_config.integral_limit,
        .output_limit = slam_bench_motor_config.max_pwm_permille,
        .max_target_cps = slam_bench_motor_config.max_wheel_cps,
        .forward_ff_u0 = slam_bench_motor_config.forward_ff_u0[wheel_index],
        .forward_ff_kv = slam_bench_motor_config.forward_ff_kv[wheel_index],
        .reverse_ff_u0 = slam_bench_motor_config.reverse_ff_u0[wheel_index],
        .reverse_ff_kv = slam_bench_motor_config.reverse_ff_kv[wheel_index],
    };
    return true;
}
