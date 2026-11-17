#include "slam_bench_motor_runtime.h"

#if defined(MECANUM_USE_GENERATED_HARDWARE_CONFIG)
#include "generated_hardware_config.h"
#define MANUAL_SLAM_WHEEL_DIAMETER_M MECANUM_WHEEL_DIAMETER_M
#define MANUAL_SLAM_WHEELBASE_M MECANUM_WHEELBASE_M
#define MANUAL_SLAM_TRACK_M MECANUM_TRACK_M
#define MANUAL_SLAM_COUNTS_PER_REV MECANUM_COUNTS_PER_WHEEL_REV
#define MANUAL_SLAM_ENCODER_SIGNS_VALID MECANUM_ENCODER_SIGNS_VALID
#define MANUAL_SLAM_SIGN_FL MECANUM_ENCODER_SIGN_FL
#define MANUAL_SLAM_SIGN_FR MECANUM_ENCODER_SIGN_FR
#define MANUAL_SLAM_SIGN_RL MECANUM_ENCODER_SIGN_RL
#define MANUAL_SLAM_SIGN_RR MECANUM_ENCODER_SIGN_RR
#else
/* Host-only profile fixture mirrors the selected SLAM bench manifest. */
#define MANUAL_SLAM_WHEEL_DIAMETER_M 0.097f
#define MANUAL_SLAM_WHEELBASE_M 0.216f
#define MANUAL_SLAM_TRACK_M 0.190f
#define MANUAL_SLAM_COUNTS_PER_REV 937.2f
#define MANUAL_SLAM_ENCODER_SIGNS_VALID 1U
#define MANUAL_SLAM_SIGN_FL 1
#define MANUAL_SLAM_SIGN_FR 1
#define MANUAL_SLAM_SIGN_RL 1
#define MANUAL_SLAM_SIGN_RR 1
#endif

/* Owner-selected offline MANUAL_SLAM target candidate, gated by bench manifest.
 * PID4 gains/feedforward remain evidenced only through the prior 1400 tick/s run. */
const slam_bench_motor_config_t slam_bench_motor_config = {
    .wheel_diameter_m = MANUAL_SLAM_WHEEL_DIAMETER_M,
    .wheelbase_m = MANUAL_SLAM_WHEELBASE_M,
    .track_m = MANUAL_SLAM_TRACK_M,
    .counts_per_revolution = MANUAL_SLAM_COUNTS_PER_REV,
    .max_wheel_cps = 2000.0f,
    .max_pwm_permille = 400.0f,
    .kp = 0.084f,
    .ki = 1.05f,
    .integral_limit = 80.0f,
    .forward_ff_u0 = {40.330665f, 32.415574f, 61.698998f, 37.521999f},
    .forward_ff_kv = {0.217819026f, 0.231811480f, 0.212679580f, 0.223981830f},
    .reverse_ff_u0 = {36.253577f, 34.233335f, 54.760209f, 32.707200f},
    .reverse_ff_kv = {0.225076821f, 0.226312521f, 0.223609266f, 0.229221684f},
    .encoder_tick_sign = {MANUAL_SLAM_SIGN_FL, MANUAL_SLAM_SIGN_FR,
                          MANUAL_SLAM_SIGN_RL, MANUAL_SLAM_SIGN_RR},
    .experimental_profile_enabled = true,
    .manual_slam_bench_profile = true,
    .tracking_guard_faults_nonfatal = true,
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
