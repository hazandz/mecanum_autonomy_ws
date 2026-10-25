#include "mecanum_kinematics.h"

#include <math.h>
#include <string.h>

bool mecanum_kinematics_compute(float vx_mps,
                                float vy_mps,
                                float wz_radps,
                                MecanumKinematicsOutput *out)
{
    MecanumKinematicsOutput result;
    float wheel_mps[MECANUM_WHEEL_COUNT];
    float max_abs_cps = 0.0f;
    uint32_t i;

    if (out == NULL)
    {
        return false;
    }

    memset(out, 0, sizeof(*out));

    if (!isfinite(vx_mps) || !isfinite(vy_mps) || !isfinite(wz_radps))
    {
        return false;
    }

    memset(&result, 0, sizeof(result));

    wheel_mps[MECANUM_WHEEL_FL] = vx_mps - vy_mps -
                                  MECANUM_ROTATION_RADIUS_M * wz_radps;
    wheel_mps[MECANUM_WHEEL_FR] = vx_mps + vy_mps +
                                  MECANUM_ROTATION_RADIUS_M * wz_radps;
    wheel_mps[MECANUM_WHEEL_RL] = vx_mps + vy_mps -
                                  MECANUM_ROTATION_RADIUS_M * wz_radps;
    wheel_mps[MECANUM_WHEEL_RR] = vx_mps - vy_mps +
                                  MECANUM_ROTATION_RADIUS_M * wz_radps;

    for (i = 0U; i < (uint32_t)MECANUM_WHEEL_COUNT; ++i)
    {
        float cps = wheel_mps[i] * MECANUM_COUNTS_PER_METER;

        if (!isfinite(wheel_mps[i]) || !isfinite(cps))
        {
            return false;
        }

        /* Canonicalize exact zero so cancellation never exposes signed zero. */
        result.raw_target_cps[i] = (cps == 0.0f) ? 0.0f : cps;
        if (fabsf(result.raw_target_cps[i]) > max_abs_cps)
        {
            max_abs_cps = fabsf(result.raw_target_cps[i]);
        }
    }

    result.scale_factor = 1.0f;
    if (max_abs_cps > MECANUM_MAX_WHEEL_CPS)
    {
        result.scale_factor = MECANUM_MAX_WHEEL_CPS / max_abs_cps;
        result.limited = 1U;
    }

    for (i = 0U; i < (uint32_t)MECANUM_WHEEL_COUNT; ++i)
    {
        float cps = result.raw_target_cps[i] * result.scale_factor;
        result.target_cps[i] = (cps == 0.0f) ? 0.0f : cps;
    }

    *out = result;
    return true;
}
