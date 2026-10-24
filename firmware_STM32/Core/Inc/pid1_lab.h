#ifndef PID1_LAB_H
#define PID1_LAB_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PID1_LOG_CAPACITY 512U
#define PID1_SAMPLE_PERIOD_MS 20U
#define PID1_MAX_PWM_PERMILLE 400U
#define PID1_DEFAULT_KP 0.084f
#define PID1_DEFAULT_KI 1.05f

typedef enum {
  PID1_WHEEL_FL = 0U,
  PID1_WHEEL_FR = 1U,
  PID1_WHEEL_RL = 2U,
  PID1_WHEEL_RR = 3U
} Pid1Wheel;

typedef enum {
  PID1_DIRECTION_FORWARD = 1U,
  PID1_DIRECTION_REVERSE = 2U
} Pid1Direction;

typedef enum {
  PID1_REQUEST_NONE = 0U,
  PID1_REQUEST_RUN_PROFILE = 1U,
  PID1_REQUEST_ABORT = 2U,
  PID1_REQUEST_CLEAR_LOG = 3U
} Pid1Request;

typedef enum {
  PID1_STATE_IDLE = 0U,
  PID1_STATE_ZERO_GAP = 1U,
  PID1_STATE_RUN_PROFILE = 2U,
  PID1_STATE_COMPLETE = 3U,
  PID1_STATE_ABORTED = 4U,
  PID1_STATE_FAULT = 5U
} Pid1State;

typedef enum {
  PID1_ERROR_NONE = 0U,
  PID1_ERROR_INVALID_REQUEST = 1U,
  PID1_ERROR_INVALID_WHEEL = 2U,
  PID1_ERROR_INVALID_DIRECTION = 3U,
  PID1_ERROR_INVALID_TIMING = 4U,
  PID1_ERROR_ENCODER_START = 5U,
  PID1_ERROR_PWM_START = 6U,
  PID1_ERROR_LOG_OVERFLOW = 7U,
  PID1_ERROR_TIMEOUT = 8U,
  PID1_ERROR_WRONG_DIRECTION = 9U,
  PID1_ERROR_STALL = 10U,
  PID1_ERROR_STATE = 11U,
  PID1_ERROR_BAD_DT = 12U
} Pid1Error;

typedef struct {
  uint32_t timestamp_ms;
  uint32_t state;
  uint32_t selected_wheel;
  uint32_t direction;
  float target_cps;
  float measured_cps;
  float error_cps;
  float u_ff_permille;
  float u_p_permille;
  float u_i_permille;
  float u_output_permille;
  int32_t encoder_delta;
  uint32_t dt_ms;
} Pid1LabSample;

typedef struct {
  volatile uint32_t request;
  volatile uint32_t state;
  volatile uint32_t selected_wheel;
  volatile uint32_t direction;
  volatile float kp;
  volatile float ki;
  volatile uint32_t plateau_ms;
  volatile uint32_t zero_gap_ms;
  volatile uint32_t last_error;
  volatile uint32_t log_count;
  volatile uint32_t log_overflow;
  volatile uint32_t completed_count;
  volatile uint32_t elapsed_ms;
  volatile float target_cps;
  volatile float measured_cps;
  volatile float error_cps;
  volatile float u_ff;
  volatile float u_p;
  volatile float u_i;
  volatile float u_output;
  volatile int32_t encoder_delta;
  volatile uint32_t dt_ms;
} Pid1LabControl;

extern volatile Pid1LabControl g_pid1;
extern Pid1LabSample g_pid1_log[PID1_LOG_CAPACITY];

void pid1_lab_init(void);
void pid1_lab_step(uint32_t now_ms);

#ifdef __cplusplus
}
#endif
#endif
