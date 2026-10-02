/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : safety_io.c
  * @brief          : Fail-closed motor-output baseline implementation.
  ******************************************************************************
  */
/* USER CODE END Header */

#include "safety_io.h"

#include "main.h"

/* TIM3 is generated and initialized by main.c before safety_io_init_safe(). */
extern TIM_HandleTypeDef htim3;

static void safety_io_set_direction_pins_low(void)
{
  HAL_GPIO_WritePin(MOTOR_FR_IN1_GPIO_Port,
                    MOTOR_FR_IN1_Pin | MOTOR_FR_IN2_Pin |
                    MOTOR_FL_IN1_Pin | MOTOR_FL_IN2_Pin,
                    GPIO_PIN_RESET);

  HAL_GPIO_WritePin(MOTOR_RL_IN1_GPIO_Port,
                    MOTOR_RL_IN1_Pin | MOTOR_RL_IN2_Pin |
                    MOTOR_RR_IN1_Pin | MOTOR_RR_IN2_Pin,
                    GPIO_PIN_RESET);
}

static void safety_io_zero_and_stop_pwm(void)
{
  __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_1, 0U);
  __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_2, 0U);
  __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_3, 0U);
  __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_4, 0U);

  (void)HAL_TIM_PWM_Stop(&htim3, TIM_CHANNEL_1);
  (void)HAL_TIM_PWM_Stop(&htim3, TIM_CHANNEL_2);
  (void)HAL_TIM_PWM_Stop(&htim3, TIM_CHANNEL_3);
  (void)HAL_TIM_PWM_Stop(&htim3, TIM_CHANNEL_4);
}

void safety_io_force_motor_disabled(void)
{
  /* PB10 enters the hardware gate and cannot override the physical E-stop. */
  HAL_GPIO_WritePin(MCU_MOTOR_ENABLE_GPIO_Port,
                    MCU_MOTOR_ENABLE_Pin,
                    GPIO_PIN_RESET);

  safety_io_zero_and_stop_pwm();
  safety_io_set_direction_pins_low();
}

void safety_io_init_safe(void)
{
  safety_io_force_motor_disabled();
}
