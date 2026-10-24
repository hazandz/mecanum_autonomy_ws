#include "pid2_lab.h"

#include <math.h>
#include <stdbool.h>
#include <string.h>

#include "main.h"
#include "motor_logic.h"
#include "safety_io.h"

extern TIM_HandleTypeDef htim1, htim2, htim3, htim4, htim5;

#define PID2_DEFAULT_PLATEAU_MS 1500U
#define PID2_DEFAULT_ZERO_GAP_MS 400U
#define PID2_RUN_TIMEOUT_MS 20000U
#define PID2_MAX_RUN_PROFILE_MS 17000U
#define PID2_INTEGRAL_LIMIT 80.0f
#define PID2_DIRECTION_THRESHOLD_CPS 100.0f
#define PID2_DIRECTION_FAULT_MS 200U
#define PID2_STALL_OUTPUT_PERMILLE 120.0f
#define PID2_STALL_GRACE_MS 400U
#define PID2_STALL_FAULT_MS 500U
#define PID2_SYNC_GRACE_MS 500U
#define PID2_SYNC_WARNING_ABS_CPS 150.0f
#define PID2_SYNC_WARNING_FRACTION 0.15f
#define PID2_SYNC_FAULT_ABS_CPS 300.0f
#define PID2_SYNC_FAULT_FRACTION 0.25f
#define PID2_SYNC_FAULT_MS 500U
#define PID2_PROFILE_COUNT 5U
#define PID2_COMPARE_SCALE 1000ULL
#define PID2_LOG_PERIOD_MS (PID2_SAMPLE_PERIOD_MS * PID2_LOG_EVERY_CYCLES)
#define PID2_LOG_MARGIN_SAMPLES 5ULL

typedef struct { uint32_t fl, fr, rl, rr; } EncoderRaw;
typedef struct { float u0, kv; } Pid2Feedforward;

/* Index order: [wheel][0 = forward, 1 = reverse]. */
static const Pid2Feedforward feedforward[PID2_WHEEL_COUNT][2] = {
  {{40.330665f, 0.217819026f}, {36.253577f, 0.225076821f}},
  {{32.415574f, 0.231811480f}, {34.233335f, 0.226312521f}},
  {{61.698998f, 0.212679580f}, {54.760209f, 0.223609266f}},
  {{37.521999f, 0.223981830f}, {32.707200f, 0.229221684f}}
};
static const float profile_cps[PID2_PROFILE_COUNT] = {
  500.0f, 1000.0f, 1400.0f, 1000.0f, 500.0f
};
static const uint32_t pwm_channel[PID2_WHEEL_COUNT] = {
  TIM_CHANNEL_4, TIM_CHANNEL_3, TIM_CHANNEL_1, TIM_CHANNEL_2
};
static const MotorWheel motor_wheel[PID2_WHEEL_COUNT] = {
  MOTOR_WHEEL_FL, MOTOR_WHEEL_FR, MOTOR_WHEEL_RL, MOTOR_WHEEL_RR
};

_Static_assert(sizeof(Pid2LabSample) * PID2_LOG_CAPACITY <= 32768U,
               "PID2 RAM log exceeds 32 KiB budget");

volatile Pid2LabControl g_pid2;
Pid2LabSample g_pid2_log[PID2_LOG_CAPACITY];

static EncoderRaw previous_raw;
static uint32_t internal_state, active_mode;
static uint32_t active_plateau_ms, active_zero_gap_ms, profile_index;
static uint32_t last_sample_ms, run_started_ms, phase_started_ms;
static uint32_t log_used, log_divider, pwm_started, finish_after_gap;
static uint32_t wrong_direction_ms[PID2_WHEEL_COUNT];
static uint32_t stall_ms[PID2_WHEEL_COUNT];
static uint32_t sync_fault_ms;
static float integral_permille[PID2_WHEEL_COUNT];

static uint32_t elapsed(uint32_t now, uint32_t then) { return now - then; }

static int32_t delta32(uint32_t old, uint32_t now)
{
  uint32_t d = now - old;
  return d <= 0x7fffffffU ? (int32_t)d : (int32_t)((int64_t)d - 4294967296LL);
}

static int32_t delta16(uint32_t old, uint32_t now)
{
  uint16_t d = (uint16_t)((uint16_t)now - (uint16_t)old);
  return d <= 0x7fffU ? (int32_t)d : (int32_t)d - 65536;
}

static EncoderRaw read_all_encoders(void)
{
  EncoderRaw raw;
  raw.fl = __HAL_TIM_GET_COUNTER(&htim2);
  raw.fr = __HAL_TIM_GET_COUNTER(&htim5);
  raw.rl = (uint32_t)(uint16_t)__HAL_TIM_GET_COUNTER(&htim1);
  raw.rr = (uint32_t)(uint16_t)__HAL_TIM_GET_COUNTER(&htim4);
  return raw;
}

static void encoder_deltas(EncoderRaw old, EncoderRaw now, int32_t delta[4])
{
  delta[PID2_WHEEL_FL] = delta32(old.fl, now.fl);
  delta[PID2_WHEEL_FR] = delta32(old.fr, now.fr);
  delta[PID2_WHEEL_RL] = delta16(old.rl, now.rl);
  delta[PID2_WHEEL_RR] = delta16(old.rr, now.rr);
}

static void set_state(uint32_t state)
{
  internal_state = state;
  g_pid2.state = state;
}

static void safe_outputs(void)
{
  safety_io_force_motor_disabled();
  motor_logic_stop_all();
  pwm_started = 0U;
  g_pid2.fl_u_output = 0.0f;
  g_pid2.fr_u_output = 0.0f;
  g_pid2.rl_u_output = 0.0f;
  g_pid2.rr_u_output = 0.0f;
}

static void reset_controller(void)
{
  uint32_t i;
  for (i = 0U; i < PID2_WHEEL_COUNT; ++i) {
    integral_permille[i] = 0.0f;
    wrong_direction_ms[i] = 0U;
    stall_ms[i] = 0U;
  }
  sync_fault_ms = 0U;
  g_pid2.target_cps = 0.0f;
  g_pid2.dt_ms = 0U;
  g_pid2.fl_measured_cps = 0.0f;
  g_pid2.fr_measured_cps = 0.0f;
  g_pid2.rl_measured_cps = 0.0f;
  g_pid2.rr_measured_cps = 0.0f;
  g_pid2.fl_error_cps = 0.0f;
  g_pid2.fr_error_cps = 0.0f;
  g_pid2.rl_error_cps = 0.0f;
  g_pid2.rr_error_cps = 0.0f;
  g_pid2.fl_u_ff = 0.0f;
  g_pid2.fr_u_ff = 0.0f;
  g_pid2.rl_u_ff = 0.0f;
  g_pid2.rr_u_ff = 0.0f;
  g_pid2.fl_u_p = 0.0f;
  g_pid2.fr_u_p = 0.0f;
  g_pid2.rl_u_p = 0.0f;
  g_pid2.rr_u_p = 0.0f;
  g_pid2.fl_u_i = 0.0f;
  g_pid2.fr_u_i = 0.0f;
  g_pid2.rl_u_i = 0.0f;
  g_pid2.rr_u_i = 0.0f;
  g_pid2.fl_encoder_delta = 0;
  g_pid2.fr_encoder_delta = 0;
  g_pid2.rl_encoder_delta = 0;
  g_pid2.rr_encoder_delta = 0;
  g_pid2.sync_spread_cps = 0.0f;
  g_pid2.sync_warning = 0U;
}

static void fail_closed(uint32_t error, uint32_t wheel_mask)
{
  safe_outputs();
  reset_controller();
  g_pid2.fault_wheel_mask = wheel_mask & PID2_FAULT_MASK_ALL;
  g_pid2.last_error = error;
  g_pid2.target_cps = 0.0f;
  set_state(PID2_STATE_FAULT);
}

static bool valid_mode(uint32_t mode)
{
  return mode == PID2_MODE_ALL_FORWARD || mode == PID2_MODE_ALL_REVERSE;
}

static float mode_sign(uint32_t mode)
{
  return mode == PID2_MODE_ALL_FORWARD ? 1.0f : -1.0f;
}

static void set_debug_vector(const float measured[4], const float error[4],
                             const float ff[4], const float up[4],
                             const float ui[4], const float output[4],
                             const int32_t delta[4])
{
  g_pid2.fl_measured_cps = measured[0];
  g_pid2.fr_measured_cps = measured[1];
  g_pid2.rl_measured_cps = measured[2];
  g_pid2.rr_measured_cps = measured[3];
  g_pid2.fl_error_cps = error[0];
  g_pid2.fr_error_cps = error[1];
  g_pid2.rl_error_cps = error[2];
  g_pid2.rr_error_cps = error[3];
  g_pid2.fl_u_ff = ff[0];
  g_pid2.fr_u_ff = ff[1];
  g_pid2.rl_u_ff = ff[2];
  g_pid2.rr_u_ff = ff[3];
  g_pid2.fl_u_p = up[0];
  g_pid2.fr_u_p = up[1];
  g_pid2.rl_u_p = up[2];
  g_pid2.rr_u_p = up[3];
  g_pid2.fl_u_i = ui[0];
  g_pid2.fr_u_i = ui[1];
  g_pid2.rl_u_i = ui[2];
  g_pid2.rr_u_i = ui[3];
  g_pid2.fl_u_output = output[0];
  g_pid2.fr_u_output = output[1];
  g_pid2.rl_u_output = output[2];
  g_pid2.rr_u_output = output[3];
  g_pid2.fl_encoder_delta = delta[0];
  g_pid2.fr_encoder_delta = delta[1];
  g_pid2.rl_encoder_delta = delta[2];
  g_pid2.rr_encoder_delta = delta[3];
}

static bool validate_run(void)
{
  uint64_t duration_ms;
  uint64_t expected_samples;
  if (!valid_mode(g_pid2.mode)) {
    fail_closed(PID2_ERROR_INVALID_MODE, PID2_FAULT_MASK_ALL);
    return false;
  }
  if (!isfinite(g_pid2.kp) || !isfinite(g_pid2.ki) ||
      g_pid2.kp < 0.0f || g_pid2.kp > 1.0f ||
      g_pid2.ki < 0.0f || g_pid2.ki > 10.0f ||
      g_pid2.plateau_ms < 500U || g_pid2.plateau_ms > 3000U ||
      g_pid2.zero_gap_ms < PID2_SAMPLE_PERIOD_MS || g_pid2.zero_gap_ms > 1000U) {
    fail_closed(PID2_ERROR_INVALID_TIMING, PID2_FAULT_MASK_ALL);
    return false;
  }
  duration_ms = (uint64_t)PID2_PROFILE_COUNT * g_pid2.plateau_ms +
                2ULL * g_pid2.zero_gap_ms;
  expected_samples = (5ULL * g_pid2.plateau_ms + PID2_LOG_PERIOD_MS - 1ULL) /
                     PID2_LOG_PERIOD_MS + PID2_LOG_MARGIN_SAMPLES;
  if (duration_ms > PID2_MAX_RUN_PROFILE_MS ||
      expected_samples > PID2_LOG_CAPACITY) {
    fail_closed(PID2_ERROR_INVALID_TIMING, PID2_FAULT_MASK_ALL);
    return false;
  }
  return true;
}

static void clear_log_request(void)
{
  safe_outputs();
  reset_controller();
  memset(g_pid2_log, 0, sizeof(g_pid2_log));
  log_used = 0U;
  log_divider = 0U;
  finish_after_gap = 0U;
  g_pid2.log_count = 0U;
  g_pid2.log_overflow = 0U;
  g_pid2.elapsed_ms = 0U;
  g_pid2.completed_count = 0U;
  g_pid2.fault_wheel_mask = 0U;
  g_pid2.last_error = PID2_ERROR_NONE;
  set_state(PID2_STATE_IDLE);
}

static void begin_run(uint32_t now_ms)
{
  if (log_used != 0U) {
    fail_closed(PID2_ERROR_STATE, PID2_FAULT_MASK_ALL);
    return;
  }
  if (!validate_run()) return;
  active_mode = g_pid2.mode;
  active_plateau_ms = g_pid2.plateau_ms;
  active_zero_gap_ms = g_pid2.zero_gap_ms;
  profile_index = 0U;
  finish_after_gap = 0U;
  run_started_ms = now_ms;
  phase_started_ms = now_ms;
  reset_controller();
  safe_outputs();
  g_pid2.fault_wheel_mask = 0U;
  g_pid2.last_error = PID2_ERROR_NONE;
  g_pid2.elapsed_ms = 0U;
  log_divider = 0U;
  set_state(PID2_STATE_ZERO_GAP);
}

static void handle_request(uint32_t now_ms)
{
  uint32_t request = g_pid2.request;
  if (request == PID2_REQUEST_ABORT) {
    g_pid2.request = PID2_REQUEST_NONE;
    safe_outputs();
    reset_controller();
    g_pid2.fault_wheel_mask = 0U;
    g_pid2.last_error = PID2_ERROR_NONE;
    set_state(PID2_STATE_ABORTED);
    return;
  }
  if (request == PID2_REQUEST_CLEAR_LOG) {
    g_pid2.request = PID2_REQUEST_NONE;
    clear_log_request();
    return;
  }
  if (request == PID2_REQUEST_NONE) return;
  if (request != PID2_REQUEST_RUN_PROFILE) {
    g_pid2.request = PID2_REQUEST_NONE;
    fail_closed(PID2_ERROR_INVALID_REQUEST, PID2_FAULT_MASK_ALL);
    return;
  }
  g_pid2.request = PID2_REQUEST_NONE;
  if (internal_state == PID2_STATE_IDLE || internal_state == PID2_STATE_COMPLETE ||
      internal_state == PID2_STATE_ABORTED) {
    begin_run(now_ms);
  } else {
    fail_closed(PID2_ERROR_STATE, PID2_FAULT_MASK_ALL);
  }
}

static void start_all_pwm_or_fault(const float output[4])
{
  uint32_t i;
  uint32_t arr = __HAL_TIM_GET_AUTORELOAD(&htim3);
  uint32_t compare[PID2_WHEEL_COUNT];
  for (i = 0U; i < PID2_WHEEL_COUNT; ++i) {
    if (!isfinite(output[i]) || output[i] < 0.0f ||
        output[i] > (float)PID2_MAX_PWM_PERMILLE) {
      fail_closed(PID2_ERROR_INVALID_OUTPUT, 1UL << i);
      return;
    }
    compare[i] = (uint32_t)(((uint64_t)arr + 1ULL) *
                 (uint32_t)(output[i] + 0.5f) / PID2_COMPARE_SCALE);
    if (output[i] > 0.0f && compare[i] == 0U) compare[i] = 1U;
  }
  if (pwm_started == 0U) {
    /* Direction pins are prepared after all outputs validate, with gate low. */
    for (i = 0U; i < PID2_WHEEL_COUNT; ++i) {
      motor_logic_set_direction(motor_wheel[i],
          active_mode == PID2_MODE_ALL_FORWARD ?
          MOTOR_DIRECTION_FORWARD : MOTOR_DIRECTION_REVERSE);
    }
  }
  /* All four compares are prepared before any new PWM channel is started. */
  for (i = 0U; i < PID2_WHEEL_COUNT; ++i) {
    __HAL_TIM_SET_COMPARE(&htim3, pwm_channel[i], compare[i]);
  }
  if (pwm_started == 0U) {
    for (i = 0U; i < PID2_WHEEL_COUNT; ++i) {
      if (HAL_TIM_PWM_Start(&htim3, pwm_channel[i]) != HAL_OK) {
        fail_closed(PID2_ERROR_PWM_START, 1UL << i);
        return;
      }
    }
    pwm_started = 1U;
    /* Gate stays low until every PWM channel has started successfully. */
    HAL_GPIO_WritePin(MCU_MOTOR_ENABLE_GPIO_Port, MCU_MOTOR_ENABLE_Pin, GPIO_PIN_SET);
  }
}

static void append_sample(uint32_t now_ms, uint32_t dt_ms, float target_signed,
                          const float measured[4], const float error[4],
                          const float ff[4], const float ui[4],
                          const float output[4], const int32_t delta[4])
{
  Pid2LabSample *sample;
  uint32_t i;
  if (log_used >= PID2_LOG_CAPACITY) {
    g_pid2.log_overflow = 1U;
    fail_closed(PID2_ERROR_LOG_OVERFLOW, PID2_FAULT_MASK_ALL);
    return;
  }
  sample = &g_pid2_log[log_used++];
  sample->timestamp_ms = now_ms;
  sample->state = PID2_STATE_RUN_PROFILE;
  sample->mode = active_mode;
  sample->target_cps = target_signed;
  sample->dt_ms = dt_ms;
  for (i = 0U; i < PID2_WHEEL_COUNT; ++i) {
    sample->measured_cps[i] = measured[i];
    sample->error_cps[i] = error[i];
    sample->u_ff_permille[i] = ff[i];
    sample->u_i_permille[i] = ui[i];
    sample->u_output_permille[i] = output[i];
    sample->encoder_delta[i] = delta[i];
  }
  sample->sync_spread_cps = g_pid2.sync_spread_cps;
  sample->sync_warning = g_pid2.sync_warning;
  g_pid2.log_count = log_used;
}

static uint32_t monitor_guards(uint32_t now_ms, uint32_t dt_ms,
                               const float y[4], const float output[4],
                               float target, uint32_t *error,
                               uint32_t *fault_mask)
{
  uint32_t i, min_i = 0U, max_i = 0U;
  float min_speed = y[0], max_speed = y[0];
  float warning_limit = fmaxf(PID2_SYNC_WARNING_ABS_CPS,
                              PID2_SYNC_WARNING_FRACTION * target);
  float fault_limit = fmaxf(PID2_SYNC_FAULT_ABS_CPS,
                            PID2_SYNC_FAULT_FRACTION * target);
  bool grace_elapsed = elapsed(now_ms, phase_started_ms) >= PID2_SYNC_GRACE_MS;
  for (i = 0U; i < PID2_WHEEL_COUNT; ++i) {
    uint32_t bit = 1UL << i;
    if (target >= 500.0f && output[i] >= 80.0f &&
        y[i] < -PID2_DIRECTION_THRESHOLD_CPS) {
      wrong_direction_ms[i] += dt_ms;
    } else {
      wrong_direction_ms[i] = 0U;
    }
    if (wrong_direction_ms[i] >= PID2_DIRECTION_FAULT_MS) {
      *error = PID2_ERROR_WRONG_DIRECTION;
      *fault_mask = bit;
      return 1U;
    }
    if (grace_elapsed && target >= 500.0f &&
        output[i] >= PID2_STALL_OUTPUT_PERMILLE &&
        fabsf(y[i]) < PID2_DIRECTION_THRESHOLD_CPS) {
      stall_ms[i] += dt_ms;
    } else {
      stall_ms[i] = 0U;
    }
    if (stall_ms[i] >= PID2_STALL_FAULT_MS) {
      *error = PID2_ERROR_STALL;
      *fault_mask = bit;
      return 1U;
    }
    if (y[i] < min_speed) { min_speed = y[i]; min_i = i; }
    if (y[i] > max_speed) { max_speed = y[i]; max_i = i; }
  }
  g_pid2.sync_spread_cps = max_speed - min_speed;
  g_pid2.sync_warning = (grace_elapsed && g_pid2.sync_spread_cps > warning_limit) ? 1U : 0U;
  if (grace_elapsed && g_pid2.sync_spread_cps > fault_limit) {
    sync_fault_ms += dt_ms;
  } else {
    sync_fault_ms = 0U;
  }
  if (sync_fault_ms >= PID2_SYNC_FAULT_MS) {
    *error = PID2_ERROR_SYNC;
    *fault_mask = (1UL << min_i) | (1UL << max_i);
    return 1U;
  }
  return 0U;
}

static void compute_all_outputs(uint32_t dt_ms, const int32_t delta[4],
                                float target, float sign, float measured[4],
                                float y[4], float error[4], float ff[4],
                                float up[4], float ui[4], float output[4])
{
  uint32_t i;
  uint32_t direction_index = active_mode == PID2_MODE_ALL_FORWARD ? 0U : 1U;
  float dt_seconds = (float)dt_ms / 1000.0f;
  for (i = 0U; i < PID2_WHEEL_COUNT; ++i) {
    float candidate, raw;
    const Pid2Feedforward *coeff = &feedforward[i][direction_index];
    measured[i] = (float)delta[i] * 1000.0f / (float)dt_ms;
    y[i] = sign * measured[i];
    error[i] = target - y[i];
    ff[i] = coeff->u0 + coeff->kv * target;
    up[i] = g_pid2.kp * error[i];
    candidate = integral_permille[i] + g_pid2.ki * error[i] * dt_seconds;
    if (candidate > PID2_INTEGRAL_LIMIT) candidate = PID2_INTEGRAL_LIMIT;
    if (candidate < -PID2_INTEGRAL_LIMIT) candidate = -PID2_INTEGRAL_LIMIT;
    raw = ff[i] + up[i] + candidate;
    if (!((raw >= (float)PID2_MAX_PWM_PERMILLE && error[i] > 0.0f) ||
          (raw <= 0.0f && error[i] < 0.0f))) {
      integral_permille[i] = candidate;
    }
    ui[i] = integral_permille[i];
    raw = ff[i] + up[i] + ui[i];
    if (raw < 0.0f) raw = 0.0f;
    if (raw > (float)PID2_MAX_PWM_PERMILLE) raw = (float)PID2_MAX_PWM_PERMILLE;
    output[i] = raw;
  }
}

void pid2_lab_init(void)
{
  uint32_t i;
  safe_outputs();
  g_pid2.request = PID2_REQUEST_NONE;
  g_pid2.state = PID2_STATE_IDLE;
  g_pid2.mode = PID2_MODE_ALL_FORWARD;
  g_pid2.kp = PID2_DEFAULT_KP;
  g_pid2.ki = PID2_DEFAULT_KI;
  g_pid2.plateau_ms = PID2_DEFAULT_PLATEAU_MS;
  g_pid2.zero_gap_ms = PID2_DEFAULT_ZERO_GAP_MS;
  g_pid2.last_error = PID2_ERROR_NONE;
  g_pid2.fault_wheel_mask = 0U;
  g_pid2.log_count = 0U;
  g_pid2.log_overflow = 0U;
  g_pid2.completed_count = 0U;
  g_pid2.elapsed_ms = 0U;
  log_used = 0U;
  internal_state = PID2_STATE_IDLE;
  active_mode = PID2_MODE_ALL_FORWARD;
  finish_after_gap = 0U;
  reset_controller();
  for (i = 0U; i < PID2_WHEEL_COUNT; ++i) {
    integral_permille[i] = 0.0f;
    wrong_direction_ms[i] = 0U;
    stall_ms[i] = 0U;
  }
  if (HAL_TIM_Encoder_Start(&htim2, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim5, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim1, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim4, TIM_CHANNEL_ALL) != HAL_OK) {
    fail_closed(PID2_ERROR_ENCODER_START, PID2_FAULT_MASK_ALL);
  }
}

void pid2_lab_step(uint32_t now_ms)
{
  uint32_t state, i;
  handle_request(now_ms);
  state = internal_state;
  if (state == PID2_STATE_IDLE || state == PID2_STATE_COMPLETE ||
      state == PID2_STATE_ABORTED || state == PID2_STATE_FAULT) return;
  g_pid2.elapsed_ms = elapsed(now_ms, run_started_ms);
  if (g_pid2.elapsed_ms >= PID2_RUN_TIMEOUT_MS) {
    fail_closed(PID2_ERROR_TIMEOUT, PID2_FAULT_MASK_ALL);
    return;
  }
  if (state == PID2_STATE_ZERO_GAP) {
    if (elapsed(now_ms, phase_started_ms) < active_zero_gap_ms) return;
    if (finish_after_gap != 0U) {
      safe_outputs();
      g_pid2.target_cps = 0.0f;
      set_state(PID2_STATE_COMPLETE);
      g_pid2.completed_count++;
      return;
    }
    /* Gate remains low through the zero gap; directions are prepared only
     * after the first cycle has computed and validated all four outputs. */
    safe_outputs();
    previous_raw = read_all_encoders();
    last_sample_ms = now_ms;
    phase_started_ms = now_ms;
    g_pid2.target_cps = mode_sign(active_mode) * profile_cps[profile_index];
    set_state(PID2_STATE_RUN_PROFILE);
    return;
  }
  if (state != PID2_STATE_RUN_PROFILE || !valid_mode(active_mode) ||
      g_pid2.mode != active_mode) {
    fail_closed(PID2_ERROR_STATE, PID2_FAULT_MASK_ALL);
    return;
  }
  {
    EncoderRaw current = read_all_encoders();
    int32_t delta[PID2_WHEEL_COUNT];
    float measured[PID2_WHEEL_COUNT], y[PID2_WHEEL_COUNT];
    float error[PID2_WHEEL_COUNT], ff[PID2_WHEEL_COUNT];
    float up[PID2_WHEEL_COUNT], ui[PID2_WHEEL_COUNT];
    float output[PID2_WHEEL_COUNT];
    uint32_t dt_ms = elapsed(now_ms, last_sample_ms);
    uint32_t fault_error = PID2_ERROR_NONE, fault_mask = 0U;
    float target, sign;
    if (dt_ms == 0U) {
      fail_closed(PID2_ERROR_BAD_DT, PID2_FAULT_MASK_ALL);
      return;
    }
    encoder_deltas(previous_raw, current, delta);
    previous_raw = current;
    last_sample_ms = now_ms;
    target = profile_cps[profile_index];
    sign = mode_sign(active_mode);
    g_pid2.dt_ms = dt_ms;
    compute_all_outputs(dt_ms, delta, target, sign, measured, y, error,
                        ff, up, ui, output);
    for (i = 0U; i < PID2_WHEEL_COUNT; ++i) {
      if (!isfinite(measured[i]) || !isfinite(error[i]) || !isfinite(ff[i]) ||
          !isfinite(up[i]) || !isfinite(ui[i]) || !isfinite(output[i]) ||
          output[i] < 0.0f || output[i] > (float)PID2_MAX_PWM_PERMILLE) {
        fail_closed(PID2_ERROR_INVALID_OUTPUT, 1UL << i);
        return;
      }
    }
    g_pid2.target_cps = sign * target;
    set_debug_vector(measured, error, ff, up, ui, output, delta);
    if (monitor_guards(now_ms, dt_ms, y, output, target,
                       &fault_error, &fault_mask) != 0U) {
      fail_closed(fault_error, fault_mask);
      return;
    }
    /* Prepare all compare values, start all channels with gate low, then enable. */
    start_all_pwm_or_fault(output);
    if (internal_state == PID2_STATE_FAULT) return;
    if (++log_divider >= PID2_LOG_EVERY_CYCLES) {
      log_divider = 0U;
      append_sample(now_ms, dt_ms, sign * target, measured, error,
                    ff, ui, output, delta);
      if (internal_state == PID2_STATE_FAULT) return;
    }
    if (elapsed(now_ms, phase_started_ms) >= active_plateau_ms) {
      wrong_direction_ms[0] = wrong_direction_ms[1] = 0U;
      wrong_direction_ms[2] = wrong_direction_ms[3] = 0U;
      stall_ms[0] = stall_ms[1] = 0U;
      stall_ms[2] = stall_ms[3] = 0U;
      sync_fault_ms = 0U;
      profile_index++;
      if (profile_index >= PID2_PROFILE_COUNT) {
        safe_outputs();
        reset_controller();
        finish_after_gap = 1U;
        phase_started_ms = now_ms;
        set_state(PID2_STATE_ZERO_GAP);
      } else {
        phase_started_ms = now_ms;
        g_pid2.target_cps = sign * profile_cps[profile_index];
      }
    }
  }
}
