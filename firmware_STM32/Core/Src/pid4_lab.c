#include "pid4_lab.h"

#include <math.h>
#include <stdbool.h>
#include <string.h>

#include "main.h"
#include "motor_logic.h"
#include "safety_io.h"

extern TIM_HandleTypeDef htim1, htim2, htim3, htim4, htim5;

#define PID4_INTEGRAL_LIMIT 80.0f
#define PID4_DIRECTION_THRESHOLD_CPS 100.0f
#define PID4_DIRECTION_FAULT_MS 200U
#define PID4_STALL_OUTPUT_PERMILLE 120.0f
#define PID4_STALL_GRACE_MS 400U
#define PID4_STALL_FAULT_MS 500U
#define PID4_SYNC_GRACE_MS 500U
#define PID4_SYNC_WARNING_CPS 150.0f
#define PID4_SYNC_FAULT_CPS 300.0f
#define PID4_SYNC_FAULT_MS 500U
#define PID4_SYNC_TARGET_TOLERANCE_CPS 1.0f
#define PID4_RUN_TIMEOUT_MS 6000U
#define PID4_MAX_CONTROL_DT_MS 100U
#define PID4_COMPARE_SCALE 1000ULL

typedef struct { uint32_t fl, fr, rl, rr; } EncoderRaw;
typedef struct { float u0, kv; } Pid4Feedforward;

/* Validated coefficients, indexed [wheel][0=forward, 1=reverse]. */
static const Pid4Feedforward feedforward[PID4_WHEEL_COUNT][2] = {
  {
    {40.330665f, 0.217819026f},
    {36.253577f, 0.225076821f}
  },
  {
    {32.415574f, 0.231811480f},
    {34.233335f, 0.226312521f}
  },
  {
    {61.698998f, 0.212679580f},
    {54.760209f, 0.223609266f}
  },
  {
    {37.521999f, 0.223981830f},
    {32.707200f, 0.229221684f}
  }
};
static const uint32_t pwm_channel[PID4_WHEEL_COUNT] = {
  TIM_CHANNEL_4, TIM_CHANNEL_3, TIM_CHANNEL_1, TIM_CHANNEL_2
};
static const MotorWheel motor_wheel[PID4_WHEEL_COUNT] = {
  MOTOR_WHEEL_FL, MOTOR_WHEEL_FR, MOTOR_WHEEL_RL, MOTOR_WHEEL_RR
};

_Static_assert(sizeof(Pid4LabSample) == 132U,
               "PID4 sample layout must remain 132 bytes");
_Static_assert(sizeof(Pid4LabSample) * PID4_LOG_CAPACITY <= 32768U,
               "PID4 RAM log exceeds 32 KiB budget");

volatile Pid4LabControl g_pid4;
Pid4LabSample g_pid4_log[PID4_LOG_CAPACITY];

static EncoderRaw previous_raw;
static uint32_t internal_state, last_sample_ms, arm_started_ms;
static uint32_t run_started_ms, hold_started_ms, log_used, log_divider;
static uint32_t pwm_started;
static uint32_t wrong_direction_ms[PID4_WHEEL_COUNT];
static uint32_t stall_ms[PID4_WHEEL_COUNT], sync_fault_ms;
static float integral_permille[PID4_WHEEL_COUNT];

static uint32_t elapsed(uint32_t now, uint32_t then)
{
  return now - then;
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
  g_pid4.state = state;
}

static void safe_outputs(void)
{
  safety_io_force_motor_disabled();
  motor_logic_stop_all();
  pwm_started = 0U;
  g_pid4.u_output[0] = 0.0f;
  g_pid4.u_output[1] = 0.0f;
  g_pid4.u_output[2] = 0.0f;
  g_pid4.u_output[3] = 0.0f;
}

static void reset_controller(void)
{
  uint32_t i;
  for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
    integral_permille[i] = 0.0f;
    wrong_direction_ms[i] = 0U;
    stall_ms[i] = 0U;
    g_pid4.u_i[i] = 0.0f;
  }
  sync_fault_ms = 0U;
  g_pid4.dt_ms = 0U;
  g_pid4.sync_spread_cps = 0.0f;
  g_pid4.sync_warning = 0U;
}

static void fail_closed(uint32_t error, uint32_t wheel_mask)
{
  safe_outputs();
  reset_controller();
  g_pid4.fault_wheel_mask = wheel_mask & PID4_FAULT_MASK_ALL;
  g_pid4.last_error = error;
  g_pid4.arm_magic = 0U;
  set_state(PID4_STATE_FAULT);
}

static void set_debug_vectors(const float measured[4], const float error[4],
                              const float ff[4],
                              const float ui[4], const float output[4],
                              const int32_t delta[4])
{
  uint32_t i;
  for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
    g_pid4.measured_cps[i] = measured[i];
    g_pid4.error_cps[i] = error[i];
    g_pid4.u_ff[i] = ff[i];
    g_pid4.u_i[i] = ui[i];
    g_pid4.u_output[i] = output[i];
    g_pid4.encoder_delta[i] = delta[i];
  }
}

static void clear_log_request(void)
{
  uint32_t i;
  safe_outputs();
  reset_controller();
  memset(g_pid4_log, 0, sizeof(g_pid4_log));
  log_used = 0U;
  log_divider = 0U;
  g_pid4.request = PID4_REQUEST_NONE;
  g_pid4.arm_magic = 0U;
  g_pid4.arm_elapsed_ms = 0U;
  g_pid4.arm_remaining_ms = PID4_DEFAULT_ARM_DELAY_MS;
  g_pid4.elapsed_ms = 0U;
  g_pid4.log_count = 0U;
  g_pid4.log_overflow = 0U;
  g_pid4.completed_count = 0U;
  g_pid4.last_error = PID4_ERROR_NONE;
  g_pid4.fault_wheel_mask = 0U;
  g_pid4.sync_guard_enabled = 0U;
  g_pid4.total_delta_fl = 0;
  g_pid4.total_delta_fr = 0;
  g_pid4.total_delta_rl = 0;
  g_pid4.total_delta_rr = 0;
  for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
    g_pid4.active_target_cps[i] = 0.0f;
    g_pid4.measured_cps[i] = 0.0f;
    g_pid4.error_cps[i] = 0.0f;
    g_pid4.u_ff[i] = 0.0f;
    g_pid4.u_output[i] = 0.0f;
    g_pid4.encoder_delta[i] = 0;
  }
  set_state(PID4_STATE_IDLE);
}

static bool snapshot_targets(float snapshot[PID4_WHEEL_COUNT],
                             uint32_t *invalid_mask)
{
  uint32_t i;
  *invalid_mask = 0U;
  for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
    float target = g_pid4.requested_target_cps[i];
    if (!isfinite(target) || fabsf(target) > PID4_MAX_TARGET_CPS) {
      *invalid_mask |= 1UL << i;
    } else {
      snapshot[i] = target;
    }
  }
  return *invalid_mask == 0U;
}

static uint32_t sync_targets_are_comparable(void)
{
  uint32_t i;
  float reference;
  if (g_pid4.active_target_cps[0] == 0.0f ||
      g_pid4.active_target_cps[1] == 0.0f ||
      g_pid4.active_target_cps[2] == 0.0f ||
      g_pid4.active_target_cps[3] == 0.0f)
    return 0U;
  reference = fabsf(g_pid4.active_target_cps[0]);
  for (i = 1U; i < PID4_WHEEL_COUNT; ++i) {
    if (fabsf(fabsf(g_pid4.active_target_cps[i]) - reference) >
        PID4_SYNC_TARGET_TOLERANCE_CPS)
      return 0U;
  }
  return 1U;
}

static void handle_request(uint32_t now_ms)
{
  uint32_t request = g_pid4.request;
  if (request == PID4_REQUEST_ABORT) {
    g_pid4.request = PID4_REQUEST_NONE;
    safe_outputs();
    reset_controller();
    g_pid4.arm_magic = 0U;
    g_pid4.last_error = PID4_ERROR_NONE;
    g_pid4.fault_wheel_mask = 0U;
    set_state(PID4_STATE_ABORTED);
    return;
  }
  if (request == PID4_REQUEST_CLEAR_LOG) {
    clear_log_request();
    return;
  }
  if (request == PID4_REQUEST_NONE) return;
  g_pid4.request = PID4_REQUEST_NONE;
  if (request != PID4_REQUEST_ARM_AUTORUN) {
    fail_closed(PID4_ERROR_INVALID_REQUEST, PID4_FAULT_MASK_ALL);
    return;
  }
  if (internal_state != PID4_STATE_IDLE ||
      g_pid4.arm_magic != PID4_ARM_MAGIC) {
    g_pid4.arm_magic = 0U;
    g_pid4.last_error = PID4_ERROR_INVALID_ARM;
    fail_closed(PID4_ERROR_INVALID_ARM, 0U);
    return;
  }
  {
    float snapshot[PID4_WHEEL_COUNT];
    uint32_t invalid_mask;
    if (!snapshot_targets(snapshot, &invalid_mask)) {
      g_pid4.arm_magic = 0U;
      fail_closed(PID4_ERROR_INVALID_TARGET, invalid_mask);
      return;
    }
    g_pid4.arm_magic = 0U; /* Consume the one-shot PID4 token immediately. */
    safe_outputs();
    reset_controller();
    g_pid4.last_error = PID4_ERROR_NONE;
    g_pid4.fault_wheel_mask = 0U;
    g_pid4.arm_elapsed_ms = 0U;
    g_pid4.arm_remaining_ms = PID4_DEFAULT_ARM_DELAY_MS;
    g_pid4.elapsed_ms = 0U;
    g_pid4.total_delta_fl = 0;
    g_pid4.total_delta_fr = 0;
    g_pid4.total_delta_rl = 0;
    g_pid4.total_delta_rr = 0;
    for (uint32_t i = 0U; i < PID4_WHEEL_COUNT; ++i)
      g_pid4.active_target_cps[i] = snapshot[i];
    g_pid4.sync_guard_enabled = sync_targets_are_comparable();
    arm_started_ms = now_ms;
    set_state(PID4_STATE_ARMED_DELAY);
  }
}

static void start_outputs_or_fault(const float output[4])
{
  uint32_t i, arr = __HAL_TIM_GET_AUTORELOAD(&htim3);
  uint32_t compare[PID4_WHEEL_COUNT];
  bool any_target = false;
  for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
    float target = g_pid4.active_target_cps[i];
    if (!isfinite(target) || fabsf(target) > PID4_MAX_TARGET_CPS ||
        !isfinite(output[i]) || output[i] < 0.0f ||
        output[i] > (float)PID4_MAX_PWM_PERMILLE) {
      fail_closed(PID4_ERROR_INVALID_OUTPUT, 1UL << i);
      return;
    }
    if (target != 0.0f) any_target = true;
    compare[i] = (uint32_t)(((uint64_t)arr + 1ULL) *
                 (uint32_t)(output[i] + 0.5f) / PID4_COMPARE_SCALE);
    if (output[i] > 0.0f && compare[i] == 0U) compare[i] = 1U;
  }

  if (!any_target) {
    safe_outputs();
    for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
      motor_logic_set_direction(motor_wheel[i], MOTOR_DIRECTION_FORWARD);
      __HAL_TIM_SET_COMPARE(&htim3, pwm_channel[i], 0U);
    }
    return;
  }

  if (pwm_started == 0U) {
    safety_io_force_motor_disabled();
    motor_logic_stop_all();
    for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
      MotorDirection direction = g_pid4.active_target_cps[i] < 0.0f ?
          MOTOR_DIRECTION_REVERSE : MOTOR_DIRECTION_FORWARD;
      motor_logic_set_direction(motor_wheel[i], direction);
    }
  }
  for (i = 0U; i < PID4_WHEEL_COUNT; ++i)
    __HAL_TIM_SET_COMPARE(&htim3, pwm_channel[i], compare[i]);
  if (pwm_started == 0U) {
    for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
      if (HAL_TIM_PWM_Start(&htim3, pwm_channel[i]) != HAL_OK) {
        fail_closed(PID4_ERROR_PWM_START, 1UL << i);
        return;
      }
    }
    pwm_started = 1U;
    HAL_GPIO_WritePin(MCU_MOTOR_ENABLE_GPIO_Port, MCU_MOTOR_ENABLE_Pin,
                     GPIO_PIN_SET);
  }
}

static void compute_outputs(uint32_t dt_ms,
                            const volatile float target[4],
                            const float ramped_magnitude[4],
                            const int32_t delta[4], float measured[4],
                            float error[4], float ff[4], float up[4],
                            float ui[4], float output[4])
{
  uint32_t i;
  float dt_seconds = (float)dt_ms / 1000.0f;
  for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
    float candidate, raw, direction_sign, y;
    uint32_t direction_index;
    const Pid4Feedforward *coeff;
    measured[i] = (float)delta[i] * 1000.0f / (float)dt_ms;
    ff[i] = 0.0f;
    up[i] = 0.0f;
    ui[i] = 0.0f;
    output[i] = 0.0f;
    if (target[i] == 0.0f) {
      integral_permille[i] = 0.0f;
      error[i] = 0.0f;
      continue;
    }

    direction_sign = target[i] > 0.0f ? 1.0f : -1.0f;
    y = direction_sign * measured[i];
    error[i] = ramped_magnitude[i] - y;
    direction_index = target[i] > 0.0f ? 0U : 1U;
    coeff = &feedforward[i][direction_index];
    if (ramped_magnitude[i] > 0.0f)
      ff[i] = coeff->u0 + coeff->kv * ramped_magnitude[i];
    up[i] = PID4_DEFAULT_KP * error[i];
    candidate = integral_permille[i] +
                PID4_DEFAULT_KI * error[i] * dt_seconds;
    if (candidate > PID4_INTEGRAL_LIMIT) candidate = PID4_INTEGRAL_LIMIT;
    if (candidate < -PID4_INTEGRAL_LIMIT) candidate = -PID4_INTEGRAL_LIMIT;
    raw = ff[i] + up[i] + candidate;
    if (!((raw >= (float)PID4_MAX_PWM_PERMILLE && error[i] > 0.0f) ||
          (raw <= 0.0f && error[i] < 0.0f)))
      integral_permille[i] = candidate;
    ui[i] = integral_permille[i];
    raw = ff[i] + up[i] + ui[i];
    if (raw < 0.0f) raw = 0.0f;
    if (raw > (float)PID4_MAX_PWM_PERMILLE)
      raw = (float)PID4_MAX_PWM_PERMILLE;
    output[i] = raw;
  }
}

static uint32_t monitor_guards(uint32_t run_elapsed_ms, uint32_t dt_ms,
                               const float measured[4],
                               const float output[4], uint32_t *error,
                               uint32_t *fault_mask)
{
  uint32_t i, min_i = 0U, max_i = 0U;
  bool have_active_wheel = false;
  bool stall_grace = run_elapsed_ms >= PID4_STALL_GRACE_MS;
  bool sync_grace = run_elapsed_ms >= PID4_SYNC_GRACE_MS;
  float min_speed = 0.0f, max_speed = 0.0f;

  for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
    float target = g_pid4.active_target_cps[i];
    uint32_t bit = 1UL << i;
    if (target == 0.0f) {
      wrong_direction_ms[i] = 0U;
      stall_ms[i] = 0U;
      continue;
    }
    {
      float direction_sign = target > 0.0f ? 1.0f : -1.0f;
      float y = direction_sign * measured[i];
      if (y < -PID4_DIRECTION_THRESHOLD_CPS)
        wrong_direction_ms[i] += dt_ms;
      else
        wrong_direction_ms[i] = 0U;
      if (wrong_direction_ms[i] >= PID4_DIRECTION_FAULT_MS) {
        *error = PID4_ERROR_WRONG_DIRECTION;
        *fault_mask = bit;
        return 1U;
      }
      if (stall_grace && output[i] >= PID4_STALL_OUTPUT_PERMILLE &&
          fabsf(y) < PID4_DIRECTION_THRESHOLD_CPS)
        stall_ms[i] += dt_ms;
      else
        stall_ms[i] = 0U;
      if (stall_ms[i] >= PID4_STALL_FAULT_MS) {
        *error = PID4_ERROR_STALL;
        *fault_mask = bit;
        return 1U;
      }
      if (!have_active_wheel) {
        min_speed = y;
        max_speed = y;
        min_i = i;
        max_i = i;
        have_active_wheel = true;
      } else {
        if (y < min_speed) { min_speed = y; min_i = i; }
        if (y > max_speed) { max_speed = y; max_i = i; }
      }
    }
  }

  g_pid4.sync_spread_cps = have_active_wheel ? max_speed - min_speed : 0.0f;
  if (g_pid4.sync_guard_enabled != 0U) {
    g_pid4.sync_warning = (sync_grace &&
        g_pid4.sync_spread_cps > PID4_SYNC_WARNING_CPS) ? 1U : 0U;
    if (sync_grace && g_pid4.sync_spread_cps > PID4_SYNC_FAULT_CPS)
      sync_fault_ms += dt_ms;
    else
      sync_fault_ms = 0U;
    if (sync_fault_ms >= PID4_SYNC_FAULT_MS) {
      *error = PID4_ERROR_SYNC;
      *fault_mask = (1UL << min_i) | (1UL << max_i);
      return 1U;
    }
  } else {
    g_pid4.sync_warning = 0U;
    sync_fault_ms = 0U;
  }
  return 0U;
}

static void append_sample(uint32_t now_ms, uint32_t dt_ms,
                          const float target[4], const float measured[4],
                          const float error[4], const float ff[4],
                          const float ui[4], const float output[4],
                          const int32_t delta[4])
{
  Pid4LabSample *sample;
  uint32_t i;
  if (log_used >= PID4_LOG_CAPACITY) {
    g_pid4.log_overflow = 1U;
    fail_closed(PID4_ERROR_LOG_OVERFLOW, PID4_FAULT_MASK_ALL);
    return;
  }
  sample = &g_pid4_log[log_used++];
  sample->timestamp_ms = now_ms;
  sample->state = PID4_STATE_RUN;
  sample->dt_ms = dt_ms;
  for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
    sample->target_cps[i] = target[i];
    sample->measured_cps[i] = measured[i];
    sample->error_cps[i] = error[i];
    sample->u_ff[i] = ff[i];
    sample->u_i[i] = ui[i];
    sample->u_output[i] = output[i];
    sample->encoder_delta[i] = delta[i];
  }
  sample->sync_spread_cps = g_pid4.sync_spread_cps;
  sample->sync_warning = g_pid4.sync_warning;
  g_pid4.log_count = log_used;
}

void pid4_lab_init(void)
{
  uint32_t i;
  safe_outputs();
  memset(g_pid4_log, 0, sizeof(g_pid4_log));
  log_used = 0U;
  log_divider = 0U;
  internal_state = PID4_STATE_IDLE;
  g_pid4.request = PID4_REQUEST_NONE;
  g_pid4.state = PID4_STATE_IDLE;
  g_pid4.arm_magic = 0U;
  g_pid4.total_delta_fl = 0;
  g_pid4.total_delta_fr = 0;
  g_pid4.total_delta_rl = 0;
  g_pid4.total_delta_rr = 0;
  g_pid4.last_error = PID4_ERROR_NONE;
  g_pid4.fault_wheel_mask = 0U;
  g_pid4.log_count = 0U;
  g_pid4.log_overflow = 0U;
  g_pid4.completed_count = 0U;
  g_pid4.elapsed_ms = 0U;
  g_pid4.dt_ms = 0U;
  g_pid4.arm_elapsed_ms = 0U;
  g_pid4.arm_remaining_ms = PID4_DEFAULT_ARM_DELAY_MS;
  g_pid4.sync_guard_enabled = 0U;
  g_pid4.sync_spread_cps = 0.0f;
  g_pid4.sync_warning = 0U;
  for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
    g_pid4.requested_target_cps[i] = 0.0f;
    g_pid4.active_target_cps[i] = 0.0f;
    g_pid4.measured_cps[i] = 0.0f;
    g_pid4.error_cps[i] = 0.0f;
    g_pid4.u_ff[i] = 0.0f;
    g_pid4.u_i[i] = 0.0f;
    g_pid4.u_output[i] = 0.0f;
    g_pid4.encoder_delta[i] = 0;
  }
  reset_controller();
  if (HAL_TIM_Encoder_Start(&htim2, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim5, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim1, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim4, TIM_CHANNEL_ALL) != HAL_OK)
    fail_closed(PID4_ERROR_ENCODER_START, PID4_FAULT_MASK_ALL);
}

static void add_cycle_totals(const int32_t delta[4])
{
  g_pid4.total_delta_fl += delta[0];
  g_pid4.total_delta_fr += delta[1];
  g_pid4.total_delta_rl += delta[2];
  g_pid4.total_delta_rr += delta[3];
}

static void ramp_targets(uint32_t run_elapsed_ms, float target[4],
                         float magnitude[4])
{
  uint32_t i;
  float fraction = run_elapsed_ms >= PID4_RAMP_DURATION_MS ? 1.0f :
      (float)run_elapsed_ms / (float)PID4_RAMP_DURATION_MS;
  for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
    float requested = g_pid4.active_target_cps[i];
    magnitude[i] = fabsf(requested) * fraction;
    target[i] = requested > 0.0f ? magnitude[i] :
                (requested < 0.0f ? -magnitude[i] : 0.0f);
  }
}

void pid4_lab_step(uint32_t now_ms)
{
  uint32_t state;
  handle_request(now_ms);
  state = internal_state;
  if (g_pid4.state != internal_state) {
    fail_closed(PID4_ERROR_STATE, PID4_FAULT_MASK_ALL);
    return;
  }
  if (state == PID4_STATE_IDLE || state == PID4_STATE_COMPLETE ||
      state == PID4_STATE_ABORTED || state == PID4_STATE_FAULT)
    return;

  if (state == PID4_STATE_ARMED_DELAY) {
    uint32_t arm_elapsed = elapsed(now_ms, arm_started_ms);
    g_pid4.arm_elapsed_ms = arm_elapsed;
    g_pid4.arm_remaining_ms = arm_elapsed >= PID4_DEFAULT_ARM_DELAY_MS ? 0U :
        PID4_DEFAULT_ARM_DELAY_MS - arm_elapsed;
    safe_outputs();
    reset_controller();
    if (arm_elapsed >= PID4_DEFAULT_ARM_DELAY_MS) {
      previous_raw = read_all_encoders();
      last_sample_ms = now_ms;
      run_started_ms = now_ms;
      g_pid4.elapsed_ms = 0U;
      log_divider = 0U;
      set_state(PID4_STATE_RUN);
    }
    return;
  }

  if (state == PID4_STATE_STOP_HOLD) {
    safe_outputs();
    reset_controller();
    if (elapsed(now_ms, hold_started_ms) >= PID4_DEFAULT_STOP_HOLD_MS) {
      g_pid4.completed_count++;
      set_state(PID4_STATE_COMPLETE);
    }
    return;
  }
  if (state != PID4_STATE_RUN) {
    fail_closed(PID4_ERROR_STATE, PID4_FAULT_MASK_ALL);
    return;
  }

  g_pid4.elapsed_ms = elapsed(now_ms, run_started_ms);
  if (g_pid4.elapsed_ms >= PID4_RUN_TIMEOUT_MS) {
    fail_closed(PID4_ERROR_TIMEOUT, PID4_FAULT_MASK_ALL);
    return;
  }
  if (g_pid4.elapsed_ms >= PID4_DEFAULT_RUN_DURATION_MS) {
    EncoderRaw final_raw = read_all_encoders();
    int32_t final_delta[PID4_WHEEL_COUNT];
    encoder_deltas(previous_raw, final_raw, final_delta);
    add_cycle_totals(final_delta);
    previous_raw = final_raw;
    safe_outputs();
    reset_controller();
    hold_started_ms = now_ms;
    set_state(PID4_STATE_STOP_HOLD);
    return;
  }

  {
    float ramped_target[PID4_WHEEL_COUNT];
    float ramped_magnitude[PID4_WHEEL_COUNT];
    float measured[PID4_WHEEL_COUNT], error[PID4_WHEEL_COUNT];
    float ff[PID4_WHEEL_COUNT], up[PID4_WHEEL_COUNT];
    float ui[PID4_WHEEL_COUNT], output[PID4_WHEEL_COUNT];
    EncoderRaw current = read_all_encoders();
    int32_t delta[PID4_WHEEL_COUNT];
    uint32_t dt_ms = elapsed(now_ms, last_sample_ms);
    uint32_t fault_error = PID4_ERROR_NONE, fault_mask = 0U;
    uint32_t i;
    if (dt_ms == 0U || dt_ms > PID4_MAX_CONTROL_DT_MS) {
      fail_closed(PID4_ERROR_BAD_DT, PID4_FAULT_MASK_ALL);
      return;
    }
    for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
      float active = g_pid4.active_target_cps[i];
      if (!isfinite(active) || fabsf(active) > PID4_MAX_TARGET_CPS) {
        fail_closed(PID4_ERROR_INVALID_TARGET, 1UL << i);
        return;
      }
    }
    encoder_deltas(previous_raw, current, delta);
    previous_raw = current;
    last_sample_ms = now_ms;
    add_cycle_totals(delta);
    g_pid4.dt_ms = dt_ms;
    ramp_targets(g_pid4.elapsed_ms, ramped_target, ramped_magnitude);
    compute_outputs(dt_ms, g_pid4.active_target_cps,
                    ramped_magnitude, delta, measured, error, ff, up, ui,
                    output);
    for (i = 0U; i < PID4_WHEEL_COUNT; ++i) {
      if (!isfinite(measured[i]) || !isfinite(error[i]) || !isfinite(ff[i]) ||
          !isfinite(up[i]) || !isfinite(ui[i]) || !isfinite(output[i]) ||
          output[i] < 0.0f || output[i] > (float)PID4_MAX_PWM_PERMILLE) {
        fail_closed(PID4_ERROR_INVALID_OUTPUT, 1UL << i);
        return;
      }
    }
    set_debug_vectors(measured, error, ff, ui, output, delta);
    if (monitor_guards(g_pid4.elapsed_ms, dt_ms, measured, output,
                       &fault_error, &fault_mask) != 0U) {
      fail_closed(fault_error, fault_mask);
      return;
    }
    start_outputs_or_fault(output);
    if (internal_state == PID4_STATE_FAULT) return;
    if (++log_divider >= PID4_LOG_EVERY_CYCLES) {
      log_divider = 0U;
      append_sample(now_ms, dt_ms, ramped_target, measured, error, ff, ui,
                    output, delta);
      if (internal_state == PID4_STATE_FAULT) return;
    }
  }
}
