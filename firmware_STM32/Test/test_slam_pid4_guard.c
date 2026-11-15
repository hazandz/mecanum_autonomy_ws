#include "slam_pid4_guard.h"

#include <assert.h>
#include <math.h>

static void fill(float values[SLAM_PID4_WHEEL_COUNT], float value)
{
    for (unsigned i = 0U; i < SLAM_PID4_WHEEL_COUNT; ++i) values[i] = value;
}

int main(void)
{
    slam_pid4_guard_state_t state;
    float requested[4], measured[4], effort[4];
    slam_pid4_guard_reset(&state);
    fill(requested, 1400.0f);
    assert(slam_pid4_guard_ramp(&state, requested, 20U) == SLAM_PID4_FAULT_NONE);
    for (unsigned i = 0U; i < 4U; ++i)
        assert(fabsf(state.ramped_target_cps[i] - 28.0f) < 1e-5f);
    for (unsigned n = 1U; n < 50U; ++n)
        assert(slam_pid4_guard_ramp(&state, requested, 20U) == SLAM_PID4_FAULT_NONE);
    for (unsigned i = 0U; i < 4U; ++i)
        assert(fabsf(state.ramped_target_cps[i] - 1400.0f) < 1e-4f);
    fill(requested, 0.0f);
    assert(slam_pid4_guard_ramp(&state, requested, 20U) == SLAM_PID4_FAULT_NONE);
    for (unsigned i = 0U; i < 4U; ++i) assert(state.ramped_target_cps[i] == 0.0f);
    assert(slam_pid4_guard_ramp(&state, requested, 101U) == SLAM_PID4_FAULT_BAD_DT);

    /* Reverse commands slew through zero; no direct sign step is emitted. */
    slam_pid4_guard_reset(&state);
    fill(requested, 1400.0f);
    for (unsigned n = 0U; n < 50U; ++n)
        assert(slam_pid4_guard_ramp(&state, requested, 20U) == SLAM_PID4_FAULT_NONE);
    fill(requested, -1400.0f);
    for (unsigned n = 0U; n < 50U; ++n) {
        assert(slam_pid4_guard_ramp(&state, requested, 20U) == SLAM_PID4_FAULT_NONE);
        assert(state.ramped_target_cps[0] >= 0.0f);
    }
    assert(state.ramped_target_cps[0] == 0.0f);
    assert(slam_pid4_guard_ramp(&state, requested, 20U) == SLAM_PID4_FAULT_NONE);
    assert(state.ramped_target_cps[0] < 0.0f);

    /* Wrong direction faults after 200 ms, using the currently ramped sign. */
    slam_pid4_guard_reset(&state);
    fill(requested, 500.0f);
    fill(measured, -101.0f);
    fill(effort, 150.0f);
    for (unsigned n = 0U; n < 9U; ++n)
        assert(slam_pid4_guard_check(&state, requested, measured, effort, 20U)
               == SLAM_PID4_FAULT_NONE);
    assert(slam_pid4_guard_check(&state, requested, measured, effort, 20U)
           == SLAM_PID4_FAULT_WRONG_DIRECTION);

    /* Stall requires grace plus 500 ms of high effort with near-zero speed. */
    slam_pid4_guard_reset(&state);
    fill(requested, 500.0f);
    fill(measured, 0.0f);
    fill(effort, 120.0f);
    for (unsigned n = 0U; n < 43U; ++n)
        assert(slam_pid4_guard_check(&state, requested, measured, effort, 20U)
               == SLAM_PID4_FAULT_NONE);
    assert(slam_pid4_guard_check(&state, requested, measured, effort, 20U)
           == SLAM_PID4_FAULT_STALL);

    /* Synchronization guard applies only to four comparable active wheels. */
    slam_pid4_guard_reset(&state);
    fill(requested, 500.0f);
    measured[0] = 0.0f; measured[1] = 400.0f;
    measured[2] = 0.0f; measured[3] = 400.0f;
    fill(effort, 100.0f);
    for (unsigned n = 0U; n < 48U; ++n) {
        assert(slam_pid4_guard_check(&state, requested, measured, effort, 20U)
               == SLAM_PID4_FAULT_NONE);
        if (n == 24U) assert(state.sync_warning);
    }
    assert(slam_pid4_guard_check(&state, requested, measured, effort, 20U)
           == SLAM_PID4_FAULT_SYNC);
    slam_pid4_guard_reset(&state);
    requested[3] = 0.0f;
    fill(measured, 0.0f);
    fill(effort, 100.0f);
    for (unsigned n = 0U; n < 30U; ++n)
        assert(slam_pid4_guard_check(&state, requested, measured, effort, 20U)
               == SLAM_PID4_FAULT_NONE);

    /* Commutation always coasts before changing polarity and delays drive. */
    slam_pid4_guard_reset(&state);
    assert(slam_pid4_guard_commutate(&state, 0U, 100.0f) ==
           SLAM_PID4_COMMUTATE_SET_DIRECTION);
    assert(slam_pid4_guard_commutate(&state, 0U, 100.0f) == SLAM_PID4_COMMUTATE_DRIVE);
    assert(slam_pid4_guard_commutate(&state, 0U, -100.0f) == SLAM_PID4_COMMUTATE_COAST);
    assert(slam_pid4_guard_commutate(&state, 0U, -100.0f) ==
           SLAM_PID4_COMMUTATE_SET_DIRECTION);
    assert(slam_pid4_guard_commutate(&state, 0U, -100.0f) == SLAM_PID4_COMMUTATE_DRIVE);
    assert(slam_pid4_guard_commutate(&state, 0U, 0.0f) == SLAM_PID4_COMMUTATE_COAST);

    uint32_t compare = UINT32_MAX;
    assert(slam_pid4_pwm_compare(65535U, 0.0f, &compare) && compare == 0U);
    assert(slam_pid4_pwm_compare(65535U, 400.0f, &compare) && compare == 26214U);
    assert(slam_pid4_pwm_compare(65535U, 0.5f, &compare) && compare == 65U);
    assert(!slam_pid4_pwm_compare(65535U, 400.01f, &compare) && compare == 0U);
    assert(!slam_pid4_pwm_compare(65535U, NAN, &compare) && compare == 0U);
    return 0;
}
