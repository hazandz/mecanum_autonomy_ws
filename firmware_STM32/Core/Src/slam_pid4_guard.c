#include "slam_pid4_guard.h"

#include <math.h>
#include <string.h>

#define SLAM_PID4_MAX_TARGET_CPS 1400.0f
#define SLAM_PID4_MAX_PWM_PERMILLE 400.0f
#define SLAM_PID4_SYNC_GRACE_MS 500U
#define SLAM_PID4_SYNC_WARNING_CPS 150.0f

void slam_pid4_guard_reset(slam_pid4_guard_state_t *state)
{
    if (state != NULL) {
        memset(state, 0, sizeof(*state));
    }
}

static bool finite_vector(const float values[SLAM_PID4_WHEEL_COUNT])
{
    if (values == NULL) return false;
    for (unsigned i = 0U; i < SLAM_PID4_WHEEL_COUNT; ++i) {
        if (!isfinite(values[i])) return false;
    }
    return true;
}

slam_pid4_fault_t slam_pid4_guard_ramp(
    slam_pid4_guard_state_t *state,
    const float requested[SLAM_PID4_WHEEL_COUNT], uint32_t dt_ms)
{
    if (state == NULL || !finite_vector(requested)) {
        return SLAM_PID4_FAULT_INVALID_TARGET;
    }
    if (dt_ms == 0U || dt_ms > SLAM_PID4_MAX_CONTROL_DT_MS) {
        return SLAM_PID4_FAULT_BAD_DT;
    }
    for (unsigned i = 0U; i < SLAM_PID4_WHEEL_COUNT; ++i) {
        float target = requested[i];
        float current = state->ramped_target_cps[i];
        if (fabsf(target) > SLAM_PID4_MAX_TARGET_CPS) {
            return SLAM_PID4_FAULT_INVALID_TARGET;
        }
        /* Zero is an immediate stop. Nonzero targets slew over one second. */
        if (target == 0.0f) {
            state->ramped_target_cps[i] = 0.0f;
            continue;
        }
        float max_rate = fmaxf(fabsf(current), fabsf(target));
        float max_delta = max_rate * ((float)dt_ms / (float)SLAM_PID4_RAMP_DURATION_MS);
        float delta = target - current;
        if (delta > max_delta) delta = max_delta;
        if (delta < -max_delta) delta = -max_delta;
        state->ramped_target_cps[i] = current + delta;
    }
    return SLAM_PID4_FAULT_NONE;
}

static uint32_t add_ms(uint32_t elapsed, uint32_t dt_ms)
{
    return UINT32_MAX - elapsed < dt_ms ? UINT32_MAX : elapsed + dt_ms;
}

slam_pid4_fault_t slam_pid4_guard_check(
    slam_pid4_guard_state_t *state,
    const float requested[SLAM_PID4_WHEEL_COUNT],
    const float measured[SLAM_PID4_WHEEL_COUNT],
    const float effort[SLAM_PID4_WHEEL_COUNT], uint32_t dt_ms)
{
    bool comparable = true;
    float reference = 0.0f;
    float minimum = 0.0f, maximum = 0.0f;
    bool have_speed = false;

    if (state == NULL || !finite_vector(requested) || !finite_vector(measured) ||
        !finite_vector(effort)) return SLAM_PID4_FAULT_INVALID_TARGET;
    if (dt_ms == 0U || dt_ms > SLAM_PID4_MAX_CONTROL_DT_MS) {
        return SLAM_PID4_FAULT_BAD_DT;
    }

    for (unsigned i = 0U; i < SLAM_PID4_WHEEL_COUNT; ++i) {
        float target = requested[i];
        if (fabsf(target) > SLAM_PID4_MAX_TARGET_CPS ||
            fabsf(effort[i]) > SLAM_PID4_MAX_PWM_PERMILLE) {
            return fabsf(target) > SLAM_PID4_MAX_TARGET_CPS ?
                SLAM_PID4_FAULT_INVALID_TARGET : SLAM_PID4_FAULT_INVALID_PWM;
        }
        int8_t sign = target > 0.0f ? 1 : (target < 0.0f ? -1 : 0);
        if (sign != state->target_sign[i]) {
            state->target_sign[i] = sign;
            state->active_ms[i] = 0U;
            state->wrong_direction_ms[i] = 0U;
            state->stall_ms[i] = 0U;
        }
        if (sign == 0) {
            state->active_ms[i] = 0U;
            state->wrong_direction_ms[i] = 0U;
            state->stall_ms[i] = 0U;
            comparable = false;
            continue;
        }

        state->active_ms[i] = add_ms(state->active_ms[i], dt_ms);
        float directional_speed = (float)sign * measured[i];
        if (directional_speed < -SLAM_PID4_DIRECTION_THRESHOLD_CPS) {
            state->wrong_direction_ms[i] = add_ms(state->wrong_direction_ms[i], dt_ms);
        } else {
            state->wrong_direction_ms[i] = 0U;
        }
        if (state->wrong_direction_ms[i] >= SLAM_PID4_DIRECTION_FAULT_MS) {
            return SLAM_PID4_FAULT_WRONG_DIRECTION;
        }

        if (state->active_ms[i] >= SLAM_PID4_STALL_GRACE_MS &&
            fabsf(effort[i]) >= SLAM_PID4_STALL_OUTPUT_PERMILLE &&
            fabsf(directional_speed) < SLAM_PID4_DIRECTION_THRESHOLD_CPS) {
            state->stall_ms[i] = add_ms(state->stall_ms[i], dt_ms);
        } else {
            state->stall_ms[i] = 0U;
        }
        if (state->stall_ms[i] >= SLAM_PID4_STALL_FAULT_MS) {
            return SLAM_PID4_FAULT_STALL;
        }

        if (!have_speed) {
            minimum = directional_speed;
            maximum = directional_speed;
            have_speed = true;
        } else {
            if (directional_speed < minimum) minimum = directional_speed;
            if (directional_speed > maximum) maximum = directional_speed;
        }
        if (i == 0U) reference = fabsf(target);
        else if (fabsf(fabsf(target) - reference) >
                 SLAM_PID4_SYNC_TARGET_TOLERANCE_CPS) comparable = false;
    }

    state->sync_spread_cps = comparable && have_speed ? maximum - minimum : 0.0f;
    if (comparable && have_speed) {
        state->sync_active_ms = add_ms(state->sync_active_ms, dt_ms);
        state->sync_warning = state->sync_active_ms >= SLAM_PID4_SYNC_GRACE_MS &&
            state->sync_spread_cps > SLAM_PID4_SYNC_WARNING_CPS;
        if (state->sync_active_ms >= SLAM_PID4_SYNC_GRACE_MS &&
            state->sync_spread_cps > SLAM_PID4_SYNC_FAULT_CPS) {
            state->sync_fault_ms = add_ms(state->sync_fault_ms, dt_ms);
        } else {
            state->sync_fault_ms = 0U;
        }
    } else {
        state->sync_active_ms = 0U;
        state->sync_fault_ms = 0U;
        state->sync_warning = false;
    }
    if (state->sync_fault_ms >= SLAM_PID4_SYNC_FAULT_MS) {
        return SLAM_PID4_FAULT_SYNC;
    }
    return SLAM_PID4_FAULT_NONE;
}

slam_pid4_commutation_t slam_pid4_guard_commutate(
    slam_pid4_guard_state_t *state, unsigned wheel_index, float target_cps)
{
    if (state == NULL || wheel_index >= SLAM_PID4_WHEEL_COUNT ||
        !isfinite(target_cps)) return SLAM_PID4_COMMUTATE_COAST;
    int8_t wanted = target_cps > 0.0f ? 1 : (target_cps < 0.0f ? -1 : 0);
    int8_t current = state->direction_sign[wheel_index];
    if (wanted == 0) {
        state->direction_sign[wheel_index] = 0;
        return SLAM_PID4_COMMUTATE_COAST;
    }
    if (current == wanted) return SLAM_PID4_COMMUTATE_DRIVE;
    if (current != 0) {
        state->direction_sign[wheel_index] = 0;
        return SLAM_PID4_COMMUTATE_COAST;
    }
    state->direction_sign[wheel_index] = wanted;
    return SLAM_PID4_COMMUTATE_SET_DIRECTION;
}

bool slam_pid4_pwm_compare(uint32_t autoreload, float effort_permille,
                           uint32_t *compare)
{
    if (compare == NULL) return false;
    *compare = 0U;
    if (!isfinite(effort_permille) || effort_permille < 0.0f ||
        effort_permille > SLAM_PID4_MAX_PWM_PERMILLE) return false;
    uint32_t rounded_permille = (uint32_t)(effort_permille + 0.5f);
    *compare = (uint32_t)(((uint64_t)autoreload + 1ULL) * rounded_permille / 1000ULL);
    if (rounded_permille > 0U && *compare == 0U) *compare = 1U;
    return true;
}
