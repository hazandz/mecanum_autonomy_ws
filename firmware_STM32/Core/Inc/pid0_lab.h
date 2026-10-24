#ifndef PID0_LAB_H
#define PID0_LAB_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PID0_LOG_CAPACITY 512U
#define PID0_SAMPLE_PERIOD_MS 20U
#define PID0_MAX_DUTY_PERMILLE 400U

typedef enum {
  PID0_WHEEL_FL = 0U, PID0_WHEEL_FR = 1U,
  PID0_WHEEL_RL = 2U, PID0_WHEEL_RR = 3U
} Pid0Wheel;

typedef enum {
  PID0_DIRECTION_FORWARD = 1U,
  PID0_DIRECTION_REVERSE = 2U
} Pid0Direction;

typedef enum {
  PID0_REQUEST_NONE = 0U,
  PID0_REQUEST_RUN_SINGLE_STEP = 1U,
  PID0_REQUEST_RUN_SWEEP = 2U,
  PID0_REQUEST_ABORT = 3U,
  PID0_REQUEST_CLEAR_LOG = 4U,
  PID0_REQUEST_DUMP_UART = 5U
} Pid0Request;

typedef enum {
  PID0_STATE_IDLE = 0U,
  PID0_STATE_ZERO_GAP = 1U,
  PID0_STATE_SETTLE = 2U,
  PID0_STATE_MEASURE = 3U,
  PID0_STATE_COMPLETE = 4U,
  PID0_STATE_ABORTED = 5U,
  PID0_STATE_FAULT = 6U
} Pid0State;

typedef enum {
  PID0_ERROR_NONE = 0U,
  PID0_ERROR_INVALID_REQUEST = 1U,
  PID0_ERROR_INVALID_WHEEL = 2U,
  PID0_ERROR_INVALID_DIRECTION = 3U,
  PID0_ERROR_INVALID_DUTY = 4U,
  PID0_ERROR_INVALID_TIMING = 5U,
  PID0_ERROR_PWM_START = 6U,
  PID0_ERROR_TIMEOUT = 7U,
  PID0_ERROR_LOGIC = 8U,
  PID0_ERROR_UART = 9U,
  PID0_ERROR_BUSY = 10U,
  PID0_ERROR_ENCODER_START = 11U
} Pid0Error;

typedef struct {
  uint32_t timestamp_ms;
  uint32_t state;
  uint32_t selected_wheel;
  uint32_t direction;
  uint32_t duty_permille;
  int32_t fl_delta, fr_delta, rl_delta, rr_delta;
  float fl_counts_per_sec, fr_counts_per_sec;
  float rl_counts_per_sec, rr_counts_per_sec;
} Pid0LabSample;

typedef struct {
  volatile uint32_t request;
  volatile uint32_t state;
  volatile uint32_t selected_wheel;
  volatile uint32_t direction;
  volatile uint32_t sweep_min_permille;
  volatile uint32_t sweep_max_permille;
  volatile uint32_t sweep_step_permille;
  volatile uint32_t settle_ms;
  volatile uint32_t measure_ms;
  volatile uint32_t zero_gap_ms;
  volatile uint32_t current_duty_permille;
  volatile uint32_t elapsed_ms;
  volatile uint32_t sample_count;
  volatile uint32_t log_count;
  volatile uint32_t last_error;
  volatile uint32_t completed_count;
  volatile uint32_t log_overflow;
  volatile int32_t fl_delta, fr_delta, rl_delta, rr_delta;
  volatile float fl_counts_per_sec, fr_counts_per_sec;
  volatile float rl_counts_per_sec, rr_counts_per_sec;
} Pid0LabControl;

extern volatile Pid0LabControl g_pid0;
extern Pid0LabSample g_pid0_log[PID0_LOG_CAPACITY];

/* Call after peripheral initialization. Initializes encoders, leaves all motor
 * outputs disabled, and does not start a test. */
void pid0_lab_init(void);
/* Call periodically (nominally every 20 ms) with the current HAL tick. */
void pid0_lab_step(uint32_t now_ms);

#ifdef __cplusplus
}
#endif
#endif
