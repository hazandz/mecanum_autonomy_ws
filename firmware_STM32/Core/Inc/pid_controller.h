#ifndef PID_CONTROLLER_H
#define PID_CONTROLLER_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float kp;
    float ki;
    float integral_limit;
    float output_limit;
    float max_target_cps;
    float forward_ff_u0;
    float forward_ff_kv;
    float reverse_ff_u0;
    float reverse_ff_kv;
} PidControllerConfig;

typedef struct {
    float integral;
} PidControllerState;

void pid_controller_reset(PidControllerState *state);

/*
 * Computes one signed wheel-control effort. Positive target produces positive
 * effort; negative target produces negative effort. Zero target resets the
 * integrator and produces zero effort. Any invalid input/configuration fails
 * closed: false, zero effort, and reset state when state is available.
 */
bool pid_controller_step(const PidControllerConfig *config,
                         PidControllerState *state,
                         float target_cps,
                         float measured_cps,
                         float dt_seconds,
                         float *signed_effort);

#ifdef __cplusplus
}
#endif

#endif /* PID_CONTROLLER_H */
