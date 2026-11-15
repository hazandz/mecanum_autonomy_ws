#include "slam_bench_motor_runtime.h"

/* MANUAL_SLAM selected kinematics, but no compatible PID/FF/PWM profile. */
const slam_bench_motor_config_t slam_bench_motor_config = {
    .wheel_diameter_m = 0.097f,
    .wheelbase_m = 0.216f,
    .track_m = 0.190f,
    .counts_per_revolution = 937.2f,
    .max_wheel_cps = 1400.0f,
    /* Remaining zero fields intentionally make valid_config() reject motion. */
    .experimental_profile_enabled = false,
};
