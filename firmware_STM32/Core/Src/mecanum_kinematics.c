#include "mecanum_kinematics.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

#define MECANUM_PI_F 3.14159265358979323846f

static bool config_is_valid(const MecanumKinematicsConfig *config)
{
    if (config == NULL) {
        return false;
    }

    return isfinite(config->wheel_diameter_m) && config->wheel_diameter_m > 0.0f &&
           isfinite(config->wheelbase_m) && config->wheelbase_m > 0.0f &&
           isfinite(config->track_m) && config->track_m > 0.0f &&
           isfinite(config->counts_per_revolution) && config->counts_per_revolution > 0.0f &&
           isfinite(config->max_wheel_cps) && config->max_wheel_cps > 0.0f;
}

bool mecanum_kinematics_compute(const MecanumKinematicsConfig *config,
                                float vx_mps,
                                float vy_mps,
                                float wz_radps,
                                MecanumKinematicsOutput *out)
{
    MecanumKinematicsOutput result;
    float wheel_mps[MECANUM_WHEEL_COUNT];
    float rotation_radius_m;
    float counts_per_meter;
    float max_abs_target = 0.0f;
    uint32_t i;

    if (out == NULL) {
        return false;
    }
    memset(out, 0, sizeof(*out));

    if (!config_is_valid(config) ||
        !isfinite(vx_mps) || !isfinite(vy_mps) || !isfinite(wz_radps)) {
        return false;
    }

    rotation_radius_m = 0.5f * (config->wheelbase_m + config->track_m);
    counts_per_meter = config->counts_per_revolution /
                       (MECANUM_PI_F * config->wheel_diameter_m);
    if (!isfinite(rotation_radius_m) || rotation_radius_m <= 0.0f ||
        !isfinite(counts_per_meter) || counts_per_meter <= 0.0f) {
        return false;
    }

    wheel_mps[MECANUM_WHEEL_FL] = vx_mps - vy_mps - rotation_radius_m * wz_radps;
    wheel_mps[MECANUM_WHEEL_FR] = vx_mps + vy_mps + rotation_radius_m * wz_radps;
    wheel_mps[MECANUM_WHEEL_RL] = vx_mps + vy_mps - rotation_radius_m * wz_radps;
    wheel_mps[MECANUM_WHEEL_RR] = vx_mps - vy_mps + rotation_radius_m * wz_radps;

    memset(&result, 0, sizeof(result));
    for (i = 0U; i < (uint32_t)MECANUM_WHEEL_COUNT; ++i) {
        float cps;
        if (!isfinite(wheel_mps[i])) {
            return false;
        }
        cps = wheel_mps[i] * counts_per_meter;
        if (!isfinite(cps)) {
            return false;
        }
        result.raw_target_cps[i] = (cps == 0.0f) ? 0.0f : cps;
        if (fabsf(cps) > max_abs_target) {
            max_abs_target = fabsf(cps);
        }
    }

    result.scale_factor = 1.0f;
    if (max_abs_target > config->max_wheel_cps) {
        result.scale_factor = config->max_wheel_cps / max_abs_target;
        result.limited = 1U;
    }

    for (i = 0U; i < (uint32_t)MECANUM_WHEEL_COUNT; ++i) {
        float cps = result.raw_target_cps[i] * result.scale_factor;
        if (!isfinite(cps)) {
            return false;
        }
        result.target_cps[i] = (cps == 0.0f) ? 0.0f : cps;
    }

    *out = result;
    return true;
}
