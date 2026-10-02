/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : encoder_diag.c
  * @brief          : Read-only encoder diagnostic implementation.
  ******************************************************************************
  */
/* USER CODE END Header */

#include "encoder_diag.h"

#include <limits.h>

#include "main.h"

extern TIM_HandleTypeDef htim1;
extern TIM_HandleTypeDef htim2;
extern TIM_HandleTypeDef htim4;
extern TIM_HandleTypeDef htim5;

volatile EncoderDiagSnapshot g_encoder_diag;

static int32_t encoder_diag_delta16(uint32_t previous_raw, uint32_t current_raw)
{
  const uint16_t difference = (uint16_t)((uint16_t)current_raw -
                                         (uint16_t)previous_raw);

  if (difference <= (uint16_t)INT16_MAX)
  {
    return (int32_t)difference;
  }

  return (int32_t)difference - 65536;
}

static int32_t encoder_diag_delta32(uint32_t previous_raw, uint32_t current_raw)
{
  const uint32_t difference = current_raw - previous_raw;

  if (difference <= (uint32_t)INT32_MAX)
  {
    return (int32_t)difference;
  }

  return (int32_t)((int64_t)difference - 4294967296LL);
}

static int32_t encoder_diag_accumulate(int32_t position, int32_t delta)
{
  const int64_t sum = (int64_t)position + (int64_t)delta;

  if (sum > (int64_t)INT32_MAX)
  {
    return (int32_t)(sum - 4294967296LL);
  }

  if (sum < (int64_t)INT32_MIN)
  {
    return (int32_t)(sum + 4294967296LL);
  }

  return (int32_t)sum;
}

static uint32_t encoder_diag_read_tim1(void)
{
  return (uint32_t)(uint16_t)__HAL_TIM_GET_COUNTER(&htim1);
}

static uint32_t encoder_diag_read_tim2(void)
{
  return __HAL_TIM_GET_COUNTER(&htim2);
}

static uint32_t encoder_diag_read_tim4(void)
{
  return (uint32_t)(uint16_t)__HAL_TIM_GET_COUNTER(&htim4);
}

static uint32_t encoder_diag_read_tim5(void)
{
  return __HAL_TIM_GET_COUNTER(&htim5);
}

void encoder_diag_init(void)
{
  /* Encoder start enables timer counting only; it has no motor-output path. */
  (void)HAL_TIM_Encoder_Start(&htim1, TIM_CHANNEL_ALL);
  (void)HAL_TIM_Encoder_Start(&htim2, TIM_CHANNEL_ALL);
  (void)HAL_TIM_Encoder_Start(&htim4, TIM_CHANNEL_ALL);
  (void)HAL_TIM_Encoder_Start(&htim5, TIM_CHANNEL_ALL);

  g_encoder_diag.fl_raw = encoder_diag_read_tim2();
  g_encoder_diag.fr_raw = encoder_diag_read_tim5();
  g_encoder_diag.rl_raw = encoder_diag_read_tim1();
  g_encoder_diag.rr_raw = encoder_diag_read_tim4();

  g_encoder_diag.fl_position = 0;
  g_encoder_diag.fr_position = 0;
  g_encoder_diag.rl_position = 0;
  g_encoder_diag.rr_position = 0;
  g_encoder_diag.fl_delta = 0;
  g_encoder_diag.fr_delta = 0;
  g_encoder_diag.rl_delta = 0;
  g_encoder_diag.rr_delta = 0;
  g_encoder_diag.sample_count = 0U;
}

void encoder_diag_step(void)
{
  const uint32_t fl_raw = encoder_diag_read_tim2();
  const uint32_t fr_raw = encoder_diag_read_tim5();
  const uint32_t rl_raw = encoder_diag_read_tim1();
  const uint32_t rr_raw = encoder_diag_read_tim4();
  const int32_t fl_delta = encoder_diag_delta32(g_encoder_diag.fl_raw, fl_raw);
  const int32_t fr_delta = encoder_diag_delta32(g_encoder_diag.fr_raw, fr_raw);
  const int32_t rl_delta = encoder_diag_delta16(g_encoder_diag.rl_raw, rl_raw);
  const int32_t rr_delta = encoder_diag_delta16(g_encoder_diag.rr_raw, rr_raw);

  g_encoder_diag.fl_position = encoder_diag_accumulate(g_encoder_diag.fl_position,
                                                        fl_delta);
  g_encoder_diag.fr_position = encoder_diag_accumulate(g_encoder_diag.fr_position,
                                                        fr_delta);
  g_encoder_diag.rl_position = encoder_diag_accumulate(g_encoder_diag.rl_position,
                                                        rl_delta);
  g_encoder_diag.rr_position = encoder_diag_accumulate(g_encoder_diag.rr_position,
                                                        rr_delta);
  g_encoder_diag.fl_delta = fl_delta;
  g_encoder_diag.fr_delta = fr_delta;
  g_encoder_diag.rl_delta = rl_delta;
  g_encoder_diag.rr_delta = rr_delta;
  g_encoder_diag.fl_raw = fl_raw;
  g_encoder_diag.fr_raw = fr_raw;
  g_encoder_diag.rl_raw = rl_raw;
  g_encoder_diag.rr_raw = rr_raw;
  g_encoder_diag.sample_count++;
}
