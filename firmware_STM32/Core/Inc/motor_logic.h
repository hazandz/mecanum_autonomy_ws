/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : motor_logic.h
  * @brief          : Direction-pin logic for the four mecanum motors.
  ******************************************************************************
  * Verified hardware direction mapping – 2026-09-20:
  * robot-forward is internal polarity B (IN1 LOW, IN2 HIGH) for FL and FR,
  * and internal polarity A (IN1 HIGH, IN2 LOW) for RL and RR.
  *
  * Encoder signs were verified independently: rotating every wheel in the
  * robot-forward direction increases its encoder position.  This module does
  * not alter that convention and does not control PWM or motor enable.
  ******************************************************************************
  */
/* USER CODE END Header */

#ifndef MOTOR_LOGIC_H
#define MOTOR_LOGIC_H

#ifdef __cplusplus
extern "C" {
#endif

typedef enum
{
  MOTOR_WHEEL_FL = 0,
  MOTOR_WHEEL_FR = 1,
  MOTOR_WHEEL_RL = 2,
  MOTOR_WHEEL_RR = 3
} MotorWheel;

typedef enum
{
  MOTOR_DIRECTION_COAST = 0,
  MOTOR_DIRECTION_STOP = MOTOR_DIRECTION_COAST,
  MOTOR_DIRECTION_FORWARD = 1,
  MOTOR_DIRECTION_REVERSE = 2
} MotorDirection;

/* Applies only the selected wheel's IN1/IN2 direction pins. */
void motor_logic_set_direction(MotorWheel wheel, MotorDirection direction);

/* Places all four motor direction pairs into the safe coast/stop state. */
void motor_logic_stop_all(void);

#ifdef __cplusplus
}
#endif

#endif /* MOTOR_LOGIC_H */
