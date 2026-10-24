#include "pid1_lab.h"

#include <math.h>
#include <stdbool.h>
#include <string.h>

#include "main.h"
#include "motor_logic.h"
#include "safety_io.h"

extern TIM_HandleTypeDef htim1, htim2, htim3, htim4, htim5;

#define PID1_DEFAULT_PLATEAU_MS 1500U
#define PID1_DEFAULT_ZERO_GAP_MS 400U
#define PID1_RUN_TIMEOUT_MS 20000U
#define PID1_DIRECTION_THRESHOLD_CPS 100.0f
#define PID1_DIRECTION_FAULT_MS 200U
#define PID1_STALL_OUTPUT_PERMILLE 120.0f
#define PID1_STALL_GRACE_MS 400U
#define PID1_STALL_FAULT_MS 500U
#define PID1_INTEGRAL_LIMIT 80.0f
#define PID1_PROFILE_COUNT 5U

/* Index order: [wheel][0 = forward, 1 = reverse]. */
typedef struct { float u0; float kv; } Pid1Feedforward;
static const Pid1Feedforward feedforward[4][2] = {
  {{40.330665f, 0.217819026f}, {36.253577f, 0.225076821f}},
  {{32.415574f, 0.231811480f}, {34.233335f, 0.226312521f}},
  {{61.698998f, 0.212679580f}, {54.760209f, 0.223609266f}},
  {{37.521999f, 0.223981830f}, {32.707200f, 0.229221684f}}
};
static const float profile_cps[PID1_PROFILE_COUNT] = {
  500.0f, 1000.0f, 1400.0f, 1000.0f, 500.0f
};

typedef struct { uint32_t fl, fr, rl, rr; } EncoderRaw;

volatile Pid1LabControl g_pid1;
Pid1LabSample g_pid1_log[PID1_LOG_CAPACITY];

static EncoderRaw previous_raw;
static uint32_t last_sample_ms, run_started_ms, phase_started_ms;
static uint32_t internal_state, active_wheel, active_direction;
static uint32_t active_plateau_ms, active_zero_gap_ms, profile_index;
static uint32_t wrong_direction_ms, stall_ms;
static uint32_t pwm_started, finish_after_gap, log_used;
static float integral_permille;

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
static EncoderRaw read_encoders(void)
{
  EncoderRaw r;
  r.fl = __HAL_TIM_GET_COUNTER(&htim2);
  r.fr = __HAL_TIM_GET_COUNTER(&htim5);
  r.rl = (uint32_t)(uint16_t)__HAL_TIM_GET_COUNTER(&htim1);
  r.rr = (uint32_t)(uint16_t)__HAL_TIM_GET_COUNTER(&htim4);
  return r;
}
static int32_t wheel_delta(uint32_t wheel, EncoderRaw old, EncoderRaw now)
{
  switch (wheel) {
    case PID1_WHEEL_FL: return delta32(old.fl, now.fl);
    case PID1_WHEEL_FR: return delta32(old.fr, now.fr);
    case PID1_WHEEL_RL: return delta16(old.rl, now.rl);
    case PID1_WHEEL_RR: return delta16(old.rr, now.rr);
    default: return 0;
  }
}
static uint32_t wheel_channel(uint32_t wheel)
{
  static const uint32_t channel[4] = {
    TIM_CHANNEL_4, TIM_CHANNEL_3, TIM_CHANNEL_1, TIM_CHANNEL_2
  };
  return channel[wheel];
}
static MotorWheel motor_wheel(uint32_t wheel)
{
  static const MotorWheel wheel_map[4] = {
    MOTOR_WHEEL_FL, MOTOR_WHEEL_FR, MOTOR_WHEEL_RL, MOTOR_WHEEL_RR
  };
  return wheel_map[wheel];
}
static void safe_outputs(void)
{
  safety_io_force_motor_disabled();
  motor_logic_stop_all();
  pwm_started = 0U;
  g_pid1.u_output = 0.0f;
}
static void set_state(uint32_t state)
{
  internal_state = state;
  g_pid1.state = state;
}
static void fail_closed(uint32_t error)
{
  safe_outputs();
  integral_permille = 0.0f;
  g_pid1.u_i = 0.0f;
  g_pid1.target_cps = 0.0f;
  g_pid1.last_error = error;
  set_state(PID1_STATE_FAULT);
}
static bool valid_direction(uint32_t direction)
{
  return direction == PID1_DIRECTION_FORWARD || direction == PID1_DIRECTION_REVERSE;
}
static float direction_sign(uint32_t direction)
{
  return direction == PID1_DIRECTION_FORWARD ? 1.0f : -1.0f;
}
static void clear_controller(void)
{
  integral_permille = 0.0f;
  wrong_direction_ms = 0U;
  stall_ms = 0U;
  g_pid1.target_cps = 0.0f;
  g_pid1.measured_cps = 0.0f;
  g_pid1.error_cps = 0.0f;
  g_pid1.u_ff = 0.0f;
  g_pid1.u_p = 0.0f;
  g_pid1.u_i = 0.0f;
  g_pid1.u_output = 0.0f;
  g_pid1.encoder_delta = 0;
  g_pid1.dt_ms = 0U;
}
static void append_sample(uint32_t now, int32_t delta, uint32_t dt,
                          float measured, float error, float u_ff,
                          float u_p, float u_i, float u_out)
{
  Pid1LabSample *s;
  if (log_used >= PID1_LOG_CAPACITY) {
    g_pid1.log_overflow = 1U;
    fail_closed(PID1_ERROR_LOG_OVERFLOW);
    return;
  }
  s = &g_pid1_log[log_used++];
  s->timestamp_ms = now;
  s->state = internal_state;
  s->selected_wheel = active_wheel;
  s->direction = active_direction;
  s->target_cps = g_pid1.target_cps;
  s->measured_cps = measured;
  s->error_cps = error;
  s->u_ff_permille = u_ff;
  s->u_p_permille = u_p;
  s->u_i_permille = u_i;
  s->u_output_permille = u_out;
  s->encoder_delta = delta;
  s->dt_ms = dt;
  g_pid1.log_count = log_used;
}
static bool apply_output(float permille)
{
  uint32_t channel, arr, compare;
  if (!isfinite(permille) || permille < 0.0f || permille > (float)PID1_MAX_PWM_PERMILLE ||
      active_wheel > PID1_WHEEL_RR) {
    fail_closed(PID1_ERROR_STATE);
    return false;
  }
  if (permille <= 0.0f) {
    safe_outputs();
    return true;
  }
  channel = wheel_channel(active_wheel); /* TIM_CHANNEL_1 is valid and equals zero. */
  arr = __HAL_TIM_GET_AUTORELOAD(&htim3);
  compare = (uint32_t)(((uint64_t)arr + 1ULL) * (uint32_t)(permille + 0.5f) / 1000ULL);
  if (compare == 0U) compare = 1U;
  __HAL_TIM_SET_COMPARE(&htim3, channel, compare);
  if (pwm_started == 0U) {
    motor_logic_set_direction(motor_wheel(active_wheel),
        active_direction == PID1_DIRECTION_FORWARD ?
        MOTOR_DIRECTION_FORWARD : MOTOR_DIRECTION_REVERSE);
    if (HAL_TIM_PWM_Start(&htim3, channel) != HAL_OK) {
      fail_closed(PID1_ERROR_PWM_START);
      return false;
    }
    pwm_started = 1U;
    HAL_GPIO_WritePin(MCU_MOTOR_ENABLE_GPIO_Port, MCU_MOTOR_ENABLE_Pin, GPIO_PIN_SET);
  }
  g_pid1.u_output = permille;
  return true;
}
static bool validate_request(void)
{
  uint64_t run_ms;
  if (g_pid1.selected_wheel > PID1_WHEEL_RR) {
    fail_closed(PID1_ERROR_INVALID_WHEEL); return false;
  }
  if (!valid_direction(g_pid1.direction)) {
    fail_closed(PID1_ERROR_INVALID_DIRECTION); return false;
  }
  if (g_pid1.plateau_ms < 500U || g_pid1.plateau_ms > 3000U ||
      g_pid1.zero_gap_ms < PID1_SAMPLE_PERIOD_MS || g_pid1.zero_gap_ms > 1000U ||
      !isfinite(g_pid1.kp) || !isfinite(g_pid1.ki) || g_pid1.kp < 0.0f ||
      g_pid1.ki < 0.0f || g_pid1.kp > 1.0f || g_pid1.ki > 10.0f) {
    fail_closed(PID1_ERROR_INVALID_TIMING); return false;
  }
  run_ms = (uint64_t)PID1_PROFILE_COUNT * g_pid1.plateau_ms +
           2ULL * g_pid1.zero_gap_ms;
  if (run_ms > 17000ULL) {
    fail_closed(PID1_ERROR_INVALID_TIMING); return false;
  }
  return true;
}
static void begin_run(uint32_t now)
{
  if (log_used != 0U) {
    fail_closed(PID1_ERROR_STATE);
    return;
  }
  if (!validate_request()) return;
  active_wheel = g_pid1.selected_wheel;
  active_direction = g_pid1.direction;
  active_plateau_ms = g_pid1.plateau_ms;
  active_zero_gap_ms = g_pid1.zero_gap_ms;
  profile_index = 0U;
  finish_after_gap = 0U;
  run_started_ms = now;
  phase_started_ms = now;
  wrong_direction_ms = stall_ms = 0U;
  clear_controller();
  safe_outputs();
  set_state(PID1_STATE_ZERO_GAP);
}
static void clear_log_request(void)
{
  safe_outputs();
  clear_controller();
  memset(g_pid1_log, 0, sizeof(g_pid1_log));
  log_used = 0U;
  g_pid1.log_count = 0U;
  g_pid1.log_overflow = 0U;
  g_pid1.elapsed_ms = 0U;
  g_pid1.last_error = PID1_ERROR_NONE;
  g_pid1.completed_count = 0U;
  active_wheel = g_pid1.selected_wheel;
  active_direction = g_pid1.direction;
  set_state(PID1_STATE_IDLE);
}
void pid1_lab_init(void)
{
  safe_outputs();
  g_pid1.request = PID1_REQUEST_NONE;
  internal_state = PID1_STATE_IDLE;
  g_pid1.state = PID1_STATE_IDLE;
  g_pid1.selected_wheel = PID1_WHEEL_FL;
  g_pid1.direction = PID1_DIRECTION_FORWARD;
  g_pid1.kp = PID1_DEFAULT_KP;
  g_pid1.ki = PID1_DEFAULT_KI;
  g_pid1.plateau_ms = PID1_DEFAULT_PLATEAU_MS;
  g_pid1.zero_gap_ms = PID1_DEFAULT_ZERO_GAP_MS;
  g_pid1.last_error = PID1_ERROR_NONE;
  g_pid1.log_count = 0U;
  g_pid1.log_overflow = 0U;
  g_pid1.completed_count = 0U;
  g_pid1.elapsed_ms = 0U;
  log_used = 0U;
  finish_after_gap = 0U;
  set_state(PID1_STATE_IDLE);
  clear_controller();
  if (HAL_TIM_Encoder_Start(&htim2, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim5, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim1, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim4, TIM_CHANNEL_ALL) != HAL_OK) {
    fail_closed(PID1_ERROR_ENCODER_START);
  }
}
static void handle_request(uint32_t now)
{
  uint32_t request = g_pid1.request;
  if (request == PID1_REQUEST_ABORT) {
    g_pid1.request = PID1_REQUEST_NONE;
    safe_outputs();
    clear_controller();
    g_pid1.last_error = PID1_ERROR_NONE;
    set_state(PID1_STATE_ABORTED);
    return;
  }
  if (request == PID1_REQUEST_CLEAR_LOG) {
    g_pid1.request = PID1_REQUEST_NONE;
    clear_log_request();
    return;
  }
  if (request == PID1_REQUEST_NONE) return;
  if (request != PID1_REQUEST_RUN_PROFILE) {
    g_pid1.request = PID1_REQUEST_NONE;
    fail_closed(PID1_ERROR_INVALID_REQUEST);
    return;
  }
  g_pid1.request = PID1_REQUEST_NONE;
  if (internal_state == PID1_STATE_IDLE || internal_state == PID1_STATE_COMPLETE ||
      internal_state == PID1_STATE_ABORTED) {
    begin_run(now);
  } else {
    fail_closed(PID1_ERROR_STATE);
  }
}
void pid1_lab_step(uint32_t now_ms)
{
  uint32_t state;
  handle_request(now_ms);
  state = internal_state;
  if (state == PID1_STATE_FAULT || state == PID1_STATE_ABORTED ||
      state == PID1_STATE_IDLE || state == PID1_STATE_COMPLETE) return;
  g_pid1.elapsed_ms = elapsed(now_ms, run_started_ms);
  if (g_pid1.elapsed_ms >= PID1_RUN_TIMEOUT_MS) {
    fail_closed(PID1_ERROR_TIMEOUT); return;
  }
  if (state == PID1_STATE_ZERO_GAP) {
    if (elapsed(now_ms, phase_started_ms) >= active_zero_gap_ms) {
      if (finish_after_gap != 0U) {
        safe_outputs();
        set_state(PID1_STATE_COMPLETE);
        g_pid1.completed_count++;
        return;
      }
      motor_logic_stop_all();
      motor_logic_set_direction(motor_wheel(active_wheel),
          active_direction == PID1_DIRECTION_FORWARD ?
          MOTOR_DIRECTION_FORWARD : MOTOR_DIRECTION_REVERSE);
      previous_raw = read_encoders();
      last_sample_ms = now_ms;
      integral_permille = 0.0f;
      phase_started_ms = now_ms;
      g_pid1.target_cps = direction_sign(active_direction) * profile_cps[profile_index];
      set_state(PID1_STATE_RUN_PROFILE);
    }
    return;
  }
  if (state != PID1_STATE_RUN_PROFILE || active_wheel > PID1_WHEEL_RR ||
      !valid_direction(active_direction) || g_pid1.selected_wheel != active_wheel ||
      g_pid1.direction != active_direction) {
    fail_closed(PID1_ERROR_STATE); return;
  }
  {
    EncoderRaw current = read_encoders();
    int32_t delta = wheel_delta(active_wheel, previous_raw, current);
    uint32_t dt_ms = elapsed(now_ms, last_sample_ms);
    float measured, sign, command_speed, y, error;
    float u_ff, u_p, candidate_i, raw, clamped;
    const Pid1Feedforward *ff;
    if (dt_ms == 0U) { fail_closed(PID1_ERROR_BAD_DT); return; }
    previous_raw = current;
    last_sample_ms = now_ms;
    measured = (float)delta * 1000.0f / (float)dt_ms;
    sign = direction_sign(active_direction);
    command_speed = profile_cps[profile_index];
    y = sign * measured;
    error = command_speed - y;
    ff = &feedforward[active_wheel][active_direction == PID1_DIRECTION_FORWARD ? 0U : 1U];
    u_ff = ff->u0 + ff->kv * command_speed;
    u_p = g_pid1.kp * error;
    candidate_i = integral_permille + g_pid1.ki * error * ((float)dt_ms / 1000.0f);
    if (candidate_i > PID1_INTEGRAL_LIMIT) candidate_i = PID1_INTEGRAL_LIMIT;
    if (candidate_i < -PID1_INTEGRAL_LIMIT) candidate_i = -PID1_INTEGRAL_LIMIT;
    raw = u_ff + u_p + candidate_i;
    if (!((raw >= 400.0f && error > 0.0f) || (raw <= 0.0f && error < 0.0f))) {
      integral_permille = candidate_i;
    }
    raw = u_ff + u_p + integral_permille;
    clamped = raw;
    if (clamped < 0.0f) clamped = 0.0f;
    if (clamped > (float)PID1_MAX_PWM_PERMILLE) clamped = (float)PID1_MAX_PWM_PERMILLE;
    g_pid1.target_cps = sign * command_speed;
    g_pid1.measured_cps = measured;
    g_pid1.error_cps = error;
    g_pid1.u_ff = u_ff;
    g_pid1.u_p = u_p;
    g_pid1.u_i = integral_permille;
    g_pid1.encoder_delta = delta;
    g_pid1.dt_ms = dt_ms;
    if (!apply_output(clamped)) return;
    append_sample(now_ms, delta, dt_ms, measured, error, u_ff, u_p,
                  integral_permille, clamped);
    if (internal_state == PID1_STATE_FAULT) return;
    if (command_speed >= 500.0f && clamped >= 80.0f && y < -PID1_DIRECTION_THRESHOLD_CPS) {
      wrong_direction_ms += dt_ms;
    } else wrong_direction_ms = 0U;
    if (wrong_direction_ms >= PID1_DIRECTION_FAULT_MS) {
      fail_closed(PID1_ERROR_WRONG_DIRECTION); return;
    }
    if (elapsed(now_ms, phase_started_ms) >= PID1_STALL_GRACE_MS &&
        command_speed >= 500.0f && clamped >= PID1_STALL_OUTPUT_PERMILLE &&
        fabsf(y) < PID1_DIRECTION_THRESHOLD_CPS) {
      stall_ms += dt_ms;
    } else stall_ms = 0U;
    if (stall_ms >= PID1_STALL_FAULT_MS) {
      fail_closed(PID1_ERROR_STALL); return;
    }
    if (elapsed(now_ms, phase_started_ms) >= active_plateau_ms) {
      wrong_direction_ms = stall_ms = 0U;
      profile_index++;
      if (profile_index >= PID1_PROFILE_COUNT) {
        g_pid1.target_cps = 0.0f;
        g_pid1.error_cps = 0.0f;
        g_pid1.u_ff = 0.0f;
        g_pid1.u_p = 0.0f;
        integral_permille = 0.0f;
        g_pid1.u_i = 0.0f;
        safe_outputs();
        finish_after_gap = 1U;
        phase_started_ms = now_ms;
        set_state(PID1_STATE_ZERO_GAP);
      } else {
        g_pid1.target_cps = sign * profile_cps[profile_index];
        phase_started_ms = now_ms;
      }
    }
  }
}
