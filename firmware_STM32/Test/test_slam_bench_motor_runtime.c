#include "main.h"
#include "encoder.h"
#include "motor_logic.h"
#include "safety_io.h"
#include "slam_bench_motor_runtime.h"

#include <assert.h>
#include <math.h>
#include <string.h>

TIM_TypeDef fake_timer3 = {.autoreload = 999U};
TIM_HandleTypeDef htim1, htim2, htim4, htim5;
TIM_HandleTypeDef htim3 = {.Instance = &fake_timer3};
GPIO_TypeDef fake_gpio_b;

static encoder_snapshot_t current_snapshot;
static bool snapshot_valid = true;
static bool motor_enable_high;
static bool pwm_start_fails;
static unsigned pwm_start_calls;
static unsigned stop_calls;
static unsigned direction_calls;
static uint32_t pwm_compare[5];

bool encoder_snapshot(encoder_snapshot_t *snapshot)
{
    if (!snapshot_valid || snapshot == NULL) return false;
    *snapshot = current_snapshot;
    return true;
}

void safety_io_force_motor_disabled(void)
{
    motor_enable_high = false;
    memset(pwm_compare, 0, sizeof(pwm_compare));
}

void motor_logic_stop_all(void) { ++stop_calls; }
void motor_logic_set_direction(MotorWheel wheel, MotorDirection direction)
{
    (void)wheel;
    (void)direction;
    ++direction_calls;
}

HAL_StatusTypeDef HAL_TIM_PWM_Start(TIM_HandleTypeDef *timer, uint32_t channel)
{
    (void)timer;
    (void)channel;
    ++pwm_start_calls;
    return pwm_start_fails ? HAL_ERROR : HAL_OK;
}

void HAL_GPIO_WritePin(GPIO_TypeDef *port, uint16_t pin, GPIO_PinState state)
{
    if (port == MCU_MOTOR_ENABLE_GPIO_Port && pin == MCU_MOTOR_ENABLE_Pin)
        motor_enable_high = state == GPIO_PIN_SET;
}

void manual_slam_fake_set_compare(TIM_HandleTypeDef *timer, uint32_t channel,
                                  uint32_t compare)
{
    (void)timer;
    if (channel < 5U) pwm_compare[channel] = compare;
}

uint32_t manual_slam_fake_get_compare(TIM_HandleTypeDef *timer, uint32_t channel)
{
    (void)timer;
    return channel < 5U ? pwm_compare[channel] : UINT32_MAX;
}

static void begin_runtime_case(void)
{
    memset(&current_snapshot, 0, sizeof(current_snapshot));
    current_snapshot.valid = true;
    current_snapshot.monotonic_time_us = 100000U;
    snapshot_valid = true;
    motor_enable_high = false;
    pwm_start_fails = false;
    pwm_start_calls = 0U;
    stop_calls = 0U;
    direction_calls = 0U;
    memset(pwm_compare, 0, sizeof(pwm_compare));
    assert(slam_bench_motor_runtime_profile_valid());
    assert(slam_bench_motor_runtime_init());
    assert(slam_bench_motor_runtime_new_session());
    assert(slam_bench_motor_runtime_set_body_command(0.30f, 0.0f, 0.0f));
}

static void step_with_ticks(const int32_t delta[4])
{
    current_snapshot.monotonic_time_us += 20000U;
    current_snapshot.ticks_fl += delta[0];
    current_snapshot.ticks_fr += delta[1];
    current_snapshot.ticks_rl += delta[2];
    current_snapshot.ticks_rr += delta[3];
    slam_bench_motor_runtime_step(0.020f);
}

static void assert_tracking_fault_nonfatal(slam_pid4_fault_t expected,
                                            const int32_t delta[4])
{
    begin_runtime_case();
    for (unsigned i = 0U; i < 70U &&
         slam_bench_motor_runtime_tracking_diagnostic() == SLAM_PID4_FAULT_NONE; ++i) {
        step_with_ticks(delta);
    }
    assert(slam_bench_motor_runtime_tracking_diagnostic() == expected);
    assert(slam_bench_motor_runtime_fault() == SLAM_MOTOR_RUNTIME_FAULT_NONE);
    assert(slam_bench_motor_runtime_enabled());
    assert(motor_enable_high);
    assert(pwm_start_calls == 4U);
}

int main(void)
{
    const int32_t wrong_direction[4] = {-3, -3, -3, -3};
    const int32_t stalled[4] = {0, 0, 0, 0};
    const int32_t unsynchronized[4] = {7, 14, 7, 14};
    assert_tracking_fault_nonfatal(SLAM_PID4_FAULT_WRONG_DIRECTION, wrong_direction);
    assert_tracking_fault_nonfatal(SLAM_PID4_FAULT_STALL, stalled);
    assert_tracking_fault_nonfatal(SLAM_PID4_FAULT_SYNC, unsynchronized);

    /* Only explicit MANUAL_SLAM bench profile policy suppresses tracking STOP. */
    slam_bench_motor_config_t other_profile = slam_bench_motor_config;
    assert(!slam_bench_motor_tracking_guard_fault_is_fatal(
        &slam_bench_motor_config, SLAM_PID4_FAULT_STALL));
    other_profile.manual_slam_bench_profile = false;
    assert(slam_bench_motor_tracking_guard_fault_is_fatal(
        &other_profile, SLAM_PID4_FAULT_STALL));
    other_profile.manual_slam_bench_profile = true;
    other_profile.tracking_guard_faults_nonfatal = false;
    assert(slam_bench_motor_tracking_guard_fault_is_fatal(
        &other_profile, SLAM_PID4_FAULT_WRONG_DIRECTION));
    assert(slam_bench_motor_tracking_guard_fault_is_fatal(
        &slam_bench_motor_config, SLAM_PID4_FAULT_INVALID_PWM));

    /* A true PWM peripheral failure remains a fatal DRIVER fault. */
    begin_runtime_case();
    pwm_start_fails = true;
    const int32_t forward[4] = {0, 0, 0, 0};
    step_with_ticks(forward);
    assert(slam_bench_motor_runtime_fault() == SLAM_MOTOR_RUNTIME_FAULT_DRIVER);
    assert(!slam_bench_motor_runtime_enabled());
    assert(!motor_enable_high);
    assert(stop_calls > 0U);

    /* Invalid encoder snapshot remains fatal and disables outputs. */
    begin_runtime_case();
    snapshot_valid = false;
    const int32_t still[4] = {0, 0, 0, 0};
    current_snapshot.monotonic_time_us += 20000U;
    slam_bench_motor_runtime_step(0.020f);
    assert(slam_bench_motor_runtime_fault() == SLAM_MOTOR_RUNTIME_FAULT_ENCODER);
    assert(!slam_bench_motor_runtime_enabled());
    assert(!motor_enable_high);

    /* Invalid command/config path stays fatal; no PWM start is attempted. */
    begin_runtime_case();
    assert(!slam_bench_motor_runtime_set_body_command(NAN, 0.0f, 0.0f));
    assert(slam_bench_motor_runtime_fault() == SLAM_MOTOR_RUNTIME_FAULT_CONTROL);
    assert(!motor_enable_high);
    (void)still;
    return 0;
}
