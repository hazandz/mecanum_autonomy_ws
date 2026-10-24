#include "pid3_lab.h"

#include <math.h>
#include <stdbool.h>
#include <string.h>

#include "main.h"
#include "motor_logic.h"
#include "safety_io.h"

extern TIM_HandleTypeDef htim1, htim2, htim3, htim4, htim5;

#define PID3_INTEGRAL_LIMIT 80.0f
#define PID3_DIRECTION_THRESHOLD_CPS 100.0f
#define PID3_DIRECTION_FAULT_MS 200U
#define PID3_STALL_OUTPUT_PERMILLE 120.0f
#define PID3_STALL_GRACE_MS 400U
#define PID3_STALL_FAULT_MS 500U
#define PID3_SYNC_GRACE_MS 500U
#define PID3_SYNC_WARNING_CPS 150.0f
#define PID3_SYNC_FAULT_CPS 300.0f
#define PID3_SYNC_FAULT_MS 500U
#define PID3_RUN_TIMEOUT_MS 6000U
#define PID3_MAX_CONTROL_DT_MS 100U
#define PID3_COMPARE_SCALE 1000ULL

typedef struct { uint32_t fl, fr, rl, rr; } EncoderRaw;
typedef struct { float u0, kv; } Pid3Feedforward;

/* Validated PID-2A ALL_FORWARD coefficients, indexed [FL, FR, RL, RR]. */
static const Pid3Feedforward forward_feedforward[PID3_WHEEL_COUNT] = {
  {40.330665f, 0.217819026f},
  {32.415574f, 0.231811480f},
  {61.698998f, 0.212679580f},
  {37.521999f, 0.223981830f}
};
static const uint32_t pwm_channel[PID3_WHEEL_COUNT] = {
  TIM_CHANNEL_4, TIM_CHANNEL_3, TIM_CHANNEL_1, TIM_CHANNEL_2
};
static const MotorWheel motor_wheel[PID3_WHEEL_COUNT] = {
  MOTOR_WHEEL_FL, MOTOR_WHEEL_FR, MOTOR_WHEEL_RL, MOTOR_WHEEL_RR
};

_Static_assert(sizeof(Pid3LabSample) * PID3_LOG_CAPACITY <= 32768U,
               "PID3 RAM log exceeds 32 KiB budget");

volatile Pid3LabControl g_pid3;
Pid3LabSample g_pid3_log[PID3_LOG_CAPACITY];

static EncoderRaw previous_raw;
static uint32_t internal_state, last_sample_ms, arm_started_ms;
static uint32_t run_started_ms, hold_started_ms, log_used, log_divider;
static uint32_t pwm_started, wrong_direction_ms[PID3_WHEEL_COUNT];
static uint32_t stall_ms[PID3_WHEEL_COUNT], sync_fault_ms;
static float integral_permille[PID3_WHEEL_COUNT];

static uint32_t elapsed(uint32_t now, uint32_t then) { return now - then; }

static float target_cps_for_run_elapsed(uint32_t run_elapsed_ms)
{
  if (run_elapsed_ms >= PID3_RAMP_DURATION_MS)
    return PID3_TARGET_CPS;

  return PID3_TARGET_CPS *
         ((float)run_elapsed_ms / (float)PID3_RAMP_DURATION_MS);
}

static int32_t delta32(uint32_t old, uint32_t now)
{
  uint32_t d = now - old;
  return d <= 0x7fffffffU ? (int32_t)d :
         (int32_t)((int64_t)d - 4294967296LL);
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
  delta[0] = delta32(old.fl, now.fl);
  delta[1] = delta32(old.fr, now.fr);
  delta[2] = delta16(old.rl, now.rl);
  delta[3] = delta16(old.rr, now.rr);
}

static void set_state(uint32_t state)
{
  internal_state = state;
  g_pid3.state = state;
}

static void safe_outputs(void)
{
  safety_io_force_motor_disabled();
  motor_logic_stop_all();
  pwm_started = 0U;
  g_pid3.fl_u_output = 0.0f;
  g_pid3.fr_u_output = 0.0f;
  g_pid3.rl_u_output = 0.0f;
  g_pid3.rr_u_output = 0.0f;
}

static void reset_controller(void)
{
  uint32_t i;
  for (i = 0U; i < PID3_WHEEL_COUNT; ++i) {
    integral_permille[i] = 0.0f;
    wrong_direction_ms[i] = 0U;
    stall_ms[i] = 0U;
  }
  sync_fault_ms = 0U;
  g_pid3.target_cps = 0.0f;
  g_pid3.dt_ms = 0U;
  g_pid3.fl_u_i = g_pid3.fr_u_i = 0.0f;
  g_pid3.rl_u_i = g_pid3.rr_u_i = 0.0f;
  g_pid3.sync_spread_cps = 0.0f;
  g_pid3.sync_warning = 0U;
}

static void fail_closed(uint32_t error, uint32_t wheel_mask)
{
  safe_outputs();
  reset_controller();
  g_pid3.fault_wheel_mask = wheel_mask & PID3_FAULT_MASK_ALL;
  g_pid3.last_error = error;
  g_pid3.arm_magic = 0U;
  set_state(PID3_STATE_FAULT);
}

static void set_debug_vector(const float measured[4], const float error[4],
                             const float ff[4], const float ui[4],
                             const float output[4], const int32_t delta[4])
{
  g_pid3.fl_measured_cps = measured[0];
  g_pid3.fr_measured_cps = measured[1];
  g_pid3.rl_measured_cps = measured[2];
  g_pid3.rr_measured_cps = measured[3];
  g_pid3.fl_error_cps = error[0];
  g_pid3.fr_error_cps = error[1];
  g_pid3.rl_error_cps = error[2];
  g_pid3.rr_error_cps = error[3];
  g_pid3.fl_u_ff = ff[0];
  g_pid3.fr_u_ff = ff[1];
  g_pid3.rl_u_ff = ff[2];
  g_pid3.rr_u_ff = ff[3];
  g_pid3.fl_u_i = ui[0];
  g_pid3.fr_u_i = ui[1];
  g_pid3.rl_u_i = ui[2];
  g_pid3.rr_u_i = ui[3];
  g_pid3.fl_u_output = output[0];
  g_pid3.fr_u_output = output[1];
  g_pid3.rl_u_output = output[2];
  g_pid3.rr_u_output = output[3];
  g_pid3.fl_encoder_delta = delta[0];
  g_pid3.fr_encoder_delta = delta[1];
  g_pid3.rl_encoder_delta = delta[2];
  g_pid3.rr_encoder_delta = delta[3];
}

static void clear_log_request(void)
{
  uint32_t i;
  safe_outputs();
  reset_controller();
  memset(g_pid3_log, 0, sizeof(g_pid3_log));
  log_used = 0U;
  log_divider = 0U;
  g_pid3.request = PID3_REQUEST_NONE;
  g_pid3.arm_magic = 0U;
  g_pid3.arm_elapsed_ms = 0U;
  g_pid3.arm_remaining_ms = g_pid3.arm_delay_ms;
  g_pid3.run_elapsed_ms = 0U;
  g_pid3.log_count = 0U;
  g_pid3.log_overflow = 0U;
  g_pid3.completed_count = 0U;
  g_pid3.last_error = PID3_ERROR_NONE;
  g_pid3.fault_wheel_mask = 0U;
  g_pid3.total_delta_fl = 0;
  g_pid3.total_delta_fr = 0;
  g_pid3.total_delta_rl = 0;
  g_pid3.total_delta_rr = 0;
  g_pid3.fl_measured_cps = g_pid3.fr_measured_cps = 0.0f;
  g_pid3.rl_measured_cps = g_pid3.rr_measured_cps = 0.0f;
  g_pid3.fl_error_cps = g_pid3.fr_error_cps = 0.0f;
  g_pid3.rl_error_cps = g_pid3.rr_error_cps = 0.0f;
  g_pid3.fl_encoder_delta = g_pid3.fr_encoder_delta = 0;
  g_pid3.rl_encoder_delta = g_pid3.rr_encoder_delta = 0;
  for (i = 0U; i < PID3_WHEEL_COUNT; ++i) {
    wrong_direction_ms[i] = 0U;
    stall_ms[i] = 0U;
  }
  sync_fault_ms = 0U;
  set_state(PID3_STATE_IDLE);
}

static bool parameters_are_frozen(void)
{
  return g_pid3.kp == PID3_DEFAULT_KP && g_pid3.ki == PID3_DEFAULT_KI &&
         g_pid3.arm_delay_ms == PID3_DEFAULT_ARM_DELAY_MS &&
         g_pid3.run_duration_ms == PID3_DEFAULT_RUN_DURATION_MS &&
         g_pid3.stop_hold_ms == PID3_DEFAULT_STOP_HOLD_MS;
}

static void handle_request(uint32_t now_ms)
{
  uint32_t request = g_pid3.request;
  if (request == PID3_REQUEST_ABORT) {
    g_pid3.request = PID3_REQUEST_NONE;
    safe_outputs();
    reset_controller();
    g_pid3.arm_magic = 0U;
    g_pid3.last_error = PID3_ERROR_NONE;
    g_pid3.fault_wheel_mask = 0U;
    set_state(PID3_STATE_ABORTED);
    return;
  }
  if (request == PID3_REQUEST_CLEAR_LOG) {
    clear_log_request();
    return;
  }
  if (request == PID3_REQUEST_NONE) return;
  g_pid3.request = PID3_REQUEST_NONE;
  if (request != PID3_REQUEST_ARM_AUTORUN) {
    fail_closed(PID3_ERROR_INVALID_REQUEST, PID3_FAULT_MASK_ALL);
    return;
  }
  if (internal_state != PID3_STATE_IDLE ||
      g_pid3.arm_magic != PID3_ARM_MAGIC || !parameters_are_frozen()) {
    g_pid3.arm_magic = 0U;
    safe_outputs();
    reset_controller();
    g_pid3.last_error = PID3_ERROR_INVALID_ARM;
    g_pid3.fault_wheel_mask = 0U;
    set_state(PID3_STATE_FAULT);
    return;
  }
  g_pid3.arm_magic = 0U; /* Consume the one-shot ARM token immediately. */
  safe_outputs();
  reset_controller();
  g_pid3.last_error = PID3_ERROR_NONE;
  g_pid3.fault_wheel_mask = 0U;
  g_pid3.arm_elapsed_ms = 0U;
  g_pid3.arm_remaining_ms = PID3_DEFAULT_ARM_DELAY_MS;
  g_pid3.run_elapsed_ms = 0U;
  g_pid3.total_delta_fl = 0;
  g_pid3.total_delta_fr = 0;
  g_pid3.total_delta_rl = 0;
  g_pid3.total_delta_rr = 0;
  arm_started_ms = now_ms;
  set_state(PID3_STATE_ARMED_DELAY);
}

static void start_all_pwm_or_fault(const float output[4])
{
  uint32_t i, arr = __HAL_TIM_GET_AUTORELOAD(&htim3);
  uint32_t compare[PID3_WHEEL_COUNT];
  for (i = 0U; i < PID3_WHEEL_COUNT; ++i) {
    if (!isfinite(output[i]) || output[i] < 0.0f ||
        output[i] > (float)PID3_MAX_PWM_PERMILLE) {
      fail_closed(PID3_ERROR_INVALID_OUTPUT, 1UL << i);
      return;
    }
    compare[i] = (uint32_t)(((uint64_t)arr + 1ULL) *
                 (uint32_t)(output[i] + 0.5f) / PID3_COMPARE_SCALE);
    if (output[i] > 0.0f && compare[i] == 0U) compare[i] = 1U;
  }
  if (pwm_started == 0U) {
    /* Reassert safe gate/output state immediately before direction setup. */
    safety_io_force_motor_disabled();
    motor_logic_stop_all();
    for (i = 0U; i < PID3_WHEEL_COUNT; ++i)
      motor_logic_set_direction(motor_wheel[i], MOTOR_DIRECTION_FORWARD);
  }
  for (i = 0U; i < PID3_WHEEL_COUNT; ++i)
    __HAL_TIM_SET_COMPARE(&htim3, pwm_channel[i], compare[i]);
  if (pwm_started == 0U) {
    for (i = 0U; i < PID3_WHEEL_COUNT; ++i) {
      if (HAL_TIM_PWM_Start(&htim3, pwm_channel[i]) != HAL_OK) {
        fail_closed(PID3_ERROR_PWM_START, 1UL << i);
        return;
      }
    }
    pwm_started = 1U;
    HAL_GPIO_WritePin(MCU_MOTOR_ENABLE_GPIO_Port, MCU_MOTOR_ENABLE_Pin,
                     GPIO_PIN_SET);
  }
}

static uint32_t monitor_guards(uint32_t now_ms, uint32_t dt_ms,
                               const float measured[4], const float output[4],
                               uint32_t *error, uint32_t *fault_mask)
{
  uint32_t i, min_i = 0U, max_i = 0U;
  float min_speed = measured[0], max_speed = measured[0];
  bool grace = elapsed(now_ms, run_started_ms) >= PID3_SYNC_GRACE_MS;
  for (i = 0U; i < PID3_WHEEL_COUNT; ++i) {
    uint32_t bit = 1UL << i;
    if (measured[i] < -PID3_DIRECTION_THRESHOLD_CPS)
      wrong_direction_ms[i] += dt_ms;
    else
      wrong_direction_ms[i] = 0U;
    if (wrong_direction_ms[i] >= PID3_DIRECTION_FAULT_MS) {
      *error = PID3_ERROR_WRONG_DIRECTION;
      *fault_mask = bit;
      return 1U;
    }
    if (grace && output[i] >= PID3_STALL_OUTPUT_PERMILLE &&
        fabsf(measured[i]) < PID3_DIRECTION_THRESHOLD_CPS)
      stall_ms[i] += dt_ms;
    else
      stall_ms[i] = 0U;
    if (stall_ms[i] >= PID3_STALL_FAULT_MS) {
      *error = PID3_ERROR_STALL;
      *fault_mask = bit;
      return 1U;
    }
    if (measured[i] < min_speed) { min_speed = measured[i]; min_i = i; }
    if (measured[i] > max_speed) { max_speed = measured[i]; max_i = i; }
  }
  g_pid3.sync_spread_cps = max_speed - min_speed;
  g_pid3.sync_warning = (grace && g_pid3.sync_spread_cps > PID3_SYNC_WARNING_CPS) ? 1U : 0U;
  if (grace && g_pid3.sync_spread_cps > PID3_SYNC_FAULT_CPS)
    sync_fault_ms += dt_ms;
  else
    sync_fault_ms = 0U;
  if (sync_fault_ms >= PID3_SYNC_FAULT_MS) {
    *error = PID3_ERROR_SYNC;
    *fault_mask = (1UL << min_i) | (1UL << max_i);
    return 1U;
  }
  return 0U;
}

static void compute_outputs(uint32_t dt_ms, float target_cps,
                            const int32_t delta[4], float measured[4],
                            float error[4], float ff[4], float up[4],
                            float ui[4], float output[4])
{
  uint32_t i;
  float dt_seconds = (float)dt_ms / 1000.0f;
  for (i = 0U; i < PID3_WHEEL_COUNT; ++i) {
    float candidate, raw;
    measured[i] = (float)delta[i] * 1000.0f / (float)dt_ms;
    error[i] = target_cps - measured[i];
    ff[i] = forward_feedforward[i].u0 +
            forward_feedforward[i].kv * target_cps;
    up[i] = PID3_DEFAULT_KP * error[i];
    candidate = integral_permille[i] + PID3_DEFAULT_KI * error[i] * dt_seconds;
    if (candidate > PID3_INTEGRAL_LIMIT) candidate = PID3_INTEGRAL_LIMIT;
    if (candidate < -PID3_INTEGRAL_LIMIT) candidate = -PID3_INTEGRAL_LIMIT;
    raw = ff[i] + up[i] + candidate;
    if (!((raw >= (float)PID3_MAX_PWM_PERMILLE && error[i] > 0.0f) ||
          (raw <= 0.0f && error[i] < 0.0f)))
      integral_permille[i] = candidate;
    ui[i] = integral_permille[i];
    raw = ff[i] + up[i] + ui[i];
    if (raw < 0.0f) raw = 0.0f;
    if (raw > (float)PID3_MAX_PWM_PERMILLE) raw = (float)PID3_MAX_PWM_PERMILLE;
    output[i] = raw;
  }
}

static void append_sample(uint32_t now_ms, uint32_t dt_ms, float target_cps,
                          const float measured[4], const float error[4],
                          const float ff[4], const float ui[4],
                          const float output[4], const int32_t delta[4])
{
  Pid3LabSample *sample;
  uint32_t i;
  if (log_used >= PID3_LOG_CAPACITY) {
    g_pid3.log_overflow = 1U;
    fail_closed(PID3_ERROR_LOG_OVERFLOW, PID3_FAULT_MASK_ALL);
    return;
  }
  sample = &g_pid3_log[log_used++];
  sample->timestamp_ms = now_ms;
  sample->state = PID3_STATE_RUN;
  sample->target_cps = target_cps;
  sample->dt_ms = dt_ms;
  for (i = 0U; i < PID3_WHEEL_COUNT; ++i) {
    sample->measured_cps[i] = measured[i];
    sample->error_cps[i] = error[i];
    sample->u_ff_permille[i] = ff[i];
    sample->u_i_permille[i] = ui[i];
    sample->u_output_permille[i] = output[i];
    sample->encoder_delta[i] = delta[i];
  }
  sample->sync_spread_cps = g_pid3.sync_spread_cps;
  sample->sync_warning = g_pid3.sync_warning;
  g_pid3.log_count = log_used;
}

void pid3_lab_init(void)
{
  safe_outputs();
  memset(g_pid3_log, 0, sizeof(g_pid3_log));
  log_used = 0U;
  log_divider = 0U;
  internal_state = PID3_STATE_IDLE;
  pwm_started = 0U;
  g_pid3.request = PID3_REQUEST_NONE;
  g_pid3.state = PID3_STATE_IDLE;
  g_pid3.arm_magic = 0U;
  g_pid3.kp = PID3_DEFAULT_KP;
  g_pid3.ki = PID3_DEFAULT_KI;
  g_pid3.arm_delay_ms = PID3_DEFAULT_ARM_DELAY_MS;
  g_pid3.run_duration_ms = PID3_DEFAULT_RUN_DURATION_MS;
  g_pid3.stop_hold_ms = PID3_DEFAULT_STOP_HOLD_MS;
  g_pid3.arm_elapsed_ms = 0U;
  g_pid3.arm_remaining_ms = PID3_DEFAULT_ARM_DELAY_MS;
  g_pid3.run_elapsed_ms = 0U;
  g_pid3.last_error = PID3_ERROR_NONE;
  g_pid3.fault_wheel_mask = 0U;
  g_pid3.log_count = 0U;
  g_pid3.log_overflow = 0U;
  g_pid3.completed_count = 0U;
  g_pid3.total_delta_fl = 0;
  g_pid3.total_delta_fr = 0;
  g_pid3.total_delta_rl = 0;
  g_pid3.total_delta_rr = 0;
  g_pid3.fl_measured_cps = g_pid3.fr_measured_cps = 0.0f;
  g_pid3.rl_measured_cps = g_pid3.rr_measured_cps = 0.0f;
  g_pid3.fl_error_cps = g_pid3.fr_error_cps = 0.0f;
  g_pid3.rl_error_cps = g_pid3.rr_error_cps = 0.0f;
  g_pid3.fl_u_ff = g_pid3.fr_u_ff = 0.0f;
  g_pid3.rl_u_ff = g_pid3.rr_u_ff = 0.0f;
  g_pid3.fl_encoder_delta = g_pid3.fr_encoder_delta = 0;
  g_pid3.rl_encoder_delta = g_pid3.rr_encoder_delta = 0;
  reset_controller();
  if (HAL_TIM_Encoder_Start(&htim2, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim5, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim1, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim4, TIM_CHANNEL_ALL) != HAL_OK)
    fail_closed(PID3_ERROR_ENCODER_START, PID3_FAULT_MASK_ALL);
}

void pid3_lab_step(uint32_t now_ms)
{
  uint32_t state;
  handle_request(now_ms);
  state = internal_state;
  if (g_pid3.state != internal_state) {
    fail_closed(PID3_ERROR_STATE, PID3_FAULT_MASK_ALL);
    return;
  }
  if (state == PID3_STATE_IDLE || state == PID3_STATE_COMPLETE ||
      state == PID3_STATE_ABORTED || state == PID3_STATE_FAULT) return;

  if (state == PID3_STATE_ARMED_DELAY) {
    uint32_t arm_elapsed = elapsed(now_ms, arm_started_ms);
    g_pid3.arm_elapsed_ms = arm_elapsed;
    g_pid3.arm_remaining_ms = arm_elapsed >= PID3_DEFAULT_ARM_DELAY_MS ? 0U :
                              PID3_DEFAULT_ARM_DELAY_MS - arm_elapsed;
    safe_outputs();
    reset_controller();
    if (arm_elapsed >= PID3_DEFAULT_ARM_DELAY_MS) {
      previous_raw = read_all_encoders();
      last_sample_ms = now_ms;
      run_started_ms = now_ms;
      g_pid3.run_elapsed_ms = 0U;
      log_divider = 0U;
      set_state(PID3_STATE_RUN);
    }
    return;
  }

  if (state == PID3_STATE_STOP_HOLD) {
    safe_outputs();
    reset_controller();
    if (elapsed(now_ms, hold_started_ms) >= PID3_DEFAULT_STOP_HOLD_MS) {
      g_pid3.target_cps = 0.0f;
      g_pid3.completed_count++;
      set_state(PID3_STATE_COMPLETE);
    }
    return;
  }
  if (state != PID3_STATE_RUN) {
    fail_closed(PID3_ERROR_STATE, PID3_FAULT_MASK_ALL);
    return;
  }

  g_pid3.run_elapsed_ms = elapsed(now_ms, run_started_ms);
  if (g_pid3.run_elapsed_ms >= PID3_RUN_TIMEOUT_MS) {
    fail_closed(PID3_ERROR_TIMEOUT, PID3_FAULT_MASK_ALL);
    return;
  }
  if (g_pid3.run_elapsed_ms >= PID3_DEFAULT_RUN_DURATION_MS) {
    EncoderRaw final_raw = read_all_encoders();
    int32_t final_delta[PID3_WHEEL_COUNT];
    encoder_deltas(previous_raw, final_raw, final_delta);
    g_pid3.total_delta_fl += final_delta[0];
    g_pid3.total_delta_fr += final_delta[1];
    g_pid3.total_delta_rl += final_delta[2];
    g_pid3.total_delta_rr += final_delta[3];
    previous_raw = final_raw;
    safe_outputs();
    reset_controller();
    g_pid3.target_cps = 0.0f;
    hold_started_ms = now_ms;
    set_state(PID3_STATE_STOP_HOLD);
    return;
  }

  float current_target_cps =
      target_cps_for_run_elapsed(g_pid3.run_elapsed_ms);
  g_pid3.target_cps = current_target_cps;
  {
    EncoderRaw current = read_all_encoders();
    int32_t delta[PID3_WHEEL_COUNT];
    float measured[PID3_WHEEL_COUNT], error[PID3_WHEEL_COUNT];
    float ff[PID3_WHEEL_COUNT], up[PID3_WHEEL_COUNT];
    float ui[PID3_WHEEL_COUNT], output[PID3_WHEEL_COUNT];
    uint32_t dt_ms = elapsed(now_ms, last_sample_ms);
    uint32_t fault_error = PID3_ERROR_NONE, fault_mask = 0U;
    uint32_t i;
    if (dt_ms == 0U || dt_ms > PID3_MAX_CONTROL_DT_MS) {
      fail_closed(PID3_ERROR_BAD_DT, PID3_FAULT_MASK_ALL);
      return;
    }
    encoder_deltas(previous_raw, current, delta);
    previous_raw = current;
    last_sample_ms = now_ms;
    g_pid3.total_delta_fl += delta[0];
    g_pid3.total_delta_fr += delta[1];
    g_pid3.total_delta_rl += delta[2];
    g_pid3.total_delta_rr += delta[3];
    g_pid3.dt_ms = dt_ms;
    compute_outputs(dt_ms, current_target_cps, delta, measured, error,
                    ff, up, ui, output);
    for (i = 0U; i < PID3_WHEEL_COUNT; ++i) {
      if (!isfinite(measured[i]) || !isfinite(error[i]) || !isfinite(ff[i]) ||
          !isfinite(up[i]) || !isfinite(ui[i]) || !isfinite(output[i]) ||
          output[i] < 0.0f || output[i] > (float)PID3_MAX_PWM_PERMILLE) {
        fail_closed(PID3_ERROR_INVALID_OUTPUT, 1UL << i);
        return;
      }
    }
    set_debug_vector(measured, error, ff, ui, output, delta);
    if (monitor_guards(now_ms, dt_ms, measured, output,
                       &fault_error, &fault_mask) != 0U) {
      fail_closed(fault_error, fault_mask);
      return;
    }
    start_all_pwm_or_fault(output);
    if (internal_state == PID3_STATE_FAULT) return;
    if (++log_divider >= PID3_LOG_EVERY_CYCLES) {
      log_divider = 0U;
      append_sample(now_ms, dt_ms, current_target_cps, measured, error,
                    ff, ui, output, delta);
      if (internal_state == PID3_STATE_FAULT) return;
    }
  }
}
