#include "slam_bench_motor_runtime.h"

#include <assert.h>
#include <math.h>

int main(void)
{
    static const float ff_u0_forward[4] = {40.330665f, 32.415574f, 61.698998f, 37.521999f};
    static const float ff_kv_forward[4] = {0.217819026f, 0.231811480f, 0.212679580f, 0.223981830f};
    static const float ff_u0_reverse[4] = {36.253577f, 34.233335f, 54.760209f, 32.707200f};
    static const float ff_kv_reverse[4] = {0.225076821f, 0.226312521f, 0.223609266f, 0.229221684f};
    assert(fabsf(slam_bench_motor_config.wheel_diameter_m - 0.097f) < 1e-6f);
    assert(fabsf(slam_bench_motor_config.wheelbase_m - 0.216f) < 1e-6f);
    assert(fabsf(slam_bench_motor_config.track_m - 0.190f) < 1e-6f);
    assert(fabsf(slam_bench_motor_config.counts_per_revolution - 937.2f) < 1e-4f);
    assert(fabsf(slam_bench_motor_config.max_wheel_cps - 1400.0f) < 1e-6f);
    assert(fabsf(slam_bench_motor_config.max_pwm_permille - 400.0f) < 1e-6f);
    assert(fabsf(slam_bench_motor_config.kp - 0.084f) < 1e-6f);
    assert(fabsf(slam_bench_motor_config.ki - 1.05f) < 1e-6f);
    assert(fabsf(slam_bench_motor_config.integral_limit - 80.0f) < 1e-6f);
    assert(!slam_bench_motor_config.experimental_profile_enabled);
    for (unsigned wheel = 0U; wheel < 4U; ++wheel) {
        PidControllerConfig config;
        PidControllerState state = {0.0f};
        float effort = 0.0f;
        assert(fabsf(slam_bench_motor_config.forward_ff_u0[wheel] - ff_u0_forward[wheel]) < 1e-6f);
        assert(fabsf(slam_bench_motor_config.forward_ff_kv[wheel] - ff_kv_forward[wheel]) < 1e-6f);
        assert(fabsf(slam_bench_motor_config.reverse_ff_u0[wheel] - ff_u0_reverse[wheel]) < 1e-6f);
        assert(fabsf(slam_bench_motor_config.reverse_ff_kv[wheel] - ff_kv_reverse[wheel]) < 1e-6f);
        assert(slam_bench_motor_profile_pid_config_for_wheel(wheel, &config));
        assert(fabsf(config.output_limit - 400.0f) < 1e-6f);
        assert(fabsf(config.max_target_cps - 1400.0f) < 1e-6f);
        assert(fabsf(config.kp - 0.084f) < 1e-6f);
        assert(fabsf(config.ki - 1.05f) < 1e-6f);
        assert(fabsf(config.integral_limit - 80.0f) < 1e-6f);
        assert(pid_controller_step(&config, &state, 1000.0f, 1000.0f, 0.02f, &effort));
        assert(fabsf(effort - (ff_u0_forward[wheel] + ff_kv_forward[wheel] * 1000.0f)) < 1e-4f);
        assert(pid_controller_step(&config, &state, -1000.0f, -1000.0f, 0.02f, &effort));
        assert(fabsf(effort + (ff_u0_reverse[wheel] + ff_kv_reverse[wheel] * 1000.0f)) < 1e-4f);
        pid_controller_reset(&state);
        assert(pid_controller_step(&config, &state, 100.0f, 90.0f, 0.02f, &effort));
        assert(fabsf(state.integral - 0.21f) < 1e-6f);
        for (unsigned step = 0U; step < 2U; ++step) {
            assert(pid_controller_step(&config, &state, 100.0f, 0.0f, 1.0f, &effort));
        }
        assert(fabsf(state.integral - 80.0f) < 1e-6f);
    }
    assert(!slam_bench_motor_profile_pid_config_for_wheel(4U, &(PidControllerConfig){0}));
    return 0;
}
