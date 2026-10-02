/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : motor_bench.c
  * @brief          : Locked-by-default, single-motor bench-test implementation.
  ******************************************************************************
  */
/* USER CODE END Header */

#include "motor_bench.h"

#include <stdbool.h>
#include <stdint.h>

#include "main.h"
#include "motor_logic.h"
#include "safety_io.h"

#define MOTOR_BENCH_DUTY_PERMILLE 200U
#define MOTOR_BENCH_DURATION_MS 2000U

extern TIM_HandleTypeDef htim3;

volatile MotorBenchSnapshot g_motor_bench;

static void motor_bench_set_fixed_parameters(void)
{
  g_motor_bench.duty_permille = MOTOR_BENCH_DUTY_PERMILLE;
  g_motor_bench.duration_ms = MOTOR_BENCH_DURATION_MS;
}

#if MOTOR_BENCH_OUTPUT_AUTHORIZED

static bool motor_bench_command_is_valid(uint32_t command)
{
  return (command == MOTOR_BENCH_COMMAND_FL_FORWARD) ||
         (command == MOTOR_BENCH_COMMAND_FR_FORWARD) ||
         (command == MOTOR_BENCH_COMMAND_RL_FORWARD) ||
         (command == MOTOR_BENCH_COMMAND_RR_FORWARD);
}

static uint32_t motor_bench_pwm_channel(uint32_t command)
{
  switch (command)
  {
    case MOTOR_BENCH_COMMAND_FL_FORWARD:
      return TIM_CHANNEL_4;
    case MOTOR_BENCH_COMMAND_FR_FORWARD:
      return TIM_CHANNEL_3;
    case MOTOR_BENCH_COMMAND_RL_FORWARD:
      return TIM_CHANNEL_1;
    case MOTOR_BENCH_COMMAND_RR_FORWARD:
      return TIM_CHANNEL_2;
    default:
      return 0U;
  }
}

static MotorWheel motor_bench_wheel_from_command(uint32_t command)
{
  switch (command)
  {
    case MOTOR_BENCH_COMMAND_FL_FORWARD:
      return MOTOR_WHEEL_FL;
    case MOTOR_BENCH_COMMAND_FR_FORWARD:
      return MOTOR_WHEEL_FR;
    case MOTOR_BENCH_COMMAND_RL_FORWARD:
      return MOTOR_WHEEL_RL;
    case MOTOR_BENCH_COMMAND_RR_FORWARD:
      return MOTOR_WHEEL_RR;
    default:
      return MOTOR_WHEEL_FL;
  }
}

static bool motor_bench_start_command(uint32_t command)
{
  const uint32_t channel = motor_bench_pwm_channel(command);
  const MotorWheel wheel = motor_bench_wheel_from_command(command);
  const uint32_t auto_reload = __HAL_TIM_GET_AUTORELOAD(&htim3);
  const uint32_t compare = (uint32_t)((((uint64_t)auto_reload + 1ULL) *
                                       MOTOR_BENCH_DUTY_PERMILLE) / 1000ULL);

  safety_io_force_motor_disabled();
  motor_logic_set_direction(wheel, MOTOR_DIRECTION_FORWARD);
  __HAL_TIM_SET_COMPARE(&htim3, channel, compare);

  if (HAL_TIM_PWM_Start(&htim3, channel) != HAL_OK)
  {
    safety_io_force_motor_disabled();
    motor_logic_stop_all();
    return false;
  }

  HAL_GPIO_WritePin(MCU_MOTOR_ENABLE_GPIO_Port,
                    MCU_MOTOR_ENABLE_Pin,
                    GPIO_PIN_SET);
  return true;
}

#endif /* MOTOR_BENCH_OUTPUT_AUTHORIZED */

void motor_bench_init(void)
{
  safety_io_force_motor_disabled();
  motor_logic_stop_all();

  g_motor_bench.request = MOTOR_BENCH_COMMAND_NONE;
  g_motor_bench.active_command = MOTOR_BENCH_COMMAND_NONE;
  g_motor_bench.completed_count = 0U;
  g_motor_bench.elapsed_ms = 0U;
  motor_bench_set_fixed_parameters();

#if MOTOR_BENCH_OUTPUT_AUTHORIZED
  g_motor_bench.state = MOTOR_BENCH_STATE_IDLE;
  g_motor_bench.last_result = MOTOR_BENCH_RESULT_NONE;
#else
  g_motor_bench.state = MOTOR_BENCH_STATE_LOCKED;
  g_motor_bench.last_result = MOTOR_BENCH_RESULT_LOCKED;
#endif
}

void motor_bench_step(void)
{
  motor_bench_set_fixed_parameters();

#if MOTOR_BENCH_OUTPUT_AUTHORIZED
  static uint32_t active_started_ms;

  if (g_motor_bench.state == MOTOR_BENCH_STATE_ACTIVE)
  {
    if (g_motor_bench.request != MOTOR_BENCH_COMMAND_NONE)
    {
      g_motor_bench.request = MOTOR_BENCH_COMMAND_NONE;
      g_motor_bench.last_result = MOTOR_BENCH_RESULT_BUSY;
    }

    g_motor_bench.elapsed_ms = HAL_GetTick() - active_started_ms;
    if (g_motor_bench.elapsed_ms >= MOTOR_BENCH_DURATION_MS)
    {
      safety_io_force_motor_disabled();
      motor_logic_stop_all();
      g_motor_bench.active_command = MOTOR_BENCH_COMMAND_NONE;
      g_motor_bench.state = MOTOR_BENCH_STATE_COMPLETE;
      g_motor_bench.last_result = MOTOR_BENCH_RESULT_COMPLETE;
      g_motor_bench.elapsed_ms = MOTOR_BENCH_DURATION_MS;
      g_motor_bench.completed_count++;
    }
    return;
  }

  if (g_motor_bench.request == MOTOR_BENCH_COMMAND_NONE)
  {
    return;
  }

  const uint32_t command = g_motor_bench.request;
  g_motor_bench.request = MOTOR_BENCH_COMMAND_NONE;

  if (!motor_bench_command_is_valid(command))
  {
    g_motor_bench.active_command = MOTOR_BENCH_COMMAND_NONE;
    g_motor_bench.state = MOTOR_BENCH_STATE_REJECTED;
    g_motor_bench.last_result = MOTOR_BENCH_RESULT_INVALID_REQUEST;
    g_motor_bench.elapsed_ms = 0U;
    safety_io_force_motor_disabled();
    motor_logic_stop_all();
    return;
  }

  if (!motor_bench_start_command(command))
  {
    g_motor_bench.active_command = MOTOR_BENCH_COMMAND_NONE;
    g_motor_bench.state = MOTOR_BENCH_STATE_REJECTED;
    g_motor_bench.last_result = MOTOR_BENCH_RESULT_HAL_ERROR;
    g_motor_bench.elapsed_ms = 0U;
    return;
  }

  active_started_ms = HAL_GetTick();
  g_motor_bench.active_command = command;
  g_motor_bench.state = MOTOR_BENCH_STATE_ACTIVE;
  g_motor_bench.last_result = MOTOR_BENCH_RESULT_RUNNING;
  g_motor_bench.elapsed_ms = 0U;
#else
  if (g_motor_bench.request != MOTOR_BENCH_COMMAND_NONE)
  {
    g_motor_bench.request = MOTOR_BENCH_COMMAND_NONE;
  }

  safety_io_force_motor_disabled();
  motor_logic_stop_all();
  g_motor_bench.active_command = MOTOR_BENCH_COMMAND_NONE;
  g_motor_bench.state = MOTOR_BENCH_STATE_LOCKED;
  g_motor_bench.last_result = MOTOR_BENCH_RESULT_LOCKED;
  g_motor_bench.elapsed_ms = 0U;
#endif
}
