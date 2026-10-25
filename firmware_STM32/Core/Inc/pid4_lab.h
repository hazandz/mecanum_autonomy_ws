#ifndef PID4_LAB_H
#define PID4_LAB_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PID4_ARM_MAGIC 0x50344131U
#define PID4_WHEEL_COUNT 4U
#define PID4_LOG_CAPACITY 240U
#define PID4_SAMPLE_PERIOD_MS 20U
#define PID4_LOG_EVERY_CYCLES 2U
#define PID4_MAX_PWM_PERMILLE 400U
#define PID4_MAX_TARGET_CPS 1400.0f
#define PID4_DEFAULT_KP 0.084f
#define PID4_DEFAULT_KI 1.05f
#define PID4_DEFAULT_ARM_DELAY_MS 10000U
#define PID4_DEFAULT_RUN_DURATION_MS 5000U
#define PID4_DEFAULT_STOP_HOLD_MS 1000U
#define PID4_RAMP_DURATION_MS 1000U
#define PID4_FAULT_MASK_ALL 0x0fU

typedef enum {
  PID4_REQUEST_NONE = 0U,
  PID4_REQUEST_ARM_AUTORUN = 1U,
  PID4_REQUEST_ABORT = 2U,
  PID4_REQUEST_CLEAR_LOG = 3U
} Pid4Request;

typedef enum {
  PID4_STATE_IDLE = 0U,
  PID4_STATE_ARMED_DELAY = 1U,
  PID4_STATE_RUN = 2U,
  PID4_STATE_STOP_HOLD = 3U,
  PID4_STATE_COMPLETE = 4U,
  PID4_STATE_ABORTED = 5U,
  PID4_STATE_FAULT = 6U
} Pid4State;

typedef enum {
  PID4_ERROR_NONE = 0U,
  PID4_ERROR_INVALID_ARM = 1U,
  PID4_ERROR_INVALID_REQUEST = 2U,
  PID4_ERROR_INVALID_TARGET = 3U,
  PID4_ERROR_ENCODER_START = 4U,
  PID4_ERROR_BAD_DT = 5U,
  PID4_ERROR_INVALID_OUTPUT = 6U,
  PID4_ERROR_PWM_START = 7U,
  PID4_ERROR_LOG_OVERFLOW = 8U,
  PID4_ERROR_TIMEOUT = 9U,
  PID4_ERROR_WRONG_DIRECTION = 10U,
  PID4_ERROR_STALL = 11U,
  PID4_ERROR_SYNC = 12U,
  PID4_ERROR_STATE = 13U
} Pid4Error;

typedef struct {
  uint32_t timestamp_ms;
  uint32_t state;
  uint32_t dt_ms;
  float target_cps[PID4_WHEEL_COUNT];
  float measured_cps[PID4_WHEEL_COUNT];
  float error_cps[PID4_WHEEL_COUNT];
  float u_ff[PID4_WHEEL_COUNT];
  float u_i[PID4_WHEEL_COUNT];
  float u_output[PID4_WHEEL_COUNT];
  int32_t encoder_delta[PID4_WHEEL_COUNT];
  float sync_spread_cps;
  uint32_t sync_warning;
} Pid4LabSample;

typedef struct {
  volatile uint32_t request;
  volatile uint32_t state;
  volatile uint32_t arm_magic;
  volatile float requested_target_cps[PID4_WHEEL_COUNT];
  volatile float active_target_cps[PID4_WHEEL_COUNT];
  volatile float measured_cps[PID4_WHEEL_COUNT];
  volatile float error_cps[PID4_WHEEL_COUNT];
  volatile float u_ff[PID4_WHEEL_COUNT];
  volatile float u_i[PID4_WHEEL_COUNT];
  volatile float u_output[PID4_WHEEL_COUNT];
  volatile int32_t encoder_delta[PID4_WHEEL_COUNT];
  volatile int64_t total_delta_fl;
  volatile int64_t total_delta_fr;
  volatile int64_t total_delta_rl;
  volatile int64_t total_delta_rr;
  volatile uint32_t last_error;
  volatile uint32_t fault_wheel_mask;
  volatile uint32_t log_count;
  volatile uint32_t log_overflow;
  volatile uint32_t completed_count;
  volatile uint32_t elapsed_ms;
  volatile uint32_t dt_ms;
  volatile uint32_t arm_elapsed_ms;
  volatile uint32_t arm_remaining_ms;
  volatile uint32_t sync_guard_enabled;
  volatile float sync_spread_cps;
  volatile uint32_t sync_warning;
} Pid4LabControl;

extern volatile Pid4LabControl g_pid4;
extern Pid4LabSample g_pid4_log[PID4_LOG_CAPACITY];

void pid4_lab_init(void);
void pid4_lab_step(uint32_t now_ms);

#ifdef __cplusplus
}
#endif
#endif
