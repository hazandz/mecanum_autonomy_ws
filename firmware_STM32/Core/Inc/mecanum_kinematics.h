#ifndef MECANUM_KINEMATICS_H
#define MECANUM_KINEMATICS_H

#include <stdbool.h>
#include <stdint.h>

/*
 * Experimental measured/nominal inputs. Future production firmware must
 * obtain verified geometry/encoder configuration from generated hardware
 * configuration derived from the approved hardware manifest.
 */
#define MECANUM_WHEEL_DIAMETER_M        0.097f
#define MECANUM_WHEEL_RADIUS_M          0.0485f

#define MECANUM_WHEELBASE_M             0.216f
#define MECANUM_TRACK_M                 0.190f

#define MECANUM_HALF_WHEELBASE_M        0.108f
#define MECANUM_HALF_TRACK_M            0.095f

#define MECANUM_ROTATION_RADIUS_M       0.203f

#define MECANUM_ENCODER_CPR             937.2f
#define MECANUM_COUNTS_PER_METER        3075.46418f

#define MECANUM_MAX_WHEEL_CPS           1400.0f

typedef enum
{
    MECANUM_WHEEL_FL = 0,
    MECANUM_WHEEL_FR = 1,
    MECANUM_WHEEL_RL = 2,
    MECANUM_WHEEL_RR = 3,
    MECANUM_WHEEL_COUNT = 4
} MecanumWheelIndex;

typedef struct
{
    float raw_target_cps[MECANUM_WHEEL_COUNT];
    float target_cps[MECANUM_WHEEL_COUNT];
    float scale_factor;
    uint8_t limited;
} MecanumKinematicsOutput;

/*
 * Body-frame convention: vx > 0 forward, vy > 0 left, and wz > 0 CCW.
 * Returns false and zeroes out when the output pointer is null or an input
 * (or resulting calculation) is not finite.
 */
bool mecanum_kinematics_compute(float vx_mps,
                                float vy_mps,
                                float wz_radps,
                                MecanumKinematicsOutput *out);

#endif /* MECANUM_KINEMATICS_H */
