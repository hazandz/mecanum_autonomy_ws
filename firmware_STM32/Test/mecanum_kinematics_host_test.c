#include "mecanum_kinematics.h"

#include <float.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define ARRAY_COUNT(a) (sizeof(a) / sizeof((a)[0]))
#define CPS_TOLERANCE 0.08f

static int failures;

static void check(int condition, const char *name)
{
    if (!condition)
    {
        fprintf(stderr, "FAIL: %s\n", name);
        ++failures;
    }
}

static int near(float actual, float expected, float tolerance)
{
    return isfinite(actual) && fabsf(actual - expected) <= tolerance;
}

static void check_vector(const char *name,
                         const MecanumKinematicsOutput *out,
                         const float expected[MECANUM_WHEEL_COUNT])
{
    uint32_t i;

    for (i = 0U; i < (uint32_t)MECANUM_WHEEL_COUNT; ++i)
    {
        char detail[96];
        (void)snprintf(detail, sizeof(detail), "%s wheel %lu", name,
                       (unsigned long)i);
        check(near(out->target_cps[i], expected[i], CPS_TOLERANCE), detail);
    }
}

static void expect_compute(const char *name,
                           float vx,
                           float vy,
                           float wz,
                           const float expected[MECANUM_WHEEL_COUNT],
                           uint8_t expected_limited)
{
    MecanumKinematicsOutput out;

    check(mecanum_kinematics_compute(vx, vy, wz, &out), name);
    check_vector(name, &out, expected);
    check(out.limited == expected_limited, "limited flag");
}

static void test_zero_and_cardinal_vectors(void)
{
    const float zero[MECANUM_WHEEL_COUNT] = {0.0f, 0.0f, 0.0f, 0.0f};
    const float forward[MECANUM_WHEEL_COUNT] = {
        615.093f, 615.093f, 615.093f, 615.093f
    };
    const float reverse[MECANUM_WHEEL_COUNT] = {
        -615.093f, -615.093f, -615.093f, -615.093f
    };
    const float strafe_left[MECANUM_WHEEL_COUNT] = {
        -307.546f, 307.546f, 307.546f, -307.546f
    };
    const float strafe_right[MECANUM_WHEEL_COUNT] = {
        307.546f, -307.546f, -307.546f, 307.546f
    };
    const float rotate_ccw[MECANUM_WHEEL_COUNT] = {
        -624.319f, 624.319f, -624.319f, 624.319f
    };
    const float rotate_cw[MECANUM_WHEEL_COUNT] = {
        624.319f, -624.319f, 624.319f, -624.319f
    };
    MecanumKinematicsOutput out;

    expect_compute("ZERO", 0.0f, 0.0f, 0.0f, zero, 0U);
    check(mecanum_kinematics_compute(0.0f, 0.0f, 0.0f, &out),
          "ZERO succeeds");
    check(out.scale_factor == 1.0f, "ZERO scale is exactly one");
    check(out.limited == 0U, "ZERO is not limited");
    check(memcmp(out.raw_target_cps, zero, sizeof(zero)) == 0,
          "ZERO raw vector is exact positive zero");
    check(memcmp(out.target_cps, zero, sizeof(zero)) == 0,
          "ZERO target vector is exact positive zero");

    expect_compute("FORWARD", 0.2f, 0.0f, 0.0f, forward, 0U);
    expect_compute("REVERSE", -0.2f, 0.0f, 0.0f, reverse, 0U);
    expect_compute("STRAFE LEFT", 0.0f, 0.1f, 0.0f, strafe_left, 0U);
    expect_compute("STRAFE RIGHT", 0.0f, -0.1f, 0.0f, strafe_right, 0U);
    expect_compute("ROTATE CCW", 0.0f, 0.0f, 1.0f, rotate_ccw, 0U);
    expect_compute("ROTATE CW", 0.0f, 0.0f, -1.0f, rotate_cw, 0U);
}

static void test_mixed_vectors(void)
{
    const float mixed[MECANUM_WHEEL_COUNT] = {
        -4.613f, 1234.799f, 610.480f, 619.706f
    };
    const float mixed_scaled[MECANUM_WHEEL_COUNT] = {
        -205.121f, 1400.000f, 591.465f, 603.414f
    };
    MecanumKinematicsOutput out;
    float expected_scale;
    uint32_t i;

    check(mecanum_kinematics_compute(0.2f, 0.1f, 0.5f, &out),
          "MIXED no-limit succeeds");
    check_vector("MIXED no-limit", &out, mixed);
    check(out.limited == 0U, "MIXED no-limit flag");
    check(out.scale_factor == 1.0f, "MIXED no-limit scale");
    for (i = 0U; i < (uint32_t)MECANUM_WHEEL_COUNT; ++i)
    {
        check(near(out.raw_target_cps[i], mixed[i], CPS_TOLERANCE),
              "MIXED no-limit raw cps");
    }

    check(mecanum_kinematics_compute(0.3f, 0.2f, 1.0f, &out),
          "MIXED scaling succeeds");
    check(out.limited == 1U, "MIXED scaling flag");
    expected_scale = MECANUM_MAX_WHEEL_CPS / out.raw_target_cps[MECANUM_WHEEL_FR];
    check(near(out.scale_factor, 0.647533f, 0.0002f),
          "MIXED scaling factor");
    check(near(out.scale_factor, expected_scale, 0.000001f),
          "MIXED scale from max wheel");
    check_vector("MIXED scaling", &out, mixed_scaled);
    check(near(out.target_cps[MECANUM_WHEEL_FR], 1400.0f, 0.001f),
          "MIXED max wheel reaches limit");

    /* Every wheel uses the same scalar, preserving the requested vector. */
    for (i = 0U; i < (uint32_t)MECANUM_WHEEL_COUNT; ++i)
    {
        check(near(out.target_cps[i],
                   out.raw_target_cps[i] * out.scale_factor,
                   0.001f),
              "MIXED vector-preserving scale ratio");
    }
}

static void check_zero_output(const MecanumKinematicsOutput *out,
                              const char *name)
{
    MecanumKinematicsOutput zero;

    memset(&zero, 0, sizeof(zero));
    check(memcmp(out, &zero, sizeof(zero)) == 0, name);
}

static void test_invalid_inputs(void)
{
    MecanumKinematicsOutput out;

    memset(&out, 0xA5, sizeof(out));
    check(!mecanum_kinematics_compute(NAN, 0.0f, 0.0f, &out), "NAN rejected");
    check_zero_output(&out, "NAN output zeroed");

    memset(&out, 0xA5, sizeof(out));
    check(!mecanum_kinematics_compute(0.0f, INFINITY, 0.0f, &out),
          "INFINITY rejected");
    check_zero_output(&out, "INFINITY output zeroed");

    check(!mecanum_kinematics_compute(0.0f, 0.0f, 0.0f, NULL),
          "NULL output rejected");

    memset(&out, 0xA5, sizeof(out));
    check(!mecanum_kinematics_compute(FLT_MAX, FLT_MAX, FLT_MAX, &out),
          "finite inputs with nonfinite result rejected");
    check_zero_output(&out, "nonfinite result output zeroed");
}

int main(void)
{
    test_zero_and_cardinal_vectors();
    test_mixed_vectors();
    test_invalid_inputs();

    if (failures != 0)
    {
        fprintf(stderr, "%d mecanum kinematics host test(s) failed\n", failures);
        return 1;
    }

    printf("mecanum kinematics host tests: PASS\n");
    return 0;
}
