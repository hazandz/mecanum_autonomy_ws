/* Host integration seam: hardware PWM/enable remains unavailable offline. */
#include "slam_bench_motor_runtime.h"
static slam_motor_runtime_fault_t fake_fault;
static slam_pid4_fault_t fake_tracking_diagnostic;
static unsigned fake_step_calls;
unsigned slam_bench_motor_runtime_test_step_calls(void) { return fake_step_calls; }
bool slam_bench_motor_runtime_init(void) { return true; }
bool slam_bench_motor_runtime_profile_valid(void) { return true; }
bool slam_bench_motor_runtime_set_body_command(float x,float y,float z)
{ (void)x; (void)y; (void)z; return false; }
void slam_bench_motor_runtime_stop(void) {}
bool slam_bench_motor_runtime_new_session(void)
{
    fake_fault = SLAM_MOTOR_RUNTIME_FAULT_NONE;
    fake_tracking_diagnostic = SLAM_PID4_FAULT_NONE;
    fake_step_calls = 0U;
    return true;
}
slam_motor_runtime_fault_t slam_bench_motor_runtime_fault(void)
{ return fake_fault; }
slam_pid4_fault_t slam_bench_motor_runtime_tracking_diagnostic(void)
{ return fake_tracking_diagnostic; }
bool slam_bench_motor_runtime_enabled(void) { return false; }
bool slam_bench_motor_runtime_telemetry_allowed(void) { return false; }
void slam_bench_motor_runtime_step(float dt) { (void)dt; ++fake_step_calls; }
void slam_bench_motor_runtime_test_set_fault(slam_motor_runtime_fault_t fault)
{ fake_fault = fault; }
void slam_bench_motor_runtime_test_set_tracking_diagnostic(slam_pid4_fault_t fault)
{ fake_tracking_diagnostic = fault; }
