#include "slam_bench_motor_runtime.h"

#include "encoder.h"
#include "main.h"
#include "mecanum_kinematics.h"
#include "motor_logic.h"
#include "pid_controller.h"
#include "safety_io.h"

#include <math.h>
#include <string.h>

extern TIM_HandleTypeDef htim1, htim2, htim3, htim4, htim5;

/* SLAM_BENCH_EXPERIMENTAL: deliberately unconfigured and disarmed by default. */
const slam_bench_motor_config_t slam_bench_motor_config = {0};

static PidControllerState pid_state[MECANUM_WHEEL_COUNT];
static float targets[MECANUM_WHEEL_COUNT];
static int64_t previous_ticks[MECANUM_WHEEL_COUNT];
static uint64_t previous_time_us;
static bool initialized, enabled;

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
        c->counts_per_revolution,c->max_wheel_cps,c->max_pwm_effort,c->kp,c->ki,
        c->integral_limit,c->forward_ff_u0,c->forward_ff_kv,c->reverse_ff_u0,c->reverse_ff_kv};
    for (unsigned i=0; i<sizeof(values)/sizeof(values[0]); ++i)
        if (!isfinite(values[i]) || values[i] <= 0.0f) return false;
    return c->experimental_profile_enabled && c->max_pwm_effort <= 65535.0f;
}

bool slam_bench_motor_runtime_init(void)
{
    safety_io_force_motor_disabled();
    memset(targets, 0, sizeof(targets));
    memset(pid_state, 0, sizeof(pid_state));
    enabled = false;
    encoder_snapshot_t s;
    if (!encoder_snapshot(&s)) { initialized = false; return false; }
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
    safety_io_force_motor_disabled();
    motor_logic_stop_all();
    enabled=false;
}

bool slam_bench_motor_runtime_enabled(void) { return enabled; }
bool slam_bench_motor_runtime_telemetry_allowed(void)
{ return enabled && slam_bench_motor_config.experimental_profile_enabled; }

bool slam_bench_motor_runtime_set_body_command(float vx, float vy, float wz)
{
    if (!initialized || !valid_config() || !isfinite(vx) || !isfinite(vy) || !isfinite(wz)) {
        slam_bench_motor_runtime_stop(); return false;
    }
    MecanumKinematicsConfig k={slam_bench_motor_config.wheel_diameter_m,
        slam_bench_motor_config.wheelbase_m,slam_bench_motor_config.track_m,
        slam_bench_motor_config.counts_per_revolution,slam_bench_motor_config.max_wheel_cps};
    MecanumKinematicsOutput out;
    if (!mecanum_kinematics_compute(&k,vx,vy,wz,&out)) { slam_bench_motor_runtime_stop(); return false; }
    memcpy(targets,out.target_cps,sizeof(targets));
    return true;
}

void slam_bench_motor_runtime_step(float dt)
{
    if (!initialized || !valid_config() || !isfinite(dt) || dt<=0.0f) {
        slam_bench_motor_runtime_stop(); return;
    }
    encoder_snapshot_t s;
    if (!encoder_snapshot(&s) || s.monotonic_time_us<=previous_time_us) {
        slam_bench_motor_runtime_stop(); return;
    }
    int64_t ticks[MECANUM_WHEEL_COUNT]={s.ticks_fl,s.ticks_fr,s.ticks_rl,s.ticks_rr};
    float measured[MECANUM_WHEEL_COUNT];
    double elapsed=(double)(s.monotonic_time_us-previous_time_us)*1.0e-6;
    for(unsigned i=0;i<MECANUM_WHEEL_COUNT;i++)
        measured[i]=(float)((double)(ticks[i]-previous_ticks[i])/elapsed); /* encoder counts/s */
    previous_time_us=s.monotonic_time_us;
    memcpy(previous_ticks,ticks,sizeof(ticks));
    PidControllerConfig p={slam_bench_motor_config.kp,slam_bench_motor_config.ki,
        slam_bench_motor_config.integral_limit,slam_bench_motor_config.max_pwm_effort,
        slam_bench_motor_config.max_wheel_cps,slam_bench_motor_config.forward_ff_u0,
        slam_bench_motor_config.forward_ff_kv,slam_bench_motor_config.reverse_ff_u0,
        slam_bench_motor_config.reverse_ff_kv};
    float effort[MECANUM_WHEEL_COUNT];
    for(unsigned i=0;i<MECANUM_WHEEL_COUNT;i++)
        if(!pid_controller_step(&p,&pid_state[i],targets[i],measured[i],(float)elapsed,&effort[i])) {
            slam_bench_motor_runtime_stop(); return;
        }
    bool has_motion_target=false;
    for(unsigned i=0;i<MECANUM_WHEEL_COUNT;i++) has_motion_target |= targets[i] != 0.0f;
    if(!has_motion_target) { slam_bench_motor_runtime_stop(); return; }
    if (!enabled) {
        safety_io_force_motor_disabled();
        for(unsigned i=0;i<MECANUM_WHEEL_COUNT;i++) {
            motor_logic_set_direction((MotorWheel)i, MOTOR_DIRECTION_COAST);
            if(HAL_TIM_PWM_Start(&htim3,pwm_channel(i))!=HAL_OK) {
                slam_bench_motor_runtime_stop(); return;
            }
        }
        HAL_GPIO_WritePin(MCU_MOTOR_ENABLE_GPIO_Port,MCU_MOTOR_ENABLE_Pin,GPIO_PIN_SET);
        enabled=true;
    }
    for(unsigned i=0;i<MECANUM_WHEEL_COUNT;i++) {
        float e=effort[i];
        if(!isfinite(e) || fabsf(e)>slam_bench_motor_config.max_pwm_effort) {
            slam_bench_motor_runtime_stop(); return;
        }
        motor_logic_set_direction((MotorWheel)i,e>0.0f?MOTOR_DIRECTION_FORWARD:
            (e<0.0f?MOTOR_DIRECTION_REVERSE:MOTOR_DIRECTION_COAST));
        __HAL_TIM_SET_COMPARE(&htim3,pwm_channel(i),(uint32_t)fabsf(e));
    }
}
