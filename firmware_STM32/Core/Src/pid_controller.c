#include "pid_controller.h"

#include <math.h>
#include <stddef.h>

void pid_controller_reset(PidControllerState *state)
{
    if (state != NULL) {
        state->integral = 0.0f;
    }
}

static bool config_is_valid(const PidControllerConfig *config)
{
    if (config == NULL) {
        return false;
    }

    return isfinite(config->kp) && config->kp >= 0.0f &&
           isfinite(config->ki) && config->ki >= 0.0f &&
           isfinite(config->integral_limit) && config->integral_limit >= 0.0f &&
           isfinite(config->output_limit) && config->output_limit > 0.0f &&
           isfinite(config->max_target_cps) && config->max_target_cps > 0.0f &&
           isfinite(config->forward_ff_u0) && config->forward_ff_u0 >= 0.0f &&
           isfinite(config->forward_ff_kv) && config->forward_ff_kv >= 0.0f &&
           isfinite(config->reverse_ff_u0) && config->reverse_ff_u0 >= 0.0f &&
           isfinite(config->reverse_ff_kv) && config->reverse_ff_kv >= 0.0f;
}

static bool fail_closed(PidControllerState *state, float *signed_effort)
{
    pid_controller_reset(state);
    if (signed_effort != NULL) {
        *signed_effort = 0.0f;
    }
    return false;
}

bool pid_controller_step(const PidControllerConfig *config,
                         PidControllerState *state,
                         float target_cps,
                         float measured_cps,
                         float dt_seconds,
                         float *signed_effort)
{
    float direction_sign;
    float target_magnitude;
    float directional_measured;
    float error;
    float feedforward;
    float proportional;
    float candidate_integral;
    float raw;
    float magnitude;

    if (signed_effort != NULL) {
        *signed_effort = 0.0f;
    }
    if (state == NULL || signed_effort == NULL || !config_is_valid(config) ||
        !isfinite(target_cps) || !isfinite(measured_cps) ||
        !isfinite(dt_seconds) || dt_seconds <= 0.0f ||
        fabsf(target_cps) > config->max_target_cps) {
        return fail_closed(state, signed_effort);
    }

    if (target_cps == 0.0f) {
        pid_controller_reset(state);
        return true;
    }

    if (!isfinite(state->integral)) {
        return fail_closed(state, signed_effort);
    }

    direction_sign = target_cps > 0.0f ? 1.0f : -1.0f;
    target_magnitude = fabsf(target_cps);
    directional_measured = direction_sign * measured_cps;
    error = target_magnitude - directional_measured;

    if (target_cps > 0.0f) {
        feedforward = config->forward_ff_u0 +
                      config->forward_ff_kv * target_magnitude;
    } else {
        feedforward = config->reverse_ff_u0 +
                      config->reverse_ff_kv * target_magnitude;
    }
    proportional = config->kp * error;
    candidate_integral = state->integral + config->ki * error * dt_seconds;

    if (!isfinite(feedforward) || !isfinite(proportional) ||
        !isfinite(candidate_integral)) {
        return fail_closed(state, signed_effort);
    }

    if (candidate_integral > config->integral_limit) {
        candidate_integral = config->integral_limit;
    } else if (candidate_integral < -config->integral_limit) {
        candidate_integral = -config->integral_limit;
    }

    raw = feedforward + proportional + candidate_integral;
    if (!isfinite(raw)) {
        return fail_closed(state, signed_effort);
    }

    /* Match the validated PID4 anti-windup rule. */
    if (!((raw >= config->output_limit && error > 0.0f) ||
          (raw <= 0.0f && error < 0.0f))) {
        state->integral = candidate_integral;
    }

    raw = feedforward + proportional + state->integral;
    if (!isfinite(raw)) {
        return fail_closed(state, signed_effort);
    }

    if (raw < 0.0f) {
        magnitude = 0.0f;
    } else if (raw > config->output_limit) {
        magnitude = config->output_limit;
    } else {
        magnitude = raw;
    }

    *signed_effort = direction_sign * magnitude;
    return true;
}
