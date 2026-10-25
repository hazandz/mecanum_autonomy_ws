#ifndef KIN2_LAB_H
#define KIN2_LAB_H

#include <stdint.h>

#include "pid4_lab.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum
{
    KIN2_REQUEST_NONE = 0U,
    KIN2_REQUEST_PREPARE_ONLY = 1U,
    KIN2_REQUEST_ARM_RUN = 2U,
    KIN2_REQUEST_ABORT = 3U,
    KIN2_REQUEST_CLEAR = 4U
} Kin2LabRequest;

typedef enum
{
    KIN2_ERROR_NONE = 0U,
    KIN2_ERROR_KINEMATICS_INVALID = 1U,
    KIN2_ERROR_PID4_NOT_IDLE = 2U
} Kin2LabError;

typedef struct
{
    uint32_t request;
    uint32_t last_error;
    uint32_t compute_count;

    float vx_mps;
    float vy_mps;
    float wz_radps;

    float raw_target_cps[4];
    float target_cps[4];

    float scale_factor;

    uint32_t limited;
    uint32_t kinematics_valid;
} Kin2LabControl;

extern volatile Kin2LabControl g_kin2;

void kin2_lab_init(void);
void kin2_lab_step(uint32_t now_ms);

#ifdef __cplusplus
}
#endif

#endif /* KIN2_LAB_H */
