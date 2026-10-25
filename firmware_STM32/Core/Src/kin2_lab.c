#include "kin2_lab.h"

#include "mecanum_kinematics.h"
#include "pid4_lab.h"

volatile Kin2LabControl g_kin2;

static void clear_kin2_diagnostics(void)
{
    uint32_t i;

    g_kin2.request = KIN2_REQUEST_NONE;
    g_kin2.last_error = KIN2_ERROR_NONE;
    g_kin2.compute_count = 0U;
    g_kin2.vx_mps = 0.0f;
    g_kin2.vy_mps = 0.0f;
    g_kin2.wz_radps = 0.0f;
    for (i = 0U; i < MECANUM_WHEEL_COUNT; ++i)
    {
        g_kin2.raw_target_cps[i] = 0.0f;
        g_kin2.target_cps[i] = 0.0f;
    }
    g_kin2.scale_factor = 0.0f;
    g_kin2.limited = 0U;
    g_kin2.kinematics_valid = 0U;
}

static bool compute_and_record(float vx_mps,
                               float vy_mps,
                               float wz_radps,
                               MecanumKinematicsOutput *result)
{
    uint32_t i;
    bool valid = mecanum_kinematics_compute(vx_mps, vy_mps, wz_radps, result);

    ++g_kin2.compute_count;
    for (i = 0U; i < MECANUM_WHEEL_COUNT; ++i)
    {
        g_kin2.raw_target_cps[i] = result->raw_target_cps[i];
        g_kin2.target_cps[i] = result->target_cps[i];
    }
    g_kin2.scale_factor = result->scale_factor;
    g_kin2.limited = result->limited;
    g_kin2.kinematics_valid = valid ? 1U : 0U;
    g_kin2.last_error = valid ? KIN2_ERROR_NONE :
                                KIN2_ERROR_KINEMATICS_INVALID;
    return valid;
}

void kin2_lab_init(void)
{
    clear_kin2_diagnostics();
    pid4_lab_init();
}

static void process_request(void)
{
    uint32_t request = g_kin2.request;

    if (request == KIN2_REQUEST_NONE)
    {
        return;
    }
    g_kin2.request = KIN2_REQUEST_NONE;

    if (request == KIN2_REQUEST_PREPARE_ONLY)
    {
        float vx_mps = g_kin2.vx_mps;
        float vy_mps = g_kin2.vy_mps;
        float wz_radps = g_kin2.wz_radps;
        MecanumKinematicsOutput result;

        (void)compute_and_record(vx_mps, vy_mps, wz_radps, &result);
        return;
    }

    if (request == KIN2_REQUEST_ARM_RUN)
    {
        float vx_mps = g_kin2.vx_mps;
        float vy_mps = g_kin2.vy_mps;
        float wz_radps = g_kin2.wz_radps;
        MecanumKinematicsOutput result;
        uint32_t i;

        if (!compute_and_record(vx_mps, vy_mps, wz_radps, &result))
        {
            return;
        }

        if (g_pid4.state != PID4_STATE_IDLE)
        {
            g_kin2.last_error = KIN2_ERROR_PID4_NOT_IDLE;
            return;
        }

        for (i = 0U; i < MECANUM_WHEEL_COUNT; ++i)
        {
            g_pid4.requested_target_cps[i] = result.target_cps[i];
        }
        g_pid4.arm_magic = PID4_ARM_MAGIC;
        g_pid4.request = PID4_REQUEST_ARM_AUTORUN;
        return;
    }

    if (request == KIN2_REQUEST_ABORT)
    {
        g_pid4.request = PID4_REQUEST_ABORT;
        return;
    }

    if (request == KIN2_REQUEST_CLEAR)
    {
        clear_kin2_diagnostics();
        g_pid4.request = PID4_REQUEST_CLEAR_LOG;
    }
}

void kin2_lab_step(uint32_t now_ms)
{
    process_request();
    pid4_lab_step(now_ms);
}
