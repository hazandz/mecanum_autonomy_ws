#include "slam_bench_motor_runtime.h"

#include <assert.h>
#include <math.h>

int main(void)
{
    assert(fabsf(slam_bench_motor_config.wheel_diameter_m - 0.097f) < 1e-6f);
    assert(fabsf(slam_bench_motor_config.wheelbase_m - 0.216f) < 1e-6f);
    assert(fabsf(slam_bench_motor_config.track_m - 0.190f) < 1e-6f);
    assert(fabsf(slam_bench_motor_config.counts_per_revolution - 937.2f) < 1e-4f);
    assert(fabsf(slam_bench_motor_config.max_wheel_cps - 1400.0f) < 1e-6f);
    assert(!slam_bench_motor_config.experimental_profile_enabled);
    assert(slam_bench_motor_config.max_pwm_effort == 0.0f);
    assert(slam_bench_motor_config.kp == 0.0f);
    assert(slam_bench_motor_config.ki == 0.0f);
    assert(slam_bench_motor_config.forward_ff_u0 == 0.0f);
    assert(slam_bench_motor_config.forward_ff_kv == 0.0f);
    assert(slam_bench_motor_config.reverse_ff_u0 == 0.0f);
    assert(slam_bench_motor_config.reverse_ff_kv == 0.0f);
    return 0;
}
