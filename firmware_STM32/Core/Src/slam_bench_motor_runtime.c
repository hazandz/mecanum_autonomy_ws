#include "slam_bench_motor_runtime.h"

#include "encoder.h"
#include "main.h"
#include "mecanum_kinematics.h"
#include "motor_logic.h"
#include "pid_controller.h"
#include "safety_io.h"

#if defined(MECANUM_USE_GENERATED_HARDWARE_CONFIG)
#include "generated_hardware_config.h"
#endif

#include <math.h>
#include <string.h>

extern TIM_HandleTypeDef htim1, htim2, htim3, htim4, htim5;

static PidControllerState pid_state[MECANUM_WHEEL_COUNT];
static float targets[MECANUM_WHEEL_COUNT];
static int64_t previous_ticks[MECANUM_WHEEL_COUNT];
static int8_t controller_sign[MECANUM_WHEEL_COUNT];
static uint64_t previous_time_us;
static slam_pid4_guard_state_t pid4_guard;
static slam_motor_runtime_fault_t runtime_fault;
static slam_pid4_fault_t tracking_diagnostic;
static bool initialized, enabled;

static bool is_tracking_guard_fault(slam_pid4_fault_t fault)
{
    return fault == SLAM_PID4_FAULT_WRONG_DIRECTION ||
           fault == SLAM_PID4_FAULT_STALL || fault == SLAM_PID4_FAULT_SYNC;
}

bool slam_bench_motor_tracking_guard_fault_is_fatal(
    const slam_bench_motor_config_t *config, slam_pid4_fault_t fault)
{
    if (!is_tracking_guard_fault(fault)) return true;
    return config == NULL || !config->manual_slam_bench_profile ||
           !config->tracking_guard_faults_nonfatal;
}

static uint32_t pwm_channel(unsigned i)
{
    static const uint32_t channels[MECANUM_WHEEL_COUNT] = {
        TIM_CHANNEL_4, TIM_CHANNEL_3, TIM_CHANNEL_1, TIM_CHANNEL_2
    };
    return channels[i];
}

static bool valid_config(void)
{
    const slam_bench_motor_config_t *c = &slam_bench_motor_config;
    const float values[] = {c->wheel_diameter_m,c->wheelbase_m,c->track_m,
        c->counts_per_revolution,c->max_wheel_cps,c->max_pwm_permille,c->kp,c->ki,
        c->integral_limit,c->forward_ff_u0[0],c->forward_ff_u0[1],
        c->forward_ff_u0[2],c->forward_ff_u0[3],c->forward_ff_kv[0],
        c->forward_ff_kv[1],c->forward_ff_kv[2],c->forward_ff_kv[3],
        c->reverse_ff_u0[0],c->reverse_ff_u0[1],c->reverse_ff_u0[2],
        c->reverse_ff_u0[3],c->reverse_ff_kv[0],c->reverse_ff_kv[1],
        c->reverse_ff_kv[2],c->reverse_ff_kv[3]};
    for (unsigned i=0; i<sizeof(values)/sizeof(values[0]); ++i)
        if (!isfinite(values[i]) || values[i] <= 0.0f) return false;
    for (unsigned i=0; i<MECANUM_WHEEL_COUNT; ++i)
        if (c->encoder_tick_sign[i] != -1 && c->encoder_tick_sign[i] != 1) return false;
#if defined(MECANUM_USE_GENERATED_HARDWARE_CONFIG)
    if (MECANUM_MANUAL_SLAM_PROFILE_VALID != 1U ||
        MECANUM_ENCODER_SIGNS_VALID != 1U ||
        MECANUM_MANIFEST_GEOMETRY_VALID != 1U) return false;
#endif
    return c->experimental_profile_enabled && c->max_pwm_permille <= 1000.0f &&
           (!c->tracking_guard_faults_nonfatal || c->manual_slam_bench_profile);
}

bool slam_bench_motor_runtime_profile_valid(void)
{
    return valid_config();
}

static void trip(slam_motor_runtime_fault_t fault)
{
    if (runtime_fault == SLAM_MOTOR_RUNTIME_FAULT_NONE) runtime_fault = fault;
    slam_bench_motor_runtime_stop();
}

bool slam_bench_motor_runtime_init(void)
{
    safety_io_force_motor_disabled();
    memset(targets, 0, sizeof(targets));
    memset(pid_state, 0, sizeof(pid_state));
    memset(controller_sign, 0, sizeof(controller_sign));
    slam_pid4_guard_reset(&pid4_guard);
    enabled = false;
    runtime_fault = SLAM_MOTOR_RUNTIME_FAULT_NONE;
    tracking_diagnostic = SLAM_PID4_FAULT_NONE;
    encoder_snapshot_t s;
    if (!encoder_snapshot(&s)) {
        initialized = false;
        runtime_fault = SLAM_MOTOR_RUNTIME_FAULT_ENCODER;
        return false;
    }
    previous_ticks[0]=s.ticks_fl; previous_ticks[1]=s.ticks_fr;
    previous_ticks[2]=s.ticks_rl; previous_ticks[3]=s.ticks_rr;
    previous_time_us=s.monotonic_time_us;
    initialized=true;
    return true;
}

void slam_bench_motor_runtime_stop(void)
{
    memset(targets, 0, sizeof(targets));
    memset(pid_state, 0, sizeof(pid_state));
    memset(controller_sign, 0, sizeof(controller_sign));
    slam_pid4_guard_reset(&pid4_guard);
    safety_io_force_motor_disabled();
    motor_logic_stop_all();
    enabled=false;
}

bool slam_bench_motor_runtime_new_session(void)
{
    slam_bench_motor_runtime_stop();
    if (!valid_config()) {
        runtime_fault = SLAM_MOTOR_RUNTIME_FAULT_PROFILE;
        return false;
    }
    encoder_snapshot_t s;
    if (!encoder_snapshot(&s)) {
        runtime_fault = SLAM_MOTOR_RUNTIME_FAULT_ENCODER;
        return false;
    }
    previous_ticks[0]=s.ticks_fl; previous_ticks[1]=s.ticks_fr;
    previous_ticks[2]=s.ticks_rl; previous_ticks[3]=s.ticks_rr;
    previous_time_us=s.monotonic_time_us;
    runtime_fault = SLAM_MOTOR_RUNTIME_FAULT_NONE;
    tracking_diagnostic = SLAM_PID4_FAULT_NONE;
    return true;
}

slam_motor_runtime_fault_t slam_bench_motor_runtime_fault(void)
{
    return runtime_fault;
}

slam_pid4_fault_t slam_bench_motor_runtime_tracking_diagnostic(void)
{
    return tracking_diagnostic;
}

bool slam_bench_motor_runtime_enabled(void) { return enabled; }
bool slam_bench_motor_runtime_telemetry_allowed(void)
{ return enabled && slam_bench_motor_config.experimental_profile_enabled; }

bool slam_bench_motor_runtime_set_body_command(float vx, float vy, float wz)
{
    if (runtime_fault != SLAM_MOTOR_RUNTIME_FAULT_NONE) return false;
    if (!initialized || !valid_config()) {
        trip(SLAM_MOTOR_RUNTIME_FAULT_PROFILE); return false;
    }
    if (!isfinite(vx) || !isfinite(vy) || !isfinite(wz)) {
        trip(SLAM_MOTOR_RUNTIME_FAULT_CONTROL); return false;
    }
    MecanumKinematicsConfig k={slam_bench_motor_config.wheel_diameter_m,
        slam_bench_motor_config.wheelbase_m,slam_bench_motor_config.track_m,
        slam_bench_motor_config.counts_per_revolution,slam_bench_motor_config.max_wheel_cps};
    MecanumKinematicsOutput out;
    if (!mecanum_kinematics_compute(&k,vx,vy,wz,&out)) {
        trip(SLAM_MOTOR_RUNTIME_FAULT_CONTROL); return false;
    }
    memcpy(targets,out.target_cps,sizeof(targets));
    bool any_target = false;
    for (unsigned i=0; i<MECANUM_WHEEL_COUNT; ++i) any_target |= targets[i] != 0.0f;
    if (!any_target) slam_bench_motor_runtime_stop();
    return true;
}

void slam_bench_motor_runtime_step(float dt)
{
    if (runtime_fault != SLAM_MOTOR_RUNTIME_FAULT_NONE) {
        slam_bench_motor_runtime_stop(); return;
    }
    if (!initialized || !valid_config()) {
        trip(SLAM_MOTOR_RUNTIME_FAULT_PROFILE); return;
    }
    if (!isfinite(dt) || dt<=0.0f || dt > 0.100f) {
        trip(SLAM_MOTOR_RUNTIME_FAULT_CONTROL); return;
    }
    encoder_snapshot_t s;
    if (!encoder_snapshot(&s) || s.monotonic_time_us<=previous_time_us) {
        trip(SLAM_MOTOR_RUNTIME_FAULT_ENCODER); return;
    }
    bool has_requested_target=false;
    for(unsigned i=0;i<MECANUM_WHEEL_COUNT;i++) has_requested_target |= targets[i] != 0.0f;
    if (!has_requested_target) {
        if (enabled) slam_bench_motor_runtime_stop();
        int64_t idle_ticks[MECANUM_WHEEL_COUNT]={s.ticks_fl,s.ticks_fr,s.ticks_rl,s.ticks_rr};
        memcpy(previous_ticks,idle_ticks,sizeof(previous_ticks));
        previous_time_us=s.monotonic_time_us;
        return;
    }
    uint64_t elapsed_us=s.monotonic_time_us-previous_time_us;
    uint64_t elapsed_ms=elapsed_us/1000ULL;
    if (elapsed_ms < SLAM_PID4_SAMPLE_PERIOD_MS) return;
    if (elapsed_ms > SLAM_PID4_MAX_CONTROL_DT_MS) {
        trip(SLAM_MOTOR_RUNTIME_FAULT_CONTROL); return;
    }
    int64_t ticks[MECANUM_WHEEL_COUNT]={s.ticks_fl,s.ticks_fr,s.ticks_rl,s.ticks_rr};
    float measured[MECANUM_WHEEL_COUNT];
    double elapsed=(double)elapsed_us*1.0e-6;
    for(unsigned i=0;i<MECANUM_WHEEL_COUNT;i++)
        measured[i]=(float)((double)(ticks[i]-previous_ticks[i])/elapsed) *
                    (float)slam_bench_motor_config.encoder_tick_sign[i];
    previous_time_us=s.monotonic_time_us;
    memcpy(previous_ticks,ticks,sizeof(ticks));
    if (slam_pid4_guard_ramp(&pid4_guard, targets, (uint32_t)elapsed_ms)
        != SLAM_PID4_FAULT_NONE) {
        trip(SLAM_MOTOR_RUNTIME_FAULT_CONTROL); return;
    }
    float effort[MECANUM_WHEEL_COUNT];
    for(unsigned i=0;i<MECANUM_WHEEL_COUNT;i++) {
        PidControllerConfig p;
        int8_t sign = pid4_guard.ramped_target_cps[i] > 0.0f ? 1 :
                      (pid4_guard.ramped_target_cps[i] < 0.0f ? -1 : 0);
        if (sign != controller_sign[i]) {
            pid_controller_reset(&pid_state[i]);
            controller_sign[i] = sign;
        }
        if(!slam_bench_motor_profile_pid_config_for_wheel(i, &p) ||
           !pid_controller_step(&p,&pid_state[i],pid4_guard.ramped_target_cps[i],measured[i],
                                (float)elapsed,&effort[i])) {
            trip(SLAM_MOTOR_RUNTIME_FAULT_CONTROL); return;
        }
    }
    bool has_motion_target=false;
    for(unsigned i=0;i<MECANUM_WHEEL_COUNT;i++)
        has_motion_target |= pid4_guard.ramped_target_cps[i] != 0.0f;
    if(!has_motion_target) { slam_bench_motor_runtime_stop(); return; }
    slam_pid4_fault_t guard_fault = slam_pid4_guard_check(
        &pid4_guard, pid4_guard.ramped_target_cps, measured, effort,
        (uint32_t)elapsed_ms);
    if (guard_fault != SLAM_PID4_FAULT_NONE) {
        if (is_tracking_guard_fault(guard_fault)) {
            tracking_diagnostic = guard_fault;
            if (slam_bench_motor_tracking_guard_fault_is_fatal(
                    &slam_bench_motor_config, guard_fault)) {
                trip(SLAM_MOTOR_RUNTIME_FAULT_DRIVER);
                return;
            }
            /* MANUAL_SLAM bench only: preserve diagnosis and keep command control active. */
        } else {
            trip(SLAM_MOTOR_RUNTIME_FAULT_CONTROL);
            return;
        }
    }

    if (!enabled) {
        safety_io_force_motor_disabled();
        for(unsigned i=0;i<MECANUM_WHEEL_COUNT;i++) {
            motor_logic_set_direction((MotorWheel)i, MOTOR_DIRECTION_COAST);
            __HAL_TIM_SET_COMPARE(&htim3,pwm_channel(i),0U);
            if(HAL_TIM_PWM_Start(&htim3,pwm_channel(i))!=HAL_OK) {
                trip(SLAM_MOTOR_RUNTIME_FAULT_DRIVER); return;
            }
        }
        HAL_GPIO_WritePin(MCU_MOTOR_ENABLE_GPIO_Port,MCU_MOTOR_ENABLE_Pin,GPIO_PIN_SET);
        enabled=true;
    }
    for(unsigned i=0;i<MECANUM_WHEEL_COUNT;i++) {
        float e=effort[i];
        if(!isfinite(e) || fabsf(e)>slam_bench_motor_config.max_pwm_permille) {
            trip(SLAM_MOTOR_RUNTIME_FAULT_CONTROL); return;
        }
        slam_pid4_commutation_t action = slam_pid4_guard_commutate(
            &pid4_guard, i, pid4_guard.ramped_target_cps[i]);
        if (action == SLAM_PID4_COMMUTATE_COAST) {
            motor_logic_set_direction((MotorWheel)i, MOTOR_DIRECTION_COAST);
            __HAL_TIM_SET_COMPARE(&htim3,pwm_channel(i),0U);
        } else if (action == SLAM_PID4_COMMUTATE_SET_DIRECTION) {
            motor_logic_set_direction((MotorWheel)i,
                pid4_guard.ramped_target_cps[i] > 0.0f ? MOTOR_DIRECTION_FORWARD :
                                                        MOTOR_DIRECTION_REVERSE);
            __HAL_TIM_SET_COMPARE(&htim3,pwm_channel(i),0U);
        } else {
            uint32_t compare = 0U;
            motor_logic_set_direction((MotorWheel)i,
                pid4_guard.ramped_target_cps[i] > 0.0f ? MOTOR_DIRECTION_FORWARD :
                                                        MOTOR_DIRECTION_REVERSE);
            if (!slam_pid4_pwm_compare(__HAL_TIM_GET_AUTORELOAD(&htim3),
                                       fabsf(e), &compare)) {
                trip(SLAM_MOTOR_RUNTIME_FAULT_CONTROL); return;
            }
            __HAL_TIM_SET_COMPARE(&htim3,pwm_channel(i),compare);
        }
    }
}
