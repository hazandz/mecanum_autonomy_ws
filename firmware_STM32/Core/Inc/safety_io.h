/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : safety_io.h
  * @brief          : Fail-closed motor-output baseline.
  ******************************************************************************
  * @attention
  *
  * This module only requests a safe electrical state: MCU motor enable low,
  * zero PWM compare values, stopped PWM channels, and low motor-direction
  * pins. It does not grant motor-enable permission or replace the physical
  * E-stop hardware gate.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

#ifndef SAFETY_IO_H
#define SAFETY_IO_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
  * @brief  Establish the fail-closed motor-output baseline after GPIO and
  *         TIM3 initialization.
  * @note   Idempotent. This function never enables a motor output.
  */
void safety_io_init_safe(void);

/**
  * @brief  Request all motor-related MCU outputs to their disabled state.
  * @note   Idempotent and fail-closed. The physical E-stop remains independent
  *         of this firmware request.
  */
void safety_io_force_motor_disabled(void);

/**
 * Đọc E-stop phụ chỉ khi có ánh xạ GPIO/polarity đã được xác nhận.
 * Bản phần cứng hiện tại chưa có ánh xạ; trả false và không tạo giá trị giả.
 */
bool safety_io_read_estop_aux(bool *active);

#ifdef __cplusplus
}
#endif

#endif /* SAFETY_IO_H */
