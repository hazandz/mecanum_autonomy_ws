#include "telemetry.h"

#include "communication_runtime.h"
#include "control_safety_runtime.h"
#include "encoder.h"
#include "safety_io.h"
#include "FreeRTOS.h"
#include "task.h"

#include <stdint.h>

#define TELEMETRY_PERIOD_MS 20U
#define TELEMETRY_TASK_PRIORITY 8U
#define TELEMETRY_TASK_STACK_WORDS 384U

static StaticTask_t task_control;
static StackType_t task_stack[TELEMETRY_TASK_STACK_WORDS];
static TaskHandle_t task_handle;
static uint32_t telemetry_sequence;
static bool sequence_exhausted;

static void telemetry_task(void *argument)
{
    TickType_t last_wake = xTaskGetTickCount();
    (void)argument;
    for (;;) {
        (void)telemetry_runtime_service_once();
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(TELEMETRY_PERIOD_MS));
    }
}

bool telemetry_runtime_start(void)
{
    if ((__get_IPSR() != 0U) || task_handle != NULL) return false;
    task_handle = xTaskCreateStatic(telemetry_task, "Telemetry",
        TELEMETRY_TASK_STACK_WORDS, NULL, TELEMETRY_TASK_PRIORITY,
        task_stack, &task_control);
    return task_handle != NULL;
}

bool telemetry_runtime_service_once(void)
{
    control_safety_snapshot_t session;
    control_safety_snapshot_t after;
    encoder_snapshot_t enc;
    mecanum_uart_v1_telemetry_t packet = {0};
    bool estop_active;
    uint32_t faults;
    if ((__get_IPSR() != 0U) || task_handle == NULL
        || xTaskGetCurrentTaskHandle() != task_handle) return false;
    if (!control_safety_runtime_copy_snapshot(&session) || !session.configured
        || !session.telemetry_allowed || session.motor_enabled || !encoder_snapshot(&enc)
        || !safety_io_read_estop_aux(&estop_active) || sequence_exhausted
        || !control_safety_runtime_copy_snapshot(&after)
        || after.snapshot_revision != session.snapshot_revision
        || after.configured != session.configured
        || after.reset_epoch != session.reset_epoch
        || after.mcu_boot_id != session.mcu_boot_id
        || after.last_accepted_command_sequence != session.last_accepted_command_sequence
        || after.mcu_fault_bits != session.mcu_fault_bits
        || !after.telemetry_allowed) return false;
    if (telemetry_sequence == UINT32_MAX) {
        sequence_exhausted = true;
        return false;
    }
    faults = session.mcu_fault_bits;
    if (estop_active) faults |= MECANUM_FAULT_ESTOP_ACTIVE;
    packet.telemetry_sequence = telemetry_sequence;
    packet.mcu_boot_id = session.mcu_boot_id;
    packet.reset_epoch = session.reset_epoch;
    packet.mcu_monotonic_time_us = enc.monotonic_time_us;
    packet.ticks_fl = enc.ticks_fl; packet.ticks_fr = enc.ticks_fr;
    packet.ticks_rl = enc.ticks_rl; packet.ticks_rr = enc.ticks_rr;
    packet.last_accepted_command_sequence = session.last_accepted_command_sequence;
    packet.mcu_fault_bits = faults;
    packet.estop_aux_active = estop_active ? 1U : 0U;
    if (!control_safety_runtime_enqueue_telemetry_if_current(&session, &packet)) return false;
    ++telemetry_sequence;
    return true;
}
