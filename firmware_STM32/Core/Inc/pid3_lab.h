#ifndef PID3_LAB_H
#define PID3_LAB_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PID3_ARM_MAGIC 0x50334131U
#define PID3_LOG_CAPACITY 256U
#define PID3_SAMPLE_PERIOD_MS 20U
#define PID3_LOG_EVERY_CYCLES 2U
#define PID3_MAX_PWM_PERMILLE 400U
#define PID3_DEFAULT_KP 0.084f
#define PID3_DEFAULT_KI 1.05f
#define PID3_DEFAULT_ARM_DELAY_MS 10000U
#define PID3_DEFAULT_RUN_DURATION_MS 5000U
#define PID3_DEFAULT_STOP_HOLD_MS 1000U
#define PID3_TARGET_CPS 500.0f
#define PID3_WHEEL_COUNT 4U
#define PID3_FAULT_MASK_ALL 0x0fU

typedef enum {
  PID3_REQUEST_NONE = 0U,
  PID3_REQUEST_ARM_AUTORUN = 1U,
  PID3_REQUEST_ABORT = 2U,
  PID3_REQUEST_CLEAR_LOG = 3U
} Pid3Request;

typedef enum {
  PID3_STATE_IDLE = 0U,
  PID3_STATE_ARMED_DELAY = 1U,
  PID3_STATE_RUN = 2U,
  PID3_STATE_STOP_HOLD = 3U,
  PID3_STATE_COMPLETE = 4U,
  PID3_STATE_ABORTED = 5U,
  PID3_STATE_FAULT = 6U
} Pid3State;

typedef enum {
  PID3_ERROR_NONE = 0U,
  PID3_ERROR_INVALID_ARM = 1U,
  PID3_ERROR_INVALID_REQUEST = 2U,
  PID3_ERROR_INVALID_TIMING = 3U,
  PID3_ERROR_ENCODER_START = 4U,
  PID3_ERROR_BAD_DT = 5U,
  PID3_ERROR_INVALID_OUTPUT = 6U,
  PID3_ERROR_PWM_START = 7U,
  PID3_ERROR_LOG_OVERFLOW = 8U,
  PID3_ERROR_TIMEOUT = 9U,
  PID3_ERROR_WRONG_DIRECTION = 10U,
  PID3_ERROR_STALL = 11U,
  PID3_ERROR_SYNC = 12U,
  PID3_ERROR_STATE = 13U
} Pid3Error;

typedef struct {
  uint32_t timestamp_ms;
  uint32_t state;
  float target_cps;
  uint32_t dt_ms;
  float measured_cps[PID3_WHEEL_COUNT];
  float error_cps[PID3_WHEEL_COUNT];
  float u_ff_permille[PID3_WHEEL_COUNT];
  float u_i_permille[PID3_WHEEL_COUNT];
  float u_output_permille[PID3_WHEEL_COUNT];
  int32_t encoder_delta[PID3_WHEEL_COUNT];
  float sync_spread_cps;
  uint32_t sync_warning;
} Pid3LabSample;

typedef struct {
  volatile uint32_t request;
  volatile uint32_t state;
  volatile uint32_t arm_magic;
  volatile float kp;
  volatile float ki;
  volatile uint32_t arm_delay_ms;
  volatile uint32_t run_duration_ms;
  volatile uint32_t stop_hold_ms;
  volatile uint32_t last_error;
  volatile uint32_t fault_wheel_mask;
  volatile uint32_t log_count;
  volatile uint32_t log_overflow;
  volatile uint32_t completed_count;
  volatile uint32_t arm_elapsed_ms;
  volatile uint32_t arm_remaining_ms;
  volatile uint32_t run_elapsed_ms;
  volatile uint32_t dt_ms;
  volatile float target_cps;

  volatile float fl_measured_cps, fr_measured_cps;
  volatile float rl_measured_cps, rr_measured_cps;
  volatile float fl_error_cps, fr_error_cps;
  volatile float rl_error_cps, rr_error_cps;
  volatile float fl_u_ff, fr_u_ff, rl_u_ff, rr_u_ff;
  volatile float fl_u_i, fr_u_i, rl_u_i, rr_u_i;
  volatile float fl_u_output, fr_u_output, rl_u_output, rr_u_output;
  volatile int32_t fl_encoder_delta, fr_encoder_delta;
  volatile int32_t rl_encoder_delta, rr_encoder_delta;
  volatile float sync_spread_cps;
  volatile uint32_t sync_warning;
  volatile int64_t total_delta_fl, total_delta_fr;
  volatile int64_t total_delta_rl, total_delta_rr;
} Pid3LabControl;

extern volatile Pid3LabControl g_pid3;
extern Pid3LabSample g_pid3_log[PID3_LOG_CAPACITY];

void pid3_lab_init(void);
void pid3_lab_step(uint32_t now_ms);

#ifdef __cplusplus
}
#endif
#endif
