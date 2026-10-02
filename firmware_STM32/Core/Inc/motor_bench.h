/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : motor_bench.h
  * @brief          : Single-motor, debugger-requested bench-test interface.
  ******************************************************************************
  * This module is locked by default. It is not a runtime motor-control path
  * and it does not change hardware approval or E-stop ownership.
  ******************************************************************************
  */
/* USER CODE END Header */

#ifndef MOTOR_BENCH_H
#define MOTOR_BENCH_H

#include <stdint.h>

/* Deliberate, compile-time authorization; do not change automatically. */
#define MOTOR_BENCH_OUTPUT_AUTHORIZED 1

#ifdef __cplusplus
extern "C" {
#endif

typedef enum
{
  MOTOR_BENCH_COMMAND_NONE = 0,
  MOTOR_BENCH_COMMAND_FL_FORWARD = 1,
  MOTOR_BENCH_COMMAND_FR_FORWARD = 2,
  MOTOR_BENCH_COMMAND_RL_FORWARD = 3,
  MOTOR_BENCH_COMMAND_RR_FORWARD = 4
} MotorBenchCommand;

typedef enum
{
  MOTOR_BENCH_STATE_LOCKED = 0,
  MOTOR_BENCH_STATE_IDLE = 1,
  MOTOR_BENCH_STATE_ACTIVE = 2,
  MOTOR_BENCH_STATE_COMPLETE = 3,
  MOTOR_BENCH_STATE_REJECTED = 4
} MotorBenchState;

typedef enum
{
  MOTOR_BENCH_RESULT_NONE = 0,
  MOTOR_BENCH_RESULT_LOCKED = 1,
  MOTOR_BENCH_RESULT_RUNNING = 2,
  MOTOR_BENCH_RESULT_COMPLETE = 3,
  MOTOR_BENCH_RESULT_BUSY = 4,
  MOTOR_BENCH_RESULT_INVALID_REQUEST = 5,
  MOTOR_BENCH_RESULT_HAL_ERROR = 6
} MotorBenchResult;

typedef struct
{
  uint32_t request;
  uint32_t active_command;
  uint32_t state;
  uint32_t last_result;
  uint32_t completed_count;
  uint32_t elapsed_ms;
  uint32_t duty_permille;
  uint32_t duration_ms;
} MotorBenchSnapshot;

/* Debugger-visible request/status snapshot; StartDefaultTask owns updates. */
extern volatile MotorBenchSnapshot g_motor_bench;

void motor_bench_init(void);
void motor_bench_step(void);

#ifdef __cplusplus
}
#endif

#endif /* MOTOR_BENCH_H */
