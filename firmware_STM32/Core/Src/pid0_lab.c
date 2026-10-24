#include "pid0_lab.h"

#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include "main.h"
#include "motor_logic.h"
#include "safety_io.h"

extern TIM_HandleTypeDef htim1, htim2, htim3, htim4, htim5;
extern UART_HandleTypeDef huart6;

#define PID0_RUN_TIMEOUT_MS 120000U
#define PID0_MAX_PHASE_MS 10000U
#define PID0_DEFAULT_SETTLE_MS 400U
#define PID0_DEFAULT_MEASURE_MS 800U
#define PID0_DEFAULT_ZERO_GAP_MS 400U
#define PID0_DEFAULT_SWEEP_MIN 100U
#define PID0_DEFAULT_SWEEP_MAX 400U
#define PID0_DEFAULT_SWEEP_STEP 50U
#define PID0_DEFAULT_SINGLE_DUTY 200U
#define PID0_UART_TIMEOUT_MS 100U

typedef struct { uint32_t fl, fr, rl, rr; } EncoderRaw;

volatile Pid0LabControl g_pid0;
Pid0LabSample g_pid0_log[PID0_LOG_CAPACITY];

static EncoderRaw previous_raw;
static uint32_t last_sample_ms, run_started_ms, phase_started_ms;
static uint32_t log_used, sweep_mode, next_duty, pending_duty;
static uint32_t internal_state;
static uint32_t active_wheel, active_direction;
static uint32_t active_sweep_min, active_sweep_max, active_sweep_step;
static uint32_t active_settle_ms, active_measure_ms, active_zero_gap_ms;
static uint32_t applied_duty;

static uint32_t elapsed_ms(uint32_t now, uint32_t then) { return now - then; }

static void set_state(uint32_t state)
{
  internal_state = state;
  g_pid0.state = state;
}

static uint32_t read_fl(void) { return __HAL_TIM_GET_COUNTER(&htim2); }
static uint32_t read_fr(void) { return __HAL_TIM_GET_COUNTER(&htim5); }
static uint32_t read_rl(void) { return (uint32_t)(uint16_t)__HAL_TIM_GET_COUNTER(&htim1); }
static uint32_t read_rr(void) { return (uint32_t)(uint16_t)__HAL_TIM_GET_COUNTER(&htim4); }

static EncoderRaw read_all(void)
{
  EncoderRaw r = { read_fl(), read_fr(), read_rl(), read_rr() };
  return r;
}

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

static uint32_t wheel_channel(uint32_t wheel)
{
  static const uint32_t channels[4] = {
    TIM_CHANNEL_4, TIM_CHANNEL_3, TIM_CHANNEL_1, TIM_CHANNEL_2
  };
  return wheel < 4U ? channels[wheel] : 0U;
}

static MotorWheel motor_wheel(uint32_t wheel)
{
  static const MotorWheel wheels[4] = {
    MOTOR_WHEEL_FL, MOTOR_WHEEL_FR, MOTOR_WHEEL_RL, MOTOR_WHEEL_RR
  };
  return wheels[wheel];
}

static void stop_outputs(void)
{
  safety_io_force_motor_disabled();
  motor_logic_stop_all();
}

static void fail_closed(uint32_t error)
{
  stop_outputs();
  g_pid0.last_error = error;
  set_state(PID0_STATE_FAULT);
  g_pid0.current_duty_permille = 0U;
}

static bool is_running(void)
{
  return internal_state == PID0_STATE_ZERO_GAP ||
         internal_state == PID0_STATE_SETTLE ||
         internal_state == PID0_STATE_MEASURE;
}

static const char *wheel_name(uint32_t wheel)
{
  static const char *names[4] = { "FL", "FR", "RL", "RR" };
  return wheel < 4U ? names[wheel] : "INVALID";
}

static const char *direction_name(uint32_t direction)
{
  return direction == PID0_DIRECTION_FORWARD ? "FORWARD" : "REVERSE";
}

static uint32_t sweep_count(void)
{
  return ((g_pid0.sweep_max_permille - g_pid0.sweep_min_permille) /
          g_pid0.sweep_step_permille) + 1U;
}

static bool validate_run(bool sweep)
{
  uint32_t count = 1U;
  uint64_t worst_ms;
  if (g_pid0.selected_wheel > PID0_WHEEL_RR) {
    fail_closed(PID0_ERROR_INVALID_WHEEL); return false;
  }
  if ((g_pid0.direction != PID0_DIRECTION_FORWARD) &&
      (g_pid0.direction != PID0_DIRECTION_REVERSE)) {
    fail_closed(PID0_ERROR_INVALID_DIRECTION); return false;
  }
  if ((g_pid0.settle_ms > PID0_MAX_PHASE_MS) ||
      (g_pid0.measure_ms < PID0_SAMPLE_PERIOD_MS) ||
      (g_pid0.measure_ms > PID0_MAX_PHASE_MS) ||
      (g_pid0.zero_gap_ms < PID0_SAMPLE_PERIOD_MS) ||
      (g_pid0.zero_gap_ms > PID0_MAX_PHASE_MS)) {
    fail_closed(PID0_ERROR_INVALID_TIMING); return false;
  }
  if (sweep) {
    if ((g_pid0.sweep_min_permille == 0U) ||
        (g_pid0.sweep_min_permille > g_pid0.sweep_max_permille) ||
        (g_pid0.sweep_max_permille > PID0_MAX_DUTY_PERMILLE) ||
        (g_pid0.sweep_step_permille == 0U) ||
        (((g_pid0.sweep_max_permille - g_pid0.sweep_min_permille) %
           g_pid0.sweep_step_permille) != 0U)) {
      fail_closed(PID0_ERROR_INVALID_DUTY); return false;
    }
    count = sweep_count();
  } else if ((g_pid0.current_duty_permille == 0U) ||
             (g_pid0.current_duty_permille > PID0_MAX_DUTY_PERMILLE)) {
    fail_closed(PID0_ERROR_INVALID_DUTY); return false;
  }
  worst_ms = (uint64_t)count * ((uint64_t)g_pid0.settle_ms +
      (uint64_t)g_pid0.measure_ms + (uint64_t)g_pid0.zero_gap_ms);
  if (worst_ms > PID0_RUN_TIMEOUT_MS) {
    fail_closed(PID0_ERROR_INVALID_TIMING); return false;
  }
  return true;
}

static bool start_selected_motor(uint32_t now)
{
  uint32_t channel = wheel_channel(active_wheel);
  uint32_t arr = __HAL_TIM_GET_AUTORELOAD(&htim3);
  uint32_t duty = pending_duty;
  uint32_t compare;
  if ((channel == 0U) || (duty == 0U) || (duty > PID0_MAX_DUTY_PERMILLE)) {
    fail_closed(PID0_ERROR_INVALID_DUTY); return false;
  }
  stop_outputs();
  motor_logic_set_direction(motor_wheel(active_wheel),
      active_direction == PID0_DIRECTION_FORWARD ?
      MOTOR_DIRECTION_FORWARD : MOTOR_DIRECTION_REVERSE);
  compare = (uint32_t)(((uint64_t)arr + 1ULL) * duty / 1000ULL);
  __HAL_TIM_SET_COMPARE(&htim3, channel, compare);
  if (HAL_TIM_PWM_Start(&htim3, channel) != HAL_OK) {
    fail_closed(PID0_ERROR_PWM_START); return false;
  }
  HAL_GPIO_WritePin(MCU_MOTOR_ENABLE_GPIO_Port, MCU_MOTOR_ENABLE_Pin, GPIO_PIN_SET);
  applied_duty = duty;
  g_pid0.current_duty_permille = duty;
  previous_raw = read_all();
  last_sample_ms = now;
  phase_started_ms = now;
  set_state(PID0_STATE_SETTLE);
  return true;
}

static void accept_run(uint32_t request, uint32_t now)
{
  bool sweep = request == PID0_REQUEST_RUN_SWEEP;
  if (!validate_run(sweep)) return;
  sweep_mode = sweep ? 1U : 0U;
  active_wheel = g_pid0.selected_wheel;
  active_direction = g_pid0.direction;
  active_sweep_min = g_pid0.sweep_min_permille;
  active_sweep_max = g_pid0.sweep_max_permille;
  active_sweep_step = g_pid0.sweep_step_permille;
  active_settle_ms = g_pid0.settle_ms;
  active_measure_ms = g_pid0.measure_ms;
  active_zero_gap_ms = g_pid0.zero_gap_ms;
  pending_duty = sweep_mode != 0U ? active_sweep_min : g_pid0.current_duty_permille;
  next_duty = pending_duty;
  applied_duty = 0U;
  g_pid0.current_duty_permille = 0U;
  run_started_ms = now;
  g_pid0.elapsed_ms = 0U;
  g_pid0.last_error = PID0_ERROR_NONE;
  stop_outputs();
  motor_logic_stop_all();
  phase_started_ms = now;
  set_state(PID0_STATE_ZERO_GAP);
}

static void format_speed_milli(int64_t value, char *out, size_t capacity)
{
  bool negative = value < 0;
  uint64_t magnitude = negative ? (uint64_t)(-value) : (uint64_t)value;
  (void)snprintf(out, capacity, "%s%llu.%03llu", negative ? "-" : "",
      (unsigned long long)(magnitude / 1000ULL),
      (unsigned long long)(magnitude % 1000ULL));
}

static void dump_uart(void)
{
  static const char header[] =
    "timestamp_ms,state,selected_wheel,direction,duty_permille,"
    "fl_delta,fr_delta,rl_delta,rr_delta,fl_counts_per_sec,"
    "fr_counts_per_sec,rl_counts_per_sec,rr_counts_per_sec\r\n";
  char line[192];
  if (is_running() || HAL_GPIO_ReadPin(MCU_MOTOR_ENABLE_GPIO_Port,
                                       MCU_MOTOR_ENABLE_Pin) == GPIO_PIN_SET) {
    g_pid0.last_error = PID0_ERROR_BUSY; return;
  }
  if (HAL_UART_Transmit(&huart6, (uint8_t *)header, sizeof(header) - 1U,
                        PID0_UART_TIMEOUT_MS) != HAL_OK) {
    g_pid0.last_error = PID0_ERROR_UART; return;
  }
  for (uint32_t i = 0U; i < log_used; ++i) {
    const Pid0LabSample *s = &g_pid0_log[i];
    int64_t speeds_milli[4] = {
      (int64_t)(s->fl_counts_per_sec * 1000.0f),
      (int64_t)(s->fr_counts_per_sec * 1000.0f),
      (int64_t)(s->rl_counts_per_sec * 1000.0f),
      (int64_t)(s->rr_counts_per_sec * 1000.0f)
    };
    char formatted_speeds[4][32];
    for (uint32_t j = 0U; j < 4U; ++j) {
      format_speed_milli(speeds_milli[j], formatted_speeds[j],
                         sizeof(formatted_speeds[j]));
    }
    int n = snprintf(line, sizeof(line),
      "%lu,%lu,%s,%s,%lu,%ld,%ld,%ld,%ld,%s,%s,%s,%s\r\n",
      (unsigned long)s->timestamp_ms, (unsigned long)s->state,
      wheel_name(s->selected_wheel), direction_name(s->direction),
      (unsigned long)s->duty_permille, (long)s->fl_delta, (long)s->fr_delta,
      (long)s->rl_delta, (long)s->rr_delta, formatted_speeds[0],
      formatted_speeds[1], formatted_speeds[2], formatted_speeds[3]);
    if ((n < 0) || ((size_t)n >= sizeof(line)) ||
        (HAL_UART_Transmit(&huart6, (uint8_t *)line, (uint16_t)n,
                           PID0_UART_TIMEOUT_MS) != HAL_OK)) {
      g_pid0.last_error = PID0_ERROR_UART; return;
    }
  }
  g_pid0.last_error = PID0_ERROR_NONE;
}

static void process_idle_request(uint32_t request, uint32_t now)
{
  switch (request) {
    case PID0_REQUEST_NONE: break;
    case PID0_REQUEST_RUN_SINGLE_STEP:
    case PID0_REQUEST_RUN_SWEEP: accept_run(request, now); break;
    case PID0_REQUEST_CLEAR_LOG:
      log_used = 0U; g_pid0.log_count = 0U; g_pid0.sample_count = 0U;
      g_pid0.log_overflow = 0U; g_pid0.last_error = PID0_ERROR_NONE;
      break;
    case PID0_REQUEST_DUMP_UART: dump_uart(); break;
    case PID0_REQUEST_ABORT:
      stop_outputs(); set_state(PID0_STATE_ABORTED);
      g_pid0.current_duty_permille = 0U; g_pid0.last_error = PID0_ERROR_NONE;
      break;
    default: fail_closed(PID0_ERROR_INVALID_REQUEST); break;
  }
}

static void capture_sample(uint32_t now, uint32_t dt)
{
  EncoderRaw raw = read_all();
  int32_t fl = delta32(previous_raw.fl, raw.fl);
  int32_t fr = delta32(previous_raw.fr, raw.fr);
  int32_t rl = delta16(previous_raw.rl, raw.rl);
  int32_t rr = delta16(previous_raw.rr, raw.rr);
  float scale = 1000.0f / (float)dt;
  float fl_speed = (float)fl * scale, fr_speed = (float)fr * scale;
  float rl_speed = (float)rl * scale, rr_speed = (float)rr * scale;
  previous_raw = raw;
  g_pid0.fl_delta = fl; g_pid0.fr_delta = fr;
  g_pid0.rl_delta = rl; g_pid0.rr_delta = rr;
  g_pid0.fl_counts_per_sec = fl_speed; g_pid0.fr_counts_per_sec = fr_speed;
  g_pid0.rl_counts_per_sec = rl_speed; g_pid0.rr_counts_per_sec = rr_speed;
  g_pid0.sample_count++;
  if (log_used >= PID0_LOG_CAPACITY) { g_pid0.log_overflow = 1U; return; }
  Pid0LabSample *s = &g_pid0_log[log_used++];
  s->timestamp_ms = now; s->state = internal_state;
  s->selected_wheel = active_wheel; s->direction = active_direction;
  s->duty_permille = g_pid0.current_duty_permille;
  s->fl_delta = fl; s->fr_delta = fr; s->rl_delta = rl; s->rr_delta = rr;
  s->fl_counts_per_sec = fl_speed; s->fr_counts_per_sec = fr_speed;
  s->rl_counts_per_sec = rl_speed; s->rr_counts_per_sec = rr_speed;
  g_pid0.log_count = log_used;
}

static void finish_step(uint32_t now)
{
  stop_outputs();
  g_pid0.current_duty_permille = 0U;
  if (sweep_mode != 0U && next_duty < active_sweep_max) {
    uint64_t following = (uint64_t)next_duty + active_sweep_step;
    if (following <= active_sweep_max) {
      next_duty = (uint32_t)following;
      pending_duty = next_duty;
      phase_started_ms = now;
      set_state(PID0_STATE_ZERO_GAP);
      return;
    }
  }
  set_state(PID0_STATE_COMPLETE);
  g_pid0.completed_count++;
  g_pid0.last_error = PID0_ERROR_NONE;
}

void pid0_lab_init(void)
{
  stop_outputs();
  memset((void *)&g_pid0, 0, sizeof(g_pid0));
  memset(g_pid0_log, 0, sizeof(g_pid0_log));
  log_used = 0U; sweep_mode = 0U; next_duty = 0U; pending_duty = 0U;
  internal_state = PID0_STATE_IDLE;
  g_pid0.sweep_min_permille = PID0_DEFAULT_SWEEP_MIN;
  g_pid0.sweep_max_permille = PID0_DEFAULT_SWEEP_MAX;
  g_pid0.sweep_step_permille = PID0_DEFAULT_SWEEP_STEP;
  g_pid0.settle_ms = PID0_DEFAULT_SETTLE_MS;
  g_pid0.measure_ms = PID0_DEFAULT_MEASURE_MS;
  g_pid0.zero_gap_ms = PID0_DEFAULT_ZERO_GAP_MS;
  g_pid0.current_duty_permille = PID0_DEFAULT_SINGLE_DUTY;
  if (HAL_TIM_Encoder_Start(&htim2, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim5, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim1, TIM_CHANNEL_ALL) != HAL_OK ||
      HAL_TIM_Encoder_Start(&htim4, TIM_CHANNEL_ALL) != HAL_OK) {
    fail_closed(PID0_ERROR_ENCODER_START); return;
  }
  previous_raw = read_all();
  set_state(PID0_STATE_IDLE);
  g_pid0.last_error = PID0_ERROR_NONE;
}

void pid0_lab_step(uint32_t now_ms)
{
  uint32_t request = g_pid0.request;
  g_pid0.request = PID0_REQUEST_NONE;
  g_pid0.elapsed_ms = is_running() ? elapsed_ms(now_ms, run_started_ms) : 0U;

  /* ABORT is serviced before every other request and state transition. */
  if (request == PID0_REQUEST_ABORT) {
    stop_outputs(); g_pid0.current_duty_permille = 0U;
    set_state(PID0_STATE_ABORTED); g_pid0.last_error = PID0_ERROR_NONE;
    return;
  }
  if (g_pid0.state != internal_state || g_pid0.state > PID0_STATE_FAULT) {
    fail_closed(PID0_ERROR_LOGIC); return;
  }
  if (is_running() &&
      ((internal_state == PID0_STATE_ZERO_GAP && g_pid0.current_duty_permille != 0U) ||
       ((internal_state == PID0_STATE_SETTLE || internal_state == PID0_STATE_MEASURE) &&
        g_pid0.current_duty_permille != applied_duty) ||
       g_pid0.selected_wheel != active_wheel ||
       g_pid0.direction != active_direction ||
       g_pid0.sweep_min_permille != active_sweep_min ||
       g_pid0.sweep_max_permille != active_sweep_max ||
       g_pid0.sweep_step_permille != active_sweep_step ||
       g_pid0.settle_ms != active_settle_ms ||
       g_pid0.measure_ms != active_measure_ms ||
       g_pid0.zero_gap_ms != active_zero_gap_ms)) {
    fail_closed(PID0_ERROR_LOGIC); return;
  }
  if (is_running() && request != PID0_REQUEST_NONE) {
    if (request != PID0_REQUEST_RUN_SINGLE_STEP && request != PID0_REQUEST_RUN_SWEEP &&
        request != PID0_REQUEST_CLEAR_LOG && request != PID0_REQUEST_DUMP_UART) {
      fail_closed(PID0_ERROR_INVALID_REQUEST); return;
    }
    g_pid0.last_error = PID0_ERROR_BUSY;
  } else if (!is_running()) {
    process_idle_request(request, now_ms);
  }
  if (!is_running()) return;
  if (elapsed_ms(now_ms, run_started_ms) >= PID0_RUN_TIMEOUT_MS) {
    fail_closed(PID0_ERROR_TIMEOUT); return;
  }
  if (internal_state == PID0_STATE_ZERO_GAP) {
    if (elapsed_ms(now_ms, phase_started_ms) >= active_zero_gap_ms) {
      if (!start_selected_motor(now_ms)) return;
    }
    return;
  }
  if (internal_state == PID0_STATE_SETTLE &&
      elapsed_ms(now_ms, phase_started_ms) >= active_settle_ms) {
    set_state(PID0_STATE_MEASURE);
    phase_started_ms = now_ms;
  }
  if (elapsed_ms(now_ms, last_sample_ms) >= PID0_SAMPLE_PERIOD_MS) {
    uint32_t dt = elapsed_ms(now_ms, last_sample_ms);
    if (dt == 0U) { fail_closed(PID0_ERROR_LOGIC); return; }
    last_sample_ms = now_ms;
    capture_sample(now_ms, dt);
  }
  if (internal_state == PID0_STATE_MEASURE &&
      elapsed_ms(now_ms, phase_started_ms) >= active_measure_ms) {
    finish_step(now_ms);
  }
}
