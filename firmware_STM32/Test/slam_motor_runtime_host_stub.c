/* Host integration seam: hardware PWM/enable remains unavailable offline. */
#include "slam_bench_motor_runtime.h"
bool slam_bench_motor_runtime_init(void) { return true; }
bool slam_bench_motor_runtime_set_body_command(float x,float y,float z)
{ (void)x; (void)y; (void)z; return false; }
void slam_bench_motor_runtime_stop(void) {}
bool slam_bench_motor_runtime_enabled(void) { return false; }
bool slam_bench_motor_runtime_telemetry_allowed(void) { return false; }
void slam_bench_motor_runtime_step(float dt) { (void)dt; }
