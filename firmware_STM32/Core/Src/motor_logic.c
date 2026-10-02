/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : motor_logic.c
  * @brief          : Direction-pin mapping for the verified mecanum layout.
  ******************************************************************************
  */
/* USER CODE END Header */

#include "motor_logic.h"

#include <stdbool.h>

#include "main.h"

static void motor_logic_write_direction_pair(GPIO_TypeDef *port,
                                             uint16_t in1_pin,
                                             uint16_t in2_pin,
                                             bool in1_high,
                                             bool in2_high)
{
  HAL_GPIO_WritePin(port, in1_pin | in2_pin, GPIO_PIN_RESET);

  if (in1_high)
  {
    HAL_GPIO_WritePin(port, in1_pin, GPIO_PIN_SET);
  }

  if (in2_high)
  {
    HAL_GPIO_WritePin(port, in2_pin, GPIO_PIN_SET);
  }
}

void motor_logic_set_direction(MotorWheel wheel, MotorDirection direction)
{
  bool in1_high = false;
  bool in2_high = false;
  bool forward_is_in1_high;

  switch (wheel)
  {
    case MOTOR_WHEEL_FL:
    case MOTOR_WHEEL_FR:
      /* Verified forward polarity B: IN1 LOW, IN2 HIGH. */
      forward_is_in1_high = false;
      break;

    case MOTOR_WHEEL_RL:
    case MOTOR_WHEEL_RR:
      /* Verified forward polarity A: IN1 HIGH, IN2 LOW. */
      forward_is_in1_high = true;
      break;

    default:
      motor_logic_stop_all();
      return;
  }

  if (direction == MOTOR_DIRECTION_FORWARD)
  {
    in1_high = forward_is_in1_high;
    in2_high = !forward_is_in1_high;
  }
  else if (direction == MOTOR_DIRECTION_REVERSE)
  {
    in1_high = !forward_is_in1_high;
    in2_high = forward_is_in1_high;
  }
  /* COAST/STOP and invalid directions intentionally leave both pins LOW. */

  switch (wheel)
  {
    case MOTOR_WHEEL_FL:
      motor_logic_write_direction_pair(MOTOR_FL_IN1_GPIO_Port,
                                       MOTOR_FL_IN1_Pin,
                                       MOTOR_FL_IN2_Pin,
                                       in1_high,
                                       in2_high);
      break;

    case MOTOR_WHEEL_FR:
      motor_logic_write_direction_pair(MOTOR_FR_IN1_GPIO_Port,
                                       MOTOR_FR_IN1_Pin,
                                       MOTOR_FR_IN2_Pin,
                                       in1_high,
                                       in2_high);
      break;

    case MOTOR_WHEEL_RL:
      motor_logic_write_direction_pair(MOTOR_RL_IN1_GPIO_Port,
                                       MOTOR_RL_IN1_Pin,
                                       MOTOR_RL_IN2_Pin,
                                       in1_high,
                                       in2_high);
      break;

    case MOTOR_WHEEL_RR:
      motor_logic_write_direction_pair(MOTOR_RR_IN1_GPIO_Port,
                                       MOTOR_RR_IN1_Pin,
                                       MOTOR_RR_IN2_Pin,
                                       in1_high,
                                       in2_high);
      break;

    default:
      /* Already guarded above; retained for compiler-complete switching. */
      break;
  }
}

void motor_logic_stop_all(void)
{
  HAL_GPIO_WritePin(MOTOR_FL_IN1_GPIO_Port,
                    MOTOR_FL_IN1_Pin | MOTOR_FL_IN2_Pin |
                    MOTOR_FR_IN1_Pin | MOTOR_FR_IN2_Pin,
                    GPIO_PIN_RESET);
  HAL_GPIO_WritePin(MOTOR_RL_IN1_GPIO_Port,
                    MOTOR_RL_IN1_Pin | MOTOR_RL_IN2_Pin |
                    MOTOR_RR_IN1_Pin | MOTOR_RR_IN2_Pin,
                    GPIO_PIN_RESET);
}
