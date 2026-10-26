#include "pid_controller.h"

#include <assert.h>
#include <math.h>
#include <stdio.h>

#define TOL 0.0005f

static void assert_close(float actual, float expected)
{
    assert(fabsf(actual - expected) <= TOL);
}

static PidControllerConfig synthetic_config(void)
{
    return (PidControllerConfig){
        .kp = 0.5f,
        .ki = 2.0f,
        .integral_limit = 20.0f,
        .output_limit = 100.0f,
        .max_target_cps = 1000.0f,
        .forward_ff_u0 = 10.0f,
        .forward_ff_kv = 0.10f,
        .reverse_ff_u0 = 20.0f,
        .reverse_ff_kv = 0.20f
    };
}

static void test_zero_target_resets_integral(void)
{
    PidControllerState state = {.integral = 7.0f};
    PidControllerConfig config = synthetic_config();
    float effort = 123.0f;
    assert(pid_controller_step(&config, &state, 0.0f, 100.0f, 0.02f, &effort));
    assert(effort == 0.0f);
    assert(state.integral == 0.0f);
}

static void test_signed_effort_and_feedforward_selection(void)
{
    PidControllerState state = {0};
    PidControllerConfig config = synthetic_config();
    float effort;

    config.kp = 0.0f;
    config.ki = 0.0f;
    assert(pid_controller_step(&config, &state, 100.0f, 100.0f, 0.02f, &effort));
    assert_close(effort, 20.0f);
    assert(pid_controller_step(&config, &state, -100.0f, -100.0f, 0.02f, &effort));
    assert_close(effort, -40.0f);
}

static void test_p_response_and_directional_measurement(void)
{
    PidControllerState state = {0};
    PidControllerConfig config = synthetic_config();
    float effort;

    config.ki = 0.0f;
    config.forward_ff_u0 = 0.0f;
    config.forward_ff_kv = 0.0f;
    config.reverse_ff_u0 = 0.0f;
    config.reverse_ff_kv = 0.0f;

    assert(pid_controller_step(&config, &state, 100.0f, 80.0f, 0.02f, &effort));
    assert_close(effort, 10.0f);
    assert(pid_controller_step(&config, &state, -100.0f, -80.0f, 0.02f, &effort));
    assert_close(effort, -10.0f);
}

static void test_integral_accumulation_and_clamp(void)
{
    PidControllerState state = {0};
    PidControllerConfig config = synthetic_config();
    float effort;

    config.kp = 0.0f;
    config.output_limit = 1000.0f;
    config.forward_ff_u0 = 0.0f;
    config.forward_ff_kv = 0.0f;
    config.reverse_ff_u0 = 0.0f;
    config.reverse_ff_kv = 0.0f;
    config.integral_limit = 5.0f;

    assert(pid_controller_step(&config, &state, 10.0f, 0.0f, 0.10f, &effort));
    assert_close(state.integral, 2.0f);
    assert_close(effort, 2.0f);
    assert(pid_controller_step(&config, &state, 10.0f, 0.0f, 1.0f, &effort));
    assert_close(state.integral, 5.0f);
    assert_close(effort, 5.0f);
}

static void test_output_clamp_and_anti_windup(void)
{
    PidControllerState state = {0};
    PidControllerConfig config = synthetic_config();
    float effort;

    config.kp = 1.0f;
    config.ki = 1.0f;
    config.integral_limit = 50.0f;
    config.output_limit = 10.0f;
    config.forward_ff_u0 = 0.0f;
    config.forward_ff_kv = 0.0f;

    assert(pid_controller_step(&config, &state, 100.0f, 0.0f, 1.0f, &effort));
    assert_close(effort, 10.0f);
    assert_close(state.integral, 0.0f);

    state.integral = 5.0f;
    assert(pid_controller_step(&config, &state, 100.0f, 200.0f, 1.0f, &effort));
    assert_close(effort, 0.0f);
    assert_close(state.integral, 5.0f);
}

static void test_experimental_regression_only(void)
{
    /* EXPERIMENTAL_REGRESSION_ONLY - NOT_CANONICAL_CONFIGURATION */
    PidControllerConfig config = {
        .kp = 0.084f,
        .ki = 1.05f,
        .integral_limit = 80.0f,
        .output_limit = 400.0f,
        .max_target_cps = 1400.0f,
        .forward_ff_u0 = 40.330665f,
        .forward_ff_kv = 0.217819026f,
        .reverse_ff_u0 = 36.253577f,
        .reverse_ff_kv = 0.225076821f
    };
    PidControllerState state = {0};
    float effort;

    assert(pid_controller_step(&config, &state, 615.0928f, 607.8947f, 0.02f, &effort));
    assert(effort > 170.0f && effort < 180.0f);
    assert(pid_controller_step(&config, &state, -307.5464f, -301.3158f, 0.02f, &effort));
    assert(effort < -100.0f && effort > -120.0f);
}

static void assert_failure_resets(PidControllerConfig config,
                                  float target, float measured, float dt)
{
    PidControllerState state = {.integral = 9.0f};
    float effort = 77.0f;
    assert(!pid_controller_step(&config, &state, target, measured, dt, &effort));
    assert(effort == 0.0f);
    assert(state.integral == 0.0f);
}

static void test_invalid_inputs_and_config(void)
{
    PidControllerConfig config = synthetic_config();
    PidControllerState state = {.integral = 5.0f};
    float effort = 1.0f;

    assert_failure_resets(config, 1001.0f, 0.0f, 0.02f);
    assert_failure_resets(config, 1.0f, 0.0f, 0.0f);
    assert_failure_resets(config, 1.0f, 0.0f, -0.1f);
    assert_failure_resets(config, NAN, 0.0f, 0.02f);
    assert_failure_resets(config, INFINITY, 0.0f, 0.02f);
    assert_failure_resets(config, 1.0f, NAN, 0.02f);
    assert_failure_resets(config, 1.0f, INFINITY, 0.02f);

    config = synthetic_config(); config.output_limit = 0.0f; assert_failure_resets(config, 1.0f, 0.0f, 0.02f);
    config = synthetic_config(); config.max_target_cps = 0.0f; assert_failure_resets(config, 1.0f, 0.0f, 0.02f);
    config = synthetic_config(); config.kp = -1.0f; assert_failure_resets(config, 1.0f, 0.0f, 0.02f);
    config = synthetic_config(); config.forward_ff_kv = NAN; assert_failure_resets(config, 1.0f, 0.0f, 0.02f);

    config = synthetic_config();
    assert(!pid_controller_step(&config, NULL, 1.0f, 0.0f, 0.02f, &effort));
    assert(effort == 0.0f);
    assert(!pid_controller_step(&config, &state, 1.0f, 0.0f, 0.02f, NULL));
    assert(state.integral == 0.0f);

    state.integral = NAN;
    effort = 5.0f;
    assert(!pid_controller_step(&config, &state, 1.0f, 0.0f, 0.02f, &effort));
    assert(effort == 0.0f);
    assert(state.integral == 0.0f);
}

int main(void)
{
    test_zero_target_resets_integral();
    test_signed_effort_and_feedforward_selection();
    test_p_response_and_directional_measurement();
    test_integral_accumulation_and_clamp();
    test_output_clamp_and_anti_windup();
    test_experimental_regression_only();
    test_invalid_inputs_and_config();
    puts("test_pid: PASS");
    return 0;
}
