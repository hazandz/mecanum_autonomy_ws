#ifndef MECANUM_KINEMATICS_H
#define MECANUM_KINEMATICS_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    MECANUM_WHEEL_FL = 0,
    MECANUM_WHEEL_FR = 1,
    MECANUM_WHEEL_RL = 2,
    MECANUM_WHEEL_RR = 3,
    MECANUM_WHEEL_COUNT = 4
} MecanumWheelIndex;

typedef struct {
    float wheel_diameter_m;
    float wheelbase_m;
    float track_m;
    float counts_per_revolution;
    float max_wheel_cps;
} MecanumKinematicsConfig;

typedef struct {
    float raw_target_cps[MECANUM_WHEEL_COUNT];
    float target_cps[MECANUM_WHEEL_COUNT];
    float scale_factor;
    uint8_t limited;
} MecanumKinematicsOutput;

/*
 * Body-frame convention: vx > 0 forward, vy > 0 left, wz > 0 CCW.
 * On any invalid input/configuration, returns false and zeroes *out.
 */
bool mecanum_kinematics_compute(const MecanumKinematicsConfig *config,
                                float vx_mps,
                                float vy_mps,
                                float wz_radps,
                                MecanumKinematicsOutput *out);

#ifdef __cplusplus
}
#endif

#endif /* MECANUM_KINEMATICS_H */
