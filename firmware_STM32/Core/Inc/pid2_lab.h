#ifndef PID2_LAB_H
#define PID2_LAB_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PID2_LOG_CAPACITY 256U
#define PID2_SAMPLE_PERIOD_MS 20U
#define PID2_LOG_EVERY_CYCLES 2U
#define PID2_MAX_PWM_PERMILLE 400U
#define PID2_DEFAULT_KP 0.084f
#define PID2_DEFAULT_KI 1.05f
#define PID2_WHEEL_COUNT 4U
#define PID2_FAULT_MASK_ALL 0x0fU

typedef enum {
  PID2_WHEEL_FL = 0U,
  PID2_WHEEL_FR = 1U,
  PID2_WHEEL_RL = 2U,
  PID2_WHEEL_RR = 3U
} Pid2Wheel;

typedef enum {
  PID2_MODE_ALL_FORWARD = 1U,
  PID2_MODE_ALL_REVERSE = 2U
} Pid2Mode;

typedef enum {
  PID2_REQUEST_NONE = 0U,
  PID2_REQUEST_RUN_PROFILE = 1U,
  PID2_REQUEST_ABORT = 2U,
  PID2_REQUEST_CLEAR_LOG = 3U
} Pid2Request;

typedef enum {
  PID2_STATE_IDLE = 0U,
  PID2_STATE_ZERO_GAP = 1U,
  PID2_STATE_RUN_PROFILE = 2U,
  PID2_STATE_COMPLETE = 3U,
  PID2_STATE_ABORTED = 4U,
  PID2_STATE_FAULT = 5U
} Pid2State;

typedef enum {
  PID2_ERROR_NONE = 0U,
  PID2_ERROR_INVALID_REQUEST = 1U,
  PID2_ERROR_INVALID_MODE = 2U,
  PID2_ERROR_INVALID_TIMING = 3U,
  PID2_ERROR_ENCODER_START = 4U,
  PID2_ERROR_PWM_START = 5U,
  PID2_ERROR_BAD_DT = 6U,
  PID2_ERROR_INVALID_OUTPUT = 7U,
  PID2_ERROR_LOG_OVERFLOW = 8U,
  PID2_ERROR_TIMEOUT = 9U,
  PID2_ERROR_WRONG_DIRECTION = 10U,
  PID2_ERROR_STALL = 11U,
  PID2_ERROR_SYNC = 12U,
  PID2_ERROR_STATE = 13U
} Pid2Error;

typedef struct {
  uint32_t timestamp_ms;
  uint32_t state;
  uint32_t mode;
  float target_cps;
  uint32_t dt_ms;
  float measured_cps[PID2_WHEEL_COUNT];
  float error_cps[PID2_WHEEL_COUNT];
  float u_ff_permille[PID2_WHEEL_COUNT];
  float u_i_permille[PID2_WHEEL_COUNT];
  float u_output_permille[PID2_WHEEL_COUNT];
  int32_t encoder_delta[PID2_WHEEL_COUNT];
  float sync_spread_cps;
  uint32_t sync_warning;
} Pid2LabSample;

typedef struct {
  volatile uint32_t request;
  volatile uint32_t state;
  volatile uint32_t mode;
  volatile float kp;
  volatile float ki;
  volatile uint32_t plateau_ms;
  volatile uint32_t zero_gap_ms;
  volatile uint32_t last_error;
  volatile uint32_t fault_wheel_mask;
  volatile uint32_t log_count;
  volatile uint32_t log_overflow;
  volatile uint32_t completed_count;
  volatile uint32_t elapsed_ms;
  volatile uint32_t dt_ms;
  volatile float target_cps;

  volatile float fl_measured_cps, fr_measured_cps;
  volatile float rl_measured_cps, rr_measured_cps;
  volatile float fl_error_cps, fr_error_cps;
  volatile float rl_error_cps, rr_error_cps;
  volatile float fl_u_ff, fr_u_ff, rl_u_ff, rr_u_ff;
  volatile float fl_u_p, fr_u_p, rl_u_p, rr_u_p;
  volatile float fl_u_i, fr_u_i, rl_u_i, rr_u_i;
  volatile float fl_u_output, fr_u_output, rl_u_output, rr_u_output;
  volatile int32_t fl_encoder_delta, fr_encoder_delta;
  volatile int32_t rl_encoder_delta, rr_encoder_delta;

  volatile float sync_spread_cps;
  volatile uint32_t sync_warning;
} Pid2LabControl;

extern volatile Pid2LabControl g_pid2;
extern Pid2LabSample g_pid2_log[PID2_LOG_CAPACITY];

void pid2_lab_init(void);
void pid2_lab_step(uint32_t now_ms);

#ifdef __cplusplus
}
#endif
#endif
