#include "mecanum_kinematics.h"

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define TOL_CPS 0.02f
#define TOL_SCALE 0.0001f

static const MecanumKinematicsConfig owner_regression_config = {
    0.097f,
    0.216f,
    0.190f,
    937.2f,
    1400.0f
};

static void assert_close(float actual, float expected, float tolerance)
{
    assert(fabsf(actual - expected) <= tolerance);
}

static void assert_zero_output(const MecanumKinematicsOutput *out)
{
    const MecanumKinematicsOutput zero = {0};
    assert(memcmp(out, &zero, sizeof(*out)) == 0);
}

static void test_zero(void)
{
    MecanumKinematicsOutput out;
    assert(mecanum_kinematics_compute(&owner_regression_config, 0.0f, 0.0f, 0.0f, &out));
    for (int i = 0; i < MECANUM_WHEEL_COUNT; ++i) {
        assert(out.raw_target_cps[i] == 0.0f);
        assert(out.target_cps[i] == 0.0f);
    }
    assert(out.scale_factor == 1.0f);
    assert(out.limited == 0U);
}

static void test_owner_regression_vectors(void)
{
    MecanumKinematicsOutput out;

    assert(mecanum_kinematics_compute(&owner_regression_config, 0.20f, 0.0f, 0.0f, &out));
    for (int i = 0; i < MECANUM_WHEEL_COUNT; ++i) assert_close(out.target_cps[i], 615.093f, TOL_CPS);

    assert(mecanum_kinematics_compute(&owner_regression_config, 0.0f, 0.10f, 0.0f, &out));
    assert_close(out.target_cps[MECANUM_WHEEL_FL], -307.546f, TOL_CPS);
    assert_close(out.target_cps[MECANUM_WHEEL_FR], +307.546f, TOL_CPS);
    assert_close(out.target_cps[MECANUM_WHEEL_RL], +307.546f, TOL_CPS);
    assert_close(out.target_cps[MECANUM_WHEEL_RR], -307.546f, TOL_CPS);

    assert(mecanum_kinematics_compute(&owner_regression_config, 0.0f, 0.0f, -0.50f, &out));
    assert_close(out.target_cps[MECANUM_WHEEL_FL], +312.160f, TOL_CPS);
    assert_close(out.target_cps[MECANUM_WHEEL_FR], -312.160f, TOL_CPS);
    assert_close(out.target_cps[MECANUM_WHEEL_RL], +312.160f, TOL_CPS);
    assert_close(out.target_cps[MECANUM_WHEEL_RR], -312.160f, TOL_CPS);
}

static void test_mixed_and_proportional_saturation(void)
{
    MecanumKinematicsOutput out;
    assert(mecanum_kinematics_compute(&owner_regression_config, 0.20f, 0.10f, 0.50f, &out));
    assert_close(out.target_cps[MECANUM_WHEEL_FL], -4.613f, 0.03f);
    assert_close(out.target_cps[MECANUM_WHEEL_FR], 1234.799f, 0.03f);
    assert_close(out.target_cps[MECANUM_WHEEL_RL], 610.480f, 0.03f);
    assert_close(out.target_cps[MECANUM_WHEEL_RR], 619.706f, 0.03f);
    assert(out.limited == 0U);

    assert(mecanum_kinematics_compute(&owner_regression_config, 0.30f, 0.20f, 1.0f, &out));
    assert(out.limited == 1U);
    assert_close(fabsf(out.target_cps[MECANUM_WHEEL_FR]), 1400.0f, TOL_CPS);
    assert(out.scale_factor > 0.0f && out.scale_factor < 1.0f);
    for (int i = 0; i < MECANUM_WHEEL_COUNT; ++i) {
        assert_close(out.target_cps[i], out.raw_target_cps[i] * out.scale_factor, TOL_CPS);
    }
    assert_close(out.target_cps[MECANUM_WHEEL_FL] / out.raw_target_cps[MECANUM_WHEEL_FL], out.scale_factor, TOL_SCALE);
    assert_close(out.target_cps[MECANUM_WHEEL_RL] / out.raw_target_cps[MECANUM_WHEEL_RL], out.scale_factor, TOL_SCALE);
    assert_close(out.target_cps[MECANUM_WHEEL_RR] / out.raw_target_cps[MECANUM_WHEEL_RR], out.scale_factor, TOL_SCALE);
}

static void expect_invalid_config(MecanumKinematicsConfig config)
{
    MecanumKinematicsOutput out;
    memset(&out, 0xA5, sizeof(out));
    assert(!mecanum_kinematics_compute(&config, 0.1f, 0.0f, 0.0f, &out));
    assert_zero_output(&out);
}

static void test_invalid_inputs_and_config(void)
{
    MecanumKinematicsConfig config;
    MecanumKinematicsOutput out;

    config = owner_regression_config; config.wheel_diameter_m = 0.0f; expect_invalid_config(config);
    config = owner_regression_config; config.wheelbase_m = 0.0f; expect_invalid_config(config);
    config = owner_regression_config; config.track_m = -0.1f; expect_invalid_config(config);
    config = owner_regression_config; config.counts_per_revolution = 0.0f; expect_invalid_config(config);
    config = owner_regression_config; config.max_wheel_cps = 0.0f; expect_invalid_config(config);
    config = owner_regression_config; config.wheel_diameter_m = NAN; expect_invalid_config(config);
    config = owner_regression_config; config.counts_per_revolution = INFINITY; expect_invalid_config(config);

    memset(&out, 0xA5, sizeof(out));
    assert(!mecanum_kinematics_compute(&owner_regression_config, NAN, 0.0f, 0.0f, &out));
    assert_zero_output(&out);
    memset(&out, 0xA5, sizeof(out));
    assert(!mecanum_kinematics_compute(&owner_regression_config, 0.0f, INFINITY, 0.0f, &out));
    assert_zero_output(&out);
    assert(!mecanum_kinematics_compute(&owner_regression_config, 0.0f, 0.0f, 0.0f, NULL));
}

int main(void)
{
    test_zero();
    test_owner_regression_vectors();
    test_mixed_and_proportional_saturation();
    test_invalid_inputs_and_config();
    puts("test_kinematics: PASS");
    return 0;
}
