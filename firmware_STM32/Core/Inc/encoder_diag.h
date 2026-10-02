/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : encoder_diag.h
  * @brief          : Read-only encoder diagnostic snapshot for ST-Link Watch.
  ******************************************************************************
  * This diagnostic does not establish the positive/negative direction
  * convention for any wheel. It is intended only for manual wheel rotation
  * observation through the debugger while motor outputs remain disabled.
  ******************************************************************************
  */
/* USER CODE END Header */

#ifndef ENCODER_DIAG_H
#define ENCODER_DIAG_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct
{
  int32_t fl_position;
  int32_t fr_position;
  int32_t rl_position;
  int32_t rr_position;
  int32_t fl_delta;
  int32_t fr_delta;
  int32_t rl_delta;
  int32_t rr_delta;
  uint32_t fl_raw;
  uint32_t fr_raw;
  uint32_t rl_raw;
  uint32_t rr_raw;
  uint32_t sample_count;
} EncoderDiagSnapshot;

/* Visible in ST-Link Expressions/Watch; updated by StartDefaultTask only. */
extern volatile EncoderDiagSnapshot g_encoder_diag;

/**
  * @brief  Start the encoder timer interfaces and capture their initial raw
  *         counters without resetting or writing a counter value.
  */
void encoder_diag_init(void);

/**
  * @brief  Read all encoder counters and update the debugger snapshot.
  * @note   This function does not write GPIO, PWM, or motor-control state.
  */
void encoder_diag_step(void);

#ifdef __cplusplus
}
#endif

#endif /* ENCODER_DIAG_H */
